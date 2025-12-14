"""
Middleware para FastAPI.

Proporciona middleware para logging, métricas, CORS, y manejo de errores.
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.logging import clear_request_context, get_logger, set_request_context
from src.utils.metrics import (
    api_errors_total,
    api_request_duration_seconds,
    api_requests_in_progress,
    api_requests_total,
)

logger = get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware para recolectar métricas de Prometheus automáticamente.

    Registra:
    - Número total de requests
    - Duración de requests
    - Requests en progreso
    - Errores
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Procesa el request y recolecta métricas.

        Args:
            request: Request de FastAPI
            call_next: Siguiente middleware o handler

        Returns:
            Response
        """
        # Obtener método y path
        method = request.method
        path = request.url.path

        # Normalizar path (remover IDs para agrupar métricas)
        endpoint = self._normalize_path(path)

        # Incrementar requests en progreso
        api_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        # Medir duración
        start_time = time.time()

        try:
            # Procesar request
            response = await call_next(request)

            # Obtener status code
            status = response.status_code

            # Registrar métricas
            duration = time.time() - start_time
            api_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
            api_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()

            # Log request
            logger.info(
                f"{method} {path} - {status}",
                method=method,
                path=path,
                status=status,
                duration=duration,
            )

            return response

        except Exception as exc:
            # Registrar error
            duration = time.time() - start_time
            error_type = type(exc).__name__

            api_errors_total.labels(
                method=method, endpoint=endpoint, error_type=error_type
            ).inc()

            logger.error(
                f"{method} {path} - Error: {error_type}",
                method=method,
                path=path,
                error_type=error_type,
                duration=duration,
                exc_info=True,
            )

            # Re-raise para que sea manejado por exception handlers
            raise

        finally:
            # Decrementar requests en progreso
            api_requests_in_progress.labels(method=method, endpoint=endpoint).dec()

    def _normalize_path(self, path: str) -> str:
        """
        Normaliza el path removiendo IDs para agrupar métricas.

        Args:
            path: Path original del request

        Returns:
            Path normalizado

        Example:
            >>> self._normalize_path("/api/v1/pricing/match/123")
            '/api/v1/pricing/match/{match_id}'
        """
        # Split path por "/"
        parts = path.split("/")

        # Normalizar IDs comunes (UUIDs, números)
        normalized_parts = []
        for i, part in enumerate(parts):
            if not part:
                normalized_parts.append(part)
                continue

            # Reemplazar UUIDs
            if len(part) == 36 and part.count("-") == 4:
                normalized_parts.append("{id}")
            # Reemplazar números (posibles IDs)
            elif part.isdigit():
                # Determinar el nombre del parámetro basado en el contexto
                if i > 0:
                    prev_part = parts[i - 1]
                    if prev_part == "match":
                        normalized_parts.append("{match_id}")
                    elif prev_part == "zone":
                        normalized_parts.append("{zone_id}")
                    elif prev_part == "sale":
                        normalized_parts.append("{sale_id}")
                    else:
                        normalized_parts.append("{id}")
                else:
                    normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)

        return "/".join(normalized_parts)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware para establecer contexto de request en logs.

    Añade request_id y otra información de contexto a todos los logs
    generados durante el procesamiento del request.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Procesa el request y establece contexto de logging.

        Args:
            request: Request de FastAPI
            call_next: Siguiente middleware o handler

        Returns:
            Response
        """
        # Generar request ID (o usar el que viene en headers)
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Establecer contexto
        context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_host": request.client.host if request.client else None,
        }

        # Añadir user_id si está disponible (autenticación)
        if hasattr(request.state, "user_id"):
            context["user_id"] = request.state.user_id

        set_request_context(context)

        try:
            # Procesar request
            response = await call_next(request)

            # Añadir request ID a response headers
            response.headers["X-Request-ID"] = request_id

            return response

        finally:
            # Limpiar contexto
            clear_request_context()


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging detallado de errores.

    Captura y loggea errores no manejados con información completa.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Procesa el request y loggea errores si ocurren.

        Args:
            request: Request de FastAPI
            call_next: Siguiente middleware o handler

        Returns:
            Response
        """
        try:
            response = await call_next(request)
            return response

        except Exception as exc:
            # Log detallado del error
            logger.error(
                f"Unhandled exception in request {request.method} {request.url.path}",
                method=request.method,
                path=request.url.path,
                query_params=dict(request.query_params),
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )

            # Re-raise para que sea manejado por exception handlers de FastAPI
            raise


def setup_middleware(app: ASGIApp) -> None:
    """
    Configura todos los middleware de la aplicación.

    Args:
        app: Aplicación FastAPI

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> setup_middleware(app)
    """
    # Orden de middleware (de afuera hacia adentro):
    # 1. ErrorLogging - para capturar todos los errores
    # 2. Metrics - para medir performance
    # 3. RequestContext - para añadir contexto a logs

    app.add_middleware(ErrorLoggingMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestContextMiddleware)

    logger.info("Middleware configured successfully")
