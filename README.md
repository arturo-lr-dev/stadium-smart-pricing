# Smart Pricing System

Sistema inteligente de pricing dinámico para estadios de fútbol basado en ML y análisis de demanda en tiempo real.

## Características Principales

- **Pricing Dinámico**: Ajuste automático de precios basado en múltiples factores
- **Machine Learning**: Predicción de demanda usando modelos entrenados
- **Configuración Flexible**: Todas las reglas de negocio configurables vía YAML
- **API RESTful**: Endpoints completos para gestión y consultas
- **Monitorización**: Métricas con Prometheus y dashboards en Grafana
- **Arquitectura Escalable**: Diseño modular con DI y separation of concerns

## Stack Tecnológico

- **Backend**: Python 3.11+ con FastAPI
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **ML**: scikit-learn, XGBoost, pandas
- **Monitoring**: Prometheus + Grafana
- **Container**: Docker + Docker Compose

## Requisitos Previos

- Python 3.11 o superior
- Docker y Docker Compose
- Git

## Instalación

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd stadium-smart-pricing
```

### 2. Configurar entorno virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Linux/Mac:
source venv/bin/activate
# En Windows:
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env con tus configuraciones
nano .env
```

### 5. Levantar servicios con Docker

```bash
# Iniciar PostgreSQL, Redis, Prometheus y Grafana
docker-compose up -d

# Verificar que los servicios están corriendo
docker-compose ps
```

### 6. Inicializar base de datos

```bash
# Crear tablas
python scripts/init_db.py --create

# Cargar datos de prueba (opcional)
python scripts/seed_data.py
```

## Ejecutar la Aplicación

### Modo Desarrollo

```bash
# Ejecutar API con hot-reload
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en: http://localhost:8000

- Documentación Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Ejecutar Workers

```bash
# Worker de actualización de precios
python -m src.workers price_updater

# Worker de recolección de datos
python -m src.workers data_collector
```

## Testing

```bash
# Ejecutar todos los tests
pytest

# Solo unit tests
pytest tests/unit/

# Con coverage
pytest --cov=src --cov-report=html

# Ver reporte de coverage
open htmlcov/index.html
```

## Calidad de Código

```bash
# Formatear código
black src/ tests/
isort src/ tests/

# Linting
flake8 src/ tests/

# Type checking
mypy src/
```

## Servicios Disponibles

Después de ejecutar `docker-compose up -d`:

| Servicio | Puerto | URL | Credenciales |
|----------|--------|-----|--------------|
| API | 8000 | http://localhost:8000 | - |
| PostgreSQL | 5432 | localhost:5432 | postgres/postgres |
| Redis | 6379 | localhost:6379 | - |
| Prometheus | 9090 | http://localhost:9090 | - |
| Grafana | 3001 | http://localhost:3001 | admin/admin |
| pgAdmin | 5050 | http://localhost:5050 | admin@smartpricing.com/admin |

## Estructura del Proyecto

```
stadium-smart-pricing/
├── config/                 # Archivos de configuración YAML
├── src/
│   ├── api/               # FastAPI endpoints
│   ├── core/              # Configuración, logging, DI
│   ├── domain/            # Modelos, servicios, repositorios
│   ├── ml/                # Machine Learning
│   ├── integrations/      # APIs externas
│   ├── workers/           # Background workers
│   └── utils/             # Utilidades
├── tests/                 # Tests unitarios e integración
├── scripts/               # Scripts de inicialización
├── docker/                # Configuración Docker
└── docs/                  # Documentación

```

## Configuración

El sistema utiliza configuración por capas:

1. **Variables de entorno** (.env): Configuración de infraestructura
2. **Archivos YAML** (config/): Reglas de negocio y parámetros

### Archivos de Configuración

- `config/base.yaml`: Configuración general de la aplicación
- `config/pricing_rules.yaml`: Reglas de pricing y multiplicadores
- `config/zones.yaml`: Definición de zonas del estadio
- `config/competitions.yaml`: Competiciones y sus factores

## API Endpoints

### Pricing

- `GET /api/v1/pricing/match/{match_id}`: Obtener precios de un partido
- `GET /api/v1/pricing/match/{match_id}/zone/{zone_id}`: Precio de zona específica
- `GET /api/v1/pricing/upcoming`: Precios de próximos partidos
- `POST /api/v1/pricing/match/{match_id}/recalculate`: Forzar recálculo

### Admin

- `GET /api/v1/admin/rules`: Obtener reglas actuales
- `PUT /api/v1/admin/rules`: Actualizar reglas
- `GET /api/v1/admin/zones`: Listar zonas
- `GET /api/v1/admin/matches`: Listar partidos

### Analytics

- `GET /api/v1/analytics/revenue`: Análisis de ingresos
- `GET /api/v1/analytics/occupancy`: Estadísticas de ocupación

## Monitorización

### Prometheus

Accede a Prometheus en http://localhost:9090

Métricas disponibles:
- `pricing_calculations_total`: Total de cálculos de pricing
- `api_requests_total`: Total de requests
- `api_request_duration_seconds`: Duración de requests

### Grafana

Accede a Grafana en http://localhost:3001 (admin/admin)

Dashboards configurados:
- Smart Pricing Overview
- Business Metrics

## Machine Learning

### Entrenar Modelo

```bash
python src/ml/training/train_demand.py
```

### Evaluar Modelo

```bash
python src/ml/training/evaluate.py --model-path models/demand_model.pkl
```

## Documentación Adicional

- [Arquitectura del Sistema](docs/ARCHITECTURE.md) - Diseño, patrones y componentes principales
- [Guía de Configuración](docs/CONFIGURATION.md) - Configuración YAML y variables de entorno
- [Modelo de Machine Learning](docs/ML_MODEL.md) - Feature engineering, entrenamiento y deployment
- [Plan de Implementación](docs/IMPLEMENTATION_PLAN.md) - Roadmap de desarrollo por fases
- [Plan de Integración de Cache](docs/CACHE_INTEGRATION_PLAN.md) - Estrategias de caching

## Troubleshooting

### La base de datos no conecta

```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps postgres

# Ver logs
docker-compose logs postgres

# Reiniciar servicio
docker-compose restart postgres
```

### Redis no responde

```bash
# Verificar Redis
docker-compose ps redis

# Probar conexión
redis-cli -h localhost -p 6379 ping
```

## Contribuir

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

[MIT License](LICENSE)

## Contacto

Smart Pricing Team - @legasint

Project Link: [https://github.com/username/stadium-smart-pricing](https://github.com/username/stadium-smart-pricing)
