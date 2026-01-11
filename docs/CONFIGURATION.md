# Guía de Configuración - Smart Pricing

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Variables de Entorno](#variables-de-entorno)
3. [Configuración Base](#configuración-base)
4. [Reglas de Pricing](#reglas-de-pricing)
5. [Zonas del Estadio](#zonas-del-estadio)
6. [Competiciones](#competiciones)
7. [Hot-Reloading](#hot-reloading)
8. [Ejemplos Prácticos](#ejemplos-prácticos)

## Introducción

El sistema Smart Pricing utiliza una configuración por capas:

1. **Variables de entorno** (.env): Configuración de infraestructura (conexiones, secretos)
2. **Archivos YAML** (config/): Reglas de negocio y parámetros operacionales

Este diseño permite:
- Cambiar reglas de negocio sin modificar código
- Hot-reloading de configuración sin reiniciar servicios
- Diferentes configuraciones por entorno (dev, staging, prod)
- Versionado de reglas de negocio en Git

## Variables de Entorno

### Archivo .env

Crear archivo `.env` en la raíz del proyecto:

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smart_pricing
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_PRE_PING=true

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_RELOAD=false  # true solo en desarrollo

# External APIs
FOOTBALL_DATA_API_KEY=your_api_key_here
FOOTBALL_DATA_API_URL=https://api.football-data.org/v4
WEATHER_API_KEY=your_weather_api_key
WEATHER_API_URL=https://api.openweathermap.org/data/2.5

# ML Model Configuration
ML_MODEL_PATH=models/demand_model.pkl
ML_MODEL_TYPE=random_forest  # o gradient_boosting
ML_FALLBACK_TO_HEURISTIC=true

# Worker Configuration
WORKER_PRICE_UPDATE_INTERVAL=300  # segundos (5 minutos)
WORKER_DATA_COLLECTOR_INTERVAL=3600  # 1 hora
WORKER_MODEL_RETRAIN_INTERVAL=604800  # 7 días

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json  # json o text
LOG_FILE=logs/smart_pricing.log

# Monitoring
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
GRAFANA_ENABLED=true

# Environment
ENVIRONMENT=production  # development, staging, production
```

### Variables por Entorno

#### Desarrollo
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smart_pricing_dev
API_RELOAD=true
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

#### Staging
```bash
DATABASE_URL=postgresql://postgres:postgres@staging-db:5432/smart_pricing_staging
API_RELOAD=false
LOG_LEVEL=INFO
ENVIRONMENT=staging
```

#### Producción
```bash
DATABASE_URL=postgresql://user:password@prod-db:5432/smart_pricing
API_RELOAD=false
LOG_LEVEL=WARNING
ENVIRONMENT=production
```

## Configuración Base

### config/base.yaml

Configuración general de la aplicación:

```yaml
# Configuración de Base de Datos
database:
  pool_size: 20
  max_overflow: 10
  pool_pre_ping: true
  pool_recycle: 3600  # Reciclar conexiones cada hora
  echo: false  # true para ver SQL queries en desarrollo

# Configuración de Redis Cache
cache:
  default_ttl: 300  # 5 minutos

  # Estrategias de cache específicas
  strategies:
    pricing:
      ttl: 300  # 5 minutos
      key_pattern: "pricing:match:{match_id}"

    inventory:
      ttl: 120  # 2 minutos
      key_pattern: "inventory:match:{match_id}:zone:{zone_id}"

    external_data:
      ttl: 3600  # 1 hora
      key_pattern: "external_data:{key}"

# Configuración del Motor de Pricing
pricing_engine:
  # Restricciones de cambio de precio
  max_price_change_percent: 0.20  # Máximo 20% de cambio por ajuste
  max_changes_per_day: 5  # Máximo 5 ajustes de precio al día
  min_time_between_changes_hours: 2  # Mínimo 2 horas entre cambios
  blackout_hours_before_match: 24  # No cambiar precio 24h antes

  # Ajuste gradual (smoothing)
  gradual_adjustment_enabled: true
  adjustment_smoothing_factor: 0.5  # 0-1, más alto = cambios más suaves

  # Validación de precios
  validate_min_max: true  # Validar contra min/max de zona
  allow_zero_prices: false

# Configuración de Machine Learning
ml:
  model_path: "models/demand_model.pkl"
  model_type: "random_forest"  # random_forest, gradient_boosting

  # Fallback a heurística si modelo no disponible
  fallback_to_heuristic: true

  # Hiperparámetros (Random Forest)
  random_forest:
    n_estimators: 100
    max_depth: 10
    min_samples_split: 2
    min_samples_leaf: 1
    random_state: 42

  # Hiperparámetros (Gradient Boosting)
  gradient_boosting:
    n_estimators: 100
    learning_rate: 0.1
    max_depth: 5
    random_state: 42

  # Re-entrenamiento
  retrain_interval_days: 7
  min_samples_for_training: 1000
  validation_split: 0.2

# Configuración de Workers
workers:
  price_updater:
    enabled: true
    interval_seconds: 300  # 5 minutos
    lookahead_days: 30  # Calcular precios próximos 30 días
    max_consecutive_errors: 5
    backoff_multiplier: 2  # Exponential backoff

  data_collector:
    enabled: true
    interval_seconds: 3600  # 1 hora
    sources:
      - football_data_api
      - weather_api

  model_retrainer:
    enabled: true
    interval_days: 7
    schedule_time: "03:00"  # 3 AM
    backup_old_model: true

# Integraciones Externas
external_apis:
  football_data:
    base_url: "https://api.football-data.org/v4"
    rate_limit: 10  # requests por minuto
    timeout_seconds: 10
    retry_attempts: 3
    retry_backoff_factor: 2

  weather_api:
    base_url: "https://api.openweathermap.org/data/2.5"
    timeout_seconds: 5
    cache_ttl: 3600

# Monitorización
monitoring:
  prometheus:
    enabled: true
    port: 9090
    metrics_path: "/metrics"

  health_check:
    enabled: true
    path: "/health"
    check_database: true
    check_redis: true
    check_external_apis: false

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "json"  # json, text

  # Campos adicionales en logs JSON
  include_fields:
    - timestamp
    - level
    - message
    - module
    - function
    - line_number
    - request_id

  # Logs de SQL (solo desarrollo)
  log_sql_queries: false
```

## Reglas de Pricing

### config/pricing_rules.yaml

Define todos los multiplicadores y factores de pricing:

#### Multiplicadores por Competición

```yaml
competition_multipliers:
  # LaLiga
  laliga:
    base: 1.0
    vs_top3: 2.5  # Contra Real Madrid, Barcelona, Atlético
    vs_mid_table: 1.0
    vs_bottom3: 0.8

  # Copa del Rey (progresivo por ronda)
  copa_del_rey:
    round_32: 0.7
    round_16: 0.9
    quarterfinals: 1.3
    semifinals: 1.8
    final: 3.0

  # Champions League
  champions_league:
    group_stage: 2.0
    round_16: 2.5
    quarterfinals: 3.0
    semifinals: 4.0
    final: 5.0

  # Europa League
  europa_league:
    group_stage: 1.2
    knockout: 1.5
    final: 2.5

  # Amistosos
  friendly:
    regular: 0.5
    prestigious: 0.8
```

#### Multiplicadores por Rival

```yaml
rival_multipliers:
  # Rivalidades máximas
  "Real Madrid": 3.0
  "FC Barcelona": 3.0
  "Atletico Madrid": 3.0

  # Equipos grandes
  "Sevilla FC": 1.8
  "Real Betis": 1.6
  "Athletic Club": 1.6
  "Real Sociedad": 1.5
  "Villarreal CF": 1.5

  # Equipos medianos
  "Valencia CF": 1.3
  "Celta Vigo": 1.2
  "Espanyol": 1.2

  # Equipos pequeños/recién ascendidos
  default: 1.0
  newly_promoted: 0.85
```

#### Factores de Decay Temporal

```yaml
time_decay_factors:
  # Días hasta el partido → multiplicador
  ranges:
    - days_from: 60
      days_to: 9999
      multiplier: 0.75
      description: "Early bird discount"

    - days_from: 45
      days_to: 59
      multiplier: 0.80
      description: "Very early purchase"

    - days_from: 30
      days_to: 44
      multiplier: 0.85
      description: "Anticipation discount"

    - days_from: 21
      days_to: 29
      multiplier: 0.90
      description: "Moderate advance"

    - days_from: 14
      days_to: 20
      multiplier: 1.0
      description: "Base price (2-3 weeks)"

    - days_from: 7
      days_to: 13
      multiplier: 1.15
      description: "Late purchase premium"

    - days_from: 3
      days_to: 6
      multiplier: 1.30
      description: "Last minute premium"

    - days_from: 1
      days_to: 2
      multiplier: 1.40
      description: "Very last minute"

    - days_from: 0
      days_to: 0
      multiplier: 1.50
      description: "Day of match maximum"
```

#### Presión de Inventario

```yaml
inventory_pressure_factors:
  # % Ocupación → multiplicador
  ranges:
    - occupancy_from: 0
      occupancy_to: 20
      multiplier: 0.80
      description: "Aggressive discount - very low sales"

    - occupancy_from: 20
      occupancy_to: 40
      multiplier: 0.90
      description: "Moderate discount - below target"

    - occupancy_from: 40
      occupancy_to: 60
      multiplier: 1.0
      description: "Base price - on target"

    - occupancy_from: 60
      occupancy_to: 75
      multiplier: 1.05
      description: "Slight premium - good demand"

    - occupancy_from: 75
      occupancy_to: 85
      multiplier: 1.15
      description: "Moderate premium - high demand"

    - occupancy_from: 85
      occupancy_to: 92
      multiplier: 1.30
      description: "Strong premium - very high demand"

    - occupancy_from: 92
      occupancy_to: 97
      multiplier: 1.50
      description: "Near sellout premium"

    - occupancy_from: 97
      occupancy_to: 100
      multiplier: 1.75
      description: "Maximum premium - almost sold out"
```

#### Condiciones Especiales

```yaml
special_conditions:
  # Día de la semana
  weekday_multipliers:
    monday: 0.95
    tuesday: 0.95
    wednesday: 0.95
    thursday: 0.95
    friday: 1.00
    saturday: 1.15
    sunday: 1.10

  # Hora del partido
  time_of_day_multipliers:
    morning: 0.90      # 10:00-13:59
    afternoon: 1.00    # 14:00-17:59
    evening: 1.15      # 18:00-20:59
    night: 1.10        # 21:00-23:59

  # Festivos
  holiday_multiplier: 1.25
  holiday_eve_multiplier: 1.15

  # Condiciones de partido
  derby_multiplier: 2.0
  title_decider_multiplier: 2.5
  european_qualification_multiplier: 1.8
  relegation_battle_multiplier: 1.5

# Estrategias Dinámicas
dynamic_strategies:
  # Ajuste por velocidad de ventas
  velocity_based:
    enabled: true
    thresholds:
      very_high: 50  # tickets/hora
      high: 20
      medium: 10
      low: 5
      very_low: 2

    multipliers:
      very_high: 1.20
      high: 1.10
      medium: 1.00
      low: 0.95
      very_low: 0.85

  # Last-minute discount
  last_minute_discount:
    enabled: true
    trigger_days_before: 3
    min_occupancy_percent: 40
    max_occupancy_percent: 60
    discount_percent: 0.15  # 15% off

  # Group discounts
  group_discounts:
    enabled: true
    tiers:
      - min_tickets: 4
        max_tickets: 9
        discount: 0.05  # 5%

      - min_tickets: 10
        max_tickets: 19
        discount: 0.10  # 10%

      - min_tickets: 20
        max_tickets: 999
        discount: 0.15  # 15%

  # Loyalty discounts
  loyalty_discounts:
    club_member: 0.10  # 10%
    season_ticket_holder: 0.15  # 15%
    premium_member: 0.20  # 20%
```

#### Ajustes por Clima

```yaml
weather_adjustments:
  # Solo aplica para estadios sin techo cerrado
  enabled: true

  conditions:
    clear_sky: 1.00
    partly_cloudy: 0.98
    cloudy: 0.95
    light_rain: 0.90
    moderate_rain: 0.85
    heavy_rain: 0.80
    storm: 0.75
    extreme_heat: 0.95  # >35°C
    extreme_cold: 0.90  # <5°C
```

## Zonas del Estadio

### config/zones.yaml

Define la estructura del estadio con capacidades y precios:

```yaml
stadium:
  name: "Estadio Son Moix"
  total_capacity: 23142
  venue_id: 1

zones:
  # ZONAS VIP (470 asientos)
  - id: 1
    name: "Palcos VIP Principal"
    category: VIP
    capacity: 200
    base_price: 180.00
    min_price: 120.00
    max_price: 450.00
    price_multiplier: 2.5
    amenities:
      - lounge_access
      - premium_food
      - parking
      - exclusive_entrance
    description: "Palcos VIP en tribuna principal con mejores vistas"

  - id: 2
    name: "Zona Presidencial"
    category: VIP
    capacity: 120
    base_price: 220.00
    min_price: 150.00
    max_price: 550.00
    price_multiplier: 3.0
    amenities:
      - presidential_lounge
      - gourmet_menu
      - vip_parking
      - meet_greet_access

  # ZONAS PREMIUM (6,100 asientos)
  - id: 10
    name: "Tribuna Principal Centro"
    category: Premium
    capacity: 2500
    base_price: 65.00
    min_price: 45.00
    max_price: 130.00
    price_multiplier: 1.3
    amenities:
      - covered_seating
      - good_view

  - id: 11
    name: "Tribuna Principal Lateral Derecha"
    category: Premium
    capacity: 1800
    base_price: 55.00
    min_price: 38.00
    max_price: 110.00
    price_multiplier: 1.2

  # ZONAS STANDARD (14,600 asientos)
  - id: 20
    name: "Preferencia Fondo Norte"
    category: Standard
    capacity: 3200
    base_price: 40.00
    min_price: 28.00
    max_price: 80.00
    price_multiplier: 1.0

  - id: 21
    name: "Preferencia Fondo Sur"
    category: Standard
    capacity: 3200
    base_price: 40.00
    min_price: 28.00
    max_price: 80.00
    price_multiplier: 1.0

  # ZONAS REDUCIDAS (2,800 asientos)
  - id: 30
    name: "Anfiteatro Norte"
    category: Reduced
    capacity: 800
    base_price: 25.00
    min_price: 18.00
    max_price: 50.00
    price_multiplier: 0.7
    amenities:
      - high_altitude_view

  # ZONAS ESPECIALES (972 asientos)
  - id: 40
    name: "Zona Visitante"
    category: Visitor
    capacity: 872
    base_price: 35.00
    min_price: 35.00  # Precio fijo
    max_price: 35.00  # Precio fijo
    price_multiplier: 1.0
    dynamic_pricing_enabled: false  # Precio fijo

  - id: 41
    name: "Zona Accesibilidad"
    category: Accessibility
    capacity: 100
    base_price: 20.00
    min_price: 20.00  # Precio fijo reducido
    max_price: 20.00
    price_multiplier: 1.0
    dynamic_pricing_enabled: false
    amenities:
      - wheelchair_accessible
      - companion_seat
      - elevator_access
```

### Categorías de Zonas

| Categoría | Características | Multiplicador Base |
|-----------|----------------|-------------------|
| VIP | Mejor vista, amenities premium | 2.5-3.0 |
| Premium | Buena vista, cubierta | 1.2-1.3 |
| Standard | Vista estándar | 1.0 |
| Reduced | Vista limitada, altura | 0.7 |
| Visitor | Zona visitante (precio fijo) | 1.0 |
| Accessibility | Accesibilidad (precio fijo) | 1.0 |

## Competiciones

### config/competitions.yaml

```yaml
competitions:
  - id: "laliga"
    name: "LaLiga Santander"
    type: "league"
    base_multiplier: 1.0
    features:
      - domestic
      - regular_season

    # Multiplicadores adicionales por contexto
    context_multipliers:
      vs_top3: 2.5
      vs_mid_table: 1.0
      vs_bottom3: 0.8
      title_race: 1.5
      relegation_battle: 1.3

    # Preferencias de horario
    preferred_times:
      saturday_evening: 1.15
      sunday_afternoon: 1.10

  - id: "copa_del_rey"
    name: "Copa del Rey"
    type: "cup"
    base_multiplier: 0.7
    features:
      - domestic
      - knockout
      - stage_based_pricing

    stage_multipliers:
      round_32: 0.7
      round_16: 0.9
      quarterfinals: 1.3
      semifinals: 1.8
      final: 3.0

  - id: "champions_league"
    name: "UEFA Champions League"
    type: "european_cup"
    base_multiplier: 3.0
    features:
      - international
      - prestigious
      - stage_based_pricing

    stage_multipliers:
      group_stage: 2.0
      round_16: 2.5
      quarterfinals: 3.0
      semifinals: 4.0
      final: 5.0

  - id: "europa_league"
    name: "UEFA Europa League"
    type: "european_cup"
    base_multiplier: 1.8
    features:
      - international
      - stage_based_pricing

    stage_multipliers:
      group_stage: 1.2
      knockout: 1.5
      quarterfinals: 1.8
      semifinals: 2.2
      final: 2.5

  - id: "friendly"
    name: "Partido Amistoso"
    type: "friendly"
    base_multiplier: 0.5
    features:
      - friendly
      - flexible_pricing

    context_multipliers:
      prestigious_opponent: 0.8
      preseason: 0.6
```

## Hot-Reloading

### Recargar Configuración Sin Reinicio

El sistema soporta hot-reloading de archivos YAML:

```python
# Endpoint de administración
POST /api/v1/admin/reload-config

Response:
{
  "status": "success",
  "reloaded": [
    "pricing_rules.yaml",
    "zones.yaml",
    "competitions.yaml"
  ],
  "timestamp": "2026-01-11T10:30:00Z"
}
```

### Desde Código

```python
from src.core.config import settings

# Recargar solo pricing rules
settings.rules_engine.reload_rules()

# Recargar todas las configuraciones YAML
settings.reload_yaml_configs()
```

### Workflow Recomendado

1. Modificar archivo YAML en `config/`
2. Validar sintaxis YAML
3. Hacer commit en Git
4. Llamar endpoint de reload o reiniciar servicio

```bash
# Validar YAML
python scripts/validate_config.py config/pricing_rules.yaml

# Reload via API
curl -X POST http://localhost:8000/api/v1/admin/reload-config \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Ejemplos Prácticos

### Ejemplo 1: Aumentar Precio para Partido Importante

```yaml
# En pricing_rules.yaml
special_conditions:
  # Añadir nuevo multiplicador para partido específico
  special_matches:
    - match_id: 12345
      description: "Clásico vs Real Madrid"
      multiplier: 3.5
      start_date: "2026-03-15"
      end_date: "2026-03-15"
```

### Ejemplo 2: Descuento por Promoción

```yaml
# En pricing_rules.yaml
dynamic_strategies:
  promotional_discount:
    enabled: true
    code: "PROMO2026"
    discount_percent: 0.20  # 20% off
    valid_from: "2026-02-01"
    valid_until: "2026-02-28"
    applicable_zones:
      - 20  # Preferencia Fondo Norte
      - 21  # Preferencia Fondo Sur
    max_uses: 5000
```

### Ejemplo 3: Ajustar Capacidad de Zona

```yaml
# En zones.yaml
zones:
  - id: 10
    name: "Tribuna Principal Centro"
    capacity: 2300  # Reducida de 2500 por obras
    # ... resto de configuración
```

### Ejemplo 4: Nuevo Tipo de Competición

```yaml
# En competitions.yaml
competitions:
  - id: "supercopa_espana"
    name: "Supercopa de España"
    type: "super_cup"
    base_multiplier: 2.5
    features:
      - domestic
      - prestigious
      - short_tournament
```

## Validación de Configuración

### Script de Validación

```bash
# Validar toda la configuración
python scripts/validate_config.py --all

# Validar archivo específico
python scripts/validate_config.py config/pricing_rules.yaml

# Output esperado:
✓ pricing_rules.yaml: Valid
✓ zones.yaml: Valid (23,142 total capacity)
✓ competitions.yaml: Valid (12 competitions defined)
✓ base.yaml: Valid
```

### Validaciones Automáticas

El sistema valida automáticamente:

- **Sintaxis YAML:** Formato correcto
- **Tipos de datos:** Números, strings, booleanos
- **Rangos:** Multiplicadores entre límites razonables
- **Capacidad total:** Suma de zonas = capacidad estadio
- **Precios:** min_price ≤ base_price ≤ max_price
- **Referencias:** IDs de zonas/competiciones válidos

## Troubleshooting

### Error: "Invalid YAML syntax"

```bash
# Validar sintaxis
python -c "import yaml; yaml.safe_load(open('config/pricing_rules.yaml'))"
```

### Error: "Cache connection failed"

Verificar Redis:
```bash
redis-cli -h localhost -p 6379 ping
# Debe responder: PONG
```

### Error: "Database pool exhausted"

Aumentar pool size en `base.yaml`:
```yaml
database:
  pool_size: 30  # Aumentar de 20
  max_overflow: 15  # Aumentar de 10
```

## Mejores Prácticas

1. **Versionado:** Hacer commit de cambios de configuración
2. **Testing:** Probar cambios en staging antes de producción
3. **Backup:** Mantener backup de configuraciones funcionando
4. **Documentación:** Comentar cambios no obvios en YAML
5. **Monitoreo:** Vigilar métricas después de cambios de config
6. **Rollback:** Tener plan de rollback para cambios críticos

## Referencias

- [Arquitectura](ARCHITECTURE.md)
- [Plan de Implementación](IMPLEMENTATION_PLAN.md)
- [Modelo ML](ML_MODEL.md)

## Contacto

Smart Pricing Team - @legasint
