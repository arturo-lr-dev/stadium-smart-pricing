"""
Cache Service with Redis Backend.

Proporciona una capa de abstracción para operaciones de cache
con serialización automática, TTL management y estrategias de cache.
"""

import json
import pickle
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import redis

from src.core.exceptions import CacheError
from src.core.logging import get_logger
from src.core.redis_client import get_redis_client_instance
from src.utils.metrics import (
    cache_operation_duration_seconds,
    cache_operations_total,
    update_cache_metrics,
)

logger = get_logger(__name__)


class CacheService:
    """
    Servicio de cache con Redis backend.

    Proporciona operaciones de cache con serialización automática,
    manejo de TTL y soporte para operaciones batch.

    Attributes:
        redis_client: Cliente Redis
        default_ttl: TTL por defecto en segundos
        serializer: Tipo de serialización ('json' o 'pickle')

    Example:
        >>> cache = CacheService(default_ttl=300)
        >>> cache.set("key", {"data": "value"})
        >>> cache.get("key")
        {'data': 'value'}
        >>> cache.delete("key")
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        default_ttl: int = 300,
        serializer: str = "json",
        key_prefix: str = "",
    ):
        """
        Inicializa el servicio de cache.

        Args:
            redis_client: Cliente Redis (usa singleton si no se proporciona)
            default_ttl: TTL por defecto en segundos
            serializer: Tipo de serialización ('json' o 'pickle')
            key_prefix: Prefijo para todas las keys

        Raises:
            ValueError: Si el serializer no es válido
        """
        if redis_client is None:
            redis_client_instance = get_redis_client_instance()
            self.redis_client = redis_client_instance.client
        else:
            self.redis_client = redis_client

        self.default_ttl = default_ttl
        self.key_prefix = key_prefix

        if serializer not in ["json", "pickle"]:
            raise ValueError("Serializer must be 'json' or 'pickle'")
        self.serializer = serializer

        # Metrics tracking
        self._total_gets = 0
        self._cache_hits = 0

        logger.info(
            f"CacheService initialized (ttl={default_ttl}s, "
            f"serializer={serializer}, prefix='{key_prefix}')"
        )

    def _make_key(self, key: str) -> str:
        """
        Genera la key completa con prefijo.

        Args:
            key: Key base

        Returns:
            Key con prefijo

        Example:
            >>> cache = CacheService(key_prefix="pricing")
            >>> cache._make_key("match:123")
            'pricing:match:123'
        """
        if self.key_prefix:
            return f"{self.key_prefix}:{key}"
        return key

    def _serialize(self, value: Any) -> Union[str, bytes]:
        """
        Serializa un valor para almacenamiento.

        Args:
            value: Valor a serializar

        Returns:
            Valor serializado

        Raises:
            CacheError: Si falla la serialización
        """
        try:
            if self.serializer == "json":
                # Para JSON, manejar tipos especiales
                return json.dumps(value, default=str)
            else:  # pickle
                return pickle.dumps(value)
        except Exception as e:
            raise CacheError(f"Failed to serialize value: {e}")

    def _deserialize(self, value: Union[str, bytes]) -> Any:
        """
        Deserializa un valor del cache.

        Args:
            value: Valor serializado

        Returns:
            Valor deserializado

        Raises:
            CacheError: Si falla la deserialización
        """
        if value is None:
            return None

        try:
            if self.serializer == "json":
                return json.loads(value)
            else:  # pickle
                return pickle.loads(value)
        except Exception as e:
            raise CacheError(f"Failed to deserialize value: {e}")

    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un valor del cache.

        Args:
            key: Key del valor

        Returns:
            Valor deserializado o None si no existe

        Example:
            >>> cache.set("user:123", {"name": "John"})
            >>> cache.get("user:123")
            {'name': 'John'}
            >>> cache.get("nonexistent")
            None
        """
        start_time = time.time()
        try:
            full_key = self._make_key(key)
            value = self.redis_client.get(full_key)

            # Update metrics tracking
            self._total_gets += 1

            if value is None:
                # Cache miss
                logger.debug(f"Cache miss: {key}")
                cache_operations_total.labels(
                    operation="get",
                    result="miss"
                ).inc()

                # Update hit ratio metric
                update_cache_metrics(self._cache_hits, self._total_gets)

                duration = time.time() - start_time
                cache_operation_duration_seconds.labels(operation="get").observe(duration)

                return None

            # Cache hit
            self._cache_hits += 1
            logger.debug(f"Cache hit: {key}")

            cache_operations_total.labels(
                operation="get",
                result="hit"
            ).inc()

            # Update hit ratio metric
            update_cache_metrics(self._cache_hits, self._total_gets)

            deserialized = self._deserialize(value)

            duration = time.time() - start_time
            cache_operation_duration_seconds.labels(operation="get").observe(duration)

            return deserialized

        except Exception as e:
            logger.error(f"Error getting key '{key}': {e}")

            cache_operations_total.labels(
                operation="get",
                result="error"
            ).inc()

            duration = time.time() - start_time
            cache_operation_duration_seconds.labels(operation="get").observe(duration)

            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Guarda un valor en el cache.

        Args:
            key: Key del valor
            value: Valor a guardar (será serializado)
            ttl: TTL en segundos (usa default_ttl si no se especifica)

        Returns:
            True si se guardó correctamente

        Example:
            >>> cache.set("key", {"data": "value"}, ttl=60)
            True
            >>> cache.get("key")
            {'data': 'value'}
        """
        start_time = time.time()
        try:
            full_key = self._make_key(key)
            serialized = self._serialize(value)
            ttl = ttl if ttl is not None else self.default_ttl

            if ttl > 0:
                self.redis_client.setex(full_key, ttl, serialized)
            else:
                self.redis_client.set(full_key, serialized)

            logger.debug(f"Cache set: {key} (ttl={ttl}s)")

            # Record metrics
            cache_operations_total.labels(
                operation="set",
                result="success"
            ).inc()

            duration = time.time() - start_time
            cache_operation_duration_seconds.labels(operation="set").observe(duration)

            return True

        except Exception as e:
            logger.error(f"Error setting key '{key}': {e}")

            cache_operations_total.labels(
                operation="set",
                result="error"
            ).inc()

            duration = time.time() - start_time
            cache_operation_duration_seconds.labels(operation="set").observe(duration)

            return False

    def delete(self, key: str) -> bool:
        """
        Elimina un valor del cache.

        Args:
            key: Key a eliminar

        Returns:
            True si se eliminó (existía), False si no existía

        Example:
            >>> cache.set("key", "value")
            >>> cache.delete("key")
            True
            >>> cache.delete("key")
            False
        """
        start_time = time.time()
        try:
            full_key = self._make_key(key)
            result = self.redis_client.delete(full_key)

            logger.debug(f"Cache delete: {key} (existed={result > 0})")

            # Record metrics
            cache_operations_total.labels(
                operation="delete",
                result="success" if result > 0 else "miss"
            ).inc()

            duration = time.time() - start_time
            cache_operation_duration_seconds.labels(operation="delete").observe(duration)

            return result > 0

        except Exception as e:
            logger.error(f"Error deleting key '{key}': {e}")

            cache_operations_total.labels(
                operation="delete",
                result="error"
            ).inc()

            duration = time.time() - start_time
            cache_operation_duration_seconds.labels(operation="delete").observe(duration)

            return False

    def exists(self, key: str) -> bool:
        """
        Verifica si una key existe en el cache.

        Args:
            key: Key a verificar

        Returns:
            True si existe, False en caso contrario

        Example:
            >>> cache.set("key", "value")
            >>> cache.exists("key")
            True
            >>> cache.exists("nonexistent")
            False
        """
        try:
            full_key = self._make_key(key)
            return self.redis_client.exists(full_key) > 0

        except Exception as e:
            logger.error(f"Error checking existence of key '{key}': {e}")
            return False

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Obtiene múltiples valores del cache.

        Args:
            keys: Lista de keys

        Returns:
            Diccionario con keys y valores (solo incluye keys que existen)

        Example:
            >>> cache.set("key1", "value1")
            >>> cache.set("key2", "value2")
            >>> cache.get_many(["key1", "key2", "key3"])
            {'key1': 'value1', 'key2': 'value2'}
        """
        if not keys:
            return {}

        try:
            full_keys = [self._make_key(k) for k in keys]
            values = self.redis_client.mget(full_keys)

            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize(value)

            logger.debug(f"Cache get_many: {len(result)}/{len(keys)} hits")
            return result

        except Exception as e:
            logger.error(f"Error getting multiple keys: {e}")
            return {}

    def set_many(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Guarda múltiples valores en el cache.

        Args:
            mapping: Diccionario de key-value
            ttl: TTL en segundos para todas las keys

        Returns:
            True si se guardaron correctamente

        Example:
            >>> cache.set_many({"key1": "value1", "key2": "value2"}, ttl=60)
            True
            >>> cache.get_many(["key1", "key2"])
            {'key1': 'value1', 'key2': 'value2'}
        """
        if not mapping:
            return True

        try:
            # Preparar datos para mset
            serialized_mapping = {
                self._make_key(k): self._serialize(v)
                for k, v in mapping.items()
            }

            # Guardar todas las keys
            self.redis_client.mset(serialized_mapping)

            # Si hay TTL, aplicarlo a cada key
            ttl = ttl if ttl is not None else self.default_ttl
            if ttl > 0:
                pipe = self.redis_client.pipeline()
                for full_key in serialized_mapping.keys():
                    pipe.expire(full_key, ttl)
                pipe.execute()

            logger.debug(f"Cache set_many: {len(mapping)} keys (ttl={ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Error setting multiple keys: {e}")
            return False

    def delete_many(self, keys: List[str]) -> int:
        """
        Elimina múltiples valores del cache.

        Args:
            keys: Lista de keys a eliminar

        Returns:
            Número de keys eliminadas

        Example:
            >>> cache.set_many({"key1": "value1", "key2": "value2"})
            >>> cache.delete_many(["key1", "key2", "key3"])
            2
        """
        if not keys:
            return 0

        try:
            full_keys = [self._make_key(k) for k in keys]
            deleted = self.redis_client.delete(*full_keys)
            logger.debug(f"Cache delete_many: {deleted} keys deleted")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting multiple keys: {e}")
            return 0

    def get_ttl(self, key: str) -> Optional[int]:
        """
        Obtiene el TTL restante de una key.

        Args:
            key: Key a consultar

        Returns:
            TTL en segundos, -1 si no tiene TTL, None si no existe

        Example:
            >>> cache.set("key", "value", ttl=60)
            >>> cache.get_ttl("key")
            60
        """
        try:
            full_key = self._make_key(key)
            ttl = self.redis_client.ttl(full_key)

            if ttl == -2:  # Key no existe
                return None
            elif ttl == -1:  # Key existe pero no tiene TTL
                return -1
            else:
                return ttl

        except Exception as e:
            logger.error(f"Error getting TTL for key '{key}': {e}")
            return None

    def set_ttl(self, key: str, ttl: int) -> bool:
        """
        Establece o actualiza el TTL de una key.

        Args:
            key: Key a actualizar
            ttl: TTL en segundos

        Returns:
            True si se actualizó correctamente

        Example:
            >>> cache.set("key", "value")
            >>> cache.set_ttl("key", 60)
            True
        """
        try:
            full_key = self._make_key(key)
            return self.redis_client.expire(full_key, ttl)

        except Exception as e:
            logger.error(f"Error setting TTL for key '{key}': {e}")
            return False

    def clear_prefix(self, prefix: str) -> int:
        """
        Elimina todas las keys que coinciden con un prefijo.

        Args:
            prefix: Prefijo a buscar

        Returns:
            Número de keys eliminadas

        Warning:
            Usar con cuidado en producción con grandes cantidades de keys.

        Example:
            >>> cache.set("user:123", "data1")
            >>> cache.set("user:456", "data2")
            >>> cache.clear_prefix("user:")
            2
        """
        try:
            full_prefix = self._make_key(prefix)
            pattern = f"{full_prefix}*"

            # Usar SCAN en lugar de KEYS para mejor performance
            deleted = 0
            cursor = 0

            while True:
                cursor, keys = self.redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += self.redis_client.delete(*keys)

                if cursor == 0:
                    break

            logger.info(f"Cleared {deleted} keys with prefix '{prefix}'")
            return deleted

        except Exception as e:
            logger.error(f"Error clearing prefix '{prefix}': {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del cache.

        Returns:
            Diccionario con estadísticas

        Example:
            >>> cache.get_stats()
            {'total_keys': 150, 'memory_used': '1.5M', ...}
        """
        try:
            info = self.redis_client.info()
            return {
                "total_keys": self.redis_client.dbsize(),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "used_memory_peak_human": info.get("used_memory_peak_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalida todas las keys que coinciden con un patrón.

        Args:
            pattern: Patrón Redis (soporta * y ?)

        Returns:
            Número de keys eliminadas

        Example:
            >>> cache.set("pricing:match:123", "data1")
            >>> cache.set("pricing:match:456", "data2")
            >>> cache.invalidate_pattern("pricing:match:*")
            2
        """
        return self.clear_prefix(pattern.replace("*", ""))


# Singleton para reutilizar el servicio
_cache_service_instance: Optional[CacheService] = None


def get_cache_service(
    default_ttl: int = 300,
    key_prefix: str = "",
) -> CacheService:
    """
    Obtiene o crea la instancia del servicio de cache.

    Args:
        default_ttl: TTL por defecto en segundos
        key_prefix: Prefijo para las keys

    Returns:
        Instancia de CacheService

    Example:
        >>> cache = get_cache_service(default_ttl=600, key_prefix="app")
        >>> cache.set("key", "value")
    """
    global _cache_service_instance

    if _cache_service_instance is None:
        _cache_service_instance = CacheService(
            default_ttl=default_ttl,
            key_prefix=key_prefix,
        )

    return _cache_service_instance
