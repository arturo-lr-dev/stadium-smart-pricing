"""
Sistema de métricas con Prometheus.

Proporciona métricas para monitorear el rendimiento y comportamiento de la aplicación.
Incluye métricas de negocio y técnicas.
"""

from functools import wraps
from time import time
from typing import Any, Callable, Optional

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)


# ============================================================================
# Application Info
# ============================================================================

app_info = Info("smart_pricing_app", "Smart Pricing Application Info")


# ============================================================================
# API Metrics
# ============================================================================

# Request counters
api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status"],
)

api_requests_in_progress = Gauge(
    "api_requests_in_progress",
    "Number of API requests currently being processed",
    ["method", "endpoint"],
)

# Request duration
api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

# Error tracking
api_errors_total = Counter(
    "api_errors_total",
    "Total number of API errors",
    ["method", "endpoint", "error_type"],
)


# ============================================================================
# Pricing Metrics
# ============================================================================

# Pricing calculations
pricing_calculations_total = Counter(
    "pricing_calculations_total",
    "Total number of pricing calculations performed",
    ["match_id", "calculation_type"],
)

pricing_calculation_duration_seconds = Histogram(
    "pricing_calculation_duration_seconds",
    "Duration of pricing calculations in seconds",
    ["calculation_type"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Price changes
price_changes_total = Counter(
    "price_changes_total",
    "Total number of price changes",
    ["match_id", "zone_id", "direction"],
)

price_change_magnitude = Histogram(
    "price_change_magnitude",
    "Magnitude of price changes in percentage",
    ["match_id", "zone_id"],
    buckets=(0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5),
)

# Active matches
active_matches = Gauge(
    "active_matches",
    "Number of active matches (on sale)",
)


# ============================================================================
# Cache Metrics
# ============================================================================

cache_operations_total = Counter(
    "cache_operations_total",
    "Total number of cache operations",
    ["operation", "result"],
)

cache_hit_ratio = Gauge(
    "cache_hit_ratio",
    "Cache hit ratio (0-1)",
)

cached_prices = Gauge(
    "cached_prices",
    "Number of prices currently cached",
)

cache_operation_duration_seconds = Histogram(
    "cache_operation_duration_seconds",
    "Duration of cache operations in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)


# ============================================================================
# Database Metrics
# ============================================================================

db_operations_total = Counter(
    "db_operations_total",
    "Total number of database operations",
    ["operation", "table"],
)

db_operation_duration_seconds = Histogram(
    "db_operation_duration_seconds",
    "Duration of database operations in seconds",
    ["operation", "table"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

db_errors_total = Counter(
    "db_errors_total",
    "Total number of database errors",
    ["operation", "error_type"],
)


# ============================================================================
# External API Metrics
# ============================================================================

external_api_calls_total = Counter(
    "external_api_calls_total",
    "Total number of external API calls",
    ["service", "endpoint", "status"],
)

external_api_errors_total = Counter(
    "external_api_errors_total",
    "Total number of external API errors",
    ["service", "error_type"],
)

external_api_duration_seconds = Histogram(
    "external_api_duration_seconds",
    "Duration of external API calls in seconds",
    ["service", "endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

external_api_rate_limit_hits = Counter(
    "external_api_rate_limit_hits",
    "Number of times rate limits were hit",
    ["service"],
)


# ============================================================================
# Machine Learning Metrics
# ============================================================================

ml_predictions_total = Counter(
    "ml_predictions_total",
    "Total number of ML predictions",
    ["model_name", "prediction_type"],
)

ml_prediction_duration_seconds = Histogram(
    "ml_prediction_duration_seconds",
    "Duration of ML predictions in seconds",
    ["model_name"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

ml_model_accuracy = Gauge(
    "ml_model_accuracy",
    "Current accuracy of ML models",
    ["model_name", "metric"],
)

ml_training_duration_seconds = Histogram(
    "ml_training_duration_seconds",
    "Duration of model training in seconds",
    ["model_name"],
    buckets=(10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0),
)


# ============================================================================
# Business Metrics
# ============================================================================

# Sales and revenue
tickets_sold_total = Counter(
    "tickets_sold_total",
    "Total number of tickets sold",
    ["match_id", "zone_id", "customer_type"],
)

revenue_total = Counter(
    "revenue_total",
    "Total revenue in EUR",
    ["match_id", "zone_id"],
)

average_ticket_price = Gauge(
    "average_ticket_price",
    "Average ticket price in EUR",
    ["zone_id"],
)

zone_occupancy_percent = Gauge(
    "zone_occupancy_percent",
    "Zone occupancy percentage (0-100)",
    ["match_id", "zone_id"],
)

# Demand metrics
demand_score = Gauge(
    "demand_score",
    "Current demand score (0-1)",
    ["match_id", "zone_id"],
)

sales_velocity = Gauge(
    "sales_velocity",
    "Sales velocity (tickets per hour)",
    ["match_id", "zone_id"],
)


# ============================================================================
# Worker Metrics
# ============================================================================

worker_tasks_total = Counter(
    "worker_tasks_total",
    "Total number of worker tasks executed",
    ["worker_name", "status"],
)

worker_task_duration_seconds = Histogram(
    "worker_task_duration_seconds",
    "Duration of worker tasks in seconds",
    ["worker_name"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

worker_errors_total = Counter(
    "worker_errors_total",
    "Total number of worker errors",
    ["worker_name", "error_type"],
)

worker_last_run_timestamp = Gauge(
    "worker_last_run_timestamp",
    "Unix timestamp of last worker run",
    ["worker_name"],
)


# ============================================================================
# Utility Functions
# ============================================================================


def track_time(metric: Histogram, labels: Optional[dict] = None):
    """
    Decorator para medir duración de funciones.

    Args:
        metric: Histogram de Prometheus
        labels: Labels adicionales para la métrica

    Example:
        >>> @track_time(pricing_calculation_duration_seconds, {"calculation_type": "full"})
        >>> def calculate_pricing():
        >>>     pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

        # Return appropriate wrapper based on function type
        if hasattr(func, "__call__") and hasattr(func, "__await__"):
            return async_wrapper
        return wrapper

    return decorator


def track_counter(metric: Counter, labels: Optional[dict] = None):
    """
    Decorator para incrementar contador.

    Args:
        metric: Counter de Prometheus
        labels: Labels adicionales para la métrica

    Example:
        >>> @track_counter(pricing_calculations_total, {"calculation_type": "zone"})
        >>> def calculate_zone_pricing():
        >>>     pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            if labels:
                metric.labels(**labels).inc()
            else:
                metric.inc()
            return result

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)
            if labels:
                metric.labels(**labels).inc()
            else:
                metric.inc()
            return result

        # Return appropriate wrapper based on function type
        if hasattr(func, "__call__") and hasattr(func, "__await__"):
            return async_wrapper
        return wrapper

    return decorator


def get_metrics() -> bytes:
    """
    Obtiene las métricas en formato Prometheus.

    Returns:
        Métricas serializadas en formato Prometheus

    Example:
        >>> metrics_data = get_metrics()
    """
    return generate_latest(REGISTRY)


def set_app_info(version: str, environment: str, commit_sha: Optional[str] = None) -> None:
    """
    Establece información de la aplicación.

    Args:
        version: Versión de la aplicación
        environment: Entorno (development, staging, production)
        commit_sha: SHA del commit de git (opcional)

    Example:
        >>> set_app_info("1.0.0", "production", "abc123")
    """
    info_data = {
        "version": version,
        "environment": environment,
    }
    if commit_sha:
        info_data["commit_sha"] = commit_sha

    app_info.info(info_data)


def update_cache_metrics(hits: int, misses: int) -> None:
    """
    Actualiza las métricas de cache.

    Args:
        hits: Número total de cache hits
        misses: Número total de cache misses

    Example:
        >>> update_cache_metrics(100, 20)
    """
    total = hits + misses
    if total > 0:
        cache_hit_ratio.set(hits / total)


def record_price_change(
    match_id: str,
    zone_id: str,
    old_price: float,
    new_price: float,
) -> None:
    """
    Registra un cambio de precio.

    Args:
        match_id: ID del partido
        zone_id: ID de la zona
        old_price: Precio anterior
        new_price: Precio nuevo

    Example:
        >>> record_price_change("match-1", "zone-a", 50.0, 55.0)
    """
    # Determinar dirección del cambio
    direction = "increase" if new_price > old_price else "decrease"

    # Calcular magnitud del cambio (en porcentaje)
    if old_price > 0:
        magnitude = abs(new_price - old_price) / old_price
        price_change_magnitude.labels(match_id=match_id, zone_id=zone_id).observe(magnitude)

    # Incrementar contador
    price_changes_total.labels(match_id=match_id, zone_id=zone_id, direction=direction).inc()


def record_ticket_sale(
    match_id: str,
    zone_id: str,
    customer_type: str,
    quantity: int,
    total_amount: float,
) -> None:
    """
    Registra una venta de tickets.

    Args:
        match_id: ID del partido
        zone_id: ID de la zona
        customer_type: Tipo de cliente (member, general, vip)
        quantity: Cantidad de tickets
        total_amount: Monto total en EUR

    Example:
        >>> record_ticket_sale("match-1", "zone-a", "member", 2, 100.0)
    """
    tickets_sold_total.labels(
        match_id=match_id, zone_id=zone_id, customer_type=customer_type
    ).inc(quantity)
    revenue_total.labels(match_id=match_id, zone_id=zone_id).inc(total_amount)


# ============================================================================
# Context Managers
# ============================================================================


class MetricsContext:
    """
    Context manager para medir duración de bloques de código.

    Example:
        >>> with MetricsContext(pricing_calculation_duration_seconds, {"type": "full"}):
        >>>     calculate_pricing()
    """

    def __init__(self, histogram: Histogram, labels: Optional[dict] = None):
        """
        Inicializa el context manager.

        Args:
            histogram: Histogram de Prometheus para registrar la duración
            labels: Labels adicionales para la métrica
        """
        self.histogram = histogram
        self.labels = labels or {}
        self.start_time = None

    def __enter__(self):
        """Inicia la medición."""
        self.start_time = time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finaliza la medición y registra el resultado."""
        if self.start_time is not None:
            duration = time() - self.start_time
            if self.labels:
                self.histogram.labels(**self.labels).observe(duration)
            else:
                self.histogram.observe(duration)
        return False
