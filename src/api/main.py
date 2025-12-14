"""FastAPI application entry point.

This module sets up the FastAPI application with all middleware,
routers, and event handlers.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from src.api.responses import (
    ErrorResponse,
    HealthStatus,
    ReadinessStatus,
    create_error_response,
)
from src.core.config import Settings, get_settings
from src.core.database import get_db_session
from src.core.dependencies import get_redis_client
from src.core.exceptions import (
    ConfigurationError,
    DatabaseError,
    PricingError,
    SmartPricingException,
)
from src.core.logging import setup_logging
from src.utils.metrics import get_metrics, set_app_info

# Configure logging
logger = logging.getLogger(__name__)

# Global state
app_state = {
    "startup_time": None,
    "ml_model_loaded": False,
    "config_loaded": False,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Lifespan context manager for FastAPI app.

    Handles startup and shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        Control to the application
    """
    # Startup
    logger.info("Starting Smart Pricing API...")
    settings = get_settings()

    # Setup logging
    setup_logging()

    # Set application info for metrics
    set_app_info(
        version=settings.app_version,
        environment=settings.environment,
        commit_sha=None,  # Could be populated from env variable
    )

    # Validate configuration
    warnings = settings.validate_configuration()
    if warnings:
        logger.warning(f"Configuration warnings: {warnings}")

    # Test database connection
    try:
        with get_db_session() as db:
            db.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    # Test Redis connection
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise

    # Mark configuration as loaded
    app_state["config_loaded"] = True

    # Try to load ML model (non-blocking)
    try:
        # Import here to avoid circular dependencies
        from src.domain.services.demand_predictor import DemandPredictor

        predictor = DemandPredictor(model_path=settings.ml.model_path)
        # Try to load the model
        if predictor.model is not None:
            app_state["ml_model_loaded"] = True
            logger.info("ML model loaded successfully")
        else:
            logger.warning("ML model not loaded - predictions will use fallback")
    except Exception as e:
        logger.warning(f"Failed to load ML model: {e} - will use fallback predictions")

    app_state["startup_time"] = datetime.utcnow()
    logger.info(
        f"Smart Pricing API started successfully (version {settings.app_version})"
    )

    yield

    # Shutdown
    logger.info("Shutting down Smart Pricing API...")
    # Close connections if needed
    logger.info("Shutdown complete")


# Create FastAPI app
def create_app(settings: Settings = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        settings: Application settings (if None, will load from environment)

    Returns:
        Configured FastAPI application
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="""
        Smart Pricing System API for dynamic ticket pricing optimization.

        ## Features

        * **Dynamic Pricing**: Calculate optimal prices based on demand, inventory, and market conditions
        * **ML-Powered**: Machine learning models for demand prediction
        * **Real-time**: Live pricing updates based on sales velocity
        * **Analytics**: Comprehensive analytics and reporting
        * **Configurable**: Flexible business rules via YAML configuration

        ## Authentication

        Most admin endpoints require authentication via API key or JWT token.
        """,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Setup middleware for metrics and logging
    from src.api.middleware import setup_middleware
    setup_middleware(app)

    # Add exception handlers
    @app.exception_handler(SmartPricingException)
    async def smart_pricing_exception_handler(
        request: Request, exc: SmartPricingException
    ) -> JSONResponse:
        """Handle custom SmartPricingException."""
        logger.error(
            f"SmartPricingException: {exc}",
            extra={"path": request.url.path, "error": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                code="SMART_PRICING_ERROR",
                message=str(exc),
            ).model_dump(mode='json'),
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(
        request: Request, exc: DatabaseError
    ) -> JSONResponse:
        """Handle DatabaseError."""
        logger.error(
            f"DatabaseError: {exc}",
            extra={"path": request.url.path, "error": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=create_error_response(
                code="DATABASE_ERROR",
                message="Database service unavailable",
                details={"error": str(exc)},
            ).model_dump(mode='json'),
        )

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(
        request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        """Handle ConfigurationError."""
        logger.error(
            f"ConfigurationError: {exc}",
            extra={"path": request.url.path, "error": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                code="CONFIGURATION_ERROR",
                message="Configuration error",
                details={"error": str(exc)},
            ).model_dump(mode='json'),
        )

    @app.exception_handler(PricingError)
    async def pricing_error_handler(
        request: Request, exc: PricingError
    ) -> JSONResponse:
        """Handle PricingError."""
        logger.error(
            f"PricingError: {exc}",
            extra={"path": request.url.path, "error": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                code="PRICING_ERROR",
                message="Pricing calculation error",
                details={"error": str(exc)},
            ).model_dump(mode='json'),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle generic exceptions."""
        logger.error(
            f"Unhandled exception: {exc}",
            extra={"path": request.url.path, "error": str(exc)},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                code="INTERNAL_ERROR",
                message="Internal server error",
            ).model_dump(mode='json'),
        )

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """Root endpoint with API information."""
        settings = get_settings()
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "docs": "/docs",
            "health": "/health",
            "status": "/status/ready",
        }

    # Health check endpoint
    @app.get(
        "/health",
        response_model=HealthStatus,
        tags=["Health"],
        summary="Health check",
        description="Check the health status of the API and its dependencies",
    )
    async def health_check() -> HealthStatus:
        """Check health of API and dependencies.

        Returns:
            HealthStatus with overall status and individual service statuses
        """
        settings = get_settings()
        services = {}
        overall_status = "healthy"

        # Check database
        try:
            start = time.time()
            with get_db_session() as db:
                db.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000  # Convert to ms
            services["database"] = {
                "status": "healthy",
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            services["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            overall_status = "unhealthy"

        # Check Redis
        try:
            start = time.time()
            redis_client = get_redis_client()
            redis_client.ping()
            latency = (time.time() - start) * 1000
            services["redis"] = {
                "status": "healthy",
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            services["redis"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            # Redis failure is degraded, not unhealthy
            if overall_status == "healthy":
                overall_status = "degraded"

        return HealthStatus(
            status=overall_status,
            version=settings.app_version,
            timestamp=datetime.utcnow(),
            services=services,
        )

    # Readiness check endpoint
    @app.get(
        "/status/ready",
        response_model=ReadinessStatus,
        tags=["Health"],
        summary="Readiness check",
        description="Check if the application is ready to serve requests",
    )
    async def readiness_check() -> ReadinessStatus:
        """Check if application is ready to serve requests.

        Returns:
            ReadinessStatus indicating whether the app is ready
        """
        checks = {
            "config_loaded": app_state.get("config_loaded", False),
            "ml_model_loaded": app_state.get("ml_model_loaded", False),
        }

        # Check database connectivity
        try:
            with get_db_session() as db:
                db.execute(text("SELECT 1"))
            checks["database_connected"] = True
        except Exception:
            checks["database_connected"] = False

        # Check Redis connectivity
        try:
            redis_client = get_redis_client()
            redis_client.ping()
            checks["redis_connected"] = True
        except Exception:
            checks["redis_connected"] = False

        # Application is ready if config is loaded and database is connected
        # ML model and Redis are optional for basic functionality
        ready = checks["config_loaded"] and checks["database_connected"]

        return ReadinessStatus(
            ready=ready,
            timestamp=datetime.utcnow(),
            checks=checks,
        )

    # Metrics endpoint for Prometheus
    @app.get("/metrics", tags=["Monitoring"])
    async def metrics() -> Response:
        """Expose metrics in Prometheus format.

        Returns:
            Response with Prometheus-formatted metrics
        """
        metrics_data = get_metrics()
        return Response(
            content=metrics_data,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # Include routers
    from src.api import admin, analytics, pricing, sales_simulator, simulator

    app.include_router(pricing.router, prefix="/api/v1", tags=["Pricing"])
    app.include_router(admin.router, prefix="/api/v1", tags=["Admin"])
    app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
    app.include_router(simulator.router, prefix="/api/v1", tags=["Simulator"])
    app.include_router(sales_simulator.router, prefix="/api/v1", tags=["Sales Simulator"])

    # Mount static files for dashboard
    try:
        from pathlib import Path
        dashboard_path = Path(__file__).parent.parent.parent / "dashboard"
        if dashboard_path.exists():
            app.mount("/dashboard", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")
            logger.info(f"Dashboard mounted at /dashboard from {dashboard_path}")
    except Exception as e:
        logger.warning(f"Could not mount dashboard: {e}")

    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
    )
