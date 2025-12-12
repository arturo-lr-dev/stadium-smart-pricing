"""Fixtures for repository unit tests."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.database import Base
from src.domain.models.db_models import (
    MatchDB,
    ZoneDB,
    SaleDB,
    PricingHistoryDB,
    MatchStatus,
    CustomerType,
    PaymentStatus,
)


@pytest.fixture(scope="function")
def test_db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_match_data():
    """Sample match data for testing."""
    return {
        "id": "test_match_001",
        "home_team": "RCD Mallorca",
        "away_team": "FC Barcelona",
        "competition": "la_liga",
        "match_date": datetime.now() + timedelta(days=30),
        "venue": "Son Moix",
        "capacity": 23142,
        "is_derby": False,
        "is_holiday": False,
        "home_position": 12,
        "away_position": 1,
        "status": MatchStatus.SCHEDULED,
    }


@pytest.fixture
def sample_zone_data():
    """Sample zone data for testing."""
    return {
        "id": "test_zone_001",
        "name": "Tribuna Norte",
        "category": "standard",
        "capacity": 5000,
        "base_price": 30.0,
        "min_price": 20.0,
        "max_price": 50.0,
        "price_multiplier": 1.0,
        "is_active": True,
    }


@pytest.fixture
def sample_sale_data():
    """Sample sale data for testing."""
    return {
        "id": "test_sale_001",
        "match_id": "test_match_001",
        "zone_id": "test_zone_001",
        "quantity": 2,
        "price_per_ticket": 35.0,
        "total_amount": 70.0,
        "customer_type": CustomerType.GENERAL,
        "payment_status": PaymentStatus.COMPLETED,
        "purchase_datetime": datetime.now(),
    }


@pytest.fixture
def create_match(test_db_session: Session, sample_match_data):
    """Create a test match in the database."""
    match = MatchDB(**sample_match_data)
    test_db_session.add(match)
    test_db_session.commit()
    test_db_session.refresh(match)
    return match


@pytest.fixture
def create_zone(test_db_session: Session, sample_zone_data):
    """Create a test zone in the database."""
    zone = ZoneDB(**sample_zone_data)
    test_db_session.add(zone)
    test_db_session.commit()
    test_db_session.refresh(zone)
    return zone


@pytest.fixture
def create_sale(test_db_session: Session, create_match, create_zone, sample_sale_data):
    """Create a test sale in the database."""
    sale = SaleDB(**sample_sale_data)
    test_db_session.add(sale)
    test_db_session.commit()
    test_db_session.refresh(sale)
    return sale
