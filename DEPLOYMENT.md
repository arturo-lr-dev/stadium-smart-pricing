# 🚀 Guía de Deployment - Smart Pricing System

Esta guía te ayudará a desplegar el sistema de pricing dinámico en diferentes plataformas cloud.

## 📋 Requisitos Previos

- Cuenta en la plataforma de deployment elegida
- Git repository (GitHub, GitLab, etc.)
- Variables de entorno configuradas (ver `.env.example`)

---

## 🎯 Opción 1: Render (Recomendado - Más Fácil)

### Ventajas
✅ Deploy automático desde GitHub
✅ PostgreSQL y Redis incluidos
✅ Plan gratuito disponible
✅ SSL/HTTPS automático
✅ Fácil configuración

### Pasos

1. **Sube el código a GitHub**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Crea cuenta en Render**
   - Ve a [render.com](https://render.com) y regístrate

3. **Crea la base de datos PostgreSQL**
   - Dashboard → New → PostgreSQL
   - Name: `smart-pricing-db`
   - Plan: Free (o Starter para producción)
   - Copia la `Internal Database URL`

4. **Crea Redis**
   - Dashboard → New → Redis
   - Name: `smart-pricing-redis`
   - Plan: Free
   - Copia la `Internal Redis URL`

5. **Crea el Web Service**
   - Dashboard → New → Web Service
   - Connect tu repositorio de GitHub
   - Configuración:
     - **Name**: `smart-pricing-api`
     - **Environment**: `Python 3`
     - **Build Command**:
       ```bash
       pip install -r requirements.txt && chmod +x scripts/deploy_init.sh && ./scripts/deploy_init.sh
       ```
     - **Start Command**:
       ```bash
       uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
       ```

6. **Configura Variables de Entorno**
   En el dashboard del Web Service → Environment:
   ```
   DATABASE_HOST=<from PostgreSQL service>
   DATABASE_PORT=5432
   DATABASE_NAME=smart_pricing
   DATABASE_USER=<from PostgreSQL service>
   DATABASE_PASSWORD=<from PostgreSQL service>
   REDIS_HOST=<from Redis service>
   REDIS_PORT=6379
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   SECRET_KEY=<generate-random-string>
   ```

7. **Deploy!**
   - Render detectará cambios y hará deploy automático
   - La URL será algo como: `https://smart-pricing-api.onrender.com`

8. **Verifica**
   - Abre `https://tu-app.onrender.com/docs`
   - Verifica `https://tu-app.onrender.com/health`
   - Accede al dashboard: `https://tu-app.onrender.com/dashboard/`

---

## 🚂 Opción 2: Railway

### Ventajas
✅ Deploy en 60 segundos
✅ PostgreSQL y Redis con un clic
✅ $5 crédito gratis/mes
✅ Muy intuitivo

### Pasos

1. **Sube código a GitHub**

2. **Crea proyecto en Railway**
   - Ve a [railway.app](https://railway.app)
   - New Project → Deploy from GitHub repo
   - Selecciona tu repositorio

3. **Añade servicios**
   - Haz clic en "+ New"
   - Añade: PostgreSQL
   - Añade: Redis
   - Railway auto-configurará las variables de entorno

4. **Configuración del servicio**
   Railway detectará automáticamente que es Python

   Si necesitas personalizar, añade en Settings:
   - **Build Command**: `pip install -r requirements.txt && ./scripts/deploy_init.sh`
   - **Start Command**: `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

5. **Variables adicionales**
   ```
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   SECRET_KEY=<random-string>
   FOOTBALL_DATA_API_KEY=<optional>
   WEATHER_API_KEY=<optional>
   ```

6. **Deploy**
   - Railway hace deploy automático
   - Te dará una URL pública

---

## ✈️ Opción 3: Fly.io

### Ventajas
✅ Muy rápido (edge computing)
✅ Plan gratuito generoso
✅ Control fino de configuración

### Pasos

1. **Instala Fly CLI**
   ```bash
   # macOS
   brew install flyctl

   # Linux
   curl -L https://fly.io/install.sh | sh

   # Windows
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```

2. **Login**
   ```bash
   fly auth login
   ```

3. **Crea aplicación**
   ```bash
   fly launch
   ```

   Fly detectará el `Dockerfile` y configurará automáticamente.

4. **Crea PostgreSQL**
   ```bash
   fly postgres create --name smart-pricing-db
   fly postgres attach smart-pricing-db
   ```

5. **Crea Redis (usando Upstash)**
   ```bash
   fly redis create
   ```

6. **Configura secrets**
   ```bash
   fly secrets set \
     SECRET_KEY=<random-string> \
     ENVIRONMENT=production \
     LOG_LEVEL=INFO
   ```

7. **Deploy**
   ```bash
   fly deploy
   ```

8. **Abre la app**
   ```bash
   fly open
   ```

---

## 🐳 Opción 4: Docker (DigitalOcean, AWS, GCP)

### Usando Docker Compose (local o servidor)

1. **Clona el repositorio**
   ```bash
   git clone <tu-repo>
   cd stadium-smart-pricing
   ```

2. **Configura variables de entorno**
   ```bash
   cp .env.example .env
   # Edita .env con tus valores
   ```

3. **Inicia servicios**
   ```bash
   docker-compose up -d
   ```

4. **Verifica**
   ```bash
   docker-compose logs -f api
   curl http://localhost:8000/health
   ```

### Deploy en DigitalOcean App Platform

1. **Crea app desde Docker Hub o GitHub**
   - Ve a App Platform en DigitalOcean
   - Create App → GitHub o Docker Hub

2. **Configura servicios**
   - Web Service: usa el `Dockerfile`
   - Database: PostgreSQL
   - Redis: puede usar DigitalOcean Managed Redis

3. **Variables de entorno** (igual que Render)

4. **Deploy** automático desde Git

---

## 🔧 Variables de Entorno Requeridas

### Mínimas (Base de datos y Redis)
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=smart_pricing
DATABASE_USER=smart_pricing_user
DATABASE_PASSWORD=<secure-password>

REDIS_HOST=localhost
REDIS_PORT=6379

ENVIRONMENT=production
LOG_LEVEL=INFO
SECRET_KEY=<random-secure-string>
```

### Opcionales
```env
# API Keys externas
FOOTBALL_DATA_API_KEY=<tu-key>
WEATHER_API_KEY=<tu-key>

# CORS
CORS_ORIGINS=https://tu-frontend.com,https://www.tu-frontend.com

# Pricing
PRICING_UPDATE_INTERVAL=300
PRICING_MIN_CHANGE_THRESHOLD=0.5

# ML
FORCE_RETRAIN=false
ML_MODEL_PATH=models/demand_model.pkl
```

---

## 📊 Post-Deployment

### 1. Verifica Health
```bash
curl https://tu-app.com/health
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "database": true,
  "redis": true,
  "ml_model_loaded": true
}
```

### 2. Accede a la documentación
```
https://tu-app.com/docs
```

### 3. Prueba el dashboard
```
https://tu-app.com/dashboard/
```

### 4. Prueba el simulador
```
https://tu-app.com/dashboard/simulator.html
```

---

## 🔒 Seguridad en Producción

1. **Cambia SECRET_KEY** a un valor aleatorio seguro
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Actualiza CORS_ORIGINS** con tus dominios reales
   ```env
   CORS_ORIGINS=https://tudominio.com
   ```

3. **Usa HTTPS** (automático en Render/Railway/Fly)

4. **No commits con secretos**
   - Verifica que `.env` esté en `.gitignore`
   - Nunca hagas commit de API keys

5. **Database backups** (automático en planes pagos)

---

## 📈 Monitoreo

### Logs en Render
```bash
# En el dashboard web o:
render logs
```

### Logs en Railway
```bash
railway logs
```

### Logs en Fly.io
```bash
fly logs
```

### Métricas
- Visita `/metrics` para Prometheus metrics
- Configura alertas en tu plataforma

---

## 🆘 Troubleshooting

### Error: Database connection failed
1. Verifica que PostgreSQL esté running
2. Comprueba `DATABASE_*` variables
3. Verifica network connectivity

### Error: Redis connection failed
1. Verifica que Redis esté running
2. Comprueba `REDIS_HOST` y `REDIS_PORT`

### Error: ML model not loaded
1. El modelo se entrena en el primer deploy
2. Revisa logs de `./scripts/deploy_init.sh`
3. Modo fallback (heurístico) funciona sin modelo

### App muy lenta en plan gratuito
- Render free tier "duerme" después de 15 min
- Primera request después de dormir toma ~30s
- Considera plan Starter ($7/mes) para apps en producción

---

## 💰 Costos Estimados

### Plan Gratuito (Desarrollo/Testing)
- **Render**: Gratis (con limitaciones)
- **Railway**: $5 crédito/mes gratis
- **Fly.io**: Gratis (allowances generosas)

### Plan Producción (Recomendado)
- **Render**: ~$25/mes
  - Web Service Starter: $7/mes
  - PostgreSQL Starter: $7/mes
  - Redis: $10/mes
- **Railway**: ~$20-30/mes (pago por uso)
- **DigitalOcean**: ~$35/mes
  - App Platform: $12/mes
  - PostgreSQL: $15/mes
  - Redis: $8/mes

---

## 🎉 ¡Listo!

Tu sistema de Smart Pricing está desplegado y listo para producción.

**URLs importantes:**
- API Docs: `https://tu-app.com/docs`
- Dashboard: `https://tu-app.com/dashboard/`
- Simulador: `https://tu-app.com/dashboard/simulator.html`
- Health Check: `https://tu-app.com/health`

¿Preguntas? Revisa los logs o contacta soporte de tu plataforma.
