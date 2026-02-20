"""
Sistema de logging estructurado.

Proporciona logging con formato JSON para producción y formato legible para desarrollo.
Soporta diferentes niveles de log por módulo y rotación de archivos.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.config import get_settings

# Context variable para almacenar información de request
request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})


class JSONFormatter(logging.Formatter):
    """
    Formateador JSON para logs estructurados.

    Convierte log records a formato JSON para fácil parsing y análisis.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Formatea el log record como JSON.

        Args:
            record: Log record a formatear

        Returns:
            String JSON con la información del log
        """
        # Información básica del log
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Añadir información del proceso y thread
        if record.process:
            log_data["process_id"] = record.process
        if record.thread:
            log_data["thread_id"] = record.thread

        # Añadir context de request si existe
        ctx = request_context.get()
        if ctx:
            log_data["context"] = ctx

        # Añadir información de excepción si existe
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Añadir campos adicionales del record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """
    Formateador de texto legible para desarrollo.

    Proporciona un formato claro y colorido (si el terminal lo soporta).
    """

    # Códigos de color ANSI
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Formatea el log record como texto legible.

        Args:
            record: Log record a formatear

        Returns:
            String formateado con colores (si está disponible)
        """
        # Timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Color según nivel
        color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"]

        # Construir mensaje
        message = (
            f"{color}[{timestamp}] {record.levelname:8s}{reset} "
            f"{record.name} - {record.getMessage()}"
        )

        # Añadir context si existe
        ctx = request_context.get()
        if ctx:
            message += f" | Context: {ctx}"

        # Añadir excepción si existe
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


class ContextLogger(logging.Logger):
    """
    Logger extendido que soporta campos adicionales de contexto.

    Permite añadir campos extra al log de forma sencilla.
    """

    def _log(
        self,
        level: int,
        msg: str,
        args: tuple,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
        **kwargs,
    ):
        """Sobrescribe _log para añadir campos extra."""
        if extra is None:
            extra = {}

        # Añadir kwargs como extra_fields
        if kwargs:
            extra["extra_fields"] = kwargs

        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel + 1)


# Registrar ContextLogger como clase por defecto INMEDIATAMENTE después de definirla
# Esto asegura que todos los loggers creados después de este punto usen ContextLogger
logging.setLoggerClass(ContextLogger)


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configura el sistema de logging de la aplicación.

    Lee la configuración desde Settings y configura:
    - Nivel de log por módulo
    - Formato (JSON o texto)
    - Handlers (console, file)
    - Rotación de archivos

    Args:
        level: Nivel de logging opcional que sobrescribe el valor en settings.
               Valores válidos: DEBUG, INFO, WARNING, ERROR, CRITICAL

    Example:
        >>> from src.core.logging import setup_logging
        >>> setup_logging()
        >>> setup_logging(level="DEBUG")
    """
    settings = get_settings()

    # Determinar formato
    if settings.logging.format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # Configurar handler de consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Determinar nivel de log (usa el parámetro si se proporciona, sino el de settings)
    log_level = level if level is not None else settings.logging.level

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)

    # Configurar file handler si está especificado
    if settings.logging.file:
        log_path = Path(settings.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Configurar niveles específicos por módulo (desde config YAML)
    yaml_config = settings.get_yaml_config("base")
    log_levels = yaml_config.get("logging", {}).get("levels", {})

    for module, level in log_levels.items():
        if module != "root":
            logger = logging.getLogger(module)
            logger.setLevel(getattr(logging, level.upper()))

    # Logging inicial
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging system initialized",
        environment=settings.environment,
        format=settings.logging.format,
        log_level=log_level,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado para el módulo especificado.

    Args:
        name: Nombre del módulo (típicamente __name__)

    Returns:
        Logger configurado

    Example:
        >>> from src.core.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("This is a log message", user_id=123)
    """
    return logging.getLogger(name)


def set_request_context(context: Dict[str, Any]) -> None:
    """
    Establece el contexto de la request actual.

    Args:
        context: Diccionario con información de contexto (request_id, user_id, etc.)

    Example:
        >>> set_request_context({"request_id": "abc-123", "user_id": 456})
    """
    request_context.set(context)


def clear_request_context() -> None:
    """
    Limpia el contexto de la request actual.

    Example:
        >>> clear_request_context()
    """
    request_context.set({})


def get_request_context() -> Dict[str, Any]:
    """
    Obtiene el contexto de la request actual.

    Returns:
        Diccionario con el contexto actual

    Example:
        >>> context = get_request_context()
    """
    return request_context.get()


class LoggerMixin:
    """
    Mixin para añadir logging a cualquier clase.

    Proporciona un logger configurado automáticamente con el nombre de la clase.
    """

    @property
    def logger(self) -> logging.Logger:
        """
        Logger para la clase.

        Returns:
            Logger configurado con el nombre de la clase
        """
        if not hasattr(self, "_logger"):
            self._logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self._logger


# Convenience functions para logging directo
def debug(msg: str, **kwargs) -> None:
    """Log a debug level."""
    get_logger("smart_pricing").debug(msg, **kwargs)


def info(msg: str, **kwargs) -> None:
    """Log an info level."""
    get_logger("smart_pricing").info(msg, **kwargs)


def warning(msg: str, **kwargs) -> None:
    """Log a warning level."""
    get_logger("smart_pricing").warning(msg, **kwargs)


def error(msg: str, **kwargs) -> None:
    """Log an error level."""
    get_logger("smart_pricing").error(msg, **kwargs)


def critical(msg: str, **kwargs) -> None:
    """Log a critical level."""
    get_logger("smart_pricing").critical(msg, **kwargs)
