"""
Redis Client with Connection Pooling.

Proporciona un cliente Redis robusto con connection pooling,
health checks y manejo de errores.
"""

from typing import Optional

import redis
from redis.connection import ConnectionPool

from src.core.config import get_settings
from src.core.exceptions import CacheConnectionError
from src.core.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """
    Cliente Redis con connection pooling y health checks.

    Attributes:
        pool: Connection pool de Redis
        client: Cliente Redis

    Example:
        >>> redis_client = RedisClient()
        >>> redis_client.ping()
        True
        >>> redis_client.close()
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        max_connections: int = 50,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        decode_responses: bool = True,
    ):
        """
        Inicializa el cliente Redis con connection pooling.

        Args:
            host: Host de Redis (por defecto desde settings)
            port: Puerto de Redis (por defecto desde settings)
            db: Base de datos de Redis (por defecto desde settings)
            password: Contraseña de Redis (por defecto desde settings)
            max_connections: Número máximo de conexiones en el pool
            socket_timeout: Timeout para operaciones de socket (segundos)
            socket_connect_timeout: Timeout para conexión (segundos)
            decode_responses: Si decodificar respuestas a strings

        Raises:
            CacheConnectionError: Si no se puede conectar a Redis
        """
        settings = get_settings()

        # Usar valores de settings si no se proporcionan
        self._host = host or settings.redis.host
        self._port = port or settings.redis.port
        self._db = db or settings.redis.db
        self._password = password or settings.redis.password

        try:
            # Crear connection pool
            self.pool = ConnectionPool(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password if self._password else None,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                decode_responses=decode_responses,
                encoding="utf-8",
            )

            # Crear cliente usando el pool
            self.client = redis.Redis(connection_pool=self.pool)

            # Verificar conexión
            self.client.ping()

            logger.info(
                f"Redis client initialized successfully "
                f"(host={self._host}, port={self._port}, db={self._db})"
            )

        except redis.ConnectionError as e:
            error_msg = f"Failed to connect to Redis: {e}"
            logger.error(error_msg)
            raise CacheConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error initializing Redis client: {e}"
            logger.error(error_msg)
            raise CacheConnectionError(error_msg)

    def ping(self) -> bool:
        """
        Verifica si Redis está accesible.

        Returns:
            True si Redis responde, False en caso contrario

        Example:
            >>> client = RedisClient()
            >>> client.ping()
            True
        """
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def health_check(self) -> dict:
        """
        Realiza un health check completo de Redis.

        Returns:
            Diccionario con información de salud

        Example:
            >>> client = RedisClient()
            >>> client.health_check()
            {'status': 'healthy', 'ping': True, 'info': {...}}
        """
        try:
            ping_result = self.ping()
            info = self.client.info()

            return {
                "status": "healthy" if ping_result else "unhealthy",
                "ping": ping_result,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "ping": False,
                "error": str(e),
            }

    def get_pool_info(self) -> dict:
        """
        Obtiene información del connection pool.

        Returns:
            Diccionario con información del pool

        Example:
            >>> client = RedisClient()
            >>> client.get_pool_info()
            {'max_connections': 50, 'created_connections': 5}
        """
        return {
            "max_connections": self.pool.max_connections,
            "created_connections": len(self.pool._created_connections) if hasattr(self.pool, '_created_connections') else 0,
        }

    def close(self) -> None:
        """
        Cierra el cliente y el connection pool.

        Example:
            >>> client = RedisClient()
            >>> client.close()
        """
        try:
            if self.client:
                self.client.close()
            if self.pool:
                self.pool.disconnect()
            logger.info("Redis client closed successfully")
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")

    def __enter__(self):
        """Soporte para context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra el cliente al salir del context manager."""
        self.close()

    def __repr__(self) -> str:
        """Representación string del cliente."""
        return f"RedisClient(host={self._host}, port={self._port}, db={self._db})"


# Singleton global para reutilizar la conexión
_redis_client_instance: Optional[RedisClient] = None


def get_redis_client_instance() -> RedisClient:
    """
    Obtiene o crea la instancia singleton del cliente Redis.

    Returns:
        Instancia de RedisClient

    Raises:
        CacheConnectionError: Si no se puede conectar

    Example:
        >>> client = get_redis_client_instance()
        >>> client.ping()
        True
    """
    global _redis_client_instance

    if _redis_client_instance is None:
        _redis_client_instance = RedisClient()

    return _redis_client_instance


def cleanup_redis_client() -> None:
    """
    Limpia la instancia global del cliente Redis.

    Se debe llamar al shutdown de la aplicación.

    Example:
        >>> cleanup_redis_client()
    """
    global _redis_client_instance

    if _redis_client_instance is not None:
        _redis_client_instance.close()
        _redis_client_instance = None
        logger.info("Redis client cleaned up")
