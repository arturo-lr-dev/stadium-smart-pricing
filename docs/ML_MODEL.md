# Machine Learning - Modelo de Predicción de Demanda

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Arquitectura del Modelo](#arquitectura-del-modelo)
3. [Feature Engineering](#feature-engineering)
4. [Modelos Disponibles](#modelos-disponibles)
5. [Pipeline de Entrenamiento](#pipeline-de-entrenamiento)
6. [Evaluación del Modelo](#evaluación-del-modelo)
7. [Deployment e Inferencia](#deployment-e-inferencia)
8. [Modo Heurístico (Fallback)](#modo-heurístico-fallback)
9. [Re-entrenamiento Automático](#re-entrenamiento-automático)
10. [Mejores Prácticas](#mejores-prácticas)

## Introducción

El sistema Smart Pricing utiliza Machine Learning para predecir la demanda de entradas para cada partido. Esta predicción genera un **demand score** (0.0-1.0) que se utiliza como uno de los factores en el cálculo del precio dinámico.

### Objetivo del Modelo

**Input:**
- Características del partido (competición, rival, fecha, hora)
- Características temporales (día de la semana, mes, días hasta partido)
- Datos externos (clima, posición en liga, forma reciente)

**Output:**
- Demand score: 0.0 (demanda muy baja) a 1.0 (demanda máxima)

### Ventajas del Enfoque ML

- **Aprendizaje de patrones históricos:** El modelo aprende de ventas pasadas
- **Adaptación automática:** Se ajusta a cambios en el comportamiento del público
- **Factorización de múltiples variables:** Considera 20+ features simultáneamente
- **Fallback robusto:** Modo heurístico si el modelo no está disponible

## Arquitectura del Modelo

```
┌──────────────────────────────────────────────────────────┐
│                   INPUT DATA                             │
│  Match, Zone, CurrentDateTime, ExternalData              │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│              FEATURE EXTRACTION                          │
│                                                          │
│  ┌────────────────────┐  ┌──────────────────────┐      │
│  │ MatchFeatureExt.   │  │ TemporalFeatureExt.  │      │
│  │ - competition_type │  │ - day_of_week        │      │
│  │ - rival_importance │  │ - month              │      │
│  │ - is_derby         │  │ - is_weekend         │      │
│  │ - home_position    │  │ - days_to_match      │      │
│  │ - away_position    │  │ - is_holiday         │      │
│  └────────────────────┘  └──────────────────────┘      │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ ExternalFeatureExtractor                           │ │
│  │ - weather_conditions                               │ │
│  │ - temperature                                      │ │
│  │ - away_team_form (últimos 5 partidos)            │ │
│  │ - home_team_form                                   │ │
│  └────────────────────────────────────────────────────┘ │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼ Feature Vector (20+ dimensions)
┌──────────────────────────────────────────────────────────┐
│                    ML MODEL                              │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Random Forest / Gradient Boosting Regressor    │   │
│  │  - n_estimators: 100                             │   │
│  │  - max_depth: 10                                 │   │
│  │  - Trained on historical sales data              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│                 OUTPUT: Demand Score                     │
│                    0.0 - 1.0                             │
└──────────────────────────────────────────────────────────┘
```

## Feature Engineering

### 1. Match Features (Características del Partido)

**Ubicación:** `src/ml/features/match_features.py`

```python
class MatchFeatureExtractor:
    def extract(match: Match, zone: Zone) -> dict:
        return {
            # Tipo de competición (one-hot encoded)
            "competition_laliga": 1 if match.competition == "laliga" else 0,
            "competition_copa": 1 if match.competition == "copa_del_rey" else 0,
            "competition_champions": 1 if match.competition == "champions_league" else 0,
            "competition_europa": 1 if match.competition == "europa_league" else 0,

            # Importancia del rival (0.0-1.0)
            "rival_importance": calculate_rival_importance(match.away_team),
            # Basado en:
            # - Posición en liga (si disponible)
            # - Multiplicador configurado en pricing_rules.yaml
            # - Histórico de asistencias contra ese rival

            # Posiciones en liga (normalizado 0-1)
            "home_position_normalized": match.home_position / 20,
            "away_position_normalized": match.away_position / 20,

            # Condiciones especiales (binarias)
            "is_derby": 1 if match.is_derby else 0,
            "is_title_race": 1 if is_title_race_match(match) else 0,
            "is_relegation_battle": 1 if is_relegation_match(match) else 0,

            # Categoría de zona (one-hot)
            "zone_vip": 1 if zone.category == "VIP" else 0,
            "zone_premium": 1 if zone.category == "Premium" else 0,
            "zone_standard": 1 if zone.category == "Standard" else 0,

            # Importancia del partido (0.0-1.0)
            # Calculado a partir de multiplicadores en pricing_rules.yaml
            "match_importance": calculate_match_importance(match)
        }
```

### 2. Temporal Features (Características Temporales)

**Ubicación:** `src/ml/features/temporal_features.py`

```python
class TemporalFeatureExtractor:
    def extract(match: Match, current_datetime: datetime) -> dict:
        match_date = match.date
        days_to_match = (match_date - current_datetime).days

        return {
            # Día de la semana (one-hot encoded)
            "day_monday": 1 if match_date.weekday() == 0 else 0,
            "day_tuesday": 1 if match_date.weekday() == 1 else 0,
            "day_wednesday": 1 if match_date.weekday() == 2 else 0,
            "day_thursday": 1 if match_date.weekday() == 3 else 0,
            "day_friday": 1 if match_date.weekday() == 4 else 0,
            "day_saturday": 1 if match_date.weekday() == 5 else 0,
            "day_sunday": 1 if match_date.weekday() == 6 else 0,

            # Mes del año (numérico, 1-12)
            "month": match_date.month,

            # Indicadores temporales
            "is_weekend": 1 if match_date.weekday() >= 5 else 0,
            "is_holiday": 1 if match.is_holiday else 0,

            # Días hasta el partido (múltiples representaciones)
            "days_to_match": days_to_match,
            "days_to_match_squared": days_to_match ** 2,  # Captura no-linealidad
            "days_to_match_log": log(max(days_to_match, 1)),

            # Franja temporal (categorical)
            "is_early_bird": 1 if days_to_match > 60 else 0,
            "is_last_minute": 1 if days_to_match < 7 else 0,

            # Hora del partido (0-23)
            "match_hour": match_date.hour,
            "is_evening": 1 if 18 <= match_date.hour <= 20 else 0,
            "is_night": 1 if 21 <= match_date.hour <= 23 else 0,
        }
```

### 3. External Features (Datos Externos)

**Ubicación:** `src/ml/features/external_features.py`

```python
class ExternalFeatureExtractor:
    def extract(match: Match, external_data: dict) -> dict:
        return {
            # Clima
            "weather_clear": 1 if external_data.get("weather") == "clear" else 0,
            "weather_rain": 1 if "rain" in external_data.get("weather", "") else 0,
            "weather_storm": 1 if "storm" in external_data.get("weather", "") else 0,
            "temperature": external_data.get("temperature", 20),  # °C

            # Forma reciente del equipo visitante
            "away_team_form": calculate_form_score(
                external_data.get("away_team_last_5_matches", [])
            ),  # 0.0-1.0 (0=pésima forma, 1=excelente)

            # Forma reciente del equipo local
            "home_team_form": calculate_form_score(
                external_data.get("home_team_last_5_matches", [])
            ),

            # Posición en tabla actualizada
            "away_team_position": external_data.get("away_team_position", 10),
            "home_team_position": external_data.get("home_team_position", 10),

            # Racha de victorias/derrotas
            "home_winning_streak": external_data.get("home_winning_streak", 0),
            "away_winning_streak": external_data.get("away_winning_streak", 0),
        }
```

### 4. Derived Features (Features Derivadas)

Combinaciones de features base que capturan interacciones:

```python
def create_derived_features(features: dict) -> dict:
    return {
        # Interacción tiempo x importancia
        "importance_x_days": (
            features["match_importance"] * features["days_to_match"]
        ),

        # Weekend x importancia (partidos importantes en fin de semana)
        "is_weekend_x_importance": (
            features["is_weekend"] * features["match_importance"]
        ),

        # Derby en fin de semana
        "derby_weekend": features["is_derby"] * features["is_weekend"],

        # Last minute x high importance
        "last_minute_important": (
            features["is_last_minute"] * features["match_importance"]
        ),

        # Diferencia de posición en liga
        "position_gap": abs(
            features["home_position_normalized"] -
            features["away_position_normalized"]
        ),
    }
```

### Resumen de Features

| Categoría | Cantidad | Ejemplos |
|-----------|----------|----------|
| Match Features | 12 | competition_type, rival_importance, is_derby |
| Temporal Features | 15 | day_of_week, month, days_to_match, is_weekend |
| External Features | 10 | weather, temperature, team_form, position |
| Derived Features | 5 | importance_x_days, derby_weekend |
| **TOTAL** | **~42** | - |

## Modelos Disponibles

### 1. Random Forest Regressor

**Configuración en `config/base.yaml`:**

```yaml
ml:
  model_type: "random_forest"
  random_forest:
    n_estimators: 100  # Número de árboles
    max_depth: 10      # Profundidad máxima de árboles
    min_samples_split: 2
    min_samples_leaf: 1
    max_features: "sqrt"  # sqrt(n_features) por split
    random_state: 42
    n_jobs: -1  # Usar todos los cores CPU
```

**Ventajas:**
- Robusto a outliers
- No requiere normalización de features
- Maneja bien features categóricas y numéricas
- Menor riesgo de overfitting que un solo árbol

**Desventajas:**
- Puede ser lento en inferencia con muchos árboles
- Memoria intensiva

### 2. Gradient Boosting Regressor

**Configuración:**

```yaml
ml:
  model_type: "gradient_boosting"
  gradient_boosting:
    n_estimators: 100
    learning_rate: 0.1
    max_depth: 5
    min_samples_split: 2
    min_samples_leaf: 1
    subsample: 0.8  # Fracción de samples para entrenar cada árbol
    random_state: 42
```

**Ventajas:**
- Generalmente mejor performance que Random Forest
- Captura interacciones complejas
- Buena generalización

**Desventajas:**
- Más propenso a overfitting (requiere tuning cuidadoso)
- Entrenamiento más lento
- Sensible a hiperparámetros

### Comparación de Performance

| Métrica | Random Forest | Gradient Boosting |
|---------|---------------|-------------------|
| MAE (Mean Absolute Error) | 0.12 | 0.10 |
| RMSE | 0.15 | 0.13 |
| R² Score | 0.78 | 0.82 |
| Training Time | 30s | 60s |
| Inference Time (1000 samples) | 20ms | 15ms |

## Pipeline de Entrenamiento

### Script de Entrenamiento

**Ubicación:** `src/ml/training/train_demand.py`

```bash
# Entrenar modelo con datos históricos
python src/ml/training/train_demand.py \
  --data-path data/historical_sales.csv \
  --model-type random_forest \
  --output-path models/demand_model.pkl \
  --test-split 0.2 \
  --cross-validation 5

# Output:
# Loading data... 50,000 samples
# Extracting features... done (42 features)
# Training Random Forest model...
# Cross-validation scores: [0.81, 0.79, 0.82, 0.80, 0.81]
# Mean CV score: 0.806 ± 0.011
# Final test score (R²): 0.815
# Model saved to models/demand_model.pkl
```

### Proceso de Entrenamiento

```python
def train_demand_model(data_path: str, config: dict):
    # 1. Cargar datos históricos
    df = load_historical_sales(data_path)
    # Columnas: match_id, zone_id, date, sold_tickets, available_tickets,
    #           competition, rival, days_to_match, weather, ...

    # 2. Calcular target variable (demand_score)
    df["demand_score"] = df["sold_tickets"] / df["available_tickets"]
    # Normalizar a 0-1 por ventana temporal

    # 3. Feature extraction
    X = []
    y = []
    for idx, row in df.iterrows():
        match_features = MatchFeatureExtractor.extract(row)
        temporal_features = TemporalFeatureExtractor.extract(row)
        external_features = ExternalFeatureExtractor.extract(row)

        features = {**match_features, **temporal_features, **external_features}
        derived = create_derived_features(features)
        all_features = {**features, **derived}

        X.append(list(all_features.values()))
        y.append(row["demand_score"])

    X = np.array(X)
    y = np.array(y)

    # 4. Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 5. Entrenar modelo
    if config["model_type"] == "random_forest":
        model = RandomForestRegressor(**config["random_forest"])
    else:
        model = GradientBoostingRegressor(**config["gradient_boosting"])

    model.fit(X_train, y_train)

    # 6. Evaluar
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    print(f"R² Score: {r2:.3f}")
    print(f"MAE: {mae:.3f}")
    print(f"RMSE: {rmse:.3f}")

    # 7. Feature importance
    feature_importance = pd.DataFrame({
        "feature": feature_names,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)

    print("Top 10 features:")
    print(feature_importance.head(10))

    # 8. Guardar modelo
    joblib.dump({
        "model": model,
        "feature_names": feature_names,
        "metadata": {
            "trained_at": datetime.now().isoformat(),
            "n_samples": len(X_train),
            "r2_score": r2,
            "mae": mae,
            "rmse": rmse
        }
    }, output_path)

    return model, feature_importance
```

### Feature Importance

Después del entrenamiento, las 10 features más importantes típicamente son:

| Rank | Feature | Importance | Interpretación |
|------|---------|------------|----------------|
| 1 | days_to_match | 0.18 | Urgencia temporal |
| 2 | match_importance | 0.15 | Perfil del partido |
| 3 | rival_importance | 0.12 | Atractivo del rival |
| 4 | is_weekend | 0.09 | Conveniencia de horario |
| 5 | competition_champions | 0.08 | Prestigio de competición |
| 6 | days_to_match_squared | 0.07 | Efecto no-lineal del tiempo |
| 7 | away_team_form | 0.06 | Forma reciente |
| 8 | is_derby | 0.05 | Rivalidad |
| 9 | zone_vip | 0.04 | Tipo de zona |
| 10 | temperature | 0.03 | Clima |

## Evaluación del Modelo

### Script de Evaluación

**Ubicación:** `src/ml/training/evaluate.py`

```bash
python src/ml/training/evaluate.py \
  --model-path models/demand_model.pkl \
  --test-data data/test_set.csv \
  --output-report reports/model_evaluation.html

# Genera reporte con:
# - Métricas de performance
# - Gráficos de predicción vs real
# - Análisis de residuos
# - Feature importance
```

### Métricas de Evaluación

1. **R² Score (Coefficient of Determination)**
   - Objetivo: > 0.75
   - Interpretación: % de varianza explicada por el modelo

2. **MAE (Mean Absolute Error)**
   - Objetivo: < 0.15
   - Interpretación: Error promedio absoluto en demand score

3. **RMSE (Root Mean Squared Error)**
   - Objetivo: < 0.18
   - Interpretación: Penaliza errores grandes más fuertemente

4. **MAPE (Mean Absolute Percentage Error)**
   - Objetivo: < 20%
   - Interpretación: Error porcentual promedio

### Validación Cruzada

```python
from sklearn.model_selection import cross_val_score

# 5-fold cross-validation
cv_scores = cross_val_score(
    model, X, y,
    cv=5,
    scoring='r2',
    n_jobs=-1
)

print(f"CV Scores: {cv_scores}")
print(f"Mean: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
```

### Análisis de Residuos

```python
# Residuals plot
residuals = y_test - y_pred
plt.scatter(y_pred, residuals)
plt.axhline(y=0, color='r', linestyle='--')
plt.xlabel("Predicted Demand Score")
plt.ylabel("Residuals")
plt.title("Residual Plot")
plt.savefig("residuals.png")
```

## Deployment e Inferencia

### Carga del Modelo

**Ubicación:** `src/ml/models/demand_model.py`

```python
class DemandModel:
    def __init__(self, model_path: str):
        self._model = None
        self.model_path = model_path
        self.feature_names = None
        self.metadata = None

    def load(self):
        """Lazy loading del modelo"""
        if self._model is None:
            data = joblib.load(self.model_path)
            self._model = data["model"]
            self.feature_names = data["feature_names"]
            self.metadata = data["metadata"]
            logger.info(
                f"Loaded ML model trained at {self.metadata['trained_at']} "
                f"with R² = {self.metadata['r2_score']:.3f}"
            )

    def predict(self, features: dict) -> float:
        """Predecir demand score"""
        self.load()  # Lazy load

        # Convertir dict a array en orden correcto
        feature_vector = [features[name] for name in self.feature_names]
        feature_array = np.array([feature_vector])

        # Predicción
        demand_score = self._model.predict(feature_array)[0]

        # Clamp a rango válido [0, 1]
        demand_score = np.clip(demand_score, 0.0, 1.0)

        return float(demand_score)
```

### Uso en DemandPredictor

```python
class DemandPredictor:
    def __init__(self, ml_model: Optional[DemandModel] = None):
        self.ml_model = ml_model
        self.match_feature_extractor = MatchFeatureExtractor()
        self.temporal_feature_extractor = TemporalFeatureExtractor()
        self.external_feature_extractor = ExternalFeatureExtractor()

    def predict_demand(
        self,
        match: Match,
        zone: Zone,
        current_datetime: datetime
    ) -> float:
        # Intentar ML primero
        if self.ml_model:
            try:
                features = self._extract_all_features(match, zone, current_datetime)
                demand_score = self.ml_model.predict(features)
                logger.info(f"ML prediction: {demand_score:.3f}")
                return demand_score
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}, falling back to heuristic")

        # Fallback a modo heurístico
        return self._predict_heuristic(match, zone, current_datetime)
```

### Performance de Inferencia

```python
# Benchmark
import time

start = time.time()
for _ in range(1000):
    demand_score = demand_predictor.predict_demand(match, zone, datetime.now())
end = time.time()

print(f"1000 predictions in {end - start:.2f}s")
print(f"Avg latency: {(end - start) * 1000 / 1000:.2f}ms per prediction")

# Output típico:
# 1000 predictions in 0.35s
# Avg latency: 0.35ms per prediction
```

## Modo Heurístico (Fallback)

Cuando el modelo ML no está disponible, el sistema usa predicción basada en reglas:

```python
def _predict_heuristic(
    self,
    match: Match,
    zone: Zone,
    current_datetime: datetime
) -> float:
    """Predicción heurística sin ML"""

    # Base demand según perfil de partido
    base_demand = 0.5

    # Ajuste por tipo de competición
    if match.competition == "champions_league":
        base_demand = 0.85
    elif match.competition == "laliga":
        base_demand = 0.60
    elif match.competition == "copa_del_rey":
        base_demand = 0.55
    elif match.competition == "friendly":
        base_demand = 0.30

    # Ajuste por importancia del rival
    rival_multiplier = rules_engine.get_rival_multiplier(match.away_team)
    if rival_multiplier >= 3.0:  # Real Madrid, Barcelona, Atlético
        base_demand = min(base_demand * 1.5, 1.0)
    elif rival_multiplier >= 1.5:
        base_demand = min(base_demand * 1.2, 1.0)

    # Ajuste por condiciones especiales
    if match.is_derby:
        base_demand = min(base_demand * 1.4, 1.0)

    # Ajuste por zona
    if zone.category == "VIP":
        base_demand *= 0.9  # VIP tiene demanda más estable/menor
    elif zone.category == "Reduced":
        base_demand *= 1.1  # Mayor demanda relativa en zonas baratas

    # Ajuste temporal (urgencia)
    days_to_match = (match.date - current_datetime).days
    if days_to_match < 3:
        base_demand = min(base_demand * 1.3, 1.0)  # Last-minute rush
    elif days_to_match < 7:
        base_demand = min(base_demand * 1.15, 1.0)
    elif days_to_match > 60:
        base_demand *= 0.85  # Early bird menos urgente

    # Ajuste por día de la semana
    if match.date.weekday() >= 5:  # Weekend
        base_demand = min(base_demand * 1.1, 1.0)

    return np.clip(base_demand, 0.0, 1.0)
```

### Comparación ML vs Heurística

| Métrica | Modo ML | Modo Heurístico |
|---------|---------|-----------------|
| R² Score | 0.82 | 0.45 |
| MAE | 0.10 | 0.22 |
| Latencia | 0.35ms | 0.05ms |
| Requiere datos históricos | Sí | No |
| Adaptación automática | Sí | No |

## Re-entrenamiento Automático

### Worker de Re-entrenamiento

**Ubicación:** `src/workers/model_retrainer.py`

```python
class ModelRetrainerWorker(BaseWorker):
    def __init__(self, interval_days: int = 7):
        self.interval_days = interval_days
        self.min_samples = 1000

    def execute(self):
        logger.info("Starting model retraining...")

        # 1. Obtener datos recientes
        cutoff_date = datetime.now() - timedelta(days=180)  # Últimos 6 meses
        sales_data = self.sale_repository.get_sales_since(cutoff_date)

        if len(sales_data) < self.min_samples:
            logger.warning(
                f"Insufficient data for retraining: {len(sales_data)} < {self.min_samples}"
            )
            return

        # 2. Entrenar nuevo modelo
        new_model, metrics = train_demand_model(
            sales_data,
            config=self.ml_config
        )

        # 3. Validar que el nuevo modelo es mejor
        old_model = load_model(self.model_path)
        X_test, y_test = self._prepare_test_set()

        old_score = r2_score(y_test, old_model.predict(X_test))
        new_score = metrics["r2_score"]

        logger.info(f"Old model R²: {old_score:.3f}, New model R²: {new_score:.3f}")

        # 4. Deployment si mejora
        if new_score > old_score + 0.02:  # Mejora mínima de 2%
            # Backup del modelo viejo
            backup_path = f"{self.model_path}.backup.{datetime.now().strftime('%Y%m%d')}"
            shutil.copy(self.model_path, backup_path)

            # Guardar nuevo modelo
            joblib.dump(new_model, self.model_path)
            logger.info(f"New model deployed! R² improved by {new_score - old_score:.3f}")

            # Enviar notificación
            self._send_notification(
                f"ML model retrained successfully. R²: {new_score:.3f}"
            )
        else:
            logger.info("New model does not improve performance, keeping old model")
```

### Configuración

```yaml
# En config/base.yaml
workers:
  model_retrainer:
    enabled: true
    interval_days: 7
    schedule_time: "03:00"  # 3 AM domingo
    min_samples: 1000
    min_improvement: 0.02  # 2% mejora mínima
    backup_old_model: true
    notify_on_deployment: true
```

## Mejores Prácticas

### 1. Gestión de Datos

- **Datos históricos:** Mantener al menos 6 meses de historial de ventas
- **Data cleaning:** Eliminar outliers y datos anómalos (ej. partidos cancelados)
- **Feature consistency:** Asegurar que features en entrenamiento e inferencia coincidan
- **Versionado:** Usar DVC o similar para versionar datasets

### 2. Entrenamiento

- **Validación cruzada:** Siempre usar CV para evaluar performance
- **Hyperparameter tuning:** Usar GridSearchCV o RandomizedSearchCV
- **Early stopping:** Para Gradient Boosting, usar early stopping para evitar overfitting
- **Regularización:** Ajustar max_depth, min_samples_leaf para controlar complejidad

### 3. Deployment

- **A/B Testing:** Comparar modelo nuevo vs viejo en producción antes de full rollout
- **Monitoring:** Monitorear métricas de predicción en producción
- **Fallback robusto:** Siempre tener modo heurístico disponible
- **Model versioning:** Mantener backups de modelos viejos

### 4. Mantenimiento

- **Re-entrenar regularmente:** Cada 1-2 semanas con datos frescos
- **Drift detection:** Monitorear si las predicciones se desvían de la realidad
- **Feature evolution:** Añadir nuevas features basadas en análisis de importancia
- **Performance tracking:** Dashboard con métricas de predicción vs real

## Troubleshooting

### Problema: Model performance degrading

**Síntoma:** R² score cae de 0.82 a 0.65

**Solución:**
1. Verificar si hay concept drift (comportamiento del público cambió)
2. Re-entrenar con datos más recientes
3. Revisar si hay features faltantes o con valores incorrectos
4. Considerar añadir nuevas features relevantes

### Problema: Predictions out of range

**Síntoma:** Modelo predice valores fuera de [0, 1]

**Solución:**
```python
# Clamp predictions
demand_score = np.clip(model.predict(X), 0.0, 1.0)
```

### Problema: High latency in inference

**Síntoma:** Predicciones tardan >10ms

**Solución:**
1. Reducir n_estimators en Random Forest (100 → 50)
2. Usar modelo más simple (ej. Linear Regression)
3. Cachear predicciones frecuentes
4. Pre-computar features estáticas

### Problema: Model file not found

**Síntoma:** FileNotFoundError al cargar modelo

**Solución:**
```python
# Fallback automático a heurística
try:
    model = load_model(model_path)
except FileNotFoundError:
    logger.warning("ML model not found, using heuristic mode")
    model = None
```

## Referencias

- [Arquitectura](ARCHITECTURE.md)
- [Configuración](CONFIGURATION.md)
- [Plan de Implementación](IMPLEMENTATION_PLAN.md)

## Recursos Externos

- [scikit-learn Documentation](https://scikit-learn.org/)
- [Random Forests - Breiman (2001)](https://www.stat.berkeley.edu/~breiman/randomforest2001.pdf)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)

## Contacto

Smart Pricing Team - @legasint
