#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar la carga de variables de entorno usando src.core.config.

Usage:
    python scripts/check_env.py
    python scripts/check_env.py --verbose
    python scripts/check_env.py --check-services
"""

import os
import sys
from pathlib import Path

# Añadir el directorio raíz al path para importar desde src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Cambiar al directorio raíz del proyecto para que Pydantic Settings encuentre el .env
os.chdir(project_root)

from src.core.config import get_settings, Settings


# Colores para output
class Colors:
    HEADER = '\033[95m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'


def print_header(text: str) -> None:
    """Imprime un header formateado."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(text: str) -> None:
    """Imprime mensaje de éxito."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_warning(text: str) -> None:
    """Imprime mensaje de advertencia."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text: str) -> None:
    """Imprime mensaje de error."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text: str, indent: int = 0) -> None:
    """Imprime mensaje informativo."""
    prefix = "  " * indent
    print(f"{prefix}{Colors.CYAN}{text}{Colors.ENDC}")


def check_database_connection(settings: Settings) -> bool:
    """Verifica conexión a PostgreSQL."""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=settings.database.host,
            port=settings.database.port,
            database=settings.database.name,
            user=settings.database.user,
            password=settings.database.password,
            connect_timeout=3
        )
        conn.close()
        return True
    except ImportError:
        print_warning("psycopg2 no instalado, skip verificación de PostgreSQL")
        return None
    except Exception as e:
        print_error(f"Error conectando a PostgreSQL: {e}")
        return False


def check_redis_connection(settings: Settings) -> bool:
    """Verifica conexión a Redis."""
    try:
        import redis

        r = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password,
            socket_connect_timeout=3
        )
        r.ping()
        return True
    except ImportError:
        print_warning("redis-py no instalado, skip verificación de Redis")
        return None
    except Exception as e:
        print_error(f"Error conectando a Redis: {e}")
        return False


def display_configuration(settings: Settings, verbose: bool = False) -> None:
    """Muestra la configuración cargada."""
    print_header("Configuración de la Aplicación")

    print_info(f"Nombre: {settings.app_name}")
    print_info(f"Versión: {settings.app_version}")
    print_info(f"Entorno: {settings.environment}")

    print_header("Base de Datos (PostgreSQL)")
    print_info(f"Host: {settings.database.host}")
    print_info(f"Puerto: {settings.database.port}")
    print_info(f"Base de datos: {settings.database.name}")
    print_info(f"Usuario: {settings.database.user}")
    if verbose:
        print_info(f"URL: {settings.database.url}")

    print_header("Redis Cache")
    print_info(f"Host: {settings.redis.host}")
    print_info(f"Puerto: {settings.redis.port}")
    print_info(f"DB: {settings.redis.db}")
    print_info(f"TTL: {settings.redis.ttl}s")
    if verbose:
        print_info(f"URL: {settings.redis.url}")

    print_header("API Server")
    print_info(f"Host: {settings.api.host}")
    print_info(f"Puerto: {settings.api.port}")
    print_info(f"Reload: {settings.api.reload}")

    print_header("Logging")
    print_info(f"Nivel: {settings.logging.level}")
    print_info(f"Formato: {settings.logging.format}")
    if settings.logging.file:
        print_info(f"Archivo: {settings.logging.file}")

    print_header("Motor de Pricing")
    print_info(f"Intervalo de actualización: {settings.pricing.update_interval}s")
    print_info(f"Umbral mínimo de cambio: €{settings.pricing.min_change_threshold}")
    print_info(f"Cambios máximos diarios: {settings.pricing.max_daily_changes}")

    print_header("Machine Learning")
    print_info(f"Ruta del modelo: {settings.ml.model_path}")
    print_info(f"Intervalo de reentrenamiento: {settings.ml.retrain_interval}s")

    print_header("APIs Externas")

    # Football Data API
    if settings.external_apis.football_data_api_key:
        print_success("Football Data API: Configurada")
        if verbose:
            print_info(f"URL: {settings.external_apis.football_data_api_url}", indent=1)
    else:
        print_warning("Football Data API: No configurada (API key faltante)")

    # Weather API
    if settings.external_apis.weather_api_key:
        print_success("Weather API: Configurada")
        if verbose:
            print_info(f"URL: {settings.external_apis.weather_api_url}", indent=1)
    else:
        print_warning("Weather API: No configurada (API key faltante)")

    # Google Analytics
    ga_status = "Mock" if settings.external_apis.ga_property_id == "mock" else "Configurada"
    print_info(f"Google Analytics: {ga_status}")
    if verbose:
        print_info(f"Property ID: {settings.external_apis.ga_property_id}", indent=1)
        print_info(f"Credentials: {settings.external_apis.ga_credentials_path}", indent=1)

    # Ticketing System
    ticketing_status = "Mock" if settings.external_apis.ticketing_api_key == "mock" else "Configurada"
    print_info(f"Ticketing System: {ticketing_status}")
    if verbose:
        print_info(f"URL: {settings.external_apis.ticketing_api_url}", indent=1)
        print_info(f"Reservation TTL: {settings.external_apis.ticketing_reservation_ttl}s", indent=1)

    print_header("Información del Estadio")
    print_info(f"Nombre: {settings.stadium_name}")
    print_info(f"Capacidad: {settings.stadium_capacity:,} asientos")
    if verbose:
        print_info(f"Ubicación: {settings.stadium_latitude}, {settings.stadium_longitude}")

    print_header("Archivos de Configuración YAML")
    config_files = {
        "base": settings.config_base_path,
        "pricing_rules": settings.config_pricing_rules_path,
        "zones": settings.config_zones_path,
        "competitions": settings.config_competitions_path,
    }

    for name, path in config_files.items():
        if Path(path).exists():
            print_success(f"{name}: {path}")
        else:
            print_warning(f"{name}: {path} (no existe)")


def main():
    """Función principal."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Verifica la carga de variables de entorno del sistema Smart Pricing'
    )
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar detalles completos')
    parser.add_argument('--check-services', '-s', action='store_true',
                       help='Verificar conexiones a servicios (DB, Redis)')

    args = parser.parse_args()

    # Banner
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║        Smart Pricing - Environment Checker                ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")

    # Intentar cargar configuración
    print_header("Cargando Configuración")

    try:
        # Limpiar la caché de get_settings para forzar recarga
        get_settings.cache_clear()
        settings = get_settings()
        print_success("Configuración cargada exitosamente desde .env")
    except Exception as e:
        print_error(f"Error al cargar configuración: {e}")
        print_info("\nAsegúrate de que:")
        print_info("  1. Existe un archivo .env en la raíz del proyecto")
        print_info("  2. Las variables tienen el formato correcto")
        print_info("  3. Los valores cumplen las validaciones")
        return 1

    # Mostrar configuración
    display_configuration(settings, verbose=args.verbose)

    # Validar configuración
    print_header("Validación de Configuración")

    warnings = settings.validate_configuration()

    if warnings:
        print_warning(f"Se encontraron {len(warnings)} advertencias:")
        for warning in warnings:
            print_warning(f"  {warning}")
    else:
        print_success("Todas las validaciones pasaron correctamente")

    # Verificar servicios si se solicita
    if args.check_services:
        print_header("Verificación de Servicios")

        # PostgreSQL
        db_status = check_database_connection(settings)
        if db_status is True:
            print_success("PostgreSQL: Conexión exitosa")
        elif db_status is False:
            print_error("PostgreSQL: Error de conexión")

        # Redis
        redis_status = check_redis_connection(settings)
        if redis_status is True:
            print_success("Redis: Conexión exitosa")
        elif redis_status is False:
            print_error("Redis: Error de conexión")

    # Resumen final
    print_header("Resumen")

    if not warnings:
        print_success("Sistema configurado correctamente")
        print_info("\nPuedes iniciar la aplicación con:")
        print_info("  uvicorn src.api.main:app --reload")
        return 0
    else:
        print_warning(f"Sistema configurado con {len(warnings)} advertencias")
        print_info("\nRevisa las advertencias arriba antes de continuar")
        return 0 if not any("no está configurada" in w for w in warnings) else 1


if __name__ == '__main__':
    sys.exit(main())
