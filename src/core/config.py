"""
Sistema de configuración centralizado.

Este módulo maneja la carga y validación de configuración desde:
- Variables de entorno (.env)
- Archivos YAML (config/*.yaml)
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    """Configuración de base de datos."""

    host: str = Field(default="localhost", alias="DATABASE_HOST")
    port: int = Field(default=5432, alias="DATABASE_PORT")
    name: str = Field(default="smart_pricing", alias="DATABASE_NAME")
    user: str = Field(default="postgres", alias="DATABASE_USER")
    password: str = Field(default="postgres", alias="DATABASE_PASSWORD")
    pool_size: int = Field(default=20, alias="DATABASE_POOL_SIZE")
    max_overflow: int = Field(default=0, alias="DATABASE_MAX_OVERFLOW")
    echo: bool = Field(default=False, alias="DATABASE_ECHO")

    @property
    def url(self) -> str:
        """Construye la URL de conexión a PostgreSQL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """Construye la URL de conexión asíncrona."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseModel):
    """Configuración de Redis."""

    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    db: int = Field(default=0, alias="REDIS_DB")
    password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    ttl: int = Field(default=300, alias="REDIS_TTL")

    @property
    def url(self) -> str:
        """Construye la URL de conexión a Redis."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class APISettings(BaseModel):
    """Configuración de la API."""

    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    reload: bool = Field(default=True, alias="API_RELOAD")


class LoggingSettings(BaseModel):
    """Configuración de logging."""

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    format: str = Field(default="text", alias="LOG_FORMAT")
    file: Optional[str] = Field(default=None, alias="LOG_FILE")

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Valida que el nivel de log sea válido."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v

    @field_validator("format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Valida que el formato de log sea válido."""
        valid_formats = ["json", "text"]
        v = v.lower()
        if v not in valid_formats:
            raise ValueError(f"Log format must be one of: {', '.join(valid_formats)}")
        return v


class PricingSettings(BaseModel):
    """Configuración del motor de pricing."""

    update_interval: int = Field(default=300, alias="PRICING_UPDATE_INTERVAL")
    min_change_threshold: float = Field(default=0.5, alias="PRICING_MIN_CHANGE_THRESHOLD")
    max_daily_changes: int = Field(default=5, alias="PRICING_MAX_DAILY_CHANGES")


class MLSettings(BaseModel):
    """Configuración de Machine Learning."""

    model_path: str = Field(default="models/demand_model.pkl", alias="ML_MODEL_PATH")
    retrain_interval: int = Field(default=604800, alias="ML_RETRAIN_INTERVAL")


class ExternalAPIsSettings(BaseModel):
    """Configuración de APIs externas."""

    # Football Data API
    football_data_api_key: Optional[str] = Field(default=None)
    football_data_api_url: str = Field(default="https://api.football-data.org/v4")

    # Weather API
    weather_api_key: Optional[str] = Field(default=None)
    weather_api_url: str = Field(default="https://api.openweathermap.org/data/2.5")

    # Google Analytics
    ga_property_id: Optional[str] = Field(default="mock")
    ga_credentials_path: str = Field(default="credentials/google-analytics.json")

    # Ticketing System
    ticketing_api_key: str = Field(default="mock")
    ticketing_api_url: str = Field(default="https://api.ticketing-system.example.com/v1")
    ticketing_reservation_ttl: int = Field(default=900)


class SecuritySettings(BaseModel):
    """Configuración de seguridad."""

    secret_key: str = Field(default="change-this-to-a-random-secret-key", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")


class CORSSettings(BaseModel):
    """Configuración de CORS."""

    origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], alias="CORS_ORIGINS"
    )

    @field_validator("origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        """Parsea CORS_ORIGINS desde string o lista."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class Settings(BaseSettings):
    """
    Configuración principal de la aplicación.

    Carga configuración desde variables de entorno y archivos YAML.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__"
    )

    # Información de la aplicación
    app_name: str = Field(default="Smart Pricing System", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Rutas de configuración
    config_base_path: str = Field(default="config/base.yaml", alias="CONFIG_BASE_PATH")
    config_pricing_rules_path: str = Field(
        default="config/pricing_rules.yaml", alias="CONFIG_PRICING_RULES_PATH"
    )
    config_zones_path: str = Field(default="config/zones.yaml", alias="CONFIG_ZONES_PATH")
    config_competitions_path: str = Field(
        default="config/competitions.yaml", alias="CONFIG_COMPETITIONS_PATH"
    )

    # Información del estadio
    stadium_name: str = Field(default="Son Moix", alias="STADIUM_NAME")
    stadium_capacity: int = Field(default=23142, alias="STADIUM_CAPACITY")
    stadium_latitude: float = Field(default=39.590, alias="STADIUM_LATITUDE")
    stadium_longitude: float = Field(default=2.630, alias="STADIUM_LONGITUDE")

    # External APIs configuration (captured from env vars)
    football_data_api_key: Optional[str] = Field(default=None, alias="FOOTBALL_DATA_API_KEY")
    football_data_api_url: str = Field(
        default="https://api.football-data.org/v4", alias="FOOTBALL_DATA_API_URL"
    )
    weather_api_key: Optional[str] = Field(default=None, alias="WEATHER_API_KEY")
    weather_api_url: str = Field(
        default="https://api.openweathermap.org/data/2.5", alias="WEATHER_API_URL"
    )
    ga_property_id: Optional[str] = Field(default="mock", alias="GA_PROPERTY_ID")
    ga_credentials_path: str = Field(
        default="credentials/google-analytics.json", alias="GA_CREDENTIALS_PATH"
    )
    ticketing_api_key: str = Field(default="mock", alias="TICKETING_API_KEY")
    ticketing_api_url: str = Field(
        default="https://api.ticketing-system.example.com/v1", alias="TICKETING_API_URL"
    )
    ticketing_reservation_ttl: int = Field(default=900, alias="TICKETING_RESERVATION_TTL")

    # Sub-configuraciones
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    pricing: PricingSettings = Field(default_factory=PricingSettings)
    ml: MLSettings = Field(default_factory=MLSettings)
    external_apis: Optional[ExternalAPIsSettings] = Field(default=None)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)

    # Configuraciones YAML cargadas
    _yaml_configs: Dict[str, Any] = {}

    def __init__(self, **kwargs):
        """Inicializa y carga configuraciones YAML."""
        super().__init__(**kwargs)

        # Build external_apis from captured env vars
        if self.external_apis is None:
            self.external_apis = ExternalAPIsSettings(
                football_data_api_key=self.football_data_api_key,
                football_data_api_url=self.football_data_api_url,
                weather_api_key=self.weather_api_key,
                weather_api_url=self.weather_api_url,
                ga_property_id=self.ga_property_id,
                ga_credentials_path=self.ga_credentials_path,
                ticketing_api_key=self.ticketing_api_key,
                ticketing_api_url=self.ticketing_api_url,
                ticketing_reservation_ttl=self.ticketing_reservation_ttl,
            )

        self._load_yaml_configs()

    # Convenient properties for external APIs
    @property
    def FOOTBALL_DATA_API_KEY(self) -> Optional[str]:
        """Get Football Data API key."""
        return self.external_apis.football_data_api_key

    @property
    def WEATHER_API_KEY(self) -> Optional[str]:
        """Get Weather API key."""
        return self.external_apis.weather_api_key

    @property
    def GA_PROPERTY_ID(self) -> Optional[str]:
        """Get Google Analytics Property ID."""
        return self.external_apis.ga_property_id

    @property
    def GA_CREDENTIALS_PATH(self) -> str:
        """Get Google Analytics credentials path."""
        return self.external_apis.ga_credentials_path

    @property
    def TICKETING_API_KEY(self) -> str:
        """Get Ticketing System API key."""
        return self.external_apis.ticketing_api_key

    def load_yaml_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file.

        Args:
            config_path: Path to the YAML file.

        Returns:
            Dictionary with the configuration.
        """
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _load_yaml_configs(self) -> None:
        """
        Carga todos los archivos de configuración YAML.

        Raises:
            FileNotFoundError: Si algún archivo de configuración no existe.
            yaml.YAMLError: Si hay errores al parsear YAML.
        """
        config_files = {
            "base": self.config_base_path,
            "pricing_rules": self.config_pricing_rules_path,
            "zones": self.config_zones_path,
            "competitions": self.config_competitions_path,
        }

        for config_name, config_path in config_files.items():
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        self._yaml_configs[config_name] = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(f"Error parsing YAML file {config_path}: {e}")
            else:
                # Para la primera ejecución, los archivos pueden no existir
                self._yaml_configs[config_name] = {}

    def get_yaml_config(self, config_name: str) -> Dict[str, Any]:
        """
        Obtiene una configuración YAML cargada.

        Args:
            config_name: Nombre de la configuración (base, pricing_rules, zones, competitions)

        Returns:
            Diccionario con la configuración

        Raises:
            KeyError: Si la configuración no existe
        """
        if config_name not in self._yaml_configs:
            raise KeyError(f"Configuration '{config_name}' not found")
        return self._yaml_configs[config_name]

    def reload_yaml_configs(self) -> None:
        """Recarga todos los archivos de configuración YAML."""
        self._yaml_configs.clear()
        self._load_yaml_configs()

    @property
    def is_production(self) -> bool:
        """Verifica si el entorno es producción."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Verifica si el entorno es desarrollo."""
        return self.environment.lower() == "development"

    @property
    def is_testing(self) -> bool:
        """Verifica si el entorno es testing."""
        return self.environment.lower() == "testing"

    def validate_configuration(self) -> List[str]:
        """
        Valida la configuración completa.

        Returns:
            Lista de advertencias/errores de configuración
        """
        warnings = []

        # Validar clave secreta en producción
        if self.is_production and self.security.secret_key == "change-this-to-a-random-secret-key":
            warnings.append("SECRET_KEY debe ser cambiada en producción")

        # Validar APIs externas
        if not self.external_apis.football_data_api_key:
            warnings.append("FOOTBALL_DATA_API_KEY no está configurada")

        if not self.external_apis.weather_api_key:
            warnings.append("WEATHER_API_KEY no está configurada")

        # Validar archivos de configuración
        for config_name in ["base", "pricing_rules", "zones", "competitions"]:
            if not self._yaml_configs.get(config_name):
                warnings.append(f"Archivo de configuración '{config_name}' está vacío o no existe")

        return warnings


@lru_cache()
def get_settings() -> Settings:
    """
    Obtiene la instancia singleton de Settings.

    Returns:
        Instancia de Settings con toda la configuración cargada

    Example:
        >>> from src.core.config import get_settings
        >>> settings = get_settings()
        >>> print(settings.database.url)
    """
    return Settings()
