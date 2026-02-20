# Plan de Integración de Métricas

**Fecha**: 2025-12-14
**Objetivo**: Instrumentar toda la aplicación con el sistema de métricas de Prometheus

## Estado Actual

✅ **Completado**:
- Sistema de métricas (`src/utils/metrics.py`)
- Middleware de FastAPI para métricas automáticas de API
- Configuración de Prometheus y Grafana
- Dashboards y alertas
- Tests del sistema de métricas

⚠️ **Pendiente**:
- Instrumentación de servicios de dominio
- Instrumentación de repositorios
- Instrumentación de workers
- Instrumentación de integraciones externas
- Instrumentación de cache
- Instrumentación de ML

---

## Fases de Integración

### FASE 1: Pricing Engine (CRÍTICO) ⭐⭐⭐

**Archivo**: `src/domain/services/pricing_engine.py`

**Métricas a Integrar**:

1. **Contador de cálculos**:
   ```python
   from src.utils.metrics import pricing_calculations_total

   # En calculate_match_pricing()
   pricing_calculations_total.labels(
       match_id=match.id,
       calculation_type="full"
   ).inc()
   ```

2. **Duración de cálculos**:
   ```python
   from src.utils.metrics import MetricsContext, pricing_calculation_duration_seconds

   # Envolver el cálculo completo
   with MetricsContext(pricing_calculation_duration_seconds, {"calculation_type": "full"}):
       # ... código de cálculo
   ```

3. **Cambios de precio**:
   ```python
   from src.utils.metrics import record_price_change

   # En _calculate_zone_price() cuando cambia el precio
   if should_update:
       record_price_change(match_id, zone_id, old_price, new_price)
   ```

4. **Active matches gauge**:
   ```python
   from src.utils.metrics import active_matches

   # Actualizar al calcular pricing para partidos activos
   active_matches.set(len(active_match_ids))
   ```

**Cambios Requeridos**:
- [ ] Añadir imports de métricas
- [ ] Instrumentar `calculate_match_pricing()`
- [ ] Instrumentar `_calculate_zone_price()`
- [ ] Instrumentar `_calculate_pricing_factors()`
- [ ] Actualizar gauge de active_matches
- [ ] Registrar cambios de precio

**Ubicaciones Específicas**:
```python
# Línea ~80: En calculate_match_pricing()
pricing_calculations_total.labels(match_id=match.id, calculation_type="full").inc()

with MetricsContext(pricing_calculation_duration_seconds, {"calculation_type": "full"}):
    for zone in zones:
        zone_pricing = self._calculate_zone_price(match, zone, current_datetime)
        # ...

# Línea ~150: En _calculate_zone_price()
with MetricsContext(pricing_calculation_duration_seconds, {"calculation_type": "zone"}):
    factors = self._calculate_pricing_factors(match, zone, current_datetime)
    # ...
```

---

### FASE 2: Demand Predictor (ML) ⭐⭐⭐

**Archivo**: `src/domain/services/demand_predictor.py`

**Métricas a Integrar**:

1. **Contador de predicciones**:
   ```python
   from src.utils.metrics import ml_predictions_total

   ml_predictions_total.labels(
       model_name="demand_model",
       prediction_type="demand_score"
   ).inc()
   ```

2. **Duración de predicciones**:
   ```python
   from src.utils.metrics import ml_prediction_duration_seconds, MetricsContext

   with MetricsContext(ml_prediction_duration_seconds, {"model_name": "demand_model"}):
       prediction = self.model.predict(features)
   ```

3. **Accuracy del modelo**:
   ```python
   from src.utils.metrics import ml_model_accuracy

   # Actualizar cuando se evalúa el modelo
   ml_model_accuracy.labels(model_name="demand_model", metric="r2_score").set(r2)
   ml_model_accuracy.labels(model_name="demand_model", metric="mae").set(mae)
   ```

**Cambios Requeridos**:
- [ ] Instrumentar `predict_demand()`
- [ ] Instrumentar `_extract_features()`
- [ ] Actualizar accuracy gauge al cargar modelo
- [ ] Registrar cuando se usa fallback

**Ubicaciones Específicas**:
```python
# Línea ~60: En predict_demand()
ml_predictions_total.labels(model_name="demand_model", prediction_type="demand_score").inc()

with MetricsContext(ml_prediction_duration_seconds, {"model_name": "demand_model"}):
    if self.model is not None:
        prediction = self.model.predict(features_df)
    else:
        # Fallback
        prediction = self._fallback_prediction(match, zone, days_to_match)
```

---

### FASE 3: Inventory Manager ⭐⭐

**Archivo**: `src/domain/services/inventory_manager.py`

**Métricas a Integrar**:

1. **Zone occupancy**:
   ```python
   from src.utils.metrics import zone_occupancy_percent

   # En get_zone_inventory()
   occupancy = (sold / total) * 100
   zone_occupancy_percent.labels(match_id=match_id, zone_id=zone_id).set(occupancy)
   ```

2. **Sales velocity**:
   ```python
   from src.utils.metrics import sales_velocity

   # En get_sales_velocity()
   velocity = tickets_sold / hours
   sales_velocity.labels(match_id=match_id, zone_id=zone_id).set(velocity)
   ```

**Cambios Requeridos**:
- [ ] Instrumentar `get_zone_inventory()`
- [ ] Instrumentar `get_sales_velocity()`
- [ ] Actualizar gauge de occupancy
- [ ] Actualizar gauge de sales velocity

**Ubicaciones Específicas**:
```python
# Línea ~40: En get_zone_inventory()
sold, available = self._calculate_inventory(match_id, zone_id)
occupancy = (sold / (sold + available)) * 100 if (sold + available) > 0 else 0
zone_occupancy_percent.labels(match_id=match_id, zone_id=zone_id).set(occupancy)

# Línea ~80: En get_sales_velocity()
velocity = tickets_sold / hours if hours > 0 else 0
sales_velocity.labels(match_id=match_id, zone_id=zone_id).set(velocity)
```

---

### FASE 4: Cache Strategies ⭐⭐

**Archivos**:
- `src/core/cache_service.py`
- `src/core/cache_strategies.py`

**Métricas a Integrar**:

1. **Cache operations**:
   ```python
   from src.utils.metrics import cache_operations_total, cache_operation_duration_seconds

   # En cada operación de cache
   cache_operations_total.labels(operation="get", result="hit").inc()
   cache_operations_total.labels(operation="get", result="miss").inc()

   with MetricsContext(cache_operation_duration_seconds, {"operation": "get"}):
       value = self._get_from_cache(key)
   ```

2. **Cache hit ratio**:
   ```python
   from src.utils.metrics import update_cache_metrics

   # Periódicamente o en cada operación
   update_cache_metrics(hits=self.hits, misses=self.misses)
   ```

3. **Cached prices gauge**:
   ```python
   from src.utils.metrics import cached_prices

   # Al cachear precios
   cached_prices.set(len(cached_pricing_keys))
   ```

**Cambios Requeridos**:
- [ ] Instrumentar `CacheService.get()`
- [ ] Instrumentar `CacheService.set()`
- [ ] Instrumentar `CacheService.delete()`
- [ ] Añadir contador de hits/misses
- [ ] Actualizar cache_hit_ratio periódicamente
- [ ] Actualizar cached_prices gauge

**Ubicaciones Específicas**:
```python
# En CacheService.get()
start_time = time.time()
result = self.redis.get(key)
duration = time.time() - start_time

cache_operation_duration_seconds.labels(operation="get").observe(duration)

if result is not None:
    cache_operations_total.labels(operation="get", result="hit").inc()
    self._hits += 1
else:
    cache_operations_total.labels(operation="get", result="miss").inc()
    self._misses += 1

# Actualizar ratio periódicamente
update_cache_metrics(self._hits, self._misses)
```

---

### FASE 5: External Integrations ⭐⭐

**Archivos**:
- `src/integrations/football_data.py`
- `src/integrations/weather_api.py`
- `src/integrations/analytics.py`
- `src/integrations/ticketing_system.py`

**Métricas a Integrar**:

1. **API calls counter**:
   ```python
   from src.utils.metrics import external_api_calls_total

   external_api_calls_total.labels(
       service="football_data",
       endpoint="/standings",
       status="200"
   ).inc()
   ```

2. **API duration**:
   ```python
   from src.utils.metrics import external_api_duration_seconds, MetricsContext

   with MetricsContext(external_api_duration_seconds, {
       "service": "football_data",
       "endpoint": "/standings"
   }):
       response = httpx.get(url)
   ```

3. **API errors**:
   ```python
   from src.utils.metrics import external_api_errors_total

   external_api_errors_total.labels(
       service="football_data",
       error_type="timeout"
   ).inc()
   ```

4. **Rate limit hits**:
   ```python
   from src.utils.metrics import external_api_rate_limit_hits

   if response.status_code == 429:
       external_api_rate_limit_hits.labels(service="football_data").inc()
   ```

**Cambios Requeridos**:
- [ ] Instrumentar `FootballDataAPI` (todos los métodos)
- [ ] Instrumentar `WeatherAPI` (todos los métodos)
- [ ] Instrumentar `GoogleAnalyticsIntegration` (todos los métodos)
- [ ] Instrumentar `TicketingSystemAPI` (todos los métodos)
- [ ] Registrar errores y rate limits

**Ubicaciones Específicas**:
```python
# En FootballDataAPI._make_request()
with MetricsContext(external_api_duration_seconds, {
    "service": "football_data",
    "endpoint": endpoint
}):
    try:
        response = httpx.get(url, headers=headers, timeout=30)

        external_api_calls_total.labels(
            service="football_data",
            endpoint=endpoint,
            status=str(response.status_code)
        ).inc()

        if response.status_code == 429:
            external_api_rate_limit_hits.labels(service="football_data").inc()

        response.raise_for_status()
        return response.json()

    except httpx.TimeoutException:
        external_api_errors_total.labels(
            service="football_data",
            error_type="timeout"
        ).inc()
        raise
    except Exception as e:
        external_api_errors_total.labels(
            service="football_data",
            error_type=type(e).__name__
        ).inc()
        raise
```

---

### FASE 6: Database Repositories ⭐⭐

**Archivos**:
- `src/domain/repositories/*.py` (todos los repositorios)

**Métricas a Integrar**:

1. **DB operations counter**:
   ```python
   from src.utils.metrics import db_operations_total

   db_operations_total.labels(operation="select", table="matches").inc()
   ```

2. **DB operation duration**:
   ```python
   from src.utils.metrics import db_operation_duration_seconds, MetricsContext

   with MetricsContext(db_operation_duration_seconds, {
       "operation": "select",
       "table": "matches"
   }):
       results = db.query(MatchDB).filter(...).all()
   ```

3. **DB errors**:
   ```python
   from src.utils.metrics import db_errors_total

   except SQLAlchemyError as e:
       db_errors_total.labels(
           operation="insert",
           error_type=type(e).__name__
       ).inc()
       raise
   ```

4. **Active connections** (si es posible):
   ```python
   from src.utils.metrics import db_connections_active

   db_connections_active.set(engine.pool.checkedout())
   ```

**Cambios Requeridos**:
- [ ] Crear decorador `@track_db_operation` para métodos de repositorio
- [ ] Instrumentar BaseRepository (si existe)
- [ ] O instrumentar cada repositorio individualmente
- [ ] Registrar errores de DB

**Implementación Sugerida**:
```python
# En src/utils/metrics.py - añadir nuevo decorador
def track_db_operation(table: str, operation: str):
    """Decorator para trackear operaciones de DB."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            db_operations_total.labels(operation=operation, table=table).inc()

            with MetricsContext(db_operation_duration_seconds, {
                "operation": operation,
                "table": table
            }):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    db_errors_total.labels(
                        operation=operation,
                        error_type=type(e).__name__
                    ).inc()
                    raise
        return wrapper
    return decorator

# Uso en repositorio:
@track_db_operation(table="matches", operation="select")
def get_by_id(self, match_id: str):
    return self.db.query(MatchDB).filter_by(id=match_id).first()
```

---

### FASE 7: Workers ⭐⭐⭐

**Archivos**:
- `src/workers/price_updater.py`
- `src/workers/data_collector.py`
- `src/workers/model_retrainer.py`

**Métricas a Integrar**:

1. **Worker task counter**:
   ```python
   from src.utils.metrics import worker_tasks_total

   worker_tasks_total.labels(worker_name="price_updater", status="success").inc()
   worker_tasks_total.labels(worker_name="price_updater", status="failed").inc()
   ```

2. **Worker task duration**:
   ```python
   from src.utils.metrics import worker_task_duration_seconds, MetricsContext

   with MetricsContext(worker_task_duration_seconds, {"worker_name": "price_updater"}):
       self._update_prices()
   ```

3. **Worker errors**:
   ```python
   from src.utils.metrics import worker_errors_total

   worker_errors_total.labels(
       worker_name="price_updater",
       error_type="DatabaseError"
   ).inc()
   ```

4. **Last run timestamp**:
   ```python
   from src.utils.metrics import worker_last_run_timestamp
   import time

   worker_last_run_timestamp.labels(worker_name="price_updater").set(time.time())
   ```

**Cambios Requeridos**:
- [ ] Instrumentar `PriceUpdaterWorker.run()`
- [ ] Instrumentar `DataCollectorWorker.run()`
- [ ] Instrumentar `ModelRetrainerWorker.run()`
- [ ] Actualizar timestamp en cada ejecución
- [ ] Registrar éxitos y fallos

**Ubicaciones Específicas**:
```python
# En PriceUpdaterWorker.run()
def run(self):
    while not self.should_stop:
        worker_last_run_timestamp.labels(worker_name="price_updater").set(time.time())

        with MetricsContext(worker_task_duration_seconds, {"worker_name": "price_updater"}):
            try:
                matches_updated = self._update_prices()
                worker_tasks_total.labels(
                    worker_name="price_updater",
                    status="success"
                ).inc()

            except Exception as e:
                worker_errors_total.labels(
                    worker_name="price_updater",
                    error_type=type(e).__name__
                ).inc()
                worker_tasks_total.labels(
                    worker_name="price_updater",
                    status="failed"
                ).inc()
                self.logger.error(f"Error in worker: {e}", exc_info=True)

        time.sleep(self.interval)
```

---

### FASE 8: Business Events ⭐⭐⭐

**Ubicaciones**: Donde se registren ventas o eventos de negocio

**Métricas a Integrar**:

1. **Ticket sales**:
   ```python
   from src.utils.metrics import record_ticket_sale

   # Cuando se confirma una venta
   record_ticket_sale(
       match_id="match-123",
       zone_id="zone-vip",
       customer_type="member",
       quantity=2,
       total_amount=150.0
   )
   ```

2. **Average ticket price**:
   ```python
   from src.utils.metrics import average_ticket_price

   avg_price = total_revenue / total_tickets
   average_ticket_price.labels(zone_id=zone_id).set(avg_price)
   ```

3. **Demand score**:
   ```python
   from src.utils.metrics import demand_score

   demand_score.labels(match_id=match_id, zone_id=zone_id).set(score)
   ```

**Cambios Requeridos**:
- [ ] Identificar dónde se registran ventas (probablemente en sales_simulator o ticketing integration)
- [ ] Instrumentar eventos de venta
- [ ] Calcular y actualizar average ticket price
- [ ] Actualizar demand score desde DemandPredictor

**Ubicaciones Potenciales**:
- `src/integrations/ticketing_system.py` - método `confirm_purchase()`
- `src/api/sales_simulator.py` - cuando se simula una venta
- Cualquier endpoint que registre ventas

---

## Orden de Implementación Recomendado

### Sprint 1: Core Business Metrics (Más Valor Inmediato)
1. ✅ Fase 1: Pricing Engine - **CRÍTICO**
2. ✅ Fase 3: Inventory Manager - **ALTO VALOR**
3. ✅ Fase 8: Business Events - **ALTO VALOR**

### Sprint 2: Technical Metrics
4. ✅ Fase 2: Demand Predictor (ML)
5. ✅ Fase 7: Workers
6. ✅ Fase 4: Cache Strategies

### Sprint 3: Infrastructure Metrics
7. ✅ Fase 5: External Integrations
8. ✅ Fase 6: Database Repositories

---

## Patrón de Implementación Consistente

Para cada servicio/componente:

1. **Añadir imports al inicio del archivo**:
   ```python
   from src.utils.metrics import (
       MetricsContext,
       pricing_calculations_total,
       pricing_calculation_duration_seconds,
       # ... otras métricas necesarias
   )
   ```

2. **Instrumentar método principal con context manager**:
   ```python
   with MetricsContext(metric_duration, {"label": "value"}):
       # código existente
   ```

3. **Incrementar contadores en eventos clave**:
   ```python
   metric_counter.labels(key1="value1", key2="value2").inc()
   ```

4. **Actualizar gauges con valores actuales**:
   ```python
   metric_gauge.labels(key="value").set(current_value)
   ```

5. **Registrar errores**:
   ```python
   except Exception as e:
       error_metric.labels(error_type=type(e).__name__).inc()
       raise
   ```

---

## Validación Post-Integración

Para cada fase completada:

### 1. Verificar Métricas en Prometheus
```bash
# Acceder a Prometheus
open http://localhost:9090

# Queries de ejemplo:
pricing_calculations_total
rate(pricing_calculations_total[5m])
pricing_calculation_duration_seconds
```

### 2. Verificar Dashboards en Grafana
```bash
# Acceder a Grafana
open http://localhost:3001

# Verificar que los paneles muestran datos
```

### 3. Tests de Integración
Crear tests que:
- Ejecuten operaciones
- Verifiquen que las métricas se incrementan
- Validen los valores de las métricas

Ejemplo:
```python
def test_pricing_calculation_increments_metrics():
    initial_count = pricing_calculations_total._value.get()

    # Ejecutar cálculo
    pricing_engine.calculate_match_pricing(match, zones)

    # Verificar incremento
    new_count = pricing_calculations_total._value.get()
    assert new_count > initial_count
```

---

## Checklist de Integración

### Antes de Empezar
- [ ] Revisar este plan completo
- [ ] Priorizar fases según necesidades
- [ ] Configurar entorno de desarrollo con Prometheus/Grafana

### Durante la Implementación
- [ ] Seguir patrón consistente
- [ ] Añadir métricas sin romper funcionalidad existente
- [ ] Testear cada integración
- [ ] Verificar que las métricas aparecen en Prometheus

### Después de Cada Fase
- [ ] Ejecutar tests
- [ ] Verificar dashboards
- [ ] Documentar métricas añadidas
- [ ] Commit con mensaje descriptivo

### Al Finalizar Todo
- [ ] Ejecutar suite completa de tests
- [ ] Validar todos los dashboards
- [ ] Verificar todas las alertas
- [ ] Actualizar documentación
- [ ] Performance test para verificar overhead mínimo

---

## Notas Importantes

1. **Overhead de Performance**: Las métricas añaden ~1ms por operación. Esto es aceptable.

2. **Cardinalidad de Labels**: Evitar labels de alta cardinalidad (ej: no usar user_id directamente)

3. **Nombres Consistentes**: Seguir convenciones de nomenclatura de Prometheus

4. **Documentación**: Documentar cada métrica añadida en PHASE_12_COMPLETION.md

5. **Testing**: Cada integración debe tener tests que verifiquen las métricas

6. **Rollback**: Si una métrica causa problemas, se puede comentar temporalmente

---

## Recursos de Referencia

- **Prometheus Best Practices**: https://prometheus.io/docs/practices/naming/
- **Métricas Existentes**: `src/utils/metrics.py`
- **Dashboards**: `docker/grafana/provisioning/dashboards/json/`
- **Tests de Ejemplo**: `tests/unit/utils/test_metrics.py`

---

**Última Actualización**: 2025-12-14
**Estado**: Plan Listo para Implementación
**Prioridad**: Alta - Maximiza el valor del sistema de observabilidad
