"""
Tests for Cache Strategies.

Tests para las diferentes estrategias de cache (pricing, inventory, external data, session).
"""

import fakeredis
import pytest

from src.core.cache_service import CacheService
from src.core.cache_strategies import (
    ExternalDataCacheStrategy,
    InventoryCacheStrategy,
    PricingCacheStrategy,
    SessionCacheStrategy,
)


@pytest.fixture
def fake_redis():
    """Fixture que proporciona un cliente Redis falso."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cache_service(fake_redis):
    """Fixture que proporciona un CacheService base."""
    return CacheService(redis_client=fake_redis)


class TestPricingCacheStrategy:
    """Tests para PricingCacheStrategy."""

    @pytest.fixture
    def pricing_cache(self, cache_service):
        """Fixture para pricing cache."""
        return PricingCacheStrategy(cache_service=cache_service)

    def test_set_and_get(self, pricing_cache):
        """Test guardar y recuperar pricing."""
        pricing_data = {
            "match_id": "match_123",
            "zones": [
                {"zone_id": "A", "price": 50.0},
                {"zone_id": "B", "price": 30.0},
            ],
        }

        result = pricing_cache.set("match_123", pricing_data)
        assert result is True

        retrieved = pricing_cache.get("match_123")
        assert retrieved == pricing_data

    def test_get_nonexistent(self, pricing_cache):
        """Test obtener pricing que no existe."""
        result = pricing_cache.get("nonexistent")
        assert result is None

    def test_invalidate(self, pricing_cache):
        """Test invalidar pricing."""
        pricing_cache.set("match_123", {"data": "value"})
        result = pricing_cache.invalidate("match_123")

        assert result is True
        assert pricing_cache.get("match_123") is None

    def test_invalidate_all(self, pricing_cache):
        """Test invalidar todo el pricing cache."""
        pricing_cache.set("match_123", {"data": "value1"})
        pricing_cache.set("match_456", {"data": "value2"})
        pricing_cache.set("match_789", {"data": "value3"})

        deleted = pricing_cache.invalidate_all()

        assert deleted == 3
        assert pricing_cache.get("match_123") is None
        assert pricing_cache.get("match_456") is None

    def test_key_pattern(self, pricing_cache):
        """Test que las keys siguen el patrón correcto."""
        key = pricing_cache._make_key("match_123")
        assert key == "match:match_123"


class TestInventoryCacheStrategy:
    """Tests para InventoryCacheStrategy."""

    @pytest.fixture
    def inventory_cache(self, cache_service):
        """Fixture para inventory cache."""
        return InventoryCacheStrategy(cache_service=cache_service)

    def test_set_and_get(self, inventory_cache):
        """Test guardar y recuperar inventario."""
        inventory_data = (50, 100)  # (sold, available)

        result = inventory_cache.set("match_123", "zone_A", inventory_data)
        assert result is True

        retrieved = inventory_cache.get("match_123", "zone_A")
        # JSON serialization converts tuples to lists
        assert retrieved == [50, 100] or retrieved == inventory_data

    def test_get_nonexistent(self, inventory_cache):
        """Test obtener inventario que no existe."""
        result = inventory_cache.get("match_123", "zone_A")
        assert result is None

    def test_get_match_inventory(self, inventory_cache):
        """Test obtener inventario de múltiples zonas."""
        inventory_cache.set("match_123", "zone_A", (50, 100))
        inventory_cache.set("match_123", "zone_B", (30, 70))
        inventory_cache.set("match_123", "zone_C", (80, 20))

        zone_ids = ["zone_A", "zone_B", "zone_C", "zone_D"]
        result = inventory_cache.get_match_inventory("match_123", zone_ids)

        # Solo debería retornar las zonas que existen en cache
        assert len(result) == 3
        # JSON serialization converts tuples to lists
        assert [50, 100] in result.values()
        assert [30, 70] in result.values()
        assert [80, 20] in result.values()

    def test_invalidate(self, inventory_cache):
        """Test invalidar inventario de una zona."""
        inventory_cache.set("match_123", "zone_A", (50, 100))
        result = inventory_cache.invalidate("match_123", "zone_A")

        assert result is True
        assert inventory_cache.get("match_123", "zone_A") is None

    def test_invalidate_match(self, inventory_cache):
        """Test invalidar todo el inventario de un match."""
        inventory_cache.set("match_123", "zone_A", (50, 100))
        inventory_cache.set("match_123", "zone_B", (30, 70))
        inventory_cache.set("match_456", "zone_A", (80, 20))

        deleted = inventory_cache.invalidate_match("match_123")

        assert deleted == 2
        assert inventory_cache.get("match_123", "zone_A") is None
        assert inventory_cache.get("match_123", "zone_B") is None
        # No debe afectar a otros matches
        assert inventory_cache.get("match_456", "zone_A") is not None

    def test_key_pattern(self, inventory_cache):
        """Test que las keys siguen el patrón correcto."""
        key = inventory_cache._make_key("match_123", "zone_A")
        assert key == "match:match_123:zone:zone_A"


class TestExternalDataCacheStrategy:
    """Tests para ExternalDataCacheStrategy."""

    @pytest.fixture
    def external_cache(self, cache_service):
        """Fixture para external data cache."""
        return ExternalDataCacheStrategy(cache_service=cache_service)

    def test_set_and_get(self, external_cache):
        """Test guardar y recuperar datos externos."""
        weather_data = {
            "temperature": 25,
            "precipitation": 0.1,
            "wind_speed": 10,
        }

        result = external_cache.set("weather", "forecast:2024-12-14", weather_data)
        assert result is True

        retrieved = external_cache.get("weather", "forecast:2024-12-14")
        assert retrieved == weather_data

    def test_get_nonexistent(self, external_cache):
        """Test obtener datos que no existen."""
        result = external_cache.get("weather", "nonexistent")
        assert result is None

    def test_set_with_custom_ttl(self, external_cache):
        """Test guardar con TTL custom."""
        data = {"key": "value"}
        result = external_cache.set("custom_source", "key", data, ttl=7200)

        assert result is True
        assert external_cache.get("custom_source", "key") == data

    def test_default_ttls(self, external_cache):
        """Test TTLs por defecto según fuente."""
        assert external_cache._get_ttl("weather") == 3600  # 1 hora
        assert external_cache._get_ttl("football_stats") == 21600  # 6 horas
        assert external_cache._get_ttl("standings") == 21600  # 6 horas
        assert external_cache._get_ttl("transport") == 1800  # 30 min
        assert external_cache._get_ttl("unknown_source") == 3600  # default

    def test_invalidate(self, external_cache):
        """Test invalidar datos específicos."""
        external_cache.set("weather", "forecast:2024-12-14", {"temp": 25})
        result = external_cache.invalidate("weather", "forecast:2024-12-14")

        assert result is True
        assert external_cache.get("weather", "forecast:2024-12-14") is None

    def test_invalidate_source(self, external_cache):
        """Test invalidar todos los datos de una fuente."""
        external_cache.set("weather", "forecast:2024-12-14", {"temp": 25})
        external_cache.set("weather", "forecast:2024-12-15", {"temp": 26})
        external_cache.set("football_stats", "team:123", {"wins": 10})

        deleted = external_cache.invalidate_source("weather")

        assert deleted == 2
        assert external_cache.get("weather", "forecast:2024-12-14") is None
        assert external_cache.get("weather", "forecast:2024-12-15") is None
        # No debe afectar otras fuentes
        assert external_cache.get("football_stats", "team:123") is not None

    def test_key_pattern(self, external_cache):
        """Test que las keys siguen el patrón correcto."""
        key = external_cache._make_key("weather", "forecast:2024-12-14")
        assert key == "weather:forecast:2024-12-14"


class TestSessionCacheStrategy:
    """Tests para SessionCacheStrategy."""

    @pytest.fixture
    def session_cache(self, cache_service):
        """Fixture para session cache."""
        return SessionCacheStrategy(cache_service=cache_service)

    def test_set_and_get(self, session_cache):
        """Test guardar y recuperar datos de sesión."""
        cart_data = {
            "items": [
                {"match_id": "123", "zone_id": "A", "quantity": 2},
            ],
            "total": 100.0,
        }

        result = session_cache.set("session_abc123", "cart", cart_data)
        assert result is True

        retrieved = session_cache.get("session_abc123", "cart")
        assert retrieved == cart_data

    def test_get_nonexistent(self, session_cache):
        """Test obtener datos de sesión que no existen."""
        result = session_cache.get("session_abc123", "cart")
        assert result is None

    def test_set_with_custom_ttl(self, session_cache):
        """Test guardar con TTL custom."""
        data = {"key": "value"}
        result = session_cache.set("session_abc123", "data", data, ttl=600)

        assert result is True
        assert session_cache.get("session_abc123", "data") == data

    def test_invalidate(self, session_cache):
        """Test invalidar datos específicos de sesión."""
        session_cache.set("session_abc123", "cart", {"items": []})
        result = session_cache.invalidate("session_abc123", "cart")

        assert result is True
        assert session_cache.get("session_abc123", "cart") is None

    def test_invalidate_session(self, session_cache):
        """Test invalidar toda una sesión."""
        session_cache.set("session_abc123", "cart", {"items": []})
        session_cache.set("session_abc123", "preferences", {"theme": "dark"})
        session_cache.set("session_xyz789", "cart", {"items": []})

        deleted = session_cache.invalidate_session("session_abc123")

        assert deleted == 2
        assert session_cache.get("session_abc123", "cart") is None
        assert session_cache.get("session_abc123", "preferences") is None
        # No debe afectar otras sesiones
        assert session_cache.get("session_xyz789", "cart") is not None

    def test_refresh_ttl(self, session_cache):
        """Test refrescar TTL de sesión."""
        session_cache.set("session_abc123", "cart", {"items": []}, ttl=60)

        # Refrescar TTL
        result = session_cache.refresh_ttl("session_abc123", "cart")
        assert result is True

        # Verificar que el TTL cambió
        ttl = session_cache.cache_service.get_ttl(
            session_cache._make_key("session_abc123", "cart")
        )
        assert ttl > 60  # Debería ser ~1800 ahora

    def test_key_pattern(self, session_cache):
        """Test que las keys siguen el patrón correcto."""
        key = session_cache._make_key("session_abc123", "cart")
        assert key == "session_abc123:cart"


class TestCacheStrategiesIntegration:
    """Tests de integración entre estrategias."""

    def test_different_strategies_isolated(self, cache_service):
        """Test que diferentes estrategias están aisladas."""
        pricing_cache = PricingCacheStrategy(cache_service=cache_service)
        inventory_cache = InventoryCacheStrategy(cache_service=cache_service)

        # Guardar datos similares en ambas estrategias
        pricing_cache.set("match_123", {"price": 50})
        inventory_cache.set("match_123", "zone_A", (50, 100))

        # Deben estar aislados (diferentes prefijos)
        assert pricing_cache.get("match_123") == {"price": 50}
        # JSON serialization converts tuples to lists
        assert inventory_cache.get("match_123", "zone_A") == [50, 100]

        # Invalidar uno no debe afectar al otro
        pricing_cache.invalidate("match_123")
        assert pricing_cache.get("match_123") is None
        assert inventory_cache.get("match_123", "zone_A") is not None
