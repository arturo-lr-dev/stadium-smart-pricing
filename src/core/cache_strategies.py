"""
Cache Strategies for Different Data Types.

Define estrategias de cache específicas para pricing, inventario,
datos externos, etc., con sus respectivos TTLs y patrones de keys.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.cache_service import CacheService, get_cache_service
from src.core.logging import get_logger

logger = get_logger(__name__)


class PricingCacheStrategy:
    """
    Estrategia de cache para datos de pricing.

    - Key pattern: pricing:match:{match_id}
    - TTL: 5 minutos (300 segundos)
    - Use case: Cachear pricing calculations que son costosas

    Example:
        >>> strategy = PricingCacheStrategy()
        >>> strategy.set("match_123", pricing_data)
        >>> strategy.get("match_123")
    """

    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Inicializa la estrategia.

        Args:
            cache_service: Servicio de cache (crea uno si no se proporciona)
        """
        self.cache_service = cache_service or get_cache_service(
            default_ttl=300,  # 5 minutos
            key_prefix="pricing",
        )
        self.ttl = 300

    def _make_key(self, match_id: str) -> str:
        """Genera la key para un match."""
        return f"match:{match_id}"

    def get(self, match_id: str) -> Optional[Any]:
        """
        Obtiene pricing de un match desde cache.

        Args:
            match_id: ID del match

        Returns:
            Datos de pricing o None si no está en cache
        """
        key = self._make_key(match_id)
        return self.cache_service.get(key)

    def set(self, match_id: str, pricing_data: Any) -> bool:
        """
        Guarda pricing de un match en cache.

        Args:
            match_id: ID del match
            pricing_data: Datos de pricing (será serializado)

        Returns:
            True si se guardó correctamente
        """
        key = self._make_key(match_id)
        return self.cache_service.set(key, pricing_data, ttl=self.ttl)

    def invalidate(self, match_id: str) -> bool:
        """
        Invalida el cache de pricing para un match.

        Args:
            match_id: ID del match

        Returns:
            True si se eliminó
        """
        key = self._make_key(match_id)
        return self.cache_service.delete(key)

    def invalidate_all(self) -> int:
        """
        Invalida todo el cache de pricing.

        Returns:
            Número de keys eliminadas
        """
        return self.cache_service.clear_prefix("match:")


class InventoryCacheStrategy:
    """
    Estrategia de cache para datos de inventario.

    - Key pattern: inventory:match:{match_id}:zone:{zone_id}
    - TTL: 2 minutos (120 segundos)
    - Use case: Cachear conteos de inventario que cambian frecuentemente

    Example:
        >>> strategy = InventoryCacheStrategy()
        >>> strategy.set("match_123", "zone_A", (50, 100))
        >>> strategy.get("match_123", "zone_A")
        (50, 100)
    """

    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Inicializa la estrategia.

        Args:
            cache_service: Servicio de cache (crea uno si no se proporciona)
        """
        self.cache_service = cache_service or get_cache_service(
            default_ttl=120,  # 2 minutos
            key_prefix="inventory",
        )
        self.ttl = 120

    def _make_key(self, match_id: str, zone_id: str) -> str:
        """Genera la key para un match y zona."""
        return f"match:{match_id}:zone:{zone_id}"

    def _make_match_key(self, match_id: str) -> str:
        """Genera el prefijo de key para un match."""
        return f"match:{match_id}"

    def get(self, match_id: str, zone_id: str) -> Optional[Any]:
        """
        Obtiene inventario de una zona desde cache.

        Args:
            match_id: ID del match
            zone_id: ID de la zona

        Returns:
            Tupla (sold, available) o None si no está en cache
        """
        key = self._make_key(match_id, zone_id)
        return self.cache_service.get(key)

    def set(self, match_id: str, zone_id: str, inventory_data: Any) -> bool:
        """
        Guarda inventario de una zona en cache.

        Args:
            match_id: ID del match
            zone_id: ID de la zona
            inventory_data: Datos de inventario (típicamente tupla (sold, available))

        Returns:
            True si se guardó correctamente
        """
        key = self._make_key(match_id, zone_id)
        return self.cache_service.set(key, inventory_data, ttl=self.ttl)

    def get_match_inventory(self, match_id: str, zone_ids: List[str]) -> Dict[str, Any]:
        """
        Obtiene inventario de múltiples zonas de un match.

        Args:
            match_id: ID del match
            zone_ids: Lista de IDs de zonas

        Returns:
            Diccionario {zone_id: inventory_data}
        """
        keys = [self._make_key(match_id, zone_id) for zone_id in zone_ids]
        # Necesitamos mapear de vuelta a zone_ids
        full_keys_mapping = {self._make_key(match_id, zone_id): zone_id for zone_id in zone_ids}

        # get_many del cache service usa keys sin el prefijo del servicio
        result = self.cache_service.get_many(keys)

        # Mapear de vuelta a zone_ids
        return {
            full_keys_mapping[k]: v
            for k, v in result.items()
            if k in full_keys_mapping
        }

    def invalidate(self, match_id: str, zone_id: str) -> bool:
        """
        Invalida el cache de inventario para una zona.

        Args:
            match_id: ID del match
            zone_id: ID de la zona

        Returns:
            True si se eliminó
        """
        key = self._make_key(match_id, zone_id)
        return self.cache_service.delete(key)

    def invalidate_match(self, match_id: str) -> int:
        """
        Invalida todo el cache de inventario para un match.

        Args:
            match_id: ID del match

        Returns:
            Número de keys eliminadas
        """
        prefix = self._make_match_key(match_id)
        return self.cache_service.clear_prefix(prefix)


class ExternalDataCacheStrategy:
    """
    Estrategia de cache para datos externos (APIs, etc.).

    - Key pattern: external:{source}:{key}
    - TTL: Variable según la fuente (1-6 horas)
    - Use case: Cachear respuestas de APIs externas

    Example:
        >>> strategy = ExternalDataCacheStrategy()
        >>> strategy.set("weather", "forecast:2024-12-14", data, ttl=3600)
        >>> strategy.get("weather", "forecast:2024-12-14")
    """

    # TTLs recomendados por fuente (en segundos)
    DEFAULT_TTLS = {
        "weather": 3600,  # 1 hora
        "football_stats": 21600,  # 6 horas
        "standings": 21600,  # 6 horas
        "transport": 1800,  # 30 minutos
        "analytics": 1800,  # 30 minutos
    }

    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Inicializa la estrategia.

        Args:
            cache_service: Servicio de cache (crea uno si no se proporciona)
        """
        self.cache_service = cache_service or get_cache_service(
            default_ttl=3600,  # 1 hora por defecto
            key_prefix="external",
        )

    def _make_key(self, source: str, data_key: str) -> str:
        """Genera la key para datos externos."""
        return f"{source}:{data_key}"

    def _get_ttl(self, source: str) -> int:
        """Obtiene el TTL recomendado para una fuente."""
        return self.DEFAULT_TTLS.get(source, 3600)

    def get(self, source: str, data_key: str) -> Optional[Any]:
        """
        Obtiene datos externos desde cache.

        Args:
            source: Fuente de datos (weather, football_stats, etc.)
            data_key: Key específica de los datos

        Returns:
            Datos o None si no está en cache
        """
        key = self._make_key(source, data_key)
        return self.cache_service.get(key)

    def set(
        self,
        source: str,
        data_key: str,
        data: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Guarda datos externos en cache.

        Args:
            source: Fuente de datos
            data_key: Key específica de los datos
            data: Datos a guardar
            ttl: TTL en segundos (usa TTL recomendado si no se especifica)

        Returns:
            True si se guardó correctamente
        """
        key = self._make_key(source, data_key)
        ttl = ttl if ttl is not None else self._get_ttl(source)
        return self.cache_service.set(key, data, ttl=ttl)

    def invalidate(self, source: str, data_key: str) -> bool:
        """
        Invalida datos externos específicos.

        Args:
            source: Fuente de datos
            data_key: Key específica de los datos

        Returns:
            True si se eliminó
        """
        key = self._make_key(source, data_key)
        return self.cache_service.delete(key)

    def invalidate_source(self, source: str) -> int:
        """
        Invalida todos los datos de una fuente.

        Args:
            source: Fuente de datos

        Returns:
            Número de keys eliminadas
        """
        return self.cache_service.clear_prefix(f"{source}:")


class SessionCacheStrategy:
    """
    Estrategia de cache para datos de sesión/temporal.

    - Key pattern: session:{session_id}:{key}
    - TTL: 30 minutos (1800 segundos)
    - Use case: Datos temporales de usuario, carritos, etc.

    Example:
        >>> strategy = SessionCacheStrategy()
        >>> strategy.set("session_abc123", "cart", cart_data)
        >>> strategy.get("session_abc123", "cart")
    """

    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Inicializa la estrategia.

        Args:
            cache_service: Servicio de cache (crea uno si no se proporciona)
        """
        self.cache_service = cache_service or get_cache_service(
            default_ttl=1800,  # 30 minutos
            key_prefix="session",
        )
        self.ttl = 1800

    def _make_key(self, session_id: str, data_key: str) -> str:
        """Genera la key para datos de sesión."""
        return f"{session_id}:{data_key}"

    def get(self, session_id: str, data_key: str) -> Optional[Any]:
        """
        Obtiene datos de sesión desde cache.

        Args:
            session_id: ID de sesión
            data_key: Key de los datos dentro de la sesión

        Returns:
            Datos o None si no está en cache
        """
        key = self._make_key(session_id, data_key)
        return self.cache_service.get(key)

    def set(
        self,
        session_id: str,
        data_key: str,
        data: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Guarda datos de sesión en cache.

        Args:
            session_id: ID de sesión
            data_key: Key de los datos
            data: Datos a guardar
            ttl: TTL en segundos (usa default si no se especifica)

        Returns:
            True si se guardó correctamente
        """
        key = self._make_key(session_id, data_key)
        ttl = ttl if ttl is not None else self.ttl
        return self.cache_service.set(key, data, ttl=ttl)

    def invalidate(self, session_id: str, data_key: str) -> bool:
        """
        Invalida datos de sesión específicos.

        Args:
            session_id: ID de sesión
            data_key: Key de los datos

        Returns:
            True si se eliminó
        """
        key = self._make_key(session_id, data_key)
        return self.cache_service.delete(key)

    def invalidate_session(self, session_id: str) -> int:
        """
        Invalida toda una sesión.

        Args:
            session_id: ID de sesión

        Returns:
            Número de keys eliminadas
        """
        return self.cache_service.clear_prefix(f"{session_id}:")

    def refresh_ttl(self, session_id: str, data_key: str) -> bool:
        """
        Refresca el TTL de datos de sesión.

        Args:
            session_id: ID de sesión
            data_key: Key de los datos

        Returns:
            True si se actualizó correctamente
        """
        key = self._make_key(session_id, data_key)
        return self.cache_service.set_ttl(key, self.ttl)


# Funciones helper para obtener estrategias singleton
_pricing_cache: Optional[PricingCacheStrategy] = None
_inventory_cache: Optional[InventoryCacheStrategy] = None
_external_data_cache: Optional[ExternalDataCacheStrategy] = None
_session_cache: Optional[SessionCacheStrategy] = None


def get_pricing_cache() -> PricingCacheStrategy:
    """Obtiene la estrategia de cache de pricing."""
    global _pricing_cache
    if _pricing_cache is None:
        _pricing_cache = PricingCacheStrategy()
    return _pricing_cache


def get_inventory_cache() -> InventoryCacheStrategy:
    """Obtiene la estrategia de cache de inventario."""
    global _inventory_cache
    if _inventory_cache is None:
        _inventory_cache = InventoryCacheStrategy()
    return _inventory_cache


def get_external_data_cache() -> ExternalDataCacheStrategy:
    """Obtiene la estrategia de cache de datos externos."""
    global _external_data_cache
    if _external_data_cache is None:
        _external_data_cache = ExternalDataCacheStrategy()
    return _external_data_cache


def get_session_cache() -> SessionCacheStrategy:
    """Obtiene la estrategia de cache de sesión."""
    global _session_cache
    if _session_cache is None:
        _session_cache = SessionCacheStrategy()
    return _session_cache
