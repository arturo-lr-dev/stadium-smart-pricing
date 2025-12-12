#!/usr/bin/env python3
"""
Database seeding script.

Populates the database with sample data for testing and development.
"""

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings
from src.core.database import check_database_connection, get_db
from src.core.logging import get_logger, setup_logging
from src.domain.models import (
    CustomerType,
    MatchDB,
    MatchStatus,
    PaymentStatus,
    PricingHistoryDB,
    SaleDB,
    ZoneDB,
)

logger = get_logger(__name__)


def clear_all_data() -> None:
    """Clear all data from the database."""
    logger.warning("Clearing all data from database...")

    with get_db() as db:
        db.query(PricingHistoryDB).delete()
        db.query(SaleDB).delete()
        db.query(MatchDB).delete()
        db.query(ZoneDB).delete()
        db.commit()

    logger.info("✓ All data cleared")


def seed_zones() -> None:
    """Seed stadium zones."""
    logger.info("Seeding zones...")

    zones = [
        # VIP Zones
        {
            "id": "zone_vip_palco",
            "name": "Palcos VIP",
            "category": "vip",
            "capacity": 500,
            "base_price": 120.0,
            "min_price": 100.0,
            "max_price": 200.0,
            "price_multiplier": 1.5,
            "is_active": True,
            "description": "Luxury boxes with premium service",
            "amenities": ["private_bar", "waiter_service", "parking", "premium_seating"],
        },
        # Premium Zones
        {
            "id": "zone_tribuna_central",
            "name": "Tribuna Central",
            "category": "premium",
            "capacity": 3000,
            "base_price": 60.0,
            "min_price": 45.0,
            "max_price": 90.0,
            "price_multiplier": 1.2,
            "is_active": True,
            "description": "Central stand with best view",
            "amenities": ["covered", "food_stand", "restrooms"],
        },
        # Standard Zones
        {
            "id": "zone_tribuna_norte",
            "name": "Tribuna Norte",
            "category": "standard",
            "capacity": 5000,
            "base_price": 35.0,
            "min_price": 25.0,
            "max_price": 55.0,
            "price_multiplier": 1.0,
            "is_active": True,
            "description": "North stand - great atmosphere",
            "amenities": ["covered", "food_stand", "restrooms"],
        },
        {
            "id": "zone_tribuna_sur",
            "name": "Tribuna Sur",
            "category": "standard",
            "capacity": 5000,
            "base_price": 35.0,
            "min_price": 25.0,
            "max_price": 55.0,
            "price_multiplier": 1.0,
            "is_active": True,
            "description": "South stand - family friendly",
            "amenities": ["covered", "food_stand", "restrooms"],
        },
        {
            "id": "zone_lateral_este",
            "name": "Lateral Este",
            "category": "standard",
            "capacity": 4000,
            "base_price": 32.0,
            "min_price": 22.0,
            "max_price": 50.0,
            "price_multiplier": 0.95,
            "is_active": True,
            "description": "East side stand",
            "amenities": ["covered", "food_stand"],
        },
        {
            "id": "zone_lateral_oeste",
            "name": "Lateral Oeste",
            "category": "standard",
            "capacity": 4000,
            "base_price": 32.0,
            "min_price": 22.0,
            "max_price": 50.0,
            "price_multiplier": 0.95,
            "is_active": True,
            "description": "West side stand",
            "amenities": ["covered", "food_stand"],
        },
        # Reduced Price Zones
        {
            "id": "zone_animacion",
            "name": "Zona Animación",
            "category": "reduced",
            "capacity": 1000,
            "base_price": 20.0,
            "min_price": 15.0,
            "max_price": 35.0,
            "price_multiplier": 0.8,
            "is_active": True,
            "description": "Fan zone with ultras",
            "amenities": ["standing", "food_stand"],
        },
        {
            "id": "zone_general",
            "name": "Entrada General",
            "category": "reduced",
            "capacity": 642,
            "base_price": 18.0,
            "min_price": 12.0,
            "max_price": 30.0,
            "price_multiplier": 0.75,
            "is_active": True,
            "description": "General admission",
            "amenities": ["standing"],
        },
    ]

    with get_db() as db:
        for zone_data in zones:
            zone = ZoneDB(**zone_data)
            db.add(zone)

        db.commit()

    logger.info(f"✓ Seeded {len(zones)} zones")


def seed_matches() -> None:
    """Seed sample matches."""
    logger.info("Seeding matches...")

    # Teams in La Liga
    la_liga_teams = [
        ("FC Barcelona", 1),
        ("Real Madrid", 2),
        ("Atlético Madrid", 3),
        ("Real Sociedad", 4),
        ("Athletic Bilbao", 5),
        ("Valencia", 8),
        ("Villarreal", 9),
        ("Sevilla", 10),
        ("Real Betis", 11),
        ("Osasuna", 12),
        ("Getafe", 14),
        ("Cádiz", 18),
        ("Granada", 19),
        ("Almería", 20),
    ]

    competitions = [
        "La Liga",
        "Copa del Rey",
    ]

    base_date = datetime.now() + timedelta(days=7)
    matches = []

    # Create 12 upcoming matches
    for i in range(12):
        match_date = base_date + timedelta(days=i * 7)
        away_team, away_position = random.choice(la_liga_teams)

        is_derby = away_team in ["FC Barcelona", "Real Madrid", "Atlético Madrid"]
        competition = random.choice(competitions)

        # Important matches are more likely on weekends
        if match_date.weekday() in [5, 6]:  # Saturday or Sunday
            is_holiday = random.random() < 0.1
        else:
            is_holiday = False

        match = {
            "id": f"match_{uuid.uuid4().hex[:8]}",
            "home_team": "RCD Mallorca",
            "away_team": away_team,
            "competition": competition,
            "match_date": match_date,
            "venue": "Son Moix",
            "capacity": 23142,
            "is_derby": is_derby,
            "is_holiday": is_holiday,
            "home_position": random.randint(8, 15),
            "away_position": away_position,
            "status": MatchStatus.ON_SALE,
        }

        matches.append(match)

    with get_db() as db:
        for match_data in matches:
            match = MatchDB(**match_data)
            db.add(match)

        db.commit()

    logger.info(f"✓ Seeded {len(matches)} matches")


def seed_sales() -> None:
    """Seed sample sales data."""
    logger.info("Seeding sales...")

    with get_db() as db:
        matches = db.query(MatchDB).all()
        zones = db.query(ZoneDB).all()

        if not matches or not zones:
            logger.warning("No matches or zones found. Skipping sales seeding.")
            return

        total_sales = 0

        for match in matches:
            days_until = (match.match_date - datetime.now()).days

            # More sales for closer matches
            if days_until < 7:
                sales_factor = 0.7
            elif days_until < 14:
                sales_factor = 0.5
            elif days_until < 30:
                sales_factor = 0.3
            else:
                sales_factor = 0.1

            # More sales for derby matches
            if match.is_derby:
                sales_factor *= 1.5

            for zone in zones:
                # Number of sales for this zone (not tickets)
                num_sales = int(zone.capacity * sales_factor * random.uniform(0.05, 0.15))

                for _ in range(num_sales):
                    # Random date before match
                    days_before = random.randint(1, max(1, days_until))
                    sale_date = match.match_date - timedelta(days=days_before)

                    quantity = random.randint(1, 4)
                    price = zone.base_price * random.uniform(0.9, 1.2)
                    total = quantity * price

                    sale = SaleDB(
                        id=f"sale_{uuid.uuid4().hex[:8]}",
                        match_id=match.id,
                        zone_id=zone.id,
                        quantity=quantity,
                        price_per_ticket=round(price, 2),
                        total_amount=round(total, 2),
                        customer_type=random.choice(list(CustomerType)),
                        payment_status=PaymentStatus.COMPLETED,
                        purchase_datetime=sale_date,
                    )

                    db.add(sale)
                    total_sales += 1

        db.commit()

    logger.info(f"✓ Seeded {total_sales} sales")


def seed_pricing_history() -> None:
    """Seed sample pricing history."""
    logger.info("Seeding pricing history...")

    with get_db() as db:
        matches = db.query(MatchDB).all()
        zones = db.query(ZoneDB).all()

        if not matches or not zones:
            logger.warning("No matches or zones found. Skipping pricing history seeding.")
            return

        total_entries = 0

        for match in matches:
            days_until = (match.match_date - datetime.now()).days

            if days_until <= 0:
                continue

            # Create pricing history entries (daily)
            for day_offset in range(0, min(days_until, 60), 1):
                timestamp = datetime.now() + timedelta(days=day_offset)

                for zone in zones:
                    # Calculate some factors
                    time_factor = 1.0 + (60 - day_offset) * 0.01  # Increases as match approaches
                    demand_score = random.uniform(0.3, 0.9)

                    # Get sales count for this zone/match
                    sales_count = (
                        db.query(SaleDB)
                        .filter(SaleDB.match_id == match.id, SaleDB.zone_id == zone.id)
                        .count()
                    )
                    occupancy = (sales_count / zone.capacity) * 100 if zone.capacity > 0 else 0

                    inventory_factor = 1.0 + (occupancy / 100) * 0.3

                    price = zone.base_price * time_factor * inventory_factor
                    price = max(zone.min_price, min(price, zone.max_price))

                    history = PricingHistoryDB(
                        id=f"ph_{uuid.uuid4().hex[:8]}",
                        match_id=match.id,
                        zone_id=zone.id,
                        price=round(price, 2),
                        demand_score=round(demand_score, 3),
                        time_factor=round(time_factor, 3),
                        inventory_factor=round(inventory_factor, 3),
                        competition_factor=1.5 if match.is_derby else 1.0,
                        rival_factor=1.0,
                        weather_factor=1.0,
                        sold_tickets=sales_count,
                        available_tickets=zone.capacity - sales_count,
                        occupancy_percent=round(occupancy, 2),
                        timestamp=timestamp,
                    )

                    db.add(history)
                    total_entries += 1

        db.commit()

    logger.info(f"✓ Seeded {total_entries} pricing history entries")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database seeding script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed all data
  python scripts/seed_data.py

  # Clear existing data and seed
  python scripts/seed_data.py --clear

  # Seed only zones
  python scripts/seed_data.py --zones-only
        """,
    )

    parser.add_argument(
        "--clear", action="store_true", help="Clear existing data before seeding"
    )
    parser.add_argument(
        "--zones-only", action="store_true", help="Seed only zones"
    )
    parser.add_argument(
        "--matches-only", action="store_true", help="Seed only matches"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Check database connection
    if not check_database_connection():
        logger.error("Cannot connect to database. Please check your configuration.")
        sys.exit(1)

    logger.info("=== Database Seeding ===")

    # Clear data if requested
    if args.clear:
        clear_all_data()

    # Seed data
    try:
        if args.zones_only:
            seed_zones()
        elif args.matches_only:
            seed_matches()
        else:
            # Seed in order (zones first, then matches, then sales and pricing)
            seed_zones()
            seed_matches()
            seed_sales()
            seed_pricing_history()

        logger.info("✓ Database seeding completed successfully")

    except Exception as e:
        logger.error(f"Failed to seed database: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
