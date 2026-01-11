# Arquitectura del Sistema - Smart Pricing

## Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Principios de Diseño](#principios-de-diseño)
3. [Arquitectura de Capas](#arquitectura-de-capas)
4. [Componentes Principales](#componentes-principales)
5. [Flujo de Datos](#flujo-de-datos)
6. [Estrategia de Caching](#estrategia-de-caching)
7. [Patrones de Diseño](#patrones-de-diseño)
8. [Escalabilidad y Performance](#escalabilidad-y-performance)

## Visión General

Smart Pricing es un sistema de pricing dinámico para estadios de fútbol que utiliza Machine Learning, análisis de demanda en tiempo real y reglas de negocio configurables para optimizar los precios de entradas.

### Stack Tecnológico

```yaml
Backend:
  Framework: FastAPI (Python 3.11+)
  ORM: SQLAlchemy 2.0
  Validation: Pydantic V2

Datos:
  Database: PostgreSQL 15+
  Cache: Redis 7+

Machine Learning:
  Frameworks: scikit-learn, XGBoost
  Data Processing: pandas, numpy

Infraestructura:
  Containerization: Docker + Docker Compose
  Monitoring: Prometheus + Grafana
  Logging: JSON estructurado
```

## Principios de Diseño

### 1. Configuración sobre Código
- Todas las reglas de negocio en archivos YAML
- Multiplicadores y factores configurables sin cambios de código
- Hot-reloading de configuración sin reinicio del sistema

### 2. Separation of Concerns
```
API Layer          → Endpoints, validación de entrada
Domain Layer       → Lógica de negocio, modelos
Repository Layer   → Acceso a datos
Infrastructure     → Redis, PostgreSQL, logging
```

### 3. Dependency Injection
- Todas las dependencias inyectadas explícitamente
- Facilita testing con mocks
- Configuración centralizada en `core/dependencies.py`

### 4. API-First Design
- Diseño de endpoints antes de implementación
- Documentación automática con OpenAPI/Swagger
- Versionado de API (v1)

### 5. Idempotencia
- Operaciones de pricing reproducibles
- Cálculos determinísticos dado el mismo input
- Auditoría completa de cambios de precio

### 6. Observabilidad
- Logs estructurados JSON con contexto
- Métricas Prometheus en todos los endpoints
- Health checks para monitoreo

## Arquitectura de Capas

```
┌─────────────────────────────────────────────────────────────┐
│                     API LAYER (FastAPI)                     │
│  /api/v1/pricing  │  /api/v1/admin  │  /api/v1/analytics  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER (Services)                  │
│  PricingEngine  │  RulesEngine  │  DemandPredictor  │       │
│  InventoryManager  │  FootballDataAPI                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 REPOSITORY LAYER (Data Access)              │
│  MatchRepository  │  ZoneRepository  │  SaleRepository      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              INFRASTRUCTURE LAYER (Persistence)             │
│        PostgreSQL  │  Redis  │  External APIs               │
└─────────────────────────────────────────────────────────────┘
```

## Componentes Principales

### 1. PricingEngine (Motor de Pricing)

**Ubicación:** `src/domain/services/pricing_engine.py`

**Responsabilidad:** Orquestar todos los cálculos de pricing.

**Flujo de Cálculo:**

```python
def calculate_match_pricing(match, zones, current_datetime):
    # 1. Verificar cache (TTL: 5 minutos)
    cached = pricing_cache.get(match_id)
    if cached:
        return cached

    # 2. Para cada zona del estadio:
    for zone in zones:
        # a) Calcular factor temporal (días hasta partido)
        time_factor = rules_engine.get_time_decay_factor(days_to_match)

        # b) Obtener presión de inventario
        inventory = inventory_manager.get_zone_inventory(match_id, zone_id)
        inventory_factor = rules_engine.get_inventory_pressure_factor(
            inventory.occupancy_percent
        )

        # c) Predicción de demanda (ML o heurística)
        demand_score = demand_predictor.predict_demand(match, zone)

        # d) Multiplicadores de competición y rival
        competition_factor = rules_engine.get_competition_multiplier(
            match.competition, context
        )
        rival_factor = rules_engine.get_rival_multiplier(match.away_team)

        # e) Condiciones especiales (derby, festivo, clima)
        special_factor = rules_engine.get_special_conditions_multiplier(match)
        weather_factor = get_weather_adjustment(match.date)

        # 3. Combinar todos los factores
        final_price = zone.base_price * (
            time_factor *
            inventory_factor *
            competition_factor *
            rival_factor *
            special_factor *
            weather_factor *
            (1 + demand_score * 0.2)  # Demanda ajusta ±20%
        )

        # 4. Validar límites min/max de zona
        final_price = clamp(final_price, zone.min_price, zone.max_price)

        # 5. Aplicar ajuste gradual (máx 20% cambio)
        final_price = apply_gradual_adjustment(previous_price, final_price)

    # 6. Guardar en cache y base de datos
    pricing_cache.set(match_id, result, ttl=300)
    pricing_repo.save_history(result)

    return result
```

**Restricciones:**
- Máximo 20% de cambio por ajuste
- Máximo 5 cambios por día
- Mínimo 2 horas entre cambios
- Blackout de 24 horas antes del partido

### 2. RulesEngine (Motor de Reglas)

**Ubicación:** `src/domain/services/rules_engine.py`

**Responsabilidad:** Cargar y evaluar reglas de pricing desde YAML.

**Reglas Configurables:**

```yaml
competition_multipliers:
  laliga: 1.0
  laliga_vs_top3: 2.5
  champions_league: 3.0
  copa_del_rey_final: 3.0

rival_multipliers:
  "Real Madrid": 3.0
  "FC Barcelona": 3.0
  "Atletico Madrid": 3.0

time_decay_factors:
  # Días hasta partido: multiplicador
  60+: 0.75    # Early bird discount
  30-59: 0.85
  14-29: 1.0
  7-13: 1.15
  1-6: 1.30    # Last minute premium

inventory_pressure:
  0-20%: 0.80   # Aggressive discount
  20-40%: 0.90
  40-60%: 1.0
  75-85%: 1.15
  92-97%: 1.50  # Near sellout
  97-100%: 1.75 # Maximum premium
```

**Métodos Principales:**
- `get_competition_multiplier()`: 1.0-3.0
- `get_rival_multiplier()`: 0.8-3.0
- `get_time_decay_factor()`: 0.75-1.5
- `get_inventory_pressure_factor()`: 0.8-1.75
- `reload_rules()`: Hot-reload sin reinicio

### 3. DemandPredictor (Predictor de Demanda)

**Ubicación:** `src/domain/services/demand_predictor.py`

**Responsabilidad:** Predecir demanda de entradas (score 0.0-1.0).

**Dos Modos de Operación:**

#### Modo ML (cuando hay modelo entrenado):
```python
def predict_demand_ml(match, zone):
    # Extraer features
    features = feature_extractor.extract(match, zone)
    # features = [competition_type, rival_importance, days_to_match,
    #             day_of_week, month, is_weekend, is_holiday, ...]

    # Predicción con modelo sklearn
    demand_score = ml_model.predict(features)  # 0.0-1.0
    return demand_score
```

#### Modo Heurístico (fallback):
```python
def predict_demand_heuristic(match, zone):
    base_demand = 0.5

    # Ajustes por perfil de partido
    if match.is_derby:
        base_demand = 0.9
    elif match.competition == "champions_league":
        base_demand = 0.85
    elif match.away_team in TOP_TEAMS:
        base_demand = 0.75

    # Ajuste por urgencia temporal
    if days_to_match < 7:
        base_demand *= 1.2
    elif days_to_match > 60:
        base_demand *= 0.8

    return min(base_demand, 1.0)
```

### 4. InventoryManager (Gestor de Inventario)

**Ubicación:** `src/domain/services/inventory_manager.py`

**Responsabilidad:** Tracking de ventas e inventario.

**Métricas Clave:**
```python
class InventoryMetrics:
    sold_tickets: int
    available_tickets: int
    occupancy_percent: float  # 0-100
    sales_velocity: float     # tickets/hour
    estimated_sellout: Optional[datetime]
```

**Métodos:**
- `get_zone_inventory(match_id, zone_id)`: Estado actual
- `get_match_inventory(match_id)`: Agregado completo
- `calculate_sales_velocity(match_id, zone_id, hours=24)`: Ritmo de ventas
- `predict_sellout_time()`: ¿Cuándo se agotará?

**Caché:** InventoryCacheStrategy (TTL: 2 minutos)

### 5. FootballDataAPI (Integración de Datos)

**Ubicación:** `src/integrations/football_data.py`

**Responsabilidad:** Obtener datos externos de fútbol.

**Datos Obtenidos:**
- Clasificación de equipos (posición en liga)
- Forma reciente (últimos 5 partidos)
- Estadísticas de rivalidad
- Calendario de partidos

**Características:**
- Rate limiting: 10 requests/minuto
- Retry logic: 3 intentos con exponential backoff
- Cache: ExternalDataCacheStrategy (TTL: 1 hora)

## Flujo de Datos

### Flujo de Cálculo de Precio

```
┌─────────────┐
│   Cliente   │
└──────┬──────┘
       │ GET /api/v1/pricing/match/{match_id}
       ▼
┌─────────────────────────┐
│   API Endpoint          │
│   (pricing.py)          │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐      ┌──────────────┐
│   PricingEngine         │─────→│ Redis Cache  │
│   calculate_pricing()   │      │ (5 min TTL)  │
└──────┬──────────────────┘      └──────────────┘
       │
       ├─────→ RulesEngine.get_multipliers()
       │
       ├─────→ InventoryManager.get_inventory()
       │       └──→ Redis Cache (2 min TTL)
       │
       ├─────→ DemandPredictor.predict_demand()
       │       └──→ ML Model o Heurística
       │
       ├─────→ FootballDataAPI.get_team_stats()
       │       └──→ Redis Cache (1 hour TTL)
       │
       └─────→ WeatherAPI.get_forecast()
               └──→ Redis Cache (1 hour TTL)
       │
       ▼
┌─────────────────────────┐
│   PostgreSQL            │
│   - Save pricing        │
│   - Save history        │
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│   Response JSON         │
│   {                     │
│     match_id,           │
│     zones: [            │
│       {zone_id, price,  │
│        factors}         │
│     ]                   │
│   }                     │
└─────────────────────────┘
```

### Flujo de Background Workers

```
┌─────────────────────────────────────────┐
│   PriceUpdaterWorker (cada 5 minutos)   │
│                                         │
│   1. Obtener próximos 30 días          │
│   2. Para cada partido:                │
│      - Calcular pricing                │
│      - Actualizar cache                │
│      - Guardar historial               │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│   DataCollectorWorker (cada hora)       │
│                                         │
│   1. Fetch football data API            │
│   2. Fetch weather forecasts            │
│   3. Actualizar cache externo           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│   ModelRetrainerWorker (cada 7 días)    │
│                                         │
│   1. Obtener datos de ventas recientes │
│   2. Re-entrenar modelo ML              │
│   3. Validar performance                │
│   4. Desplegar si mejora                │
└─────────────────────────────────────────┘
```

## Estrategia de Caching

### Tres Niveles de Cache

#### 1. PricingCacheStrategy (TTL: 5 minutos)
```python
Patrón: pricing:match:{match_id}
Uso: Cálculos de pricing completos
Razón: Cálculos costosos, actualizaciones moderadas
Invalidación: Manual o TTL
```

#### 2. InventoryCacheStrategy (TTL: 2 minutos)
```python
Patrón: inventory:match:{match_id}:zone:{zone_id}
Uso: Estado de inventario y ventas
Razón: Datos cambiantes, necesitan actualización frecuente
Invalidación: Auto-invalidación en escritura
```

#### 3. ExternalDataCacheStrategy (TTL: 1 hora)
```python
Patrón: external_data:{key}
Uso: Datos de APIs externas (football data, weather)
Razón: Datos estables, rate limiting de APIs
Invalidación: TTL solamente
```

### Ventajas del Multi-TTL

- **Performance:** Cache hit rate optimizado por tipo de dato
- **Consistencia:** Datos críticos actualizados más frecuentemente
- **Costos:** Reduce llamadas a APIs externas con rate limits
- **Escalabilidad:** Redis puede manejar millones de requests

## Patrones de Diseño

### 1. Repository Pattern
```python
class BaseRepository:
    def get(id) -> Entity
    def get_all() -> List[Entity]
    def create(entity) -> Entity
    def update(entity) -> Entity
    def delete(id) -> bool

# Implementaciones específicas
MatchRepository(BaseRepository)
ZoneRepository(BaseRepository)
SaleRepository(BaseRepository)
```

### 2. Strategy Pattern
```python
# Diferentes estrategias de cache
class CacheStrategy(ABC):
    def get_ttl() -> int
    def get_key_pattern() -> str

PricingCacheStrategy(CacheStrategy)  # 5 min
InventoryCacheStrategy(CacheStrategy)  # 2 min
ExternalDataCacheStrategy(CacheStrategy)  # 1 hour
```

### 3. Dependency Injection
```python
# Container centralizado
def get_pricing_engine(
    rules_engine: RulesEngine = Depends(get_rules_engine),
    demand_predictor: DemandPredictor = Depends(get_demand_predictor),
    inventory_manager: InventoryManager = Depends(get_inventory_manager),
    cache_service: CacheService = Depends(get_cache_service)
) -> PricingEngine:
    return PricingEngine(
        rules_engine=rules_engine,
        demand_predictor=demand_predictor,
        inventory_manager=inventory_manager,
        cache_service=cache_service
    )
```

### 4. Factory Pattern
```python
# Creación de servicios configurados
class ServiceFactory:
    @staticmethod
    def create_pricing_engine() -> PricingEngine:
        settings = load_settings()
        return PricingEngine(
            max_price_change=settings.max_price_change,
            max_changes_per_day=settings.max_changes_per_day
        )
```

### 5. Template Method Pattern
```python
# Base para workers
class BaseWorker(ABC):
    def run(self):
        self.setup()
        while self.should_continue():
            try:
                self.execute()  # Abstract
            except Exception as e:
                self.handle_error(e)
            self.sleep()

    @abstractmethod
    def execute(self):
        pass
```

## Escalabilidad y Performance

### Optimizaciones Implementadas

1. **Connection Pooling**
```python
PostgreSQL:
  Pool size: 20 conexiones
  Max overflow: 10 adicionales
  Pool pre-ping: True (health check)
```

2. **Redis Pipeline**
```python
# Batch operations
pipe = redis.pipeline()
pipe.set(key1, value1)
pipe.set(key2, value2)
pipe.execute()  # Una sola roundtrip
```

3. **Async Endpoints**
```python
@router.get("/pricing/match/{match_id}")
async def get_match_pricing(match_id: int):
    # FastAPI maneja concurrencia automáticamente
    return await pricing_service.calculate_async(match_id)
```

4. **Lazy Loading de ML Models**
```python
class DemandPredictor:
    _model = None

    @property
    def model(self):
        if self._model is None:
            self._model = load_model()
        return self._model
```

### Puntos de Medición

**Métricas Prometheus:**
```python
pricing_calculations_total: Counter
pricing_calculation_duration_seconds: Histogram
cache_hit_rate: Gauge
api_request_duration_seconds: Histogram
database_connection_pool_size: Gauge
worker_execution_duration_seconds: Histogram
```

### Bottlenecks Identificados y Soluciones

| Bottleneck | Impacto | Solución |
|------------|---------|----------|
| Cálculos de pricing repetidos | Alto | PricingCacheStrategy (5 min) |
| Consultas de inventario frecuentes | Medio | InventoryCacheStrategy (2 min) |
| APIs externas con rate limits | Alto | ExternalDataCacheStrategy (1 hour) |
| Conexiones DB saturadas | Medio | Connection pool 20+10 |
| Predicciones ML lentas | Bajo | Lazy loading + cache |

### Capacidad y Límites

**Capacidad Actual:**
- API: ~1000 requests/segundo
- Pricing calculations: ~100/segundo (con cache)
- Workers: 3 procesos simultáneos
- Database: 20 conexiones concurrentes

**Escalabilidad Horizontal:**
- API: Múltiples instancias detrás de load balancer
- Workers: Múltiples workers independientes
- Redis: Redis Cluster para alta disponibilidad
- PostgreSQL: Read replicas para consultas

## Health Checks y Monitoring

### Endpoints de Health

```python
GET /health
Response:
{
  "status": "healthy",
  "services": {
    "database": {"status": "up", "latency_ms": 12},
    "redis": {"status": "up", "latency_ms": 3},
    "football_api": {"status": "up", "latency_ms": 245}
  },
  "version": "1.0.0",
  "uptime_seconds": 86400
}

GET /status/ready
Response:
{
  "ready": true,
  "checks": {
    "config_loaded": true,
    "database_connected": true,
    "redis_connected": true
  }
}
```

### Dashboards Grafana

1. **Smart Pricing Overview:**
   - Requests por minuto
   - Latencia P50, P95, P99
   - Cache hit rates
   - Error rates

2. **Business Metrics:**
   - Precios actuales por zona
   - Revenue estimado
   - Occupancy rates
   - Sales velocity

## Seguridad

### Prácticas Implementadas

1. **Validación de Input:** Pydantic schemas en todos los endpoints
2. **Rate Limiting:** Límites por IP en API Gateway (futuro)
3. **SQL Injection Prevention:** SQLAlchemy ORM (prepared statements)
4. **Secrets Management:** Variables de entorno, nunca en código
5. **CORS:** Configurado para dominios autorizados
6. **API Versioning:** `/api/v1/` permite breaking changes

### Auditoría

- Todos los cambios de precio guardados en `pricing_history`
- Logs estructurados con user_id cuando aplique
- Timestamps UTC en todas las operaciones

## Referencias

- [Plan de Implementación](IMPLEMENTATION_PLAN.md)
- [Guía de Configuración](CONFIGURATION.md)
- [Documentación ML](ML_MODEL.md)

## Contacto

Smart Pricing Team - @legasint
