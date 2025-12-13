"""Unit tests for PriceUpdaterWorker."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.domain.models.match import CompetitionType, Match, MatchStatus
from src.domain.models.pricing import MatchPricing, PricingFactors, ZonePricing
from src.domain.models.zone import Zone, ZoneCategory
from src.workers.price_updater import PriceUpdaterWorker


@pytest.fixture
def mock_dependencies():
    """Mock all dependencies for PriceUpdaterWorker."""
    with patch("src.workers.price_updater.get_db_session") as mock_db_session, \
         patch("src.workers.price_updater.get_redis_client") as mock_redis, \
         patch("src.workers.price_updater.get_pricing_engine") as mock_pricing_engine, \
         patch("src.workers.price_updater.MatchRepository") as mock_match_repo, \
         patch("src.workers.price_updater.ZoneRepository") as mock_zone_repo, \
         patch("src.workers.price_updater.PricingHistoryRepository") as mock_pricing_repo:

        # Mock database session
        db_mock = MagicMock()
        mock_db_session.return_value = iter([db_mock])

        # Mock Redis client
        redis_mock = MagicMock()
        mock_redis.return_value = redis_mock

        # Mock pricing engine
        pricing_engine_mock = MagicMock()
        mock_pricing_engine.return_value = pricing_engine_mock

        # Mock repositories
        match_repo_mock = MagicMock()
        zone_repo_mock = MagicMock()
        pricing_repo_mock = MagicMock()

        mock_match_repo.return_value = match_repo_mock
        mock_zone_repo.return_value = zone_repo_mock
        mock_pricing_repo.return_value = pricing_repo_mock

        yield {
            "db": db_mock,
            "redis": redis_mock,
            "pricing_engine": pricing_engine_mock,
            "match_repo": match_repo_mock,
            "zone_repo": zone_repo_mock,
            "pricing_repo": pricing_repo_mock,
        }


def create_sample_match():
    """Create a sample match for testing."""
    return Match(
        id="match1",
        home_team="Real Mallorca",
        away_team="FC Barcelona",
        competition=CompetitionType.LA_LIGA,
        date=datetime.now() + timedelta(days=7),
        venue="Son Moix",
        capacity=23142,
        is_derby=False,
        is_holiday=False,
        status=MatchStatus.SCHEDULED,
    )


def create_sample_zone():
    """Create a sample zone for testing."""
    return Zone(
        id="zone1",
        name="Tribune",
        category=ZoneCategory.STANDARD,
        capacity=5000,
        base_price=35.0,
        min_price=25.0,
        max_price=60.0,
        price_multiplier=1.0,
    )


def create_sample_pricing():
    """Create sample pricing data."""
    zone_pricing = ZonePricing(
        zone_id="zone1",
        zone_name="Tribune",
        current_price=40.0,
        base_price=35.0,
        factors=PricingFactors(
            demand_score=0.6,
            time_factor=1.2,
            inventory_factor=1.0,
            competition_factor=1.5,
            weather_factor=1.0,
        ),
        last_updated=datetime.now(),
        sold_tickets=500,
        available_tickets=4500,
        capacity=5000,
        occupancy_percent=10.0,
    )

    return MatchPricing(
        match_id="match1",
        zones=[zone_pricing],
        total_revenue=20000.0,
        total_sold=500,
        total_capacity=23142,
        avg_price=40.0,
        last_calculation=datetime.now(),
    )


def test_worker_initialization():
    """Test worker initialization."""
    worker = PriceUpdaterWorker(
        update_interval=300,
        lookback_days=30,
        max_consecutive_errors=5
    )

    assert worker.name == "PriceUpdaterWorker"
    assert worker.update_interval == 300
    assert worker.lookback_days == 30
    assert worker.max_consecutive_errors == 5
    assert worker.matches_processed == 0
    assert worker.prices_updated == 0


def test_fetch_upcoming_matches(mock_dependencies):
    """Test fetching upcoming matches."""
    worker = PriceUpdaterWorker(update_interval=1, lookback_days=30)
    worker.db = mock_dependencies["db"]

    # Mock match repository
    sample_match = create_sample_match()
    mock_dependencies["match_repo"].get_upcoming.return_value = [sample_match]

    with patch("src.workers.price_updater.MatchRepository", return_value=mock_dependencies["match_repo"]):
        matches = worker._fetch_upcoming_matches()

    assert len(matches) == 1
    assert matches[0].id == "match1"
    mock_dependencies["match_repo"].get_upcoming.assert_called_once_with(days=30)


def test_fetch_zones(mock_dependencies):
    """Test fetching zones."""
    worker = PriceUpdaterWorker(update_interval=1)
    worker.db = mock_dependencies["db"]

    # Mock zone repository
    sample_zone = create_sample_zone()
    mock_dependencies["zone_repo"].get_active_zones.return_value = [sample_zone]

    with patch("src.workers.price_updater.ZoneRepository", return_value=mock_dependencies["zone_repo"]):
        zones = worker._fetch_zones()

    assert len(zones) == 1
    assert zones[0].id == "zone1"
    mock_dependencies["zone_repo"].get_active_zones.assert_called_once()


def test_process_match(mock_dependencies):
    """Test processing a single match."""
    worker = PriceUpdaterWorker(update_interval=1)
    worker.pricing_engine = mock_dependencies["pricing_engine"]
    worker.redis = mock_dependencies["redis"]
    worker.db = mock_dependencies["db"]

    # Mock data
    sample_match = create_sample_match()
    sample_zone = create_sample_zone()
    sample_pricing = create_sample_pricing()

    # Mock pricing engine
    mock_dependencies["pricing_engine"].calculate_match_pricing.return_value = sample_pricing

    # Mock pricing repository
    with patch("src.workers.price_updater.PricingHistoryRepository", return_value=mock_dependencies["pricing_repo"]):
        worker._process_match(sample_match, [sample_zone])

    # Verify pricing was calculated
    mock_dependencies["pricing_engine"].calculate_match_pricing.assert_called_once()

    # Verify pricing was cached
    mock_dependencies["redis"].setex.assert_called_once()

    # Verify pricing was saved to history
    mock_dependencies["pricing_repo"].save_pricing.assert_called_once_with(sample_pricing)
    mock_dependencies["db"].commit.assert_called_once()


def test_cache_pricing(mock_dependencies):
    """Test caching pricing data."""
    worker = PriceUpdaterWorker(update_interval=1)
    worker.redis = mock_dependencies["redis"]

    sample_pricing = create_sample_pricing()

    worker._cache_pricing("match1", sample_pricing)

    # Verify Redis setex was called
    mock_dependencies["redis"].setex.assert_called_once()
    call_args = mock_dependencies["redis"].setex.call_args
    assert call_args[0][0] == "pricing:match:match1"  # key
    assert call_args[0][1] == 300  # TTL


def test_save_pricing_history(mock_dependencies):
    """Test saving pricing to history."""
    worker = PriceUpdaterWorker(update_interval=1)
    worker.db = mock_dependencies["db"]

    sample_pricing = create_sample_pricing()

    with patch("src.workers.price_updater.PricingHistoryRepository", return_value=mock_dependencies["pricing_repo"]):
        worker._save_pricing_history(sample_pricing)

    mock_dependencies["pricing_repo"].save_pricing.assert_called_once_with(sample_pricing)
    mock_dependencies["db"].commit.assert_called_once()


def test_get_metrics():
    """Test getting worker metrics."""
    worker = PriceUpdaterWorker(update_interval=300)
    worker.matches_processed = 10
    worker.prices_updated = 15
    worker.total_execution_time = 125.5
    worker.error_count = 2

    metrics = worker.get_metrics()

    assert metrics["worker_name"] == "PriceUpdaterWorker"
    assert metrics["running"] is False
    assert metrics["matches_processed"] == 10
    assert metrics["prices_updated"] == 15
    assert metrics["total_execution_time"] == 125.5
    assert metrics["error_count"] == 2
    assert "is_healthy" in metrics


def test_execute_update_cycle_no_matches(mock_dependencies):
    """Test update cycle when no matches are found."""
    worker = PriceUpdaterWorker(update_interval=1)
    worker.db = mock_dependencies["db"]
    worker.redis = mock_dependencies["redis"]
    worker.pricing_engine = mock_dependencies["pricing_engine"]

    # Mock no matches
    mock_dependencies["match_repo"].get_upcoming.return_value = []
    mock_dependencies["zone_repo"].get_active_zones.return_value = []

    with patch("src.workers.price_updater.MatchRepository", return_value=mock_dependencies["match_repo"]), \
         patch("src.workers.price_updater.ZoneRepository", return_value=mock_dependencies["zone_repo"]):
        worker._execute_update_cycle()

    # Should not process anything
    assert worker.matches_processed == 0
    mock_dependencies["pricing_engine"].calculate_match_pricing.assert_not_called()


def test_execute_update_cycle_with_matches(mock_dependencies):
    """Test update cycle with matches."""
    worker = PriceUpdaterWorker(update_interval=1)
    worker.db = mock_dependencies["db"]
    worker.redis = mock_dependencies["redis"]
    worker.pricing_engine = mock_dependencies["pricing_engine"]

    # Mock data
    sample_match = create_sample_match()
    sample_zone = create_sample_zone()
    sample_pricing = create_sample_pricing()

    mock_dependencies["match_repo"].get_upcoming.return_value = [sample_match]
    mock_dependencies["zone_repo"].get_active_zones.return_value = [sample_zone]
    mock_dependencies["pricing_engine"].calculate_match_pricing.return_value = sample_pricing

    with patch("src.workers.price_updater.MatchRepository", return_value=mock_dependencies["match_repo"]), \
         patch("src.workers.price_updater.ZoneRepository", return_value=mock_dependencies["zone_repo"]), \
         patch("src.workers.price_updater.PricingHistoryRepository", return_value=mock_dependencies["pricing_repo"]):
        worker._execute_update_cycle()

    # Verify match was processed
    assert worker.matches_processed == 1
    mock_dependencies["pricing_engine"].calculate_match_pricing.assert_called_once()
