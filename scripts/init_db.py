#!/usr/bin/env python3
"""
Database initialization script.

This script creates or drops all database tables.
Use with caution in production!
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings
from src.core.database import (
    Base,
    check_database_connection,
    create_all_tables,
    drop_all_tables,
    get_engine,
)
from src.core.logging import get_logger, setup_logging

# Import all models to ensure they're registered with Base
from src.domain.models import (  # noqa: F401
    ConfigurationDB,
    DemandMetricsDB,
    ExternalDataDB,
    MatchDB,
    PricingHistoryDB,
    SaleDB,
    TeamDB,
    ZoneDB,
)

logger = get_logger(__name__)


def confirm_action(message: str) -> bool:
    """
    Ask user for confirmation.

    Args:
        message: Confirmation message

    Returns:
        True if user confirms, False otherwise
    """
    response = input(f"{message} (yes/no): ").lower().strip()
    return response in ["yes", "y"]


def list_tables() -> None:
    """List all tables that will be created."""
    logger.info("Tables to be created:")
    for table_name in Base.metadata.tables.keys():
        logger.info(f"  - {table_name}")


def create_tables(force: bool = False) -> None:
    """
    Create all database tables.

    Args:
        force: Skip confirmation if True
    """
    logger.info("=== Creating Database Tables ===")

    # Check database connection
    if not check_database_connection():
        logger.error("Cannot connect to database. Please check your configuration.")
        sys.exit(1)

    # List tables
    list_tables()

    # Confirm action
    if not force:
        if not confirm_action("Do you want to create these tables?"):
            logger.info("Operation cancelled")
            return

    # Create tables
    try:
        create_all_tables()
        logger.info("✓ Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        sys.exit(1)


def drop_tables(force: bool = False) -> None:
    """
    Drop all database tables.

    Args:
        force: Skip confirmation if True
    """
    logger.warning("=== Dropping Database Tables ===")
    logger.warning("WARNING: This will DELETE ALL DATA!")

    # Check database connection
    if not check_database_connection():
        logger.error("Cannot connect to database. Please check your configuration.")
        sys.exit(1)

    # List tables
    list_tables()

    # Confirm action
    if not force:
        if not confirm_action("Are you SURE you want to DROP these tables?"):
            logger.info("Operation cancelled")
            return

        # Double confirmation for safety
        if not confirm_action("This will delete ALL data. Continue?"):
            logger.info("Operation cancelled")
            return

    # Drop tables
    try:
        drop_all_tables()
        logger.warning("✓ Database tables dropped")
    except Exception as e:
        logger.error(f"Failed to drop tables: {e}")
        sys.exit(1)


def reset_tables(force: bool = False) -> None:
    """
    Drop and recreate all database tables.

    Args:
        force: Skip confirmation if True
    """
    logger.warning("=== Resetting Database ===")
    logger.warning("This will DROP and RECREATE all tables")

    if not force:
        if not confirm_action("Are you SURE you want to RESET the database?"):
            logger.info("Operation cancelled")
            return

    drop_tables(force=True)
    create_tables(force=True)
    logger.info("✓ Database reset complete")


def show_info() -> None:
    """Show database connection information."""
    settings = get_settings()

    logger.info("=== Database Configuration ===")
    logger.info(f"Host: {settings.database.host}")
    logger.info(f"Port: {settings.database.port}")
    logger.info(f"Database: {settings.database.name}")
    logger.info(f"User: {settings.database.user}")
    logger.info(f"Pool Size: {settings.database.pool_size}")
    logger.info(f"Max Overflow: {settings.database.max_overflow}")

    # Test connection
    if check_database_connection():
        logger.info("✓ Database connection: OK")
    else:
        logger.error("✗ Database connection: FAILED")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database initialization script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show database info
  python scripts/init_db.py --info

  # Create tables (with confirmation)
  python scripts/init_db.py --create

  # Create tables (skip confirmation)
  python scripts/init_db.py --create --force

  # Drop tables
  python scripts/init_db.py --drop

  # Reset database (drop + create)
  python scripts/init_db.py --reset
        """,
    )

    parser.add_argument(
        "--create", action="store_true", help="Create all database tables"
    )
    parser.add_argument("--drop", action="store_true", help="Drop all database tables")
    parser.add_argument(
        "--reset", action="store_true", help="Drop and recreate all tables"
    )
    parser.add_argument(
        "--info", action="store_true", help="Show database configuration"
    )
    parser.add_argument(
        "--force", action="store_true", help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Execute command
    if args.info:
        show_info()
    elif args.create:
        create_tables(force=args.force)
    elif args.drop:
        drop_tables(force=args.force)
    elif args.reset:
        reset_tables(force=args.force)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
