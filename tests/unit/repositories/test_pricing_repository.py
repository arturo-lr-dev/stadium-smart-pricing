"""Unit tests for PricingHistoryRepository."""

import pytest
from datetime import datetime, timedelta

from src.domain.repositories.pricing_repository import PricingHistoryRepository
from src.domain.models.pricing import PricingFactors, ZonePricing, MatchPricing


class TestPricingHistoryRepository:
    """Test suite for PricingHistoryRepository."""

    @pytest.fixture
    def sample_pricing_factors(self):
        """Sample pricing factors."""
        return PricingFactors(
            demand_score=0.75,
            time_factor=1.2,
            inventory_factor=1.1,
            competition_factor=1.5,
            rival_factor=1.0,
            weather_factor=1.0,
            special_conditions={},
        )

    @pytest.fixture
    def sample_zone_pricing(self, sample_pricing_factors):
        """Sample zone pricing."""
        return ZonePricing(
            zone_id="test_zone_001",
            zone_name="Tribuna Norte",
            current_price=35.50,
            base_price=30.0,
            factors=sample_pricing_factors,
            last_updated=datetime.now(),
            sold_tickets=3500,
            available_tickets=1500,
            capacity=5000,
            occupancy_percent=70.0,
        )

    def test_save_zone_pricing(self, test_db_session, create_match, create_zone, sample_zone_pricing):
        """Test saving pricing history for a zone."""
        repo = PricingHistoryRepository(test_db_session)

        record = repo.save_zone_pricing(create_match.id, sample_zone_pricing)

        assert record is not None
        assert record["match_id"] == create_match.id
        assert record["zone_id"] == sample_zone_pricing.zone_id
        assert record["price"] == sample_zone_pricing.current_price

    def test_get_latest_price(self, test_db_session, create_match, create_zone, sample_zone_pricing):
        """Test getting latest price for a match and zone."""
        repo = PricingHistoryRepository(test_db_session)

        # Save multiple pricing records
        for i in range(3):
            pricing = sample_zone_pricing.model_copy(update={"current_price": 30.0 + i})
            repo.save_zone_pricing(create_match.id, pricing)

        latest = repo.get_latest_price(create_match.id, create_zone.id)

        assert latest is not None
        # When timestamps are the same, any of the prices could be returned
        assert latest["price"] in [30.0, 31.0, 32.0]

    def test_get_latest_price_not_found(self, test_db_session):
        """Test getting latest price when no records exist."""
        repo = PricingHistoryRepository(test_db_session)

        latest = repo.get_latest_price("non_existent_match", "non_existent_zone")

        assert latest is None

    def test_get_price_history(self, test_db_session, create_match, create_zone, sample_zone_pricing):
        """Test getting price history over time."""
        repo = PricingHistoryRepository(test_db_session)

        # Save multiple pricing records
        for i in range(5):
            pricing = sample_zone_pricing.model_copy(update={"current_price": 30.0 + i})
            repo.save_zone_pricing(create_match.id, pricing)

        history = repo.get_price_history(create_match.id, create_zone.id, hours=24)

        assert len(history) == 5

    def test_get_by_match(self, test_db_session, create_match, create_zone, sample_zone_pricing):
        """Test getting all pricing history for a match."""
        repo = PricingHistoryRepository(test_db_session)

        # Save multiple records
        for i in range(3):
            repo.save_zone_pricing(create_match.id, sample_zone_pricing)

        records = repo.get_by_match(create_match.id)

        assert len(records) == 3

    def test_save_pricing_match(self, test_db_session, create_match, create_zone, sample_zone_pricing):
        """Test saving pricing for entire match."""
        repo = PricingHistoryRepository(test_db_session)

        # Create match pricing with multiple zones
        match_pricing = MatchPricing(
            match_id=create_match.id,
            zones=[sample_zone_pricing],
            total_capacity=5000,
            last_calculation=datetime.now(),
        )

        records = repo.save_pricing(match_pricing)

        assert len(records) == 1
        assert records[0]["match_id"] == create_match.id

    def test_get_average_price(self, test_db_session, create_match, create_zone, sample_zone_pricing):
        """Test calculating average price over time."""
        repo = PricingHistoryRepository(test_db_session)

        # Save records with different prices
        for i in range(3):
            pricing = sample_zone_pricing.model_copy(update={"current_price": 30.0 + (i * 10)})
            repo.save_zone_pricing(create_match.id, pricing)

        avg = repo.get_average_price(create_match.id, create_zone.id, hours=24)

        assert avg == 40.0  # (30 + 40 + 50) / 3

    def test_get_price_changes(self, test_db_session, create_match, create_zone, sample_zone_pricing):
        """Test getting significant price changes."""
        repo = PricingHistoryRepository(test_db_session)

        # Save records with varying prices
        prices = [30.0, 32.0, 40.0, 42.0]  # 40 is a significant change from 32
        for price in prices:
            pricing = sample_zone_pricing.model_copy(update={"current_price": price})
            repo.save_zone_pricing(create_match.id, pricing)

        changes = repo.get_price_changes(create_match.id, create_zone.id, min_change_percent=5.0)

        assert len(changes) >= 1  # At least one significant change

    def test_delete_old_records(self, test_db_session, create_match, create_zone, sample_zone_pricing):
        """Test deleting old pricing records."""
        repo = PricingHistoryRepository(test_db_session)

        # Save some records
        for i in range(5):
            repo.save_zone_pricing(create_match.id, sample_zone_pricing)

        # Delete records older than 90 days (none in this case)
        count = repo.delete_old_records(days=90)

        # Since we just created them, none should be deleted
        assert count == 0
