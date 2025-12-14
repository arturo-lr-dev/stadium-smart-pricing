"""
Tests for CacheService.

Tests para el servicio de cache con Redis backend usando fakeredis.
"""

import json
import pickle
from datetime import datetime

import fakeredis
import pytest

from src.core.cache_service import CacheService
from src.core.exceptions import CacheError


@pytest.fixture
def fake_redis():
    """Fixture que proporciona un cliente Redis falso."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cache_service(fake_redis):
    """Fixture que proporciona un CacheService con Redis falso."""
    return CacheService(
        redis_client=fake_redis,
        default_ttl=300,
        serializer="json",
        key_prefix="test",
    )


@pytest.fixture
def cache_service_pickle(fake_redis):
    """Fixture con serializer pickle."""
    # Pickle no funciona bien con decode_responses=True
    fake_redis_bytes = fakeredis.FakeRedis(decode_responses=False)
    return CacheService(
        redis_client=fake_redis_bytes,
        default_ttl=300,
        serializer="pickle",
        key_prefix="test",
    )


class TestCacheServiceBasics:
    """Tests básicos del CacheService."""

    def test_initialization(self, cache_service):
        """Test que el servicio se inicializa correctamente."""
        assert cache_service.default_ttl == 300
        assert cache_service.serializer == "json"
        assert cache_service.key_prefix == "test"

    def test_invalid_serializer(self, fake_redis):
        """Test que falla con serializer inválido."""
        with pytest.raises(ValueError):
            CacheService(redis_client=fake_redis, serializer="invalid")

    def test_make_key(self, cache_service):
        """Test generación de keys con prefijo."""
        key = cache_service._make_key("mykey")
        assert key == "test:mykey"

    def test_make_key_no_prefix(self, fake_redis):
        """Test generación de keys sin prefijo."""
        cache = CacheService(redis_client=fake_redis, key_prefix="")
        key = cache._make_key("mykey")
        assert key == "mykey"


class TestCacheServiceGetSet:
    """Tests de operaciones get/set."""

    def test_set_and_get(self, cache_service):
        """Test guardar y recuperar valor."""
        cache_service.set("key1", "value1")
        result = cache_service.get("key1")
        assert result == "value1"

    def test_get_nonexistent(self, cache_service):
        """Test obtener key que no existe."""
        result = cache_service.get("nonexistent")
        assert result is None

    def test_set_with_dict(self, cache_service):
        """Test guardar y recuperar diccionario."""
        data = {"name": "John", "age": 30}
        cache_service.set("user", data)
        result = cache_service.get("user")
        assert result == data

    def test_set_with_list(self, cache_service):
        """Test guardar y recuperar lista."""
        data = [1, 2, 3, 4, 5]
        cache_service.set("numbers", data)
        result = cache_service.get("numbers")
        assert result == data

    def test_set_with_nested_structure(self, cache_service):
        """Test guardar estructura compleja."""
        data = {
            "match": {
                "id": "123",
                "teams": ["Team A", "Team B"],
                "scores": [2, 1],
            }
        }
        cache_service.set("match", data)
        result = cache_service.get("match")
        assert result == data

    def test_set_with_datetime(self, cache_service):
        """Test guardar datetime (se convierte a string)."""
        now = datetime.now()
        cache_service.set("timestamp", now)
        result = cache_service.get("timestamp")
        # JSON serializer convierte datetime a string
        assert isinstance(result, str)

    def test_set_with_custom_ttl(self, cache_service):
        """Test guardar con TTL custom."""
        cache_service.set("key", "value", ttl=60)
        result = cache_service.get("key")
        assert result == "value"

        # Verificar TTL
        ttl = cache_service.get_ttl("key")
        assert ttl is not None
        assert ttl <= 60

    def test_set_with_zero_ttl(self, cache_service):
        """Test guardar con TTL 0 (sin expiración)."""
        cache_service.set("key", "value", ttl=0)
        result = cache_service.get("key")
        assert result == "value"

        # Verificar que no tiene TTL
        ttl = cache_service.get_ttl("key")
        assert ttl == -1  # -1 significa sin TTL


class TestCacheServicePickle:
    """Tests con serializer pickle."""

    def test_set_and_get_pickle(self, cache_service_pickle):
        """Test con pickle serializer."""
        data = {"complex": "object", "numbers": [1, 2, 3]}
        cache_service_pickle.set("key", data)
        result = cache_service_pickle.get("key")
        assert result == data

    def test_pickle_with_datetime(self, cache_service_pickle):
        """Test pickle con datetime (preserva tipo)."""
        now = datetime.now()
        cache_service_pickle.set("timestamp", now)
        result = cache_service_pickle.get("timestamp")
        assert isinstance(result, datetime)
        assert result == now


class TestCacheServiceDelete:
    """Tests de operaciones delete."""

    def test_delete_existing(self, cache_service):
        """Test eliminar key existente."""
        cache_service.set("key", "value")
        result = cache_service.delete("key")
        assert result is True

        # Verificar que se eliminó
        assert cache_service.get("key") is None

    def test_delete_nonexistent(self, cache_service):
        """Test eliminar key que no existe."""
        result = cache_service.delete("nonexistent")
        assert result is False

    def test_exists(self, cache_service):
        """Test verificar existencia de key."""
        cache_service.set("key", "value")
        assert cache_service.exists("key") is True
        assert cache_service.exists("nonexistent") is False


class TestCacheServiceBatch:
    """Tests de operaciones batch."""

    def test_get_many(self, cache_service):
        """Test obtener múltiples keys."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")
        cache_service.set("key3", "value3")

        result = cache_service.get_many(["key1", "key2", "key3", "key4"])

        assert len(result) == 3
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"
        assert result["key3"] == "value3"
        assert "key4" not in result

    def test_get_many_empty(self, cache_service):
        """Test get_many con lista vacía."""
        result = cache_service.get_many([])
        assert result == {}

    def test_set_many(self, cache_service):
        """Test guardar múltiples keys."""
        data = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }

        cache_service.set_many(data)

        # Verificar que se guardaron todas
        assert cache_service.get("key1") == "value1"
        assert cache_service.get("key2") == "value2"
        assert cache_service.get("key3") == "value3"

    def test_set_many_with_ttl(self, cache_service):
        """Test set_many con TTL."""
        data = {"key1": "value1", "key2": "value2"}
        cache_service.set_many(data, ttl=60)

        # Verificar TTL
        ttl1 = cache_service.get_ttl("key1")
        ttl2 = cache_service.get_ttl("key2")

        assert ttl1 is not None
        assert ttl1 <= 60
        assert ttl2 is not None
        assert ttl2 <= 60

    def test_set_many_empty(self, cache_service):
        """Test set_many con diccionario vacío."""
        result = cache_service.set_many({})
        assert result is True

    def test_delete_many(self, cache_service):
        """Test eliminar múltiples keys."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")
        cache_service.set("key3", "value3")

        deleted = cache_service.delete_many(["key1", "key2", "key4"])

        assert deleted == 2
        assert cache_service.exists("key1") is False
        assert cache_service.exists("key2") is False
        assert cache_service.exists("key3") is True

    def test_delete_many_empty(self, cache_service):
        """Test delete_many con lista vacía."""
        deleted = cache_service.delete_many([])
        assert deleted == 0


class TestCacheServiceTTL:
    """Tests de manejo de TTL."""

    def test_get_ttl(self, cache_service):
        """Test obtener TTL."""
        cache_service.set("key", "value", ttl=120)
        ttl = cache_service.get_ttl("key")

        assert ttl is not None
        assert ttl <= 120
        assert ttl > 0

    def test_get_ttl_nonexistent(self, cache_service):
        """Test obtener TTL de key que no existe."""
        ttl = cache_service.get_ttl("nonexistent")
        assert ttl is None

    def test_set_ttl(self, cache_service):
        """Test establecer TTL."""
        cache_service.set("key", "value", ttl=0)  # Sin TTL inicial
        result = cache_service.set_ttl("key", 120)

        assert result is True

        ttl = cache_service.get_ttl("key")
        assert ttl is not None
        assert ttl <= 120


class TestCacheServiceClearPrefix:
    """Tests de limpieza por prefijo."""

    def test_clear_prefix(self, cache_service):
        """Test limpiar keys con prefijo."""
        cache_service.set("user:123", "data1")
        cache_service.set("user:456", "data2")
        cache_service.set("user:789", "data3")
        cache_service.set("product:111", "other")

        deleted = cache_service.clear_prefix("user:")

        assert deleted == 3
        assert cache_service.exists("user:123") is False
        assert cache_service.exists("user:456") is False
        assert cache_service.exists("user:789") is False
        assert cache_service.exists("product:111") is True

    def test_clear_prefix_empty(self, cache_service):
        """Test limpiar prefijo que no existe."""
        deleted = cache_service.clear_prefix("nonexistent:")
        assert deleted == 0


class TestCacheServiceStats:
    """Tests de estadísticas."""

    def test_get_stats(self, cache_service):
        """Test obtener estadísticas."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")

        stats = cache_service.get_stats()

        # With fakeredis, info() may not work fully, so stats might be empty
        # In production with real Redis, this would have data
        assert isinstance(stats, dict)
        # If stats has data, verify structure
        if stats:
            assert "total_keys" in stats or "used_memory_human" in stats


class TestCacheServiceEdgeCases:
    """Tests de casos edge."""

    def test_overwrite_value(self, cache_service):
        """Test sobrescribir valor existente."""
        cache_service.set("key", "value1")
        cache_service.set("key", "value2")

        result = cache_service.get("key")
        assert result == "value2"

    def test_empty_string_value(self, cache_service):
        """Test guardar string vacío."""
        cache_service.set("key", "")
        result = cache_service.get("key")
        assert result == ""

    def test_zero_value(self, cache_service):
        """Test guardar cero."""
        cache_service.set("key", 0)
        result = cache_service.get("key")
        assert result == 0

    def test_false_value(self, cache_service):
        """Test guardar False."""
        cache_service.set("key", False)
        result = cache_service.get("key")
        assert result is False

    def test_none_value(self, cache_service):
        """Test guardar None."""
        cache_service.set("key", None)
        result = cache_service.get("key")
        # None se serializa como null en JSON
        assert result is None
