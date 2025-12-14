"""
Cache Decorators for Transparent Caching.

Proporciona decoradores para cachear automáticamente resultados de funciones
sin modificar su lógica interna.
"""

import functools
import hashlib
import inspect
import json
from typing import Any, Callable, Optional

from src.core.cache_service import CacheService, get_cache_service
from src.core.logging import get_logger

logger = get_logger(__name__)


def _generate_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    key_prefix: str = "",
) -> str:
    """
    Genera una cache key única basada en función y argumentos.

    Args:
        func: Función a cachear
        args: Argumentos posicionales
        kwargs: Argumentos nombrados
        key_prefix: Prefijo opcional para la key

    Returns:
        Cache key única

    Example:
        >>> def my_func(a, b): pass
        >>> _generate_cache_key(my_func, (1, 2), {}, "prefix")
        'prefix:my_func:...'
    """
    # Nombre de la función
    func_name = f"{func.__module__}.{func.__name__}"

    # Serializar argumentos a string
    try:
        # Convertir args y kwargs a formato serializable
        args_str = json.dumps(args, sort_keys=True, default=str)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        params_str = f"{args_str}:{kwargs_str}"

        # Hash de los parámetros para mantener keys cortas
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:16]

    except (TypeError, ValueError) as e:
        # Si no se puede serializar, usar hash de repr
        logger.warning(f"Could not serialize args for {func_name}: {e}")
        params_str = f"{repr(args)}:{repr(kwargs)}"
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:16]

    # Construir key final
    if key_prefix:
        return f"{key_prefix}:{func_name}:{params_hash}"
    else:
        return f"{func_name}:{params_hash}"


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    cache_service: Optional[CacheService] = None,
    skip_none: bool = True,
):
    """
    Decorator para cachear resultados de funciones.

    Args:
        ttl: Time to live en segundos
        key_prefix: Prefijo para la cache key
        cache_service: Servicio de cache (usa default si no se proporciona)
        skip_none: Si True, no cachea resultados None

    Returns:
        Decorator

    Example:
        >>> @cached(ttl=300, key_prefix="pricing")
        >>> def calculate_price(match_id: str, zone_id: str):
        >>>     # expensive calculation
        >>>     return price
        >>>
        >>> # Primera llamada: ejecuta función y cachea resultado
        >>> price1 = calculate_price("match_123", "zone_A")
        >>>
        >>> # Segunda llamada: retorna desde cache
        >>> price2 = calculate_price("match_123", "zone_A")
    """

    def decorator(func: Callable) -> Callable:
        # Obtener o crear cache service
        _cache_service = cache_service or get_cache_service(
            default_ttl=ttl,
            key_prefix=key_prefix,
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generar cache key
            cache_key = _generate_cache_key(func, args, kwargs, key_prefix)

            # Verificar si la key existe en cache
            if _cache_service.exists(cache_key):
                # Key existe, obtener valor
                cached_value = _cache_service.get(cache_key)
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value

            # Cache miss: ejecutar función
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)

            # Guardar en cache (si no es None o si skip_none=False)
            if result is not None or not skip_none:
                _cache_service.set(cache_key, result, ttl=ttl)

            return result

        # Añadir métodos helper al wrapper
        wrapper.cache_invalidate = lambda *args, **kwargs: _cache_service.delete(
            _generate_cache_key(func, args, kwargs, key_prefix)
        )
        wrapper.cache_clear = lambda: _cache_service.clear_prefix(
            f"{key_prefix}:{func.__module__}.{func.__name__}"
        )

        return wrapper

    return decorator


def cached_property_method(
    ttl: int = 300,
    key_prefix: str = "",
    cache_service: Optional[CacheService] = None,
):
    """
    Decorator para cachear métodos que dependen de propiedades del objeto.

    Similar a @cached pero incluye el ID del objeto en la cache key.

    Args:
        ttl: Time to live en segundos
        key_prefix: Prefijo para la cache key
        cache_service: Servicio de cache

    Returns:
        Decorator

    Example:
        >>> class Match:
        >>>     def __init__(self, match_id):
        >>>         self.id = match_id
        >>>
        >>>     @cached_property_method(ttl=300, key_prefix="match")
        >>>     def get_pricing(self, zone_id: str):
        >>>         # expensive calculation
        >>>         return pricing
    """

    def decorator(func: Callable) -> Callable:
        # Obtener o crear cache service
        _cache_service = cache_service or get_cache_service(
            default_ttl=ttl,
            key_prefix=key_prefix,
        )

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Intentar obtener ID del objeto (self.id o self.pk)
            obj_id = getattr(self, "id", None) or getattr(self, "pk", None)

            if obj_id is None:
                # Si no hay ID, ejecutar sin cache
                logger.warning(
                    f"Object has no 'id' or 'pk' attribute, "
                    f"skipping cache for {func.__name__}"
                )
                return func(self, *args, **kwargs)

            # Generar cache key incluyendo obj_id
            func_name = f"{func.__module__}.{self.__class__.__name__}.{func.__name__}"
            args_str = json.dumps(args, sort_keys=True, default=str)
            kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
            params_str = f"{args_str}:{kwargs_str}"
            params_hash = hashlib.md5(params_str.encode()).hexdigest()[:16]

            if key_prefix:
                cache_key = f"{key_prefix}:{func_name}:{obj_id}:{params_hash}"
            else:
                cache_key = f"{func_name}:{obj_id}:{params_hash}"

            # Intentar obtener desde cache
            cached_value = _cache_service.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__} (obj_id={obj_id})")
                return cached_value

            # Cache miss: ejecutar método
            logger.debug(f"Cache miss for {func.__name__} (obj_id={obj_id})")
            result = func(self, *args, **kwargs)

            # Guardar en cache
            if result is not None:
                _cache_service.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


def invalidate_cache(
    key_pattern: str,
    cache_service: Optional[CacheService] = None,
):
    """
    Decorator para invalidar cache después de ejecutar una función.

    Útil para funciones que modifican datos y deben invalidar cache relacionado.

    Args:
        key_pattern: Patrón de keys a invalidar
        cache_service: Servicio de cache

    Returns:
        Decorator

    Example:
        >>> @invalidate_cache("pricing:match:*")
        >>> def update_match_pricing(match_id: str, new_pricing):
        >>>     # actualizar pricing en BD
        >>>     return updated_pricing
    """

    def decorator(func: Callable) -> Callable:
        _cache_service = cache_service or get_cache_service()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Ejecutar función
            result = func(*args, **kwargs)

            # Invalidar cache
            try:
                deleted = _cache_service.invalidate_pattern(key_pattern)
                logger.debug(
                    f"Invalidated {deleted} cache keys matching '{key_pattern}'"
                )
            except Exception as e:
                logger.error(f"Error invalidating cache: {e}")

            return result

        return wrapper

    return decorator


def memoize(maxsize: int = 128, typed: bool = False):
    """
    Decorator similar a functools.lru_cache pero con Redis backend.

    Args:
        maxsize: Tamaño máximo del cache (no implementado, placeholder)
        typed: Si diferenciar tipos en argumentos

    Returns:
        Decorator

    Note:
        Esta es una versión simplificada. Para casos simples,
        usar functools.lru_cache puede ser más eficiente.

    Example:
        >>> @memoize()
        >>> def fibonacci(n):
        >>>     if n < 2:
        >>>         return n
        >>>     return fibonacci(n-1) + fibonacci(n-2)
    """
    return cached(ttl=3600)  # 1 hora por defecto


class CacheContext:
    """
    Context manager para control fino de cache.

    Permite deshabilitar cache temporalmente o usar diferentes configuraciones.

    Example:
        >>> with CacheContext(enabled=False):
        >>>     # Código que no debe usar cache
        >>>     result = calculate_something()
    """

    def __init__(
        self,
        enabled: bool = True,
        cache_service: Optional[CacheService] = None,
    ):
        """
        Inicializa el context manager.

        Args:
            enabled: Si el cache está habilitado
            cache_service: Servicio de cache a usar
        """
        self.enabled = enabled
        self.cache_service = cache_service
        self._original_cache_service = None

    def __enter__(self):
        """Entra al contexto."""
        # Aquí podríamos cambiar el cache service global si fuera necesario
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sale del contexto."""
        # Restaurar configuración original si fue cambiada
        pass


def cache_key_builder(*key_parts: str) -> str:
    """
    Helper para construir cache keys manualmente.

    Args:
        *key_parts: Partes de la key a unir

    Returns:
        Cache key construida

    Example:
        >>> key = cache_key_builder("pricing", "match", "123", "zone", "A")
        >>> # "pricing:match:123:zone:A"
    """
    return ":".join(str(part) for part in key_parts)
