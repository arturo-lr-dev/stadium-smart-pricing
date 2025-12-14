# Plan de Integración de Cache en Servicios Existentes

**Fecha:** 2025-12-14
**Versión:** 1.0
**Objetivo:** Integrar la capa de caching (Phase 11) en todos los servicios existentes

---

## Resumen Ejecutivo

Este plan detalla cómo integrar las nuevas capacidades de caching en los servicios existentes del sistema de Smart Pricing. La integración se realizará de forma gradual y retrocompatible, minimizando cambios en las interfaces públicas.

**Beneficios esperados:**
- 70-80% reducción en consultas a base de datos
- 90%+ reducción en llamadas a APIs externas
- 10-20x mejora en tiempos de respuesta para operaciones cacheadas
- Menor carga en servicios externos (menor costo)

---

## Servicios a Actualizar

### Prioridad Alta (Impacto Inmediato)

1. **InventoryManager** - Ya usa Redis, migrar a InventoryCacheStrategy
2. **PricingEngine** - Cachear cálculos de pricing con PricingCacheStrategy
3. **FootballDataAPI** - Migrar de cache en memoria a ExternalDataCacheStrategy
4. **WeatherAPI** - Migrar de cache en memoria a ExternalDataCacheStrategy

### Prioridad Media (Mejoras de Performance)

5. **RulesEngine** - Cachear multiplicadores calculados dinámicamente
6. **DemandPredictor** - Cachear predicciones ML
7. **GoogleAnalyticsIntegration** - Cachear métricas

### Prioridad Baja (Optimizaciones Futuras)

8. **TicketingSystemAPI** - Cachear disponibilidad
9. **Repositories** - Cachear queries frecuentes

---

## FASE 1: InventoryManager Migration

### Estado Actual

El `InventoryManager` ya implementa caching con Redis usando métodos manuales:
- Usa `json.loads/dumps` para serialización
- Construye keys manualmente: `inventory:{prefix}:{args}`
- TTL configurado a 300 segundos (5 minutos)

**Archivos:**
- `src/domain/services/inventory_manager.py`

### Cambios Propuestos

**1. Reemplazar caching manual con InventoryCacheStrategy**

```python
# ANTES (líneas 1-52)
class InventoryManager:
    def __init__(self, sale_repository, zone_repository, redis_client, cache_ttl=300):
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        # ...

# DESPUÉS
from src.core.cache_strategies import InventoryCacheStrategy

class InventoryManager:
    def __init__(
        self,
        sale_repository,
        zone_repository,
        cache_strategy: Optional[InventoryCacheStrategy] = None
    ):
        self.sale_repo = sale_repository
        self.zone_repo = zone_repository
        # Usar strategy proporcionado o crear uno nuevo
        self.cache = cache_strategy or InventoryCacheStrategy()
        # ...
```

**2. Simplificar métodos de cache**

```python
# ANTES (métodos _get_cache_key, _get_from_cache, _set_in_cache)
def _get_cache_key(self, prefix: str, *args) -> str:
    return f"inventory:{prefix}:" + ":".join(str(arg) for arg in args)

def _get_from_cache(self, key: str) -> Optional[Dict]:
    try:
        cached = self.redis_client.get(key)
        if cached:
            return json.loads(cached)
        return None
    except Exception as e:
        logger.error(f"Error reading from cache: {e}")
        return None

# DESPUÉS - ELIMINAR estos métodos, usar directamente cache strategy
# Ya no son necesarios
```

**3. Actualizar get_zone_inventory**

```python
# ANTES
def get_zone_inventory(self, match_id: str, zone_id: str) -> Tuple[int, int]:
    cache_key = self._get_cache_key("zone", match_id, zone_id)
    cached = self._get_from_cache(cache_key)
    if cached:
        return (cached["sold"], cached["available"])

    # Calcular...
    result = {"sold": sold, "available": available}
    self._set_in_cache(cache_key, result)
    return (sold, available)

# DESPUÉS
def get_zone_inventory(self, match_id: str, zone_id: str) -> Tuple[int, int]:
    # Intentar desde cache
    cached = self.cache.get(match_id, zone_id)
    if cached:
        # Cache devuelve lista [sold, available] por JSON serialization
        return tuple(cached) if isinstance(cached, list) else cached

    # Calcular...
    result = (sold, available)
    self.cache.set(match_id, zone_id, result)
    return result
```

**4. Actualizar invalidate_cache**

```python
# ANTES
def invalidate_cache(self, match_id: str, zone_id: Optional[str] = None):
    if zone_id:
        key = self._get_cache_key("zone", match_id, zone_id)
        self.redis_client.delete(key)
    else:
        # Invalidar todas las zonas del match
        pattern = self._get_cache_key("zone", match_id, "*")
        # ... lógica compleja de pattern matching

# DESPUÉS
def invalidate_cache(self, match_id: str, zone_id: Optional[str] = None):
    if zone_id:
        self.cache.invalidate(match_id, zone_id)
    else:
        self.cache.invalidate_match(match_id)
```

**5. Actualizar get_match_inventory**

```python
# DESPUÉS - Nuevo método más eficiente
def get_match_inventory(self, match_id: str, zone_ids: List[str]) -> Dict[str, Tuple[int, int]]:
    """Obtener inventario de múltiples zonas eficientemente."""
    # Batch get desde cache
    cached = self.cache.get_match_inventory(match_id, zone_ids)

    result = {}
    missing_zones = []

    for zone_id in zone_ids:
        if zone_id in cached:
            data = cached[zone_id]
            result[zone_id] = tuple(data) if isinstance(data, list) else data
        else:
            missing_zones.append(zone_id)

    # Obtener zonas faltantes de DB
    for zone_id in missing_zones:
        inventory = self._calculate_zone_inventory(match_id, zone_id)
        result[zone_id] = inventory
        self.cache.set(match_id, zone_id, inventory)

    return result
```

### Cambios en Dependencies

```python
# src/core/dependencies.py

from src.core.cache_strategies import get_inventory_cache

def get_inventory_manager(db: Session = Depends(get_db)):
    """Dependency con cache strategy."""
    return InventoryManager(
        sale_repository=get_sale_repository(db),
        zone_repository=get_zone_repository(db),
        cache_strategy=get_inventory_cache(),  # Usar singleton
    )
```

### Tests a Actualizar

- `tests/unit/services/test_inventory_manager.py`
  - Actualizar mocks para usar InventoryCacheStrategy
  - Verificar que las tuplas se manejan correctamente (JSON → lista)

### Ventajas

- ✅ Elimina ~100 líneas de código de caching manual
- ✅ Mejor manejo de errores
- ✅ Operaciones batch más eficientes
- ✅ Logging consistente con resto del sistema
- ✅ TTL específico para inventario (2 minutos vs 5 actual)

---

## FASE 2: PricingEngine Integration

### Estado Actual

El `PricingEngine` NO usa caching actualmente. Cada llamada a `calculate_match_pricing()` ejecuta:
- Consultas a DB (match, zones, sales)
- Llamadas a ML model
- Cálculos complejos de factores
- Consultas a RulesEngine

**Performance actual:** ~100-200ms por cálculo

### Cambios Propuestos

**1. Inyectar PricingCacheStrategy**

```python
# src/domain/services/pricing_engine.py

from src.core.cache_strategies import PricingCacheStrategy
from src.utils.cache_decorators import cached, invalidate_cache

class PricingEngine:
    def __init__(
        self,
        rules_engine: RulesEngine,
        demand_predictor: DemandPredictor,
        inventory_manager: InventoryManager,
        match_repository: MatchRepository,
        zone_repository: ZoneRepository,
        pricing_repository: PricingHistoryRepository,
        weather_api: WeatherAPI,
        db_session: Session,
        cache_strategy: Optional[PricingCacheStrategy] = None,  # NUEVO
    ):
        # ... existing code ...
        self.cache = cache_strategy or PricingCacheStrategy()
```

**2. Cachear calculate_match_pricing**

```python
def calculate_match_pricing(
    self,
    match: Match,
    zones: List[Zone],
    current_datetime: Optional[datetime] = None,
) -> MatchPricing:
    """Calculate pricing with caching."""

    # Intentar obtener desde cache
    cached_pricing = self.cache.get(match.id)
    if cached_pricing:
        logger.info(f"Cache hit for match pricing: {match.id}")
        # Reconstruir MatchPricing desde dict
        return MatchPricing(**cached_pricing)

    # Cache miss - calcular pricing
    logger.info(f"Cache miss for match pricing: {match.id}, calculating...")

    # ... lógica existente de cálculo ...

    pricing = MatchPricing(
        match_id=match.id,
        zones=zone_pricings,
        # ... resto de campos ...
    )

    # Guardar en cache (como dict para serialización)
    self.cache.set(match.id, pricing.model_dump())

    return pricing
```

**3. Opción alternativa: Usar decorator @cached**

```python
from src.utils.cache_decorators import cached

@cached(ttl=300, key_prefix="pricing")
def calculate_match_pricing(
    self,
    match: Match,
    zones: List[Zone],
    current_datetime: Optional[datetime] = None,
) -> MatchPricing:
    """Calculate pricing - automatically cached."""
    # ... toda la lógica existente sin cambios ...
```

**Nota:** El decorator es más limpio pero requiere que los argumentos sean serializables. Como `Match` y `Zone` son Pydantic models, funcionará bien.

**4. Invalidar cache al guardar histórico**

```python
@invalidate_cache("pricing:match:*")
def save_pricing_to_history(self, pricing: MatchPricing) -> None:
    """Save pricing and invalidate related cache."""
    # ... lógica existente ...

    # Adicionalmente, invalidar cache específico del match
    self.cache.invalidate(pricing.match_id)
```

**5. Método para forzar recálculo**

```python
def recalculate_pricing(
    self,
    match_id: str,
    force: bool = False
) -> MatchPricing:
    """Calculate pricing, optionally forcing cache bypass."""
    if force:
        self.cache.invalidate(match_id)

    match = self.match_repo.get_by_id(match_id)
    zones = self.zone_repo.get_all()
    return self.calculate_match_pricing(match, zones)
```

### Cambios en API Endpoints

```python
# src/api/pricing.py

@router.post("/match/{match_id}/recalculate")
def recalculate_pricing(
    match_id: str,
    force: bool = Query(False, description="Force cache bypass"),
    engine: PricingEngine = Depends(get_pricing_engine),
):
    """Recalculate pricing, optionally forcing cache refresh."""
    pricing = engine.recalculate_pricing(match_id, force=force)
    return pricing
```

### Ventajas

- ✅ Reducción de 100-200ms a <10ms para pricing cacheado
- ✅ Menos carga en DB, ML model, y RulesEngine
- ✅ Cache TTL de 5 minutos apropiado para pricing dinámico
- ✅ Código más limpio si se usa decorator

### Performance Esperada

| Operación | Antes | Después | Mejora |
|-----------|-------|---------|--------|
| Primera llamada | 150ms | 150ms | 0% |
| Llamadas subsecuentes (5 min) | 150ms | <10ms | **15x** |
| Consultas DB por hora | ~240 | ~12 | **95%** |

---

## FASE 3: External APIs Migration

### Servicios Afectados

1. `FootballDataAPI` (src/integrations/football_data.py)
2. `WeatherAPI` (src/integrations/weather_api.py)
3. `GoogleAnalyticsIntegration` (src/integrations/analytics.py)

### Estado Actual

Cada API tiene su propio cache en memoria:
- `self._cache: Dict[str, tuple[datetime, any]] = {}`
- Gestión manual de expiración
- No persistente (se pierde al reiniciar)

### Cambios Propuestos

**1. FootballDataAPI - Migrar a ExternalDataCacheStrategy**

```python
# src/integrations/football_data.py

from src.core.cache_strategies import ExternalDataCacheStrategy

class FootballDataAPI:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.football-data.org/v4",
        cache_strategy: Optional[ExternalDataCacheStrategy] = None,  # NUEVO
    ):
        settings = get_settings()
        self.api_key = api_key or settings.FOOTBALL_DATA_API_KEY
        self.base_url = base_url.rstrip("/")

        # Usar strategy o crear uno
        self.cache = cache_strategy or ExternalDataCacheStrategy()

        # ELIMINAR: self._cache = {}  # Ya no necesario

        # Configuración de rate limiting y retry (mantener)
        # ...
```

**2. Simplificar métodos de cache**

```python
# ANTES
def _get_from_cache(self, cache_key: str) -> Optional[any]:
    if cache_key in self._cache:
        cached_time, cached_data = self._cache[cache_key]
        if datetime.now() < cached_time + timedelta(seconds=self.cache_ttl):
            return cached_data
        else:
            del self._cache[cache_key]
    return None

def _set_in_cache(self, cache_key: str, data: any) -> None:
    self._cache[cache_key] = (datetime.now(), data)

# DESPUÉS - ELIMINAR estos métodos completamente
# Usar directamente: self.cache.get() y self.cache.set()
```

**3. Actualizar get_team_standings**

```python
# ANTES
def get_team_standings(self, league: str, season: str) -> Dict:
    cache_key = f"standings_{league}_{season}"
    cached = self._get_from_cache(cache_key)
    if cached:
        return cached

    # Fetch from API...
    data = self._make_request(...)
    self._set_in_cache(cache_key, data)
    return data

# DESPUÉS
def get_team_standings(self, league: str, season: str) -> Dict:
    cache_key = f"standings:{league}:{season}"

    # Intentar desde cache
    cached = self.cache.get("football_stats", cache_key)
    if cached:
        logger.info(f"Cache hit for standings: {cache_key}")
        return cached

    # Fetch from API...
    logger.info(f"Cache miss for standings: {cache_key}, fetching from API")
    data = self._make_request(...)

    # Guardar en cache (TTL: 6 horas automático para football_stats)
    self.cache.set("football_stats", cache_key, data)
    return data
```

**4. Usar decorator para métodos simples**

```python
from src.utils.cache_decorators import cached

# Opción con decorator
@cached(ttl=21600, key_prefix="external:football_stats")
def get_team_stats(self, team_id: str) -> Dict:
    """Get team statistics - automatically cached for 6 hours."""
    return self._make_request(f"/teams/{team_id}")
```

**5. WeatherAPI - Similar approach**

```python
# src/integrations/weather_api.py

from src.core.cache_strategies import ExternalDataCacheStrategy

class WeatherAPI:
    def __init__(self, cache_strategy: Optional[ExternalDataCacheStrategy] = None):
        self.cache = cache_strategy or ExternalDataCacheStrategy()
        # ...

    def get_forecast(self, lat: float, lon: float, date: datetime) -> Dict:
        cache_key = f"forecast:{lat}:{lon}:{date.date()}"

        cached = self.cache.get("weather", cache_key)
        if cached:
            return cached

        # Fetch from API...
        data = self._fetch_from_api(...)

        # Cache for 1 hour (TTL automático para "weather")
        self.cache.set("weather", cache_key, data)
        return data
```

### Ventajas

- ✅ Cache persistente (sobrevive reinicios)
- ✅ Compartido entre workers
- ✅ TTLs optimizados por tipo de dato
- ✅ Mejor observabilidad (logs consistentes)
- ✅ Eliminación de ~50 líneas de código por API

### Cache TTLs por Fuente

| Fuente | TTL | Justificación |
|--------|-----|---------------|
| football_stats | 6 horas | Estadísticas cambian lentamente |
| standings | 6 horas | Clasificación se actualiza después de partidos |
| weather | 1 hora | Pronósticos cambian frecuentemente |
| transport | 30 min | Condiciones de tráfico variables |
| analytics | 30 min | Métricas se actualizan regularmente |

---

## FASE 4: RulesEngine Optimization

### Estado Actual

El `RulesEngine` NO cachea multiplicadores calculados dinámicamente, especialmente:
- `_get_team_position()` - Hace llamadas a FootballDataAPI
- Cálculo de rival multipliers basado en posición

### Cambios Propuestos

**1. Cachear posiciones de equipos**

```python
# src/domain/services/rules_engine.py

from src.utils.cache_decorators import cached

class RulesEngine:

    @cached(ttl=21600, key_prefix="rules:team_position")  # 6 horas
    def _get_team_position(self, team_name: str) -> Optional[int]:
        """Get team position with caching."""
        # ... lógica existente sin cambios ...
```

**2. Cachear rival multipliers calculados**

```python
@cached(ttl=3600, key_prefix="rules:rival_multiplier")  # 1 hora
def get_rival_multiplier(self, rival_team: str) -> float:
    """Get rival multiplier with caching."""
    # ... lógica existente sin cambios ...
```

### Ventajas

- ✅ Reduce llamadas a FootballDataAPI
- ✅ Mejor performance en cálculos de pricing
- ✅ Implementación trivial con decorators

---

## FASE 5: DemandPredictor Caching

### Estado Actual

El `DemandPredictor` ejecuta el modelo ML en cada llamada, sin caching.

### Cambios Propuestos

**1. Cachear predicciones ML**

```python
# src/domain/services/demand_predictor.py

from src.utils.cache_decorators import cached

class DemandPredictor:

    @cached(ttl=1800, key_prefix="ml:demand_prediction")  # 30 minutos
    def predict_demand(
        self,
        match: Match,
        zone: Zone,
        days_to_match: int
    ) -> float:
        """Predict demand with caching."""
        # ... lógica existente sin cambios ...
```

**Nota:** Las predicciones cambian con `days_to_match`, así que el cache se invalida automáticamente conforme pasa el tiempo.

### Ventajas

- ✅ Reduce carga computacional del modelo ML
- ✅ Mejora latencia de pricing engine
- ✅ Cache se auto-invalida por cambio de días

---

## Orden de Implementación Recomendado

### Sprint 1 (Prioridad Alta - Impacto Inmediato)

1. **Día 1-2: InventoryManager Migration**
   - Migrar a InventoryCacheStrategy
   - Actualizar tests
   - Desplegar y monitorear

2. **Día 3-4: PricingEngine Integration**
   - Añadir PricingCacheStrategy
   - Usar decorators donde sea apropiado
   - Actualizar API endpoints
   - Tests exhaustivos

3. **Día 5: FootballDataAPI Migration**
   - Migrar a ExternalDataCacheStrategy
   - Simplificar código
   - Verificar TTLs apropiados

### Sprint 2 (Prioridad Media - Optimizaciones)

4. **Día 1: WeatherAPI Migration**
   - Similar a FootballDataAPI
   - Verificar integración

5. **Día 2: RulesEngine Optimization**
   - Añadir decorators @cached
   - Monitorear reducción en llamadas externas

6. **Día 3: DemandPredictor Caching**
   - Añadir caching de predicciones
   - Medir impacto en performance

7. **Día 4-5: Testing & Monitoring**
   - Tests de integración completos
   - Configurar métricas de cache hit/miss
   - Documentación

---

## Checklist de Implementación

### Para Cada Servicio

- [ ] Identificar métodos que se beneficiarían de caching
- [ ] Elegir estrategia apropiada (Pricing, Inventory, ExternalData)
- [ ] Determinar TTL apropiado
- [ ] Actualizar constructor para inyectar cache strategy
- [ ] Migrar métodos de caching manual a strategy
- [ ] Añadir decorators donde sea apropiado
- [ ] Actualizar tests unitarios
- [ ] Actualizar dependency injection
- [ ] Añadir tests de integración
- [ ] Actualizar documentación
- [ ] Desplegar y monitorear métricas

### Validación

- [ ] Tests unitarios pasan (>80% coverage)
- [ ] Tests de integración pasan
- [ ] Performance tests muestran mejora
- [ ] Cache hit ratio > 70% después de warm-up
- [ ] No hay degradación en funcionalidad
- [ ] Logs muestran cache hits/misses correctamente
- [ ] Métricas de monitoreo configuradas

---

## Cambios en Dependencies (Global)

```python
# src/core/dependencies.py

from src.core.cache_strategies import (
    get_pricing_cache,
    get_inventory_cache,
    get_external_data_cache,
)

def get_inventory_manager(db: Session = Depends(get_db)):
    """Updated with cache strategy."""
    return InventoryManager(
        sale_repository=get_sale_repository(db),
        zone_repository=get_zone_repository(db),
        cache_strategy=get_inventory_cache(),
    )

def get_pricing_engine(db: Session = Depends(get_db)):
    """Updated with cache strategy."""
    return PricingEngine(
        rules_engine=get_rules_engine(db),
        demand_predictor=get_demand_predictor(),
        inventory_manager=get_inventory_manager(db),
        match_repository=get_match_repository(db),
        zone_repository=get_zone_repository(db),
        pricing_repository=get_pricing_repository(db),
        weather_api=get_weather_api(),
        db_session=db,
        cache_strategy=get_pricing_cache(),  # NUEVO
    )

@lru_cache()
def get_football_api():
    """Updated with cache strategy."""
    return FootballDataAPI(
        cache_strategy=get_external_data_cache(),  # NUEVO
    )

@lru_cache()
def get_weather_api():
    """Updated with cache strategy."""
    return WeatherAPI(
        cache_strategy=get_external_data_cache(),  # NUEVO
    )
```

---

## Métricas de Éxito

### Objetivos Cuantitativos

| Métrica | Baseline | Target | Método de Medición |
|---------|----------|--------|-------------------|
| Cache Hit Ratio | 0% | >70% | Prometheus counter |
| Pricing API Latency (p95) | 150ms | <50ms | APM/Prometheus histogram |
| DB Query Count/hour | ~1000 | <300 | DB slow query log |
| External API Calls/day | ~5000 | <500 | API provider dashboard |
| Redis Memory Usage | N/A | <500MB | Redis INFO |

### Monitoreo

```python
# Añadir a src/utils/metrics.py (Fase 12)

from prometheus_client import Counter, Histogram

cache_hits = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['strategy']
)

cache_misses = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['strategy']
)

cache_operation_duration = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation duration',
    ['operation', 'strategy']
)
```

---

## Riesgos y Mitigaciones

### Riesgo 1: Cache Stampede

**Descripción:** Múltiples requests simultáneos recalculan el mismo valor cuando expira.

**Mitigación:**
- Implementar distributed lock (Fase futura)
- Por ahora, TTLs suficientemente largos mitigan el riesgo
- Monitorear patrones de cache miss

### Riesgo 2: Stale Data

**Descripción:** Cache retorna datos desactualizados.

**Mitigación:**
- TTLs apropiados por tipo de dato
- Invalidación explícita en operaciones de escritura
- Decorators `@invalidate_cache` en updates
- Endpoint de admin para forzar invalidación

### Riesgo 3: Memory Pressure

**Descripción:** Redis consume demasiada memoria.

**Mitigación:**
- Configurar maxmemory-policy en Redis (allkeys-lru)
- Monitorear memoria con alertas
- TTLs conservadores inicialmente
- Ajustar basado en métricas

### Riesgo 4: Serialization Issues

**Descripción:** Objetos complejos no se serializan correctamente.

**Mitigación:**
- Usar Pydantic `model_dump()` para objetos complejos
- JSON serializer por defecto es seguro
- Tests exhaustivos de serialización
- Documentar limitaciones

---

## Rollback Plan

Si se detectan problemas después del despliegue:

### Nivel 1: Deshabilitar Cache Específico

```python
# Temporalmente deshabilitar caching sin revert de código
# En settings o variables de entorno:
CACHE_ENABLED = False

# En cada servicio:
if settings.CACHE_ENABLED:
    cached_value = self.cache.get(...)
else:
    cached_value = None  # Force cache miss
```

### Nivel 2: Revert a Versión Anterior

- Git revert del commit de integración
- Redesplegar versión anterior
- Investigar issue en ambiente de desarrollo

### Nivel 3: Hotfix

- Identificar servicio problemático
- Revert solo ese servicio a caching manual
- Fix y redeploy gradual

---

## Testing Strategy

### Tests Unitarios

Cada servicio migrado debe tener tests que verifiquen:

```python
def test_pricing_engine_uses_cache():
    """Verificar que pricing engine usa cache correctamente."""
    mock_cache = Mock(spec=PricingCacheStrategy)
    mock_cache.get.return_value = {"match_id": "123", ...}

    engine = PricingEngine(..., cache_strategy=mock_cache)
    result = engine.calculate_match_pricing(match, zones)

    # Verificar que se consultó cache
    mock_cache.get.assert_called_once_with("123")

def test_pricing_engine_cache_miss():
    """Verificar comportamiento en cache miss."""
    mock_cache = Mock(spec=PricingCacheStrategy)
    mock_cache.get.return_value = None  # Cache miss

    engine = PricingEngine(..., cache_strategy=mock_cache)
    result = engine.calculate_match_pricing(match, zones)

    # Verificar que se guardó en cache
    mock_cache.set.assert_called_once()
```

### Tests de Integración

```python
def test_pricing_api_cache_integration():
    """Test end-to-end de caching en API."""
    # Primera llamada - cache miss
    response1 = client.get("/api/v1/pricing/match/123")
    assert response1.status_code == 200
    time1 = response1.elapsed.total_seconds()

    # Segunda llamada - cache hit
    response2 = client.get("/api/v1/pricing/match/123")
    assert response2.status_code == 200
    time2 = response2.elapsed.total_seconds()

    # Verificar que es más rápido
    assert time2 < time1 * 0.5  # Al menos 50% más rápido

    # Verificar mismo resultado
    assert response1.json() == response2.json()
```

### Performance Tests

```python
import pytest
from time import time

@pytest.mark.performance
def test_pricing_engine_performance_with_cache():
    """Verificar mejora de performance con cache."""
    engine = PricingEngine(...)  # Con cache real

    # Warm up cache
    engine.calculate_match_pricing(match, zones)

    # Medir 100 llamadas con cache
    start = time()
    for _ in range(100):
        engine.calculate_match_pricing(match, zones)
    duration_cached = time() - start

    # Limpiar cache
    cache.invalidate_all()

    # Medir 100 llamadas sin cache
    start = time()
    for _ in range(100):
        engine.calculate_match_pricing(match, zones)
    duration_uncached = time() - start

    # Cache debe ser al menos 10x más rápido
    assert duration_cached < duration_uncached * 0.1
```

---

## Documentación a Actualizar

1. **API Documentation** (`docs/API.md`)
   - Añadir sección sobre caching behavior
   - Documentar headers de cache (si se implementan)
   - Explicar force refresh en endpoints

2. **Service Documentation**
   - Actualizar docstrings con comportamiento de cache
   - Documentar TTLs utilizados
   - Ejemplos de invalidación

3. **Deployment Guide** (`docs/DEPLOYMENT.md`)
   - Requisitos de Redis
   - Configuración de cache
   - Monitoreo de cache

4. **Troubleshooting Guide**
   - Cómo identificar problemas de cache
   - Cómo invalidar cache manualmente
   - Cómo deshabilitar cache temporalmente

---

## Ejemplo Completo: InventoryManager ANTES/DESPUÉS

### ANTES (líneas de código: ~200)

```python
class InventoryManager:
    def __init__(self, sale_repository, zone_repository, redis_client, cache_ttl=300):
        self.sale_repo = sale_repository
        self.zone_repo = zone_repository
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl

    def _get_cache_key(self, prefix: str, *args) -> str:
        return f"inventory:{prefix}:" + ":".join(str(arg) for arg in args)

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        try:
            cached = self.redis_client.get(key)
            if cached:
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(cached)
            logger.debug(f"Cache miss for key: {key}")
            return None
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
            return None

    def _set_in_cache(self, key: str, value: Dict, ttl: Optional[int] = None):
        try:
            ttl = ttl or self.cache_ttl
            self.redis_client.setex(key, ttl, json.dumps(value))
            logger.debug(f"Cached key: {key} with TTL: {ttl}s")
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")

    def get_zone_inventory(self, match_id: str, zone_id: str) -> Tuple[int, int]:
        cache_key = self._get_cache_key("zone", match_id, zone_id)
        cached = self._get_from_cache(cache_key)
        if cached:
            return (cached["sold"], cached["available"])

        # Calculate...
        zone = self.zone_repo.get_by_id(zone_id)
        sold = self.sale_repo.get_total_sold(match_id, zone_id)
        available = zone.capacity - sold

        result = {"sold": sold, "available": available}
        self._set_in_cache(cache_key, result)
        return (sold, available)
```

### DESPUÉS (líneas de código: ~120, -40% código)

```python
from src.core.cache_strategies import InventoryCacheStrategy

class InventoryManager:
    def __init__(
        self,
        sale_repository: SaleRepository,
        zone_repository: ZoneRepository,
        cache_strategy: Optional[InventoryCacheStrategy] = None,
    ):
        self.sale_repo = sale_repository
        self.zone_repo = zone_repository
        self.cache = cache_strategy or InventoryCacheStrategy()

    def get_zone_inventory(self, match_id: str, zone_id: str) -> Tuple[int, int]:
        # Try cache
        cached = self.cache.get(match_id, zone_id)
        if cached:
            return tuple(cached) if isinstance(cached, list) else cached

        # Calculate...
        zone = self.zone_repo.get_by_id(zone_id)
        sold = self.sale_repo.get_total_sold(match_id, zone_id)
        available = zone.capacity - sold

        result = (sold, available)
        self.cache.set(match_id, zone_id, result)
        return result

    def invalidate_cache(self, match_id: str, zone_id: Optional[str] = None):
        """Invalidate cache for match or specific zone."""
        if zone_id:
            self.cache.invalidate(match_id, zone_id)
        else:
            self.cache.invalidate_match(match_id)
```

**Mejoras:**
- ✅ -80 líneas de código (40% reducción)
- ✅ Eliminados 3 métodos helper (_get_cache_key, _get_from_cache, _set_in_cache)
- ✅ Mejor manejo de errores (delegado a CacheService)
- ✅ Logging consistente
- ✅ TTL optimizado (2 min vs 5 min)
- ✅ Operaciones batch disponibles

---

## Conclusión

Este plan proporciona una ruta clara para integrar la nueva capa de caching en todos los servicios existentes. La implementación es gradual, retrocompatible, y con rollback plan claro.

**Resultado esperado:**
- 70-80% reducción en queries de DB
- 90%+ reducción en llamadas a APIs externas
- 10-20x mejora en latencia para operaciones cacheadas
- Código más limpio y mantenible
- Mejor observabilidad

**Próximos pasos:**
1. Revisar y aprobar este plan
2. Crear issues/tickets para cada fase
3. Implementar Sprint 1 (InventoryManager, PricingEngine, FootballDataAPI)
4. Monitorear métricas
5. Iterar basado en resultados

---

**Versión:** 1.0
**Autor:** Claude Code
**Fecha:** 2025-12-14
