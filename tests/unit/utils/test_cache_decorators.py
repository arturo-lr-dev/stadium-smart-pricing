"""
Tests for Cache Decorators.

Tests para decoradores de cache que permiten caching transparente.
"""

import time

import fakeredis
import pytest

from src.core.cache_service import CacheService
from src.utils.cache_decorators import (
    _generate_cache_key,
    cache_key_builder,
    cached,
    cached_property_method,
    invalidate_cache,
)


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
        key_prefix="test",
    )


class TestGenerateCacheKey:
    """Tests para generación de cache keys."""

    def test_generate_key_simple(self):
        """Test generar key simple."""
        def my_func(a, b):
            return a + b

        key = _generate_cache_key(my_func, (1, 2), {}, "prefix")
        assert key.startswith("prefix:")
        assert "my_func" in key

    def test_generate_key_with_kwargs(self):
        """Test generar key con kwargs."""
        def my_func(a, b=10):
            return a + b

        key1 = _generate_cache_key(my_func, (5,), {"b": 10}, "")
        key2 = _generate_cache_key(my_func, (5,), {"b": 20}, "")

        # Different kwargs should produce different keys
        assert key1 != key2

    def test_generate_key_same_args_same_key(self):
        """Test que mismos args producen misma key."""
        def my_func(a, b):
            return a + b

        key1 = _generate_cache_key(my_func, (1, 2), {}, "")
        key2 = _generate_cache_key(my_func, (1, 2), {}, "")

        assert key1 == key2

    def test_generate_key_different_order_kwargs(self):
        """Test que orden de kwargs no afecta (se ordenan)."""
        def my_func(a, b, c):
            return a + b + c

        key1 = _generate_cache_key(my_func, (), {"a": 1, "b": 2, "c": 3}, "")
        key2 = _generate_cache_key(my_func, (), {"c": 3, "a": 1, "b": 2}, "")

        # Should be the same due to sorting
        assert key1 == key2


class TestCachedDecorator:
    """Tests para decorator @cached."""

    def test_cached_basic(self, cache_service):
        """Test caching básico."""
        call_count = {"count": 0}

        @cached(ttl=300, cache_service=cache_service)
        def expensive_function(x):
            call_count["count"] += 1
            return x * 2

        # Primera llamada: ejecuta función
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count["count"] == 1

        # Segunda llamada: usa cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count["count"] == 1  # No incrementa

    def test_cached_different_args(self, cache_service):
        """Test que diferentes argumentos no usan mismo cache."""
        call_count = {"count": 0}

        @cached(ttl=300, cache_service=cache_service)
        def expensive_function(x):
            call_count["count"] += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count["count"] == 2  # Llamado dos veces

        # Tercera llamada con arg ya usado
        result3 = expensive_function(5)
        assert result3 == 10
        assert call_count["count"] == 2  # No incrementa

    def test_cached_with_kwargs(self, cache_service):
        """Test caching con kwargs."""
        call_count = {"count": 0}

        @cached(ttl=300, cache_service=cache_service)
        def expensive_function(x, multiplier=2):
            call_count["count"] += 1
            return x * multiplier

        result1 = expensive_function(5, multiplier=2)
        result2 = expensive_function(5, multiplier=2)
        result3 = expensive_function(5, multiplier=3)

        assert result1 == 10
        assert result2 == 10
        assert result3 == 15
        assert call_count["count"] == 2  # Solo 2 llamadas únicas

    def test_cached_skip_none(self, cache_service):
        """Test skip_none parameter."""
        call_count = {"count": 0}

        @cached(ttl=300, cache_service=cache_service, skip_none=True)
        def function_returns_none(x):
            call_count["count"] += 1
            if x == 0:
                return None
            return x * 2

        # Primera llamada retorna None
        result1 = function_returns_none(0)
        assert result1 is None
        assert call_count["count"] == 1

        # Segunda llamada (None no se cacheó)
        result2 = function_returns_none(0)
        assert result2 is None
        assert call_count["count"] == 2  # Llamado de nuevo

    def test_cached_dont_skip_none(self, cache_service):
        """Test que skip_none=False cachea None."""
        call_count = {"count": 0}

        @cached(ttl=300, cache_service=cache_service, skip_none=False)
        def function_returns_none(x):
            call_count["count"] += 1
            if x == 0:
                return None
            return x * 2

        # Primera llamada retorna None
        result1 = function_returns_none(0)
        assert result1 is None
        assert call_count["count"] == 1

        # Segunda llamada (None fue cacheado)
        result2 = function_returns_none(0)
        assert result2 is None
        assert call_count["count"] == 1  # No llamado de nuevo

    def test_cache_invalidate_method(self, cache_service):
        """Test método cache_invalidate."""
        call_count = {"count": 0}

        @cached(ttl=300, cache_service=cache_service)
        def expensive_function(x):
            call_count["count"] += 1
            return x * 2

        # Llamar y cachear
        result1 = expensive_function(5)
        assert call_count["count"] == 1

        # Invalidar cache
        expensive_function.cache_invalidate(5)

        # Siguiente llamada ejecuta función de nuevo
        result2 = expensive_function(5)
        assert call_count["count"] == 2

    def test_cache_clear_method(self, cache_service):
        """Test método cache_clear."""
        call_count = {"count": 0}

        @cached(ttl=300, key_prefix="test", cache_service=cache_service)
        def expensive_function(x):
            call_count["count"] += 1
            return x * 2

        # Llamar con varios argumentos
        expensive_function(5)
        expensive_function(10)
        expensive_function(15)
        assert call_count["count"] == 3

        # Clear todo el cache
        expensive_function.cache_clear()

        # Siguientes llamadas ejecutan función de nuevo
        expensive_function(5)
        expensive_function(10)
        assert call_count["count"] == 5


class TestCachedPropertyMethod:
    """Tests para decorator @cached_property_method."""

    def test_cached_property_method_basic(self, cache_service):
        """Test caching de método de clase."""
        call_count = {"count": 0}

        class Match:
            def __init__(self, match_id):
                self.id = match_id

            @cached_property_method(ttl=300, cache_service=cache_service)
            def get_pricing(self, zone_id):
                call_count["count"] += 1
                return f"pricing-{self.id}-{zone_id}"

        match = Match("match_123")

        # Primera llamada
        result1 = match.get_pricing("zone_A")
        assert result1 == "pricing-match_123-zone_A"
        assert call_count["count"] == 1

        # Segunda llamada usa cache
        result2 = match.get_pricing("zone_A")
        assert result2 == "pricing-match_123-zone_A"
        assert call_count["count"] == 1

    def test_cached_property_method_different_instances(self, cache_service):
        """Test que diferentes instancias tienen cache separado."""
        call_count = {"count": 0}

        class Match:
            def __init__(self, match_id):
                self.id = match_id

            @cached_property_method(ttl=300, cache_service=cache_service)
            def get_pricing(self, zone_id):
                call_count["count"] += 1
                return f"pricing-{self.id}-{zone_id}"

        match1 = Match("match_123")
        match2 = Match("match_456")

        result1 = match1.get_pricing("zone_A")
        result2 = match2.get_pricing("zone_A")

        assert result1 == "pricing-match_123-zone_A"
        assert result2 == "pricing-match_456-zone_A"
        assert call_count["count"] == 2  # Dos llamadas diferentes

        # Cache hit para instancias ya llamadas
        result3 = match1.get_pricing("zone_A")
        assert call_count["count"] == 2  # No incrementa

    def test_cached_property_method_no_id(self, cache_service):
        """Test que funciona sin ID (ejecuta sin cache)."""
        call_count = {"count": 0}

        class SimpleClass:
            @cached_property_method(ttl=300, cache_service=cache_service)
            def get_data(self, x):
                call_count["count"] += 1
                return x * 2

        obj = SimpleClass()

        result1 = obj.get_data(5)
        result2 = obj.get_data(5)

        # Sin ID, no cachea
        assert call_count["count"] == 2


class TestInvalidateCacheDecorator:
    """Tests para decorator @invalidate_cache."""

    def test_invalidate_cache_basic(self, cache_service):
        """Test invalidación de cache después de operación."""
        # Primero cachear algo
        cache_service.set("pricing:match:123", {"price": 50})

        @invalidate_cache("pricing:match:*", cache_service=cache_service)
        def update_pricing(match_id, new_price):
            return {"match_id": match_id, "price": new_price}

        # Verificar que el cache existe
        assert cache_service.get("pricing:match:123") is not None

        # Ejecutar función que invalida
        result = update_pricing("123", 60)

        assert result == {"match_id": "123", "price": 60}

        # Cache debería estar invalidado
        assert cache_service.get("pricing:match:123") is None

    def test_invalidate_cache_multiple_keys(self, cache_service):
        """Test invalidar múltiples keys."""
        cache_service.set("user:session:abc", "data1")
        cache_service.set("user:session:def", "data2")
        cache_service.set("user:profile:123", "data3")

        @invalidate_cache("user:session:*", cache_service=cache_service)
        def logout_all_sessions():
            return True

        logout_all_sessions()

        # Sessions invalidadas
        assert cache_service.get("user:session:abc") is None
        assert cache_service.get("user:session:def") is None

        # Profile no afectado
        assert cache_service.get("user:profile:123") is not None


class TestCacheKeyBuilder:
    """Tests para helper cache_key_builder."""

    def test_cache_key_builder_simple(self):
        """Test construir key simple."""
        key = cache_key_builder("pricing", "match", "123")
        assert key == "pricing:match:123"

    def test_cache_key_builder_with_numbers(self):
        """Test construir key con números."""
        key = cache_key_builder("inventory", "match", 123, "zone", "A")
        assert key == "inventory:match:123:zone:A"

    def test_cache_key_builder_single_part(self):
        """Test construir key con una sola parte."""
        key = cache_key_builder("simple")
        assert key == "simple"

    def test_cache_key_builder_empty(self):
        """Test construir key vacía."""
        key = cache_key_builder()
        assert key == ""


class TestCachedIntegration:
    """Tests de integración de decorators."""

    def test_nested_cached_calls(self, cache_service):
        """Test funciones cacheadas que llaman otras funciones cacheadas."""
        call_counts = {"func1": 0, "func2": 0}

        @cached(ttl=300, cache_service=cache_service)
        def func1(x):
            call_counts["func1"] += 1
            return x * 2

        @cached(ttl=300, cache_service=cache_service)
        def func2(x):
            call_counts["func2"] += 1
            result = func1(x)
            return result + 1

        # Primera llamada
        result1 = func2(5)
        assert result1 == 11
        assert call_counts["func1"] == 1
        assert call_counts["func2"] == 1

        # Segunda llamada (ambas cacheadas)
        result2 = func2(5)
        assert result2 == 11
        assert call_counts["func1"] == 1
        assert call_counts["func2"] == 1

    def test_multiple_decorators_same_function(self, cache_service):
        """Test múltiples decoradores en misma función."""
        call_count = {"count": 0}

        @invalidate_cache("related:*", cache_service=cache_service)
        @cached(ttl=300, cache_service=cache_service)
        def complex_operation(x):
            call_count["count"] += 1
            return x * 2

        # Cachear algo relacionado
        cache_service.set("related:data", "value")

        result = complex_operation(5)
        assert result == 10
        assert call_count["count"] == 1

        # Cache relacionado debería estar invalidado
        assert cache_service.get("related:data") is None
