"""
Dependency Injection Container.

Proporciona funciones para inyección de dependencias en FastAPI.
Gestiona la creación y ciclo de vida de servicios, repositorios y conexiones.
"""

from functools import lru_cache
from typing import AsyncGenerator, Generator, Optional

import redis
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import Settings, get_settings
from src.core.exceptions import CacheConnectionError, DatabaseConnectionError
from src.core.logging import get_logger

logger = get_logger(__name__)

# ============================================================================
# DATABASE DEPENDENCIES
# ============================================================================

# Engine global (se crea una sola vez)
_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """
    Obtiene o crea el engine de SQLAlchemy.

    Returns:
        Engine de SQLAlchemy configurado

    Raises:
        DatabaseConnectionError: Si no se puede crear la conexión
    """
    global _engine
    if _engine is None:
        try:
            settings = get_settings()
            _engine = create_engine(
                settings.database.url,
                pool_size=settings.database.pool_size,
                max_overflow=settings.database.max_overflow,
                pool_pre_ping=True,  # Verificar conexiones antes de usarlas
                echo=settings.database.echo,
            )
            logger.info("Database engine created successfully")
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}")
            raise DatabaseConnectionError(str(e))
    return _engine


# Session factory
_SessionLocal: Optional[sessionmaker] = None


def get_session_factory() -> sessionmaker:
    """
    Obtiene o crea el session factory.

    Returns:
        Session factory configurado
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("Session factory created successfully")
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Dependency para obtener una sesión de base de datos.

    Yields:
        Sesión de SQLAlchemy

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/items")
        >>> def get_items(db: Session = Depends(get_db)):
        >>>     return db.query(Item).all()
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# REDIS/CACHE DEPENDENCIES
# ============================================================================

# Cliente Redis global
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Obtiene o crea el cliente de Redis.

    Returns:
        Cliente de Redis configurado

    Raises:
        CacheConnectionError: Si no se puede conectar a Redis
    """
    global _redis_client
    if _redis_client is None:
        try:
            settings = get_settings()
            _redis_client = redis.from_url(
                settings.redis.url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test de conexión
            _redis_client.ping()
            logger.info("Redis client created successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise CacheConnectionError(str(e))
    return _redis_client


def get_redis() -> redis.Redis:
    """
    Dependency para obtener el cliente de Redis.

    Returns:
        Cliente de Redis

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/cache")
        >>> def get_cache(redis_client: redis.Redis = Depends(get_redis)):
        >>>     return redis_client.get("key")
    """
    return get_redis_client()


# ============================================================================
# CONFIGURATION DEPENDENCIES
# ============================================================================


def get_current_settings() -> Settings:
    """
    Dependency para obtener la configuración actual.

    Returns:
        Instancia de Settings

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/config")
        >>> def get_config(settings: Settings = Depends(get_current_settings)):
        >>>     return {"environment": settings.environment}
    """
    return get_settings()


# ============================================================================
# SERVICE DEPENDENCIES (Placeholders para fases futuras)
# ============================================================================

# Estos serán implementados en fases posteriores cuando tengamos los servicios


@lru_cache()
def get_rules_engine():
    """
    Dependency para obtener el RulesEngine.

    Returns:
        Instancia de RulesEngine

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/rules/competition")
        >>> def get_multiplier(engine = Depends(get_rules_engine)):
        >>>     return engine.get_competition_multiplier("la_liga")
    """
    from src.domain.services.rules_engine import RulesEngine

    return RulesEngine(config_path="config/pricing_rules.yaml")


def get_pricing_engine(db: Session = None):
    """
    Dependency para obtener el PricingEngine.

    Args:
        db: Sesión de base de datos (opcional, se crea una si no se proporciona)

    Returns:
        Instancia de PricingEngine

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/pricing/calculate/{match_id}")
        >>> def calculate_pricing(match_id: str, engine = Depends(get_pricing_engine)):
        >>>     return engine.calculate_match_pricing(match, zones)
    """
    from src.domain.services.pricing_engine import PricingEngine

    if db is None:
        # Para uso directo (no como dependency de FastAPI)
        db = next(get_db())

    return PricingEngine(
        rules_engine=get_rules_engine(),
        demand_predictor=get_demand_predictor(),
        inventory_manager=get_inventory_manager(db),
        match_repository=get_match_repository(db),
        zone_repository=get_zone_repository(db),
        pricing_repository=get_pricing_repository(db),
        db_session=db,
    )


@lru_cache()
def get_demand_predictor():
    """
    Dependency para obtener el DemandPredictor.

    Returns:
        Instancia de DemandPredictor

    Note:
        Currently uses heuristic-based predictor. Full ML implementation
        will be added in Phase 7.

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/demand/predict")
        >>> def predict(predictor = Depends(get_demand_predictor)):
        >>>     return predictor.predict_demand(match, zone, days=7)
    """
    from src.domain.services.demand_predictor import DemandPredictor

    return DemandPredictor()


def get_inventory_manager(db: Session = None):
    """
    Dependency para obtener el InventoryManager.

    Args:
        db: Sesión de base de datos (opcional, se crea una si no se proporciona)

    Returns:
        Instancia de InventoryManager

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/inventory")
        >>> def get_inventory(manager = Depends(get_inventory_manager)):
        >>>     return manager.get_match_inventory("match_123")
    """
    from src.domain.services.inventory_manager import InventoryManager

    if db is None:
        # Para uso directo (no como dependency de FastAPI)
        db = next(get_db())

    sale_repo = get_sale_repository(db)
    zone_repo = get_zone_repository(db)
    redis_client = get_redis_client()

    settings = get_settings()
    cache_ttl = settings.redis.ttl

    return InventoryManager(
        sale_repository=sale_repo,
        zone_repository=zone_repo,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )


# ============================================================================
# REPOSITORY DEPENDENCIES
# ============================================================================


def get_match_repository(db: Session = None):
    """
    Dependency para obtener el MatchRepository.

    Args:
        db: Sesión de base de datos (opcional, se crea una si no se proporciona)

    Returns:
        Instancia de MatchRepository

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/matches")
        >>> def get_matches(repo = Depends(get_match_repository)):
        >>>     return repo.get_all()
    """
    from src.domain.repositories.match_repository import MatchRepository

    if db is None:
        # Para uso directo (no como dependency de FastAPI)
        db = next(get_db())

    return MatchRepository(db)


def get_zone_repository(db: Session = None):
    """
    Dependency para obtener el ZoneRepository.

    Args:
        db: Sesión de base de datos (opcional, se crea una si no se proporciona)

    Returns:
        Instancia de ZoneRepository

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/zones")
        >>> def get_zones(repo = Depends(get_zone_repository)):
        >>>     return repo.get_all()
    """
    from src.domain.repositories.zone_repository import ZoneRepository

    if db is None:
        # Para uso directo (no como dependency de FastAPI)
        db = next(get_db())

    return ZoneRepository(db)


def get_sale_repository(db: Session = None):
    """
    Dependency para obtener el SaleRepository.

    Args:
        db: Sesión de base de datos (opcional, se crea una si no se proporciona)

    Returns:
        Instancia de SaleRepository

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/sales")
        >>> def get_sales(repo = Depends(get_sale_repository)):
        >>>     return repo.get_all()
    """
    from src.domain.repositories.sale_repository import SaleRepository

    if db is None:
        # Para uso directo (no como dependency de FastAPI)
        db = next(get_db())

    return SaleRepository(db)


def get_pricing_repository(db: Session = None):
    """
    Dependency para obtener el PricingHistoryRepository.

    Args:
        db: Sesión de base de datos (opcional, se crea una si no se proporciona)

    Returns:
        Instancia de PricingHistoryRepository

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/pricing-history")
        >>> def get_history(repo = Depends(get_pricing_repository)):
        >>>     return repo.get_all()
    """
    from src.domain.repositories.pricing_repository import PricingHistoryRepository

    if db is None:
        # Para uso directo (no como dependency de FastAPI)
        db = next(get_db())

    return PricingHistoryRepository(db)


# ============================================================================
# CLEANUP FUNCTIONS
# ============================================================================


def cleanup_resources() -> None:
    """
    Limpia los recursos globales (conexiones, pools, etc.).

    Se debe llamar al shutdown de la aplicación.

    Example:
        >>> @app.on_event("shutdown")
        >>> def shutdown_event():
        >>>     cleanup_resources()
    """
    global _engine, _redis_client, _SessionLocal

    # Cerrar engine de base de datos
    if _engine is not None:
        _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")

    # Cerrar cliente Redis
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")

    # Limpiar session factory
    _SessionLocal = None

    logger.info("All resources cleaned up")


def health_check_db() -> bool:
    """
    Verifica la salud de la conexión a la base de datos.

    Returns:
        True si la conexión es exitosa, False en caso contrario
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def health_check_redis() -> bool:
    """
    Verifica la salud de la conexión a Redis.

    Returns:
        True si la conexión es exitosa, False en caso contrario
    """
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False


def health_check() -> dict:
    """
    Verifica la salud de todos los servicios.

    Returns:
        Diccionario con el estado de cada servicio
    """
    return {
        "database": health_check_db(),
        "redis": health_check_redis(),
    }
