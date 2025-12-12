"""
Excepciones personalizadas del sistema.

Define una jerarquía de excepciones para diferentes tipos de errores
y proporciona handlers para FastAPI.
"""

from typing import Any, Dict, Optional


class SmartPricingException(Exception):
    """
    Excepción base para todas las excepciones del sistema.

    Todas las excepciones personalizadas deben heredar de esta clase.

    Attributes:
        message: Mensaje de error legible para humanos
        code: Código de error para identificación programática
        details: Detalles adicionales del error
        status_code: Código HTTP asociado (para APIs)
    """

    def __init__(
        self,
        message: str,
        code: str = "SMART_PRICING_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje de error
            code: Código de error único
            details: Información adicional del error
            status_code: Código HTTP
        """
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte la excepción a diccionario para serialización.

        Returns:
            Diccionario con los datos de la excepción
        """
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


# ============================================================================
# ERRORES DE CONFIGURACIÓN
# ============================================================================


class ConfigurationError(SmartPricingException):
    """Error en la configuración del sistema."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            details=details,
            status_code=500,
        )


class InvalidConfigurationError(ConfigurationError):
    """Configuración inválida o mal formateada."""

    def __init__(self, config_name: str, reason: str):
        super().__init__(
            message=f"Invalid configuration '{config_name}': {reason}",
            details={"config_name": config_name, "reason": reason},
        )


class MissingConfigurationError(ConfigurationError):
    """Configuración requerida no encontrada."""

    def __init__(self, config_name: str):
        super().__init__(
            message=f"Missing required configuration: {config_name}",
            details={"config_name": config_name},
        )


# ============================================================================
# ERRORES DE BASE DE DATOS
# ============================================================================


class DatabaseError(SmartPricingException):
    """Error relacionado con la base de datos."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=details,
            status_code=500,
        )


class EntityNotFoundError(DatabaseError):
    """Entidad no encontrada en la base de datos."""

    def __init__(self, entity_type: str, entity_id: str):
        super().__init__(
            message=f"{entity_type} with id '{entity_id}' not found",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )
        self.status_code = 404
        self.code = "ENTITY_NOT_FOUND"


class DuplicateEntityError(DatabaseError):
    """Intento de crear una entidad que ya existe."""

    def __init__(self, entity_type: str, identifier: str):
        super().__init__(
            message=f"{entity_type} with identifier '{identifier}' already exists",
            details={"entity_type": entity_type, "identifier": identifier},
        )
        self.status_code = 409
        self.code = "DUPLICATE_ENTITY"


class DatabaseConnectionError(DatabaseError):
    """Error al conectar con la base de datos."""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Database connection failed: {reason}",
            details={"reason": reason},
        )
        self.code = "DATABASE_CONNECTION_ERROR"


# ============================================================================
# ERRORES DE VALIDACIÓN
# ============================================================================


class ValidationError(SmartPricingException):
    """Error de validación de datos."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            status_code=422,
        )


class InvalidInputError(ValidationError):
    """Entrada de datos inválida."""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Invalid input for field '{field}': {reason}",
            details={"field": field, "reason": reason},
        )
        self.code = "INVALID_INPUT"


class MissingRequiredFieldError(ValidationError):
    """Campo requerido faltante."""

    def __init__(self, field: str):
        super().__init__(
            message=f"Required field '{field}' is missing",
            details={"field": field},
        )
        self.code = "MISSING_REQUIRED_FIELD"


# ============================================================================
# ERRORES DE PRICING
# ============================================================================


class PricingError(SmartPricingException):
    """Error en el motor de pricing."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="PRICING_ERROR",
            details=details,
            status_code=500,
        )


class PriceCalculationError(PricingError):
    """Error al calcular un precio."""

    def __init__(self, match_id: str, zone_id: str, reason: str):
        super().__init__(
            message=f"Price calculation failed for match {match_id}, zone {zone_id}: {reason}",
            details={"match_id": match_id, "zone_id": zone_id, "reason": reason},
        )
        self.code = "PRICE_CALCULATION_ERROR"


class InvalidPriceError(PricingError):
    """Precio calculado inválido (fuera de límites)."""

    def __init__(self, calculated_price: float, min_price: float, max_price: float):
        super().__init__(
            message=f"Calculated price {calculated_price} is outside valid range [{min_price}, {max_price}]",
            details={
                "calculated_price": calculated_price,
                "min_price": min_price,
                "max_price": max_price,
            },
        )
        self.code = "INVALID_PRICE"


class PriceChangeNotAllowedError(PricingError):
    """Cambio de precio no permitido por las reglas."""

    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Price change not allowed: {reason}",
            details=details or {},
        )
        self.code = "PRICE_CHANGE_NOT_ALLOWED"
        self.status_code = 400


# ============================================================================
# ERRORES DE APIs EXTERNAS
# ============================================================================


class ExternalAPIError(SmartPricingException):
    """Error al comunicarse con una API externa."""

    def __init__(self, api_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"External API error ({api_name}): {message}",
            code="EXTERNAL_API_ERROR",
            details={"api_name": api_name, **(details or {})},
            status_code=502,
        )


class ExternalAPITimeoutError(ExternalAPIError):
    """Timeout al comunicarse con una API externa."""

    def __init__(self, api_name: str, timeout: int):
        super().__init__(
            api_name=api_name,
            message=f"Request timed out after {timeout} seconds",
            details={"timeout": timeout},
        )
        self.code = "EXTERNAL_API_TIMEOUT"


class ExternalAPIRateLimitError(ExternalAPIError):
    """Rate limit alcanzado en una API externa."""

    def __init__(self, api_name: str, retry_after: Optional[int] = None):
        super().__init__(
            api_name=api_name,
            message="Rate limit exceeded",
            details={"retry_after": retry_after},
        )
        self.code = "EXTERNAL_API_RATE_LIMIT"
        self.status_code = 429


# ============================================================================
# ERRORES DE CACHE
# ============================================================================


class CacheError(SmartPricingException):
    """Error relacionado con el sistema de cache."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CACHE_ERROR",
            details=details,
            status_code=500,
        )


class CacheConnectionError(CacheError):
    """Error al conectar con Redis."""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Cache connection failed: {reason}",
            details={"reason": reason},
        )
        self.code = "CACHE_CONNECTION_ERROR"


# ============================================================================
# ERRORES DE MACHINE LEARNING
# ============================================================================


class MLModelError(SmartPricingException):
    """Error relacionado con modelos de ML."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="ML_MODEL_ERROR",
            details=details,
            status_code=500,
        )


class ModelNotFoundError(MLModelError):
    """Modelo de ML no encontrado."""

    def __init__(self, model_path: str):
        super().__init__(
            message=f"ML model not found at path: {model_path}",
            details={"model_path": model_path},
        )
        self.code = "MODEL_NOT_FOUND"


class ModelPredictionError(MLModelError):
    """Error al realizar predicción con el modelo."""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Model prediction failed: {reason}",
            details={"reason": reason},
        )
        self.code = "MODEL_PREDICTION_ERROR"


# ============================================================================
# ERRORES DE NEGOCIO
# ============================================================================


class BusinessRuleError(SmartPricingException):
    """Violación de una regla de negocio."""

    def __init__(self, rule: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Business rule '{rule}' violated: {message}",
            code="BUSINESS_RULE_ERROR",
            details={"rule": rule, **(details or {})},
            status_code=400,
        )


class InventoryError(SmartPricingException):
    """Error relacionado con inventario."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="INVENTORY_ERROR",
            details=details,
            status_code=400,
        )


class InsufficientInventoryError(InventoryError):
    """Inventario insuficiente."""

    def __init__(self, zone_id: str, requested: int, available: int):
        super().__init__(
            message=f"Insufficient inventory in zone {zone_id}: requested {requested}, available {available}",
            details={
                "zone_id": zone_id,
                "requested": requested,
                "available": available,
            },
        )
        self.code = "INSUFFICIENT_INVENTORY"


# ============================================================================
# HANDLERS PARA FASTAPI
# ============================================================================


def create_error_response(exc: SmartPricingException) -> Dict[str, Any]:
    """
    Crea una respuesta de error estándar para FastAPI.

    Args:
        exc: Excepción a convertir

    Returns:
        Diccionario con la respuesta de error
    """
    return {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        }
    }


# FastAPI exception handlers se registrarán en src/api/main.py
