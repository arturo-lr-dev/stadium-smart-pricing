Principios Fundamentales
IMPORTANTE: Sigue estos principios en cada decisión de diseño:

Configuración sobre código: Todo parámetro de negocio debe ser configurable via YAML/JSON
Separation of Concerns: Cada módulo tiene una responsabilidad única
Dependency Injection: Usa DI para facilitar testing y escalabilidad
API-First: Diseña APIs antes de la implementación
Idempotencia: Operaciones repetibles sin efectos secundarios
Observabilidad: Logs estructurados, métricas y trazas desde el día 1

Stack Tecnológico Recomendado
yamlBackend:
  Core: Python 3.11+ (FastAPI)
  Database: PostgreSQL 15+ (datos transaccionales)
  Cache: Redis 7+ (precios actuales)
  Time-Series: TimescaleDB o InfluxDB (métricas históricas)
  Message Queue: RabbitMQ o AWS SQS (procesamiento asíncrono)
  ML: scikit-learn, XGBoost, pandas
  
Infraestructura:
  Container: Docker + Docker Compose
  Orchestration: Kubernetes (futuro) / Docker Swarm (MVP)
  CI/CD: GitHub Actions
  Monitoring: Prometheus + Grafana
  Logging: ELK Stack (Elasticsearch, Logstash, Kibana)

Frontend (Dashboard):
  Framework: React + TypeScript o Next.js
  UI: Tailwind CSS + shadcn/ui
  Charts: Recharts o Chart.js
  State: Zustand o Redux Toolkit
```

## Estructura del Proyecto
```
smart-pricing/
├── config/
│   ├── base.yaml              # Configuración base
│   ├── pricing_rules.yaml     # Reglas de negocio
│   ├── zones.yaml             # Definición de zonas del estadio
│   └── competitions.yaml      # Competiciones y multiplicadores
├── src/
│   ├── api/                   # FastAPI endpoints
│   │   ├── __init__.py
│   │   ├── main.py           # Entry point
│   │   ├── pricing.py        # Endpoints de pricing
│   │   ├── admin.py          # Endpoints administrativos
│   │   ├── analytics.py      # Endpoints de métricas
│   │   └── webhooks.py       # Webhooks externos
│   ├── core/
│   │   ├── config.py         # Cargador de configuración
│   │   ├── dependencies.py   # DI container
│   │   ├── logging.py        # Setup de logging
│   │   └── exceptions.py     # Custom exceptions
│   ├── domain/
│   │   ├── models/           # Domain models (Pydantic)
│   │   │   ├── match.py
│   │   │   ├── ticket.py
│   │   │   ├── zone.py
│   │   │   └── pricing.py
│   │   ├── services/         # Business logic
│   │   │   ├── pricing_engine.py
│   │   │   ├── demand_predictor.py
│   │   │   ├── inventory_manager.py
│   │   │   └── rules_engine.py
│   │   └── repositories/     # Data access layer
│   │       ├── match_repo.py
│   │       ├── sales_repo.py
│   │       └── pricing_repo.py
│   ├── ml/
│   │   ├── models/           # ML models
│   │   │   ├── demand_model.py
│   │   │   ├── elasticity_model.py
│   │   │   └── base_model.py
│   │   ├── features/         # Feature engineering
│   │   │   ├── match_features.py
│   │   │   ├── temporal_features.py
│   │   │   └── external_features.py
│   │   ├── training/         # Scripts de entrenamiento
│   │   │   ├── train_demand.py
│   │   │   └── evaluate.py
│   │   └── inference/        # Predicción en tiempo real
│   │       └── predictor.py
│   ├── integrations/         # Integraciones externas
│   │   ├── football_data.py  # API de datos deportivos
│   │   ├── weather_api.py    # API de clima
│   │   ├── analytics.py      # Google Analytics
│   │   └── ticketing_system.py # Sistema de ticketing existente
│   ├── workers/              # Background workers
│   │   ├── price_updater.py  # Actualiza precios periódicamente
│   │   ├── data_collector.py # Recolecta datos externos
│   │   └── model_retrainer.py # Reentrena modelos
│   └── utils/
│       ├── datetime_helpers.py
│       ├── validators.py
│       └── metrics.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
│   ├── init_db.py            # Inicializar BD
│   ├── seed_data.py          # Datos de prueba
│   └── migrate.py            # Migraciones
├── dashboard/                 # Frontend dashboard
│   ├── src/
│   ├── public/
│   └── package.json
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   └── Dockerfile.dashboard
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── README.md
└── .env.example

Checklist de Implementación
Para cada fase, el agente debe:

Crear la estructura de carpetas exacta
Implementar modelos Pydantic con validaciones
Crear tests unitarios para cada componente
Añadir logging estructurado con contexto
Documentar con docstrings Google style
Configurar via YAML todos los parámetros de negocio
Implementar caching en Redis para respuestas frecuentes
Añadir métricas (Prometheus) para monitorización

Si creas archivos de documentacion despues de una implementacion crealos en la carpeta /docs
