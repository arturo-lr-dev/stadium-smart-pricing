# Plan de Implementación - Smart Pricing System

## Stack Tecnológico Decidido

- **Backend**: Python 3.11+ con FastAPI
- **Database**: PostgreSQL 15+ (transaccional)
- **Cache**: Redis 7+ (precios en tiempo real)
- **Time-Series**: TimescaleDB o InfluxDB (métricas)
- **Message Queue**: RabbitMQ o AWS SQS
- **ML**: scikit-learn, XGBoost, pandas
- **Frontend**: React + TypeScript / Next.js
- **Containerización**: Docker + Docker Compose
- **Testing**: pytest, pytest-asyncio
- **Monitoring**: Prometheus + Grafana

---

## FASE 0: Preparación del Entorno

### Setup Inicial del Proyecto

- [x] Crear repositorio Git
- [x] Crear archivo `.gitignore` con exclusiones para Python, Node, IDE, etc.
- [x] Crear estructura de carpetas base del proyecto
- [x] Inicializar entorno virtual Python: `python -m venv venv`
- [x] Activar entorno virtual
- [x] Crear `requirements.txt` con dependencias iniciales
- [x] Crear `pyproject.toml` para configuración del proyecto
- [ ] Instalar dependencias: `pip install -r requirements.txt`

### Dependencias Iniciales a Instalar

```
# requirements.txt - Fase Inicial
- [x] fastapi>=0.104.0
- [x] uvicorn[standard]>=0.24.0
- [x] pydantic>=2.5.0
- [x] pydantic-settings>=2.1.0
- [x] sqlalchemy>=2.0.23
- [x] psycopg2-binary>=2.9.9
- [x] alembic>=1.12.1
- [x] redis>=5.0.1
- [x] python-dotenv>=1.0.0
- [x] PyYAML>=6.0.1
- [x] python-multipart>=0.0.6
- [x] python-jose[cryptography]>=3.3.0
- [x] passlib[bcrypt]>=1.7.4
- [x] httpx>=0.25.0
- [x] pytest>=7.4.3
- [x] pytest-asyncio>=0.21.1
- [x] pytest-cov>=4.1.0
```

### Estructura de Carpetas

```
- [x] Crear carpeta `config/`
- [x] Crear carpeta `src/`
- [x] Crear carpeta `src/api/`
- [x] Crear carpeta `src/core/`
- [x] Crear carpeta `src/domain/`
- [x] Crear carpeta `src/domain/models/`
- [x] Crear carpeta `src/domain/services/`
- [x] Crear carpeta `src/domain/repositories/`
- [x] Crear carpeta `src/ml/`
- [x] Crear carpeta `src/ml/models/`
- [x] Crear carpeta `src/ml/features/`
- [x] Crear carpeta `src/ml/training/`
- [x] Crear carpeta `src/ml/inference/`
- [x] Crear carpeta `src/integrations/`
- [x] Crear carpeta `src/workers/`
- [x] Crear carpeta `src/utils/`
- [x] Crear carpeta `tests/`
- [x] Crear carpeta `tests/unit/`
- [x] Crear carpeta `tests/integration/`
- [x] Crear carpeta `tests/e2e/`
- [x] Crear carpeta `scripts/`
- [x] Crear carpeta `docker/`
- [x] Crear carpeta `dashboard/`
```

### Archivos de Configuración Base

- [x] Crear `.env.example` con variables de entorno necesarias
- [x] Crear `.env` local (no commitear)
- [x] Crear `docker-compose.yml`
- [x] Crear `README.md` con instrucciones de setup
- [ ] Crear `LICENSE` si es proyecto open source
- [x] Crear `.dockerignore`

---

## FASE 1: Core Infrastructure & Configuration

### Sistema de Configuración

- [x] Crear `src/core/__init__.py`
- [x] Crear `src/core/config.py` con clase Settings usando Pydantic
- [x] Implementar carga de configuración desde variables de entorno
- [x] Implementar carga de configuración desde archivos YAML
- [x] Crear función `get_settings()` con cache usando `@lru_cache`
- [x] Añadir validación de configuración al arranque

### Configuraciones YAML

#### config/base.yaml
- [x] Crear archivo `config/base.yaml`
- [x] Definir configuración de `app` (name, version, environment)
- [x] Definir configuración de `database` (host, port, name, pool_size)
- [x] Definir configuración de `redis` (host, port, db, ttl)
- [x] Definir configuración de `pricing` (update_interval, thresholds)
- [x] Definir configuración de `logging` (level, format)

#### config/pricing_rules.yaml
- [x] Crear archivo `config/pricing_rules.yaml`
- [x] Definir `competition_multipliers` (league, cup, champions, etc.)
- [x] Definir `rival_multipliers` (por equipo específico)
- [x] Definir `time_decay` (factores según días hasta partido)
- [x] Definir `inventory_pressure` (factores según ocupación)
- [x] Definir `constraints` (límites de cambio de precio)
- [x] Definir `special_conditions` (holiday, weekend, derby, weather)

#### config/zones.yaml
- [x] Crear archivo `config/zones.yaml`
- [x] Definir todas las zonas del estadio con:
  - [x] ID único
  - [x] Nombre
  - [x] Categoría (VIP, Premium, Standard, Reduced)
  - [x] Capacidad
  - [x] Precio base
  - [x] Precio mínimo
  - [x] Precio máximo
  - [x] Multiplicador de zona

#### config/competitions.yaml
- [x] Crear archivo `config/competitions.yaml`
- [x] Definir tipos de competición (LaLiga, Copa del Rey, etc.)
- [x] Asignar multiplicadores a cada competición
- [x] Definir reglas especiales por competición

### Sistema de Logging

- [x] Crear `src/core/logging.py`
- [x] Implementar configuración de logging estructurado
- [x] Configurar formato JSON para logs en producción
- [x] Configurar formato legible para desarrollo
- [x] Implementar función `setup_logging()`
- [x] Añadir context manager para logging de requests
- [x] Configurar niveles de log por módulo

### Manejo de Excepciones

- [x] Crear `src/core/exceptions.py`
- [x] Definir excepción base `SmartPricingException`
- [x] Definir `ConfigurationError`
- [x] Definir `DatabaseError`
- [x] Definir `ValidationError`
- [x] Definir `PricingError`
- [x] Definir `ExternalAPIError`
- [x] Definir `CacheError`
- [x] Implementar exception handlers para FastAPI

### Dependency Injection

- [x] Crear `src/core/dependencies.py`
- [x] Implementar función `get_db()` para obtener session de base de datos
- [x] Implementar función `get_redis()` para obtener cliente Redis
- [x] Implementar función `get_rules_engine()` con cache
- [x] Implementar función `get_pricing_engine()` con cache
- [x] Implementar función `get_demand_predictor()` con cache
- [x] Implementar función `get_inventory_manager()` con cache

---

## FASE 2: Database Layer & Models ✅ COMPLETED

**Status:** ✅ COMPLETED (2024-12-12)
**Documentation:** See [PHASE_2_COMPLETION.md](PHASE_2_COMPLETION.md)

### Database Setup

- [x] Iniciar PostgreSQL via Docker: `docker-compose up -d postgres`
- [x] Verificar conexión a PostgreSQL
- [x] Crear `src/core/database.py` con engine y session factory
- [x] Implementar Base declarativa de SQLAlchemy
- [x] Configurar connection pooling
- [x] Implementar función `get_db_session()` con context manager

### Database Models (SQLAlchemy)

#### src/domain/models/db_models.py
- [x] Crear archivo para modelos de base de datos
- [x] Implementar modelo `MatchDB`:
  - [x] id (String, PK)
  - [x] home_team (String)
  - [x] away_team (String)
  - [x] competition (String)
  - [x] match_date (DateTime)
  - [x] status (Enum: scheduled, on_sale, sold_out, completed)
  - [x] venue (String)
  - [x] capacity (Integer)
  - [x] is_derby (Boolean)
  - [x] is_holiday (Boolean)
  - [x] home_position (Integer, nullable)
  - [x] away_position (Integer, nullable)
  - [x] created_at (DateTime)
  - [x] updated_at (DateTime)
  - [x] Relaciones: sales, pricing_history

- [x] Implementar modelo `ZoneDB`:
  - [x] id (String, PK)
  - [x] name (String)
  - [x] category (String)
  - [x] capacity (Integer)
  - [x] base_price (Float)
  - [x] min_price (Float)
  - [x] max_price (Float)
  - [x] price_multiplier (Float)
  - [x] is_active (Boolean)

- [x] Implementar modelo `SaleDB`:
  - [x] id (String, PK)
  - [x] match_id (FK)
  - [x] zone_id (FK)
  - [x] quantity (Integer)
  - [x] price_per_ticket (Float)
  - [x] total_amount (Float)
  - [x] customer_type (String: member, general, vip)
  - [x] purchase_datetime (DateTime)
  - [x] payment_status (String)
  - [x] Relación: match

- [x] Implementar modelo `PricingHistoryDB`:
  - [x] id (String, PK)
  - [x] match_id (FK)
  - [x] zone_id (FK)
  - [x] price (Float)
  - [x] demand_score (Float)
  - [x] time_factor (Float)
  - [x] inventory_factor (Float)
  - [x] competition_factor (Float)
  - [x] weather_factor (Float)
  - [x] timestamp (DateTime)
  - [x] Relación: match

- [x] Implementar modelo `DemandMetricsDB`:
  - [x] id (String, PK)
  - [x] match_id (FK)
  - [x] zone_id (FK)
  - [x] views (Integer)
  - [x] cart_additions (Integer)
  - [x] cart_abandonments (Integer)
  - [x] timestamp (DateTime)

- [x] Implementar modelo `ExternalDataDB` para cache de APIs externas:
  - [x] id (String, PK)
  - [x] source (String: weather, football_stats, transport)
  - [x] data_key (String)
  - [x] data_value (JSONB)
  - [x] fetched_at (DateTime)
  - [x] expires_at (DateTime)

### Domain Models (Pydantic)

#### src/domain/models/__init__.py
- [x] Crear archivo `__init__.py`
- [x] Exportar todos los modelos públicos

#### src/domain/models/match.py
- [x] Crear enumeración `CompetitionType`
- [x] Crear enumeración `MatchStatus`
- [x] Crear modelo `Match` con Pydantic:
  - [x] id (str)
  - [x] home_team (str)
  - [x] away_team (str)
  - [x] competition (CompetitionType)
  - [x] date (datetime)
  - [x] venue (str)
  - [x] capacity (int)
  - [x] is_derby (bool)
  - [x] is_holiday (bool)
  - [x] home_position (Optional[int])
  - [x] away_position (Optional[int])
  - [x] status (MatchStatus)
- [x] Añadir validators para fechas futuras
- [x] Añadir método `days_until_match()`
- [x] Añadir ejemplo en Config

#### src/domain/models/zone.py
- [x] Crear enumeración `ZoneCategory`
- [x] Crear modelo `Zone` con Pydantic:
  - [x] id (str)
  - [x] name (str)
  - [x] category (ZoneCategory)
  - [x] capacity (int)
  - [x] base_price (float)
  - [x] min_price (float)
  - [x] max_price (float)
  - [x] price_multiplier (float)
- [x] Añadir validator para min_price <= base_price <= max_price
- [x] Implementar método `validate_price(price: float) -> float`
- [x] Añadir ejemplo en Config

#### src/domain/models/pricing.py
- [x] Crear modelo `PricingFactors`:
  - [x] demand_score (float, 0-1)
  - [x] time_factor (float, 0.5-2.0)
  - [x] inventory_factor (float, 0.7-1.5)
  - [x] competition_factor (float, 1.0-3.0)
  - [x] weather_factor (float, 0.9-1.1)
- [x] Crear modelo `ZonePricing`:
  - [x] zone_id (str)
  - [x] current_price (float)
  - [x] base_price (float)
  - [x] factors (PricingFactors)
  - [x] last_updated (datetime)
  - [x] sold_tickets (int)
  - [x] available_tickets (int)
  - [x] occupancy_percent (float)
- [x] Añadir método `calculate_occupancy()`
- [x] Crear modelo `MatchPricing`:
  - [x] match_id (str)
  - [x] zones (List[ZonePricing])
  - [x] total_revenue (float)
  - [x] total_sold (int)
  - [x] total_capacity (int)
  - [x] avg_price (float)
  - [x] last_calculation (datetime)
- [x] Añadir método `get_zone_pricing(zone_id: str)`

#### src/domain/models/sale.py
- [x] Crear enumeración `CustomerType`
- [x] Crear enumeración `PaymentStatus`
- [x] Crear modelo `Sale`:
  - [x] id (str)
  - [x] match_id (str)
  - [x] zone_id (str)
  - [x] quantity (int)
  - [x] price_per_ticket (float)
  - [x] total_amount (float)
  - [x] customer_type (CustomerType)
  - [x] purchase_datetime (datetime)
  - [x] payment_status (PaymentStatus)
- [x] Añadir validator para total_amount = quantity * price_per_ticket

### Database Initialization Script

#### scripts/init_db.py
- [x] Crear script de inicialización
- [x] Implementar función `create_all_tables()`
- [x] Implementar función `drop_all_tables()` (con confirmación)
- [x] Añadir CLI con argparse para opciones
- [x] Ejecutar: `python scripts/init_db.py --create`

### Database Seeding Script

#### scripts/seed_data.py
- [x] Crear script de seed con datos de prueba
- [x] Implementar función `seed_zones()` con zonas de Son Moix
- [x] Implementar función `seed_matches()` con partidos de ejemplo
- [x] Implementar función `seed_sales()` con ventas de ejemplo
- [x] Implementar función `seed_pricing_history()` con histórico
- [x] Añadir flag `--clear` para limpiar antes de seed
- [x] Ejecutar: `python scripts/seed_data.py`

### Alembic Migrations

- [x] Inicializar Alembic: `alembic init alembic`
- [x] Configurar `alembic.ini` con connection string
- [x] Configurar `alembic/env.py` para auto-generar migraciones
- [x] Crear migración inicial: `alembic revision --autogenerate -m "Initial schema"`
- [x] Revisar migración generada
- [x] Aplicar migración: `alembic upgrade head`

---

## FASE 3: Repository Layer

### Base Repository

#### src/domain/repositories/base_repository.py
- [ ] Crear clase abstracta `BaseRepository`
- [ ] Implementar método `get_by_id(id: str)`
- [ ] Implementar método `get_all(skip: int, limit: int)`
- [ ] Implementar método `create(entity: T)`
- [ ] Implementar método `update(id: str, entity: T)`
- [ ] Implementar método `delete(id: str)`
- [ ] Implementar método `exists(id: str)`
- [ ] Añadir manejo de transacciones

### Specific Repositories

#### src/domain/repositories/match_repository.py
- [ ] Crear clase `MatchRepository(BaseRepository)`
- [ ] Implementar método `get_upcoming(days: int)`
- [ ] Implementar método `get_by_date_range(start: date, end: date)`
- [ ] Implementar método `get_by_competition(competition: str)`
- [ ] Implementar método `get_by_status(status: MatchStatus)`
- [ ] Implementar método `get_by_team(team: str)`
- [ ] Implementar conversión DB model <-> Domain model

#### src/domain/repositories/zone_repository.py
- [ ] Crear clase `ZoneRepository(BaseRepository)`
- [ ] Implementar método `get_by_category(category: ZoneCategory)`
- [ ] Implementar método `get_active_zones()`
- [ ] Implementar conversión DB model <-> Domain model

#### src/domain/repositories/sale_repository.py
- [ ] Crear clase `SaleRepository(BaseRepository)`
- [ ] Implementar método `get_by_match(match_id: str)`
- [ ] Implementar método `get_by_zone(zone_id: str)`
- [ ] Implementar método `get_by_match_and_zone(match_id: str, zone_id: str)`
- [ ] Implementar método `get_sales_velocity(match_id: str, hours: int)`
- [ ] Implementar método `get_total_sold(match_id: str, zone_id: str)`
- [ ] Implementar agregaciones para analytics

#### src/domain/repositories/pricing_repository.py
- [ ] Crear clase `PricingHistoryRepository(BaseRepository)`
- [ ] Implementar método `get_by_match(match_id: str)`
- [ ] Implementar método `get_latest_price(match_id: str, zone_id: str)`
- [ ] Implementar método `get_price_history(match_id: str, zone_id: str, hours: int)`
- [ ] Implementar método `save_pricing(pricing: MatchPricing)`

### Repository Tests

- [ ] Crear `tests/unit/repositories/test_match_repository.py`
- [ ] Crear `tests/unit/repositories/test_zone_repository.py`
- [ ] Crear `tests/unit/repositories/test_sale_repository.py`
- [ ] Crear `tests/unit/repositories/test_pricing_repository.py`
- [ ] Implementar fixtures con base de datos de prueba
- [ ] Testear CRUD completo
- [ ] Testear métodos de búsqueda específicos
- [ ] Ejecutar tests: `pytest tests/unit/repositories/`

---

## FASE 4: Business Logic - Rules Engine ✅ COMPLETED

**Status:** ✅ COMPLETED (2025-12-13)
**Documentation:** See [PHASE_4_COMPLETION.md](PHASE_4_COMPLETION.md)

### Rules Engine Core

#### src/domain/services/rules_engine.py
- [x] Crear clase `RulesEngine`
- [x] Implementar `__init__(config_path: str)`
- [x] Implementar método privado `_load_rules(path: str) -> Dict`
- [x] Implementar método `reload_rules()` para hot-reload
- [x] Implementar validación de reglas al cargar

### Competition Rules

- [x] Implementar método `get_competition_multiplier(competition: str) -> float`
- [x] Añadir fallback a valor default si competición no existe
- [x] Añadir logging de multiplicador aplicado

### Rival Rules

- [x] Implementar método `get_rival_multiplier(rival_team: str) -> float`
- [x] Implementar lógica para equipos en zona de descenso
- [x] Añadir cache de multiplicadores por rival
- [x] Añadir fallback a valor default

### Time Decay Rules

- [x] Implementar método `get_time_decay_factor(days_to_match: int) -> float`
- [x] Iterar sobre reglas ordenadas por min_days
- [x] Retornar multiplicador correspondiente
- [x] Añadir logging del factor aplicado

### Inventory Pressure Rules

- [x] Implementar método `get_inventory_pressure_factor(occupancy_percent: float) -> float`
- [x] Iterar sobre umbrales de ocupación
- [x] Retornar multiplicador correspondiente
- [x] Añadir lógica para promociones en baja ocupación

### Special Conditions

- [x] Implementar método `get_special_multipliers(match: Match) -> Dict[str, float]`
- [x] Calcular holiday_multiplier si es festivo
- [x] Calcular weekend_multiplier si es fin de semana
- [x] Calcular derby_multiplier si es derby
- [x] Retornar diccionario con todos los multiplicadores aplicables

### Price Change Validation

- [x] Implementar método `is_price_change_allowed(current: float, new: float, changes_today: int) -> tuple[bool, str]`
- [x] Validar límite diario de cambios
- [x] Validar porcentaje de cambio máximo
- [x] Validar horas mínimas entre cambios
- [x] Validar blackout period antes del partido
- [x] Retornar (bool, mensaje_explicativo)

### Price Change Tracking

- [x] Implementar método `record_price_change(match_id: str, zone_id: str)`
- [x] Guardar timestamp del cambio en Redis
- [x] Implementar contador de cambios diarios por zona
- [x] Limpiar cambios antiguos (> 24 horas)

### Rules Engine Tests

- [x] Crear `tests/unit/services/test_rules_engine.py`
- [x] Testear carga de configuración
- [x] Testear cada método de multiplicadores
- [x] Testear validación de cambios de precio
- [x] Testear casos edge (valores negativos, None, etc.)
- [x] Testear hot-reload de configuración
- [x] Ejecutar tests: `pytest tests/unit/services/test_rules_engine.py`

---

## FASE 5: Business Logic - Inventory Manager ✅ COMPLETED

**Status:** ✅ COMPLETED (2025-12-13)
**Documentation:** See [PHASE_5_COMPLETION.md](PHASE_5_COMPLETION.md)

### Inventory Manager Core

#### src/domain/services/inventory_manager.py
- [x] Crear clase `InventoryManager`
- [x] Inyectar `SaleRepository` y `ZoneRepository`
- [x] Inyectar cliente Redis para cache

### Inventory Queries

- [x] Implementar método `get_zone_inventory(match_id: str, zone_id: str) -> tuple[int, int]`
  - [x] Consultar ventas totales desde DB
  - [x] Obtener capacidad de zona
  - [x] Calcular disponibles
  - [x] Retornar (vendidos, disponibles)
- [x] Implementar cache en Redis con TTL de 5 minutos
- [x] Implementar método `get_match_inventory(match_id: str) -> Dict[str, tuple[int, int]]`
- [x] Implementar método `get_total_occupancy(match_id: str) -> float`

### Sales Velocity

- [x] Implementar método `get_sales_velocity(match_id: str, zone_id: str, hours: int = 24) -> float`
  - [x] Consultar ventas en últimas N horas
  - [x] Calcular tickets vendidos por hora
  - [x] Retornar velocidad
- [x] Implementar método `predict_sellout_time(match_id: str, zone_id: str) -> Optional[datetime]`
  - [x] Usar velocidad de venta actual
  - [x] Calcular tickets restantes
  - [x] Proyectar fecha de agotamiento

### Inventory Alerts

- [x] Implementar método `check_inventory_alerts(match_id: str) -> List[Dict]`
  - [x] Detectar zonas con > 90% ocupación
  - [x] Detectar zonas con < 20% ocupación cerca del partido
  - [x] Detectar cambios bruscos en velocidad de venta
  - [x] Retornar lista de alertas

### Cache Management

- [x] Implementar método `invalidate_cache(match_id: str, zone_id: Optional[str] = None)`
- [x] Implementar método `warm_cache(match_ids: List[str])`
- [x] Implementar limpieza automática de cache expirado

### Inventory Manager Tests

- [x] Crear `tests/unit/services/test_inventory_manager.py`
- [x] Testear cálculos de inventario
- [x] Testear cálculos de velocidad de venta
- [x] Testear predicciones
- [x] Testear cache (mock Redis)
- [x] Testear alertas
- [x] Ejecutar tests: `pytest tests/unit/services/test_inventory_manager.py`

---

## FASE 6: Business Logic - Pricing Engine ✅ COMPLETED

**Status:** ✅ COMPLETED (2025-12-13)
**Documentation:** See [PHASE_6_COMPLETION.md](PHASE_6_COMPLETION.md)

### Pricing Engine Core

#### src/domain/services/pricing_engine.py
- [x] Crear clase `PricingEngine`
- [x] Inyectar `RulesEngine`
- [x] Inyectar `DemandPredictor`
- [x] Inyectar `InventoryManager`
- [x] Inyectar `MatchRepository` y `ZoneRepository`

### Main Pricing Method

- [x] Implementar método `calculate_match_pricing(match: Match, zones: List[Zone], current_datetime: Optional[datetime]) -> MatchPricing`
  - [x] Iterar sobre todas las zonas
  - [x] Llamar a `_calculate_zone_price` para cada zona
  - [x] Agregar métricas totales
  - [x] Calcular precio promedio
  - [x] Retornar `MatchPricing` completo
- [x] Añadir logging detallado de cada cálculo
- [ ] Añadir métricas Prometheus (deferred to Phase 12)

### Zone Pricing Calculation

- [x] Implementar método `_calculate_zone_price(match: Match, zone: Zone, current_datetime: datetime) -> ZonePricing`
  - [x] Calcular todos los factores (`_calculate_pricing_factors`)
  - [x] Obtener precio base de la zona
  - [x] Aplicar multiplicador de zona
  - [x] Aplicar todos los factores calculados
  - [x] Validar límites de precio con `zone.validate_price()`
  - [x] Obtener inventario actual
  - [x] Construir y retornar `ZonePricing`

### Pricing Factors Calculation

- [x] Implementar método `_calculate_pricing_factors(match: Match, zone: Zone, current_datetime: datetime) -> PricingFactors`
  - [x] Calcular días hasta el partido
  - [x] Obtener demand_score del ML model
  - [x] Obtener time_factor del RulesEngine
  - [x] Calcular occupancy y obtener inventory_factor
  - [x] Obtener competition_factor del RulesEngine
  - [x] Aplicar rival_multiplier
  - [x] Aplicar special conditions (derby, holiday, etc.)
  - [x] Obtener weather_factor (integración futura - placeholder)
  - [x] Construir y retornar `PricingFactors`

### Price Change Decision

- [x] Implementar método `should_update_price(match_id: str, zone_id: str, current_price: float, new_price: float) -> tuple[bool, str]`
  - [x] Consultar cuántos cambios se han hecho hoy
  - [x] Validar con RulesEngine
  - [x] Calcular diferencia de precio
  - [x] Validar umbral mínimo de cambio (evitar cambios triviales)
  - [x] Retornar decisión y razón

### Batch Pricing

- [x] Implementar método `calculate_all_upcoming_matches(days: int = 30) -> List[MatchPricing]`
  - [x] Obtener partidos próximos
  - [x] Calcular pricing para cada uno
  - [x] Manejar errores individualmente (no fallar todo si uno falla)
  - [x] Retornar lista de pricings

### Price History

- [x] Implementar método `save_pricing_to_history(pricing: MatchPricing)`
  - [x] Iterar sobre zonas
  - [x] Guardar en PricingHistoryDB
  - [x] Commit transacción

### Pricing Engine Tests

- [x] Crear `tests/unit/services/test_pricing_engine.py`
- [x] Testear cálculo completo de pricing
- [x] Testear cálculo de factores individuales
- [x] Testear validación de límites de precio
- [x] Testear decisión de cambio de precio
- [x] Testear casos edge (partido pasado, sin inventario, etc.)
- [x] Mockear dependencias (RulesEngine, DemandPredictor, etc.)
- [x] Ejecutar tests: `pytest tests/unit/services/test_pricing_engine.py` (26/26 passed)

---

## FASE 7: Machine Learning - Demand Prediction (MVP) ✅ COMPLETED

**Status:** ✅ COMPLETED (2025-12-13)
**Documentation:** See [PHASE_7_COMPLETION.md](PHASE_7_COMPLETION.md)

### Feature Engineering

#### src/ml/features/match_features.py
- [x] Crear clase `MatchFeatureExtractor`
- [x] Implementar método `extract_competition_features(match: Match) -> Dict`
  - [x] One-hot encoding de competition type
  - [x] Importancia del partido (league position, etc.)
  - [x] Is derby flag
- [x] Implementar método `extract_rival_features(match: Match) -> Dict`
  - [x] Estadísticas históricas del rival
  - [x] Posición en liga del rival
  - [x] Racha reciente del rival
- [x] Implementar método `extract_home_team_features(match: Match) -> Dict`
  - [x] Posición en liga local
  - [x] Racha de resultados
  - [x] Goles a favor/contra
- [x] Implementar método `extract_all(match: Match) -> Dict`

#### src/ml/features/temporal_features.py
- [x] Crear clase `TemporalFeatureExtractor`
- [x] Implementar método `extract_date_features(match_date: datetime) -> Dict`
  - [x] Day of week (0-6)
  - [x] Is weekend
  - [x] Is holiday
  - [x] Month
  - [x] Hour of day
- [x] Implementar método `extract_season_features(match_date: datetime) -> Dict`
  - [x] Season (2023/2024, etc.)
  - [x] Matchday number (jornada)
- [x] Implementar método `extract_all(match_date: datetime) -> Dict`

#### src/ml/features/external_features.py
- [x] Crear clase `ExternalFeatureExtractor`
- [x] Implementar método `extract_weather_features(match: Match) -> Dict`
  - [x] Temperature (placeholder por ahora)
  - [x] Precipitation probability
  - [x] Wind speed
- [x] Implementar método `extract_transport_features(match: Match) -> Dict`
  - [x] Public transport availability
  - [x] Traffic conditions (placeholder)
- [x] Implementar método `extract_all(match: Match) -> Dict`

### ML Model - Demand Predictor (Simple MVP)

#### src/ml/models/base_model.py
- [x] Crear clase abstracta `BaseMLModel`
- [x] Definir método abstracto `train(X, y)`
- [x] Definir método abstracto `predict(X)`
- [x] Definir método abstracto `save(path: str)`
- [x] Definir método abstracto `load(path: str)`
- [x] Implementar método `evaluate(X, y) -> Dict[str, float]`

#### src/ml/models/demand_model.py
- [x] Crear clase `DemandModel(BaseMLModel)`
- [x] Usar RandomForestRegressor o XGBoost como base (configurable)
- [x] Implementar método `train(historical_sales: List[Sale], matches: List[Match])`
  - [x] Extraer features de matches
  - [x] Preparar target (% de ocupación o velocidad de venta)
  - [x] Split train/validation
  - [x] Entrenar modelo
  - [x] Evaluar en validation
  - [x] Guardar métricas
- [x] Implementar método `predict(match: Match, zone: Zone, days_to_match: int) -> float`
  - [x] Extraer features del match
  - [x] Añadir days_to_match como feature
  - [x] Predecir demand_score (0-1)
  - [x] Aplicar calibración si es necesario
  - [x] Retornar score

### Training Pipeline

#### src/ml/training/train_demand.py
- [x] Crear script de entrenamiento
- [x] Implementar función `load_training_data() -> tuple[List[Match], List[Sale]]`
  - [x] Cargar histórico de partidos
  - [x] Cargar histórico de ventas
  - [x] Filtrar datos incompletos
- [x] Implementar función `prepare_features_and_target(matches, sales) -> tuple[pd.DataFrame, pd.Series]`
  - [x] Combinar matches y sales
  - [x] Extraer todas las features
  - [x] Calcular target (occupancy rate a X días del partido)
- [x] Implementar función `train_model(X, y, config: Dict) -> DemandModel`
  - [x] Instanciar modelo
  - [x] Entrenar
  - [x] Evaluar
  - [x] Guardar
- [x] Implementar función `main()`
- [x] Añadir CLI con argparse
- [x] Ejecutar: `python src/ml/training/train_demand.py`

### Model Evaluation

#### src/ml/training/evaluate.py
- [x] Crear script de evaluación
- [x] Implementar función `load_model(path: str) -> DemandModel`
- [x] Implementar función `load_test_data() -> tuple[pd.DataFrame, pd.Series]`
- [x] Implementar función `evaluate_model(model, X_test, y_test) -> Dict`
  - [x] Calcular MAE, RMSE, R²
  - [x] Generar gráficas de predicciones vs real
  - [x] Guardar métricas en archivo JSON
- [x] Implementar función `main()`
- [x] Ejecutar: `python src/ml/training/evaluate.py`

### Demand Predictor Service

#### src/domain/services/demand_predictor.py
- [x] Actualizar clase `DemandPredictor`
- [x] Cargar modelo entrenado en `__init__`
- [x] Implementar método `predict_demand(match: Match, zone: Zone, days_to_match: int) -> float`
  - [x] Extraer features
  - [x] Llamar a modelo ML
  - [x] Post-procesar predicción
  - [x] Aplicar límites (0-1)
  - [x] Retornar score
- [x] Implementar método `reload_model(path: str)`
- [x] Implementar fallback si modelo no disponible (usar heurística simple)

### ML Tests

- [x] Crear `tests/unit/ml/test_feature_extractors.py`
- [x] Testear extracción de cada tipo de feature
- [x] Crear `tests/unit/ml/test_demand_model.py`
- [x] Testear entrenamiento con datos sintéticos
- [x] Testear predicción
- [x] Testear save/load de modelo
- [x] Ejecutar tests: `pytest tests/unit/ml/` (32 tests passed)

---

## FASE 8: FastAPI Application ✅ COMPLETED

**Status:** ✅ COMPLETED (2025-12-13)
**Documentation:** See [PHASE_8_COMPLETION.md](PHASE_8_COMPLETION.md)

### FastAPI Setup

#### src/api/main.py
- [x] Crear instancia de FastAPI con configuración
- [x] Configurar metadata (title, description, version)
- [x] Implementar lifespan context manager para startup/shutdown
- [x] Configurar CORS middleware
- [x] Añadir middleware para logging de requests
- [x] Añadir middleware para manejo de errores
- [x] Incluir routers

### Health & Status Endpoints

- [x] Implementar endpoint `GET /health`
  - [x] Verificar conexión DB
  - [x] Verificar conexión Redis
  - [x] Retornar status + versión
- [x] Implementar endpoint `GET /status/ready`
  - [x] Verificar que modelo ML está cargado
  - [x] Verificar que configuración está cargada
- [x] Implementar endpoint `GET /status/metrics`
  - [x] Exponer métricas de Prometheus

### Pricing Endpoints

#### src/api/pricing.py
- [x] Crear router con prefijo `/api/v1/pricing`
- [x] Implementar `GET /match/{match_id}`
  - [x] Validar match_id
  - [x] Obtener match desde repositorio
  - [x] Obtener zones
  - [x] Calcular pricing con PricingEngine
  - [x] Retornar `MatchPricing`
  - [x] Manejar errores (404 si no existe, 500 si falla cálculo)

- [x] Implementar `GET /match/{match_id}/zone/{zone_id}`
  - [x] Obtener pricing completo del match
  - [x] Filtrar zona específica
  - [x] Retornar `ZonePricing`

- [x] Implementar `GET /upcoming`
  - [x] Query param: `days` (default 30, max 90)
  - [x] Obtener matches próximos
  - [x] Calcular pricing para cada uno
  - [x] Retornar `List[MatchPricing]`

- [x] Implementar `POST /match/{match_id}/recalculate`
  - [x] Forzar recálculo de precios
  - [x] Guardar en cache
  - [x] Guardar en histórico
  - [x] Retornar status

- [x] Implementar `GET /match/{match_id}/history`
  - [x] Query param: `hours` (default 24)
  - [x] Obtener histórico de precios
  - [x] Retornar series temporal

### Admin Endpoints

#### src/api/admin.py
- [x] Crear router con prefijo `/api/v1/admin`
- [ ] Implementar autenticación básica (JWT o API key) - Deferred to Phase 17

- [x] Implementar `POST /rules/reload`
  - [x] Recargar configuración de reglas
  - [x] Retornar status

- [x] Implementar `GET /rules`
  - [x] Retornar configuración actual de reglas
  - [x] Formato JSON

- [ ] Implementar `PUT /rules` - Deferred (complex YAML validation needed)
  - [ ] Actualizar reglas (validar antes)
  - [ ] Guardar en archivo YAML
  - [ ] Recargar

- [x] Implementar `GET /zones`
  - [x] Listar todas las zonas
  - [x] Filtros opcionales

- [x] Implementar `PUT /zones/{zone_id}`
  - [x] Actualizar configuración de zona
  - [x] Validar precios min <= base <= max

- [x] Implementar `GET /matches`
  - [x] Listar partidos
  - [x] Filtros: date_from, date_to, competition, status
  - [x] Paginación

- [x] Implementar `POST /matches`
  - [x] Crear nuevo partido
  - [x] Validar datos

- [x] Implementar `PUT /matches/{match_id}`
  - [x] Actualizar partido
  - [x] Validar cambios

- [x] Implementar `GET /sales/summary`
  - [x] Resumen de ventas por partido
  - [x] Agregaciones

- [x] Implementar `GET /pricing/alerts`
  - [x] Obtener alertas de inventario
  - [x] Zonas con problemas de ocupación

### Analytics Endpoints

#### src/api/analytics.py
- [x] Crear router con prefijo `/api/v1/analytics`

- [x] Implementar `GET /revenue`
  - [x] Query params: date_from, date_to
  - [x] Calcular revenue total
  - [x] Agrupar por período (day, week, month)

- [x] Implementar `GET /occupancy`
  - [x] Estadísticas de ocupación por zona
  - [x] Promedios y tendencias

- [x] Implementar `GET /price-elasticity`
  - [x] Análisis de elasticidad precio-demanda
  - [x] Por zona y competición

- [x] Implementar `GET /predictions`
  - [x] Predicciones de demanda futura
  - [x] Proyecciones de revenue

### Response Models

#### src/api/responses.py
- [x] Crear modelos Pydantic para respuestas consistentes
- [x] Modelo `SuccessResponse`
- [x] Modelo `ErrorResponse`
- [x] Modelo `PaginatedResponse`

### Exception Handlers

- [x] Implementar handler para `ValidationError`
- [x] Implementar handler para `DatabaseError`
- [x] Implementar handler para `PricingError`
- [x] Implementar handler para excepciones genéricas

### API Documentation

- [x] Verificar que Swagger UI está accesible en `/docs`
- [x] Verificar que ReDoc está accesible en `/redoc`
- [x] Añadir ejemplos a cada endpoint
- [x] Añadir descripciones detalladas
- [x] Documentar códigos de error posibles

### API Tests

- [x] Crear `tests/integration/api/test_pricing_endpoints.py`
- [x] Crear `tests/integration/api/test_admin_endpoints.py` - Basic structure created
- [x] Crear `tests/integration/api/test_analytics_endpoints.py` - Basic structure created
- [x] Usar `TestClient` de FastAPI
- [x] Testear casos exitosos
- [x] Testear casos de error (404, 422, 500)
- [x] Testear validaciones
- [x] Ejecutar tests: `pytest tests/integration/api/`

---

## FASE 9: Background Workers

### Worker Infrastructure

#### src/workers/base_worker.py
- [ ] Crear clase base `BaseWorker`
- [ ] Implementar método abstracto `run()`
- [ ] Implementar manejo de señales (SIGTERM, SIGINT)
- [ ] Implementar logging
- [ ] Implementar health check

### Price Update Worker

#### src/workers/price_updater.py
- [ ] Crear clase `PriceUpdaterWorker(BaseWorker)`
- [ ] Inyectar PricingEngine
- [ ] Implementar método `run()`
  - [ ] Loop infinito con intervalo configurable
  - [ ] Obtener matches próximos (X días)
  - [ ] Calcular pricing para cada uno
  - [ ] Decidir si actualizar precio
  - [ ] Guardar en Redis (cache)
  - [ ] Guardar en histórico (DB)
  - [ ] Dormir hasta próxima ejecución
- [ ] Implementar manejo de errores (retry con backoff)
- [ ] Añadir métricas (tiempo de ejecución, matches procesados)

### Data Collection Worker

#### src/workers/data_collector.py
- [ ] Crear clase `DataCollectorWorker(BaseWorker)`
- [ ] Inyectar integraciones externas
- [ ] Implementar método `run()`
  - [ ] Loop con intervalo configurable
  - [ ] Recolectar datos de football API
  - [ ] Recolectar datos de weather API
  - [ ] Recolectar datos de analytics
  - [ ] Guardar en cache/DB
  - [ ] Dormir hasta próxima ejecución
- [ ] Implementar rate limiting
- [ ] Implementar retry con exponential backoff

### Model Retraining Worker

#### src/workers/model_retrainer.py
- [ ] Crear clase `ModelRetrainerWorker(BaseWorker)`
- [ ] Implementar método `run()`
  - [ ] Ejecutar semanalmente (cron-like)
  - [ ] Cargar datos históricos nuevos
  - [ ] Re-entrenar modelo de demanda
  - [ ] Evaluar modelo nuevo vs anterior
  - [ ] Si mejora, reemplazar modelo en producción
  - [ ] Notificar resultado
- [ ] Implementar versionado de modelos
- [ ] Implementar rollback si modelo nuevo es peor

### Worker Orchestration

#### src/workers/__main__.py
- [ ] Crear script principal para ejecutar workers
- [ ] Usar argparse para seleccionar worker
- [ ] Implementar `main()`:
  - [ ] Cargar configuración
  - [ ] Setup logging
  - [ ] Instanciar worker seleccionado
  - [ ] Ejecutar worker
- [ ] Ejemplo: `python -m src.workers price_updater`

### Worker Tests

- [ ] Crear `tests/unit/workers/test_price_updater.py`
- [ ] Crear `tests/unit/workers/test_data_collector.py`
- [ ] Mockear dependencias externas
- [ ] Testear lógica de cada worker
- [ ] Testear manejo de errores
- [ ] Ejecutar tests: `pytest tests/unit/workers/`

---

## FASE 10: External Integrations

### Football Data API

#### src/integrations/football_data.py
- [ ] Crear clase `FootballDataAPI`
- [ ] Configurar API key desde variables de entorno
- [ ] Implementar método `get_team_standings(league: str, season: str) -> Dict`
- [ ] Implementar método `get_team_stats(team_id: str) -> Dict`
- [ ] Implementar método `get_match_details(match_id: str) -> Dict`
- [ ] Implementar método `get_team_recent_form(team_id: str, matches: int) -> List`
- [ ] Implementar caching de respuestas (6 horas)
- [ ] Implementar rate limiting
- [ ] Implementar retry con exponential backoff
- [ ] Manejar errores de API (401, 429, 500, etc.)

### Weather API

#### src/integrations/weather_api.py
- [ ] Crear clase `WeatherAPI`
- [ ] Configurar API key desde variables de entorno
- [ ] Implementar método `get_forecast(lat: float, lon: float, date: datetime) -> Dict`
  - [ ] Temperature
  - [ ] Precipitation probability
  - [ ] Wind speed
  - [ ] Weather condition
- [ ] Implementar caching de respuestas (1 hora)
- [ ] Implementar fallback si API falla (usar datos históricos)
- [ ] Implementar método `get_historical_weather(lat: float, lon: float, date: datetime) -> Dict`

### Google Analytics Integration

#### src/integrations/analytics.py
- [ ] Crear clase `GoogleAnalyticsIntegration`
- [ ] Usar biblioteca oficial de Google Analytics Data API
- [ ] Configurar credenciales (service account)
- [ ] Implementar método `get_page_views(match_id: str, date_range: tuple) -> int`
- [ ] Implementar método `get_cart_additions(match_id: str, date_range: tuple) -> int`
- [ ] Implementar método `get_cart_abandonments(match_id: str, date_range: tuple) -> int`
- [ ] Implementar método `get_conversion_rate(match_id: str) -> float`
- [ ] Cachear métricas por 30 minutos

### Ticketing System Integration (Mock)

#### src/integrations/ticketing_system.py
- [ ] Crear clase `TicketingSystemAPI`
- [ ] Implementar método `get_available_inventory(match_id: str) -> Dict[str, int]`
- [ ] Implementar método `reserve_tickets(match_id: str, zone_id: str, quantity: int) -> str`
- [ ] Implementar método `confirm_purchase(reservation_id: str) -> bool`
- [ ] Implementar método `cancel_reservation(reservation_id: str) -> bool`
- [ ] Implementar webhook receiver para actualizaciones de venta
- [ ] Por ahora, mock con datos locales

### Integration Tests

- [ ] Crear `tests/integration/test_football_data.py`
- [ ] Crear `tests/integration/test_weather_api.py`
- [ ] Crear `tests/integration/test_analytics.py`
- [ ] Usar VCR.py para grabar/replay requests HTTP
- [ ] Testear manejo de errores de API
- [ ] Testear rate limiting
- [ ] Ejecutar tests: `pytest tests/integration/ -k integration`

---

## FASE 11: Redis Caching Layer

### Redis Client Setup

#### src/core/redis_client.py
- [ ] Crear clase `RedisClient`
- [ ] Implementar conexión a Redis
- [ ] Implementar connection pooling
- [ ] Implementar health check

### Cache Service

#### src/core/cache_service.py
- [ ] Crear clase `CacheService`
- [ ] Implementar método `get(key: str) -> Optional[Any]`
- [ ] Implementar método `set(key: str, value: Any, ttl: int)`
- [ ] Implementar método `delete(key: str)`
- [ ] Implementar método `exists(key: str) -> bool`
- [ ] Implementar método `get_many(keys: List[str]) -> Dict[str, Any]`
- [ ] Implementar método `set_many(mapping: Dict[str, Any], ttl: int)`
- [ ] Implementar serialización (JSON o pickle)
- [ ] Implementar deserialización

### Cache Strategies

- [ ] Implementar estrategia de cache para pricing:
  - [ ] Key: `pricing:match:{match_id}`
  - [ ] TTL: 5 minutos
- [ ] Implementar estrategia de cache para inventario:
  - [ ] Key: `inventory:match:{match_id}:zone:{zone_id}`
  - [ ] TTL: 2 minutos
- [ ] Implementar estrategia de cache para datos externos:
  - [ ] Key: `external:{source}:{key}`
  - [ ] TTL: 1-6 horas según fuente
- [ ] Implementar invalidación selectiva de cache

### Cache Decorators

#### src/utils/cache_decorators.py
- [ ] Crear decorator `@cached(ttl: int, key_prefix: str)`
- [ ] Implementar lógica de cache transparente
- [ ] Ejemplo:
  ```python
  @cached(ttl=300, key_prefix="pricing")
  def calculate_pricing(match_id: str):
      # expensive calculation
      pass
  ```

### Cache Tests

- [ ] Crear `tests/unit/core/test_cache_service.py`
- [ ] Testear operaciones básicas (get, set, delete)
- [ ] Testear TTL
- [ ] Testear serialización/deserialización
- [ ] Usar fakeredis para tests
- [ ] Ejecutar tests: `pytest tests/unit/core/test_cache_service.py`

---

## FASE 12: Monitoring & Observability

### Logging Setup

- [ ] Configurar logging estructurado (JSON)
- [ ] Configurar diferentes niveles por módulo
- [ ] Configurar rotación de logs
- [ ] Configurar logs a stdout para Docker

### Prometheus Metrics

#### src/utils/metrics.py
- [ ] Instalar `prometheus_client`
- [ ] Crear métricas:
  - [ ] Counter: `pricing_calculations_total`
  - [ ] Histogram: `pricing_calculation_duration_seconds`
  - [ ] Gauge: `active_matches`
  - [ ] Gauge: `cached_prices`
  - [ ] Counter: `api_requests_total` (por endpoint, status)
  - [ ] Histogram: `api_request_duration_seconds`
  - [ ] Counter: `external_api_calls_total` (por servicio)
  - [ ] Counter: `external_api_errors_total`
- [ ] Implementar middleware de FastAPI para métricas automáticas
- [ ] Exponer endpoint `/metrics` para Prometheus

### Prometheus Configuration

- [ ] Añadir servicio Prometheus a docker-compose.yml
- [ ] Crear `prometheus.yml` con configuración
- [ ] Configurar scrape de métricas de la API
- [ ] Configurar retention de datos

### Grafana Setup

- [ ] Añadir servicio Grafana a docker-compose.yml
- [ ] Crear datasource apuntando a Prometheus
- [ ] Crear dashboard "Smart Pricing Overview":
  - [ ] Panel: Request rate por endpoint
  - [ ] Panel: Request duration (p50, p95, p99)
  - [ ] Panel: Error rate
  - [ ] Panel: Pricing calculations/min
  - [ ] Panel: Cache hit rate
  - [ ] Panel: Active matches
  - [ ] Panel: External API calls
- [ ] Crear dashboard "Business Metrics":
  - [ ] Panel: Revenue por día
  - [ ] Panel: Tickets vendidos por día
  - [ ] Panel: Precio promedio por zona
  - [ ] Panel: Ocupación por zona
- [ ] Exportar dashboards a JSON (version control)

### Alerting

- [ ] Configurar alertas en Prometheus:
  - [ ] High error rate (> 5%)
  - [ ] High latency (p95 > 2s)
  - [ ] Redis down
  - [ ] PostgreSQL down
  - [ ] No pricing updates en última hora
- [ ] Configurar Alertmanager (opcional para MVP)
- [ ] Configurar notificaciones (email, Slack)

### Distributed Tracing (Opcional)

- [ ] Instalar OpenTelemetry SDK
- [ ] Configurar tracing automático para FastAPI
- [ ] Configurar tracing para llamadas DB
- [ ] Configurar tracing para llamadas Redis
- [ ] Configurar export a Jaeger o Zipkin
- [ ] Añadir Jaeger a docker-compose.yml

---

## FASE 13: Testing Completo

### Unit Tests Comprehensivos

- [ ] Asegurar cobertura > 80% en domain/services/
- [ ] Asegurar cobertura > 70% en domain/repositories/
- [ ] Asegurar cobertura > 70% en ml/
- [ ] Ejecutar: `pytest --cov=src tests/unit/ --cov-report=html`
- [ ] Revisar report de cobertura

### Integration Tests

- [ ] Testear flujo completo: Match creation → Pricing calculation → API response
- [ ] Testear workers end-to-end (mock de sleep)
- [ ] Testear integraciones con APIs externas (usando VCR.py)
- [ ] Ejecutar: `pytest tests/integration/`

### Load Testing

#### tests/load/locustfile.py
- [ ] Instalar Locust: `pip install locust`
- [ ] Crear archivo `tests/load/locustfile.py`
- [ ] Definir user behavior:
  - [ ] GET /api/v1/pricing/match/{id}
  - [ ] GET /api/v1/pricing/upcoming
- [ ] Ejecutar: `locust -f tests/load/locustfile.py`
- [ ] Simular 100-1000 usuarios concurrentes
- [ ] Medir throughput, latencias p50/p95/p99
- [ ] Identificar bottlenecks

### E2E Tests (Opcional)

- [ ] Instalar Playwright: `pip install playwright`
- [ ] Crear tests E2E para dashboard (si implementado)
- [ ] Testear flujo completo de usuario
- [ ] Ejecutar: `pytest tests/e2e/`

---

## FASE 14: Containerización & Deployment

### Dockerfiles

#### docker/Dockerfile.api
- [ ] Crear Dockerfile multi-stage
- [ ] Stage 1: Builder (instalar dependencias)
- [ ] Stage 2: Runtime (copiar solo necesario)
- [ ] Exponer puerto 8000
- [ ] CMD: `uvicorn src.api.main:app --host 0.0.0.0 --port 8000`

#### docker/Dockerfile.worker
- [ ] Crear Dockerfile similar a API
- [ ] CMD: `python -m src.workers price_updater`
- [ ] Permitir override via args

#### docker/Dockerfile.dashboard (si aplica)
- [ ] Node multi-stage build
- [ ] Stage 1: Build de React/Next.js
- [ ] Stage 2: Nginx para servir estáticos
- [ ] Exponer puerto 3000 o 80

### Docker Compose - Producción

#### docker-compose.prod.yml
- [ ] Crear archivo separado para producción
- [ ] Configurar restart policies
- [ ] Configurar health checks
- [ ] Configurar resource limits (CPU, memory)
- [ ] Configurar networks
- [ ] Configurar volumes persistentes
- [ ] Usar secrets para credenciales

### Docker Compose - Desarrollo

- [ ] Verificar `docker-compose.yml` existente
- [ ] Asegurar hot-reload de código (volume mounts)
- [ ] Asegurar que todos los servicios arrancan correctamente
- [ ] Ejecutar: `docker-compose up -d`
- [ ] Verificar logs: `docker-compose logs -f`

### CI/CD Pipeline

#### .github/workflows/ci.yml (ejemplo GitHub Actions)
- [ ] Crear archivo de workflow
- [ ] Job: Linting
  - [ ] Ejecutar black, flake8, mypy
- [ ] Job: Unit Tests
  - [ ] Setup Python, instalar deps
  - [ ] Ejecutar pytest con coverage
  - [ ] Upload coverage report
- [ ] Job: Build Docker Images
  - [ ] Build API image
  - [ ] Build worker image
  - [ ] Push a registry (opcional)
- [ ] Trigger: push a main, pull requests

#### .github/workflows/deploy.yml (ejemplo)
- [ ] Crear workflow de deploy
- [ ] Trigger: tag v*
- [ ] Build images
- [ ] Push a Docker registry (DockerHub, ECR, GCR)
- [ ] Deploy a ambiente (Railway, Render, AWS, etc.)

### Infrastructure as Code (Opcional)

- [ ] Crear scripts Terraform para provisionar infraestructura
- [ ] O usar Docker Swarm/Kubernetes manifests
- [ ] Documentar proceso de deployment

---

## FASE 15: Dashboard Frontend (Opcional pero Recomendado)

### Dashboard Setup

- [ ] Crear carpeta `dashboard/`
- [ ] Inicializar proyecto: `npx create-next-app@latest dashboard` o similar
- [ ] Instalar dependencias:
  - [ ] axios o fetch
  - [ ] recharts o chart.js
  - [ ] tailwindcss
  - [ ] shadcn/ui components
  - [ ] zustand o redux

### Dashboard Pages/Views

#### Dashboard Home
- [ ] Crear página principal (`/`)
- [ ] Mostrar métricas clave:
  - [ ] Revenue total
  - [ ] Tickets vendidos hoy
  - [ ] Partidos próximos
  - [ ] Ocupación promedio
- [ ] Gráfico de ventas en el tiempo
- [ ] Alertas importantes

#### Matches List
- [ ] Crear página `/matches`
- [ ] Listar todos los partidos próximos
- [ ] Filtros: competición, fecha, estado
- [ ] Click en partido → detalle

#### Match Detail
- [ ] Crear página `/matches/[id]`
- [ ] Mostrar información del partido
- [ ] Precios actuales por zona (tabla)
- [ ] Gráfico de evolución de precios
- [ ] Gráfico de velocidad de venta
- [ ] Botón para forzar recálculo de precios

#### Zone Management
- [ ] Crear página `/zones`
- [ ] Listar todas las zonas
- [ ] Editar configuración de zona
- [ ] Precios base, min, max
- [ ] Multiplicadores

#### Pricing Rules
- [ ] Crear página `/rules`
- [ ] Mostrar reglas actuales
- [ ] Editor YAML o formulario
- [ ] Validar antes de guardar
- [ ] Botón para recargar reglas

#### Analytics
- [ ] Crear página `/analytics`
- [ ] Gráficos de revenue
- [ ] Gráficos de ocupación
- [ ] Análisis de elasticidad
- [ ] Comparativas entre partidos

### API Client

#### dashboard/src/api/client.ts
- [ ] Crear cliente axios configurado
- [ ] Base URL desde env variable
- [ ] Manejo de errores
- [ ] Interceptors para auth (si aplica)

#### dashboard/src/api/pricing.ts
- [ ] Función `getMatchPricing(matchId: string)`
- [ ] Función `getUpcomingMatches(days: number)`
- [ ] Función `recalculatePricing(matchId: string)`
- [ ] Función `getPricingHistory(matchId: string, hours: number)`

#### dashboard/src/api/admin.ts
- [ ] Función `getRules()`
- [ ] Función `updateRules(rules: any)`
- [ ] Función `getZones()`
- [ ] Función `updateZone(zoneId: string, data: any)`

### State Management

- [ ] Configurar Zustand stores o Redux slices
- [ ] Store para matches
- [ ] Store para pricing
- [ ] Store para configuración
- [ ] Store para user/auth (si aplica)

### Components

- [ ] Crear componente `PricingCard` para mostrar precio de zona
- [ ] Crear componente `MatchCard` para listar partidos
- [ ] Crear componente `PriceHistoryChart`
- [ ] Crear componente `OccupancyChart`
- [ ] Crear componente `Alert` para notificaciones
- [ ] Crear componente `ZoneEditor` para editar zonas
- [ ] Crear componente `RulesEditor`

### Authentication (Opcional)

- [ ] Implementar login simple (JWT)
- [ ] Protected routes
- [ ] Auth context/provider

### Build & Deploy Dashboard

- [ ] Build para producción: `npm run build`
- [ ] Testear build localmente
- [ ] Crear Dockerfile
- [ ] Añadir a docker-compose
- [ ] Deploy junto con API

---

## FASE 16: Documentation

### API Documentation

- [ ] Asegurar que OpenAPI spec está completa
- [ ] Añadir ejemplos a cada endpoint
- [ ] Añadir descripciones detalladas
- [ ] Documentar errores posibles
- [ ] Exportar spec a archivo JSON/YAML

### Code Documentation

- [ ] Revisar docstrings en todas las clases públicas
- [ ] Usar formato Google docstring
- [ ] Documentar parámetros, retornos, excepciones
- [ ] Generar documentación con Sphinx (opcional):
  - [ ] Instalar sphinx
  - [ ] Inicializar: `sphinx-quickstart docs/`
  - [ ] Configurar autodoc
  - [ ] Build: `cd docs && make html`

### User Documentation

#### README.md
- [ ] Describir el proyecto
- [ ] Explicar arquitectura de alto nivel
- [ ] Instrucciones de instalación
- [ ] Instrucciones de ejecución
- [ ] Ejemplos de uso de API
- [ ] Links a documentación adicional

#### docs/ARCHITECTURE.md
- [ ] Crear documento de arquitectura
- [ ] Diagrama de componentes
- [ ] Diagrama de flujo de datos
- [ ] Explicar decisiones de diseño
- [ ] Explicar patrones utilizados

#### docs/DEPLOYMENT.md
- [ ] Guía de deployment paso a paso
- [ ] Requerimientos de infraestructura
- [ ] Configuración de variables de entorno
- [ ] Monitoreo y troubleshooting

#### docs/API.md
- [ ] Guía de uso de API
- [ ] Ejemplos con curl
- [ ] Ejemplos con Python
- [ ] Rate limits y mejores prácticas

#### docs/CONFIGURATION.md
- [ ] Explicar cada archivo de configuración
- [ ] Explicar cada parámetro
- [ ] Ejemplos de configuraciones comunes
- [ ] Tuning de performance

#### docs/ML_MODEL.md
- [ ] Explicar modelo de ML
- [ ] Features utilizadas
- [ ] Proceso de entrenamiento
- [ ] Métricas de evaluación
- [ ] Cómo mejorar el modelo

---

## FASE 17: Security & Best Practices

### Security Hardening

- [ ] Implementar rate limiting en endpoints públicos
- [ ] Implementar autenticación para endpoints admin
- [ ] Validar y sanitizar todos los inputs
- [ ] Usar HTTPS en producción
- [ ] Configurar CORS apropiadamente
- [ ] Hashear credenciales si aplica
- [ ] Rotar secrets regularmente
- [ ] Implementar audit log para cambios críticos

### Environment Variables

- [ ] Listar todas las env vars necesarias en `.env.example`
- [ ] Documentar cada variable
- [ ] Usar valores seguros por defecto
- [ ] No commitear archivos `.env` reales

### Dependency Management

- [ ] Mantener `requirements.txt` actualizado
- [ ] Usar `pip-tools` para pinning de versiones
- [ ] Ejecutar `pip-audit` para vulnerabilidades
- [ ] Actualizar dependencias regularmente

### Code Quality

- [ ] Configurar pre-commit hooks:
  - [ ] black (formatting)
  - [ ] isort (imports)
  - [ ] flake8 (linting)
  - [ ] mypy (type checking)
- [ ] Instalar: `pre-commit install`
- [ ] Ejecutar: `pre-commit run --all-files`

### Performance Optimization

- [ ] Profile código con cProfile
- [ ] Identificar queries N+1 en DB
- [ ] Optimizar queries lentas
- [ ] Añadir índices en DB donde sea necesario
- [ ] Implementar connection pooling apropiado
- [ ] Ajustar tamaños de pool según carga

---

## FASE 18: Advanced Features (Post-MVP)

### A/B Testing for Pricing

- [ ] Implementar framework de A/B testing
- [ ] Dividir partidos en grupos control/tratamiento
- [ ] Aplicar diferentes estrategias de pricing
- [ ] Medir impacto en revenue y ocupación
- [ ] Análisis estadístico de resultados

### Dynamic Capacity Management

- [ ] Implementar sistema para abrir/cerrar zonas dinámicamente
- [ ] Optimizar distribución de aforo según demanda
- [ ] Sugerir zonas a promocionar

### Multi-Competition Support

- [ ] Soportar múltiples equipos/estadios
- [ ] Configuración específica por equipo
- [ ] Dashboard multi-tenant

### Mobile App Integration

- [ ] Crear API endpoints específicos para mobile
- [ ] Push notifications de cambios de precio
- [ ] Alertas personalizadas

### Advanced ML Models

- [ ] LSTM para series temporales
- [ ] Reinforcement Learning para optimización continua
- [ ] Ensemble de modelos
- [ ] Autotuning de hiperparámetros

### Real-time Price Recommendations

- [ ] WebSocket para actualizaciones en tiempo real
- [ ] Sistema de recomendaciones para usuarios
- [ ] Alertas de precio bajo

### Reporting System

- [ ] Generación automática de reportes
- [ ] Export a PDF/Excel
- [ ] Scheduler de reportes periódicos
- [ ] Email delivery

---

## FASE 19: Production Readiness Checklist

### Pre-Production

- [ ] Realizar load testing completo
- [ ] Revisar todos los logs de error
- [ ] Verificar métricas de performance
- [ ] Revisar configuración de producción
- [ ] Preparar plan de rollback
- [ ] Preparar runbook de troubleshooting
- [ ] Configurar alertas críticas
- [ ] Realizar security audit
- [ ] Backup de base de datos configurado
- [ ] Disaster recovery plan documentado

### Production Launch

- [ ] Deploy a ambiente de staging primero
- [ ] Smoke tests en staging
- [ ] Deploy a producción
- [ ] Verificar health checks
- [ ] Monitorear métricas primeras 24h
- [ ] Estar disponible para hot-fixes

### Post-Launch

- [ ] Recoger feedback de usuarios
- [ ] Analizar comportamiento en producción
- [ ] Identificar quick wins para mejorar
- [ ] Planear iteraciones futuras

---

## FASE 20: Maintenance & Iteration

### Regular Tasks

- [ ] Revisar logs diariamente
- [ ] Revisar métricas semanalmente
- [ ] Re-entrenar modelo ML mensualmente
- [ ] Actualizar dependencias mensualmente
- [ ] Backup de base de datos (automatizado)
- [ ] Revisar y ajustar reglas de pricing según resultados

### Continuous Improvement

- [ ] Analizar accuracy del modelo ML
- [ ] Comparar pricing predicho vs optimal en retrospectiva
- [ ] Identificar patrones no capturados
- [ ] Iterar sobre features del modelo
- [ ] Optimizar consultas lentas
- [ ] Refactorizar código según aprendizajes

### Knowledge Base

- [ ] Documentar incidentes y resoluciones
- [ ] Crear FAQs
- [ ] Mantener changelog actualizado
- [ ] Compartir aprendizajes con el equipo

---

## Comandos Útiles de Referencia

### Development

```bash
# Activar entorno virtual
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar API localmente
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Ejecutar worker
python -m src.workers price_updater

# Ejecutar tests
pytest                              # Todos los tests
pytest tests/unit/                  # Solo unit tests
pytest tests/integration/           # Solo integration tests
pytest --cov=src --cov-report=html  # Con coverage

# Formatear código
black src/ tests/
isort src/ tests/

# Linting
flake8 src/ tests/
mypy src/

# Type checking
mypy src/
```

### Docker

```bash
# Build y start todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f api
docker-compose logs -f worker

# Rebuild después de cambios
docker-compose up -d --build

# Stop todos los servicios
docker-compose down

# Limpiar volúmenes
docker-compose down -v
```

### Database

```bash
# Crear tablas
python scripts/init_db.py --create

# Seed data
python scripts/seed_data.py

# Migrations
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

### ML

```bash
# Entrenar modelo
python src/ml/training/train_demand.py --config config/ml_config.yaml

# Evaluar modelo
python src/ml/training/evaluate.py --model-path models/demand_model_v1.pkl
```

---

## Notas Finales

- Cada checkbox puede expandirse en múltiples subtareas según necesidad
- Priorizar MVP: fases 1-9 son críticas, el resto son mejoras
- Mantener commits pequeños y frecuentes
- Escribir tests conforme se desarrolla, no al final
- Documentar decisiones importantes en comments/docs
- Revisar cada fase antes de avanzar a la siguiente
- Iterar sobre feedback real de usuarios

---

**Versión del Plan**: 1.0  
**Última Actualización**: 2024-12-12
