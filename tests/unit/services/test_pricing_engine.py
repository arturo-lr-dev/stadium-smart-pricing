"""
Unit tests for PricingEngine.

Tests all pricing calculation methods and business logic.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch, call

from src.domain.models.match import Match, MatchStatus
from src.domain.models.pricing import MatchPricing, PricingFactors, ZonePricing
from src.domain.models.zone import Zone
from src.domain.services.pricing_engine import PricingEngine


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_rules_engine():
    """Mock RulesEngine."""
    engine = MagicMock()
    engine.get_competition_multiplier.return_value = 1.5
    engine.get_rival_multiplier.return_value = 1.2
    engine.get_time_decay_factor.return_value = 1.3
    engine.get_inventory_pressure_factor.return_value = 1.1
    engine.get_special_multipliers.return_value = {"derby": 1.2}
    engine.is_price_change_allowed.return_value = (True, "Change allowed")
    return engine


@pytest.fixture
def mock_demand_predictor():
    """Mock DemandPredictor."""
    predictor = MagicMock()
    predictor.predict_demand.return_value = 0.75
    return predictor


@pytest.fixture
def mock_inventory_manager():
    """Mock InventoryManager."""
    manager = MagicMock()
    manager.get_zone_inventory.return_value = (1000, 4000)  # sold, available
    manager.get_match_inventory.return_value = {
        "zone_1": (1000, 4000),
        "zone_2": (500, 2500),
    }
    return manager


@pytest.fixture
def mock_match_repository():
    """Mock MatchRepository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_zone_repository():
    """Mock ZoneRepository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_pricing_repository():
    """Mock PricingHistoryRepository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = MagicMock()
    return session


@pytest.fixture
def pricing_engine(
    mock_rules_engine,
    mock_demand_predictor,
    mock_inventory_manager,
    mock_match_repository,
    mock_zone_repository,
    mock_pricing_repository,
    mock_db_session,
):
    """Create PricingEngine with all mocked dependencies."""
    return PricingEngine(
        rules_engine=mock_rules_engine,
        demand_predictor=mock_demand_predictor,
        inventory_manager=mock_inventory_manager,
        match_repository=mock_match_repository,
        zone_repository=mock_zone_repository,
        pricing_repository=mock_pricing_repository,
        db_session=mock_db_session,
    )


@pytest.fixture
def sample_match():
    """Create a sample match."""
    return Match(
        id="match_001",
        home_team="RCD Mallorca",
        away_team="FC Barcelona",
        competition="la_liga",
        match_date=datetime.now() + timedelta(days=7),
        venue="Son Moix",
        capacity=23142,
        is_derby=False,
        is_holiday=False,
        home_position=12,
        away_position=2,
        status=MatchStatus.SCHEDULED,
    )


@pytest.fixture
def sample_zone():
    """Create a sample zone."""
    return Zone(
        id="zone_1",
        name="North Stand",
        category="standard",
        capacity=5000,
        base_price=30.0,
        min_price=20.0,
        max_price=50.0,
        price_multiplier=1.0,
        is_active=True,
    )


@pytest.fixture
def sample_zones():
    """Create multiple sample zones."""
    return [
        Zone(
            id="zone_1",
            name="North Stand",
            category="standard",
            capacity=5000,
            base_price=30.0,
            min_price=20.0,
            max_price=50.0,
            price_multiplier=1.0,
            is_active=True,
        ),
        Zone(
            id="zone_2",
            name="South Stand",
            category="standard",
            capacity=3000,
            base_price=25.0,
            min_price=18.0,
            max_price=45.0,
            price_multiplier=0.95,
            is_active=True,
        ),
    ]


# ============================================================================
# TESTS: calculate_match_pricing
# ============================================================================


def test_calculate_match_pricing_success(pricing_engine, sample_match, sample_zones):
    """Test successful match pricing calculation."""
    result = pricing_engine.calculate_match_pricing(sample_match, sample_zones)

    assert isinstance(result, MatchPricing)
    assert result.match_id == sample_match.id
    assert len(result.zones) == len(sample_zones)
    assert result.total_capacity == sum(z.capacity for z in sample_zones)
    assert result.avg_price > 0


def test_calculate_match_pricing_empty_zones(pricing_engine, sample_match):
    """Test pricing calculation with no zones raises error."""
    with pytest.raises(ValueError, match="Cannot calculate pricing without zones"):
        pricing_engine.calculate_match_pricing(sample_match, [])


def test_calculate_match_pricing_with_custom_datetime(
    pricing_engine, sample_match, sample_zones
):
    """Test pricing calculation with custom datetime."""
    custom_datetime = datetime(2024, 6, 15, 12, 0, 0)
    result = pricing_engine.calculate_match_pricing(
        sample_match, sample_zones, current_datetime=custom_datetime
    )

    assert result.last_calculation == custom_datetime


def test_calculate_match_pricing_aggregates_correctly(
    pricing_engine, sample_match, sample_zones, mock_inventory_manager
):
    """Test that aggregate metrics are calculated correctly."""
    # Setup inventory mock to return known values
    mock_inventory_manager.get_zone_inventory.side_effect = [
        (1000, 4000),  # zone_1: 1000 sold, 4000 available
        (500, 2500),  # zone_2: 500 sold, 2500 available
    ]

    result = pricing_engine.calculate_match_pricing(sample_match, sample_zones)

    assert result.total_sold == 1500  # 1000 + 500
    assert result.total_capacity == 8000  # 5000 + 3000


def test_calculate_match_pricing_handles_zone_error(
    pricing_engine, sample_match, sample_zones, mock_demand_predictor, caplog
):
    """Test that calculation continues if one zone fails."""
    # Make predictor fail for first zone only
    mock_demand_predictor.predict_demand.side_effect = [
        Exception("Prediction failed"),
        0.75,  # Second zone succeeds
    ]

    result = pricing_engine.calculate_match_pricing(sample_match, sample_zones)

    # Should have pricing for only the successful zone
    assert len(result.zones) == 1
    assert "Error calculating pricing for zone" in caplog.text


# ============================================================================
# TESTS: _calculate_zone_price
# ============================================================================


def test_calculate_zone_price_basic(pricing_engine, sample_match, sample_zone):
    """Test basic zone price calculation."""
    current_datetime = datetime.now()
    result = pricing_engine._calculate_zone_price(sample_match, sample_zone, current_datetime)

    assert isinstance(result, ZonePricing)
    assert result.zone_id == sample_zone.id
    assert result.zone_name == sample_zone.name
    assert result.base_price == sample_zone.base_price
    assert result.current_price >= sample_zone.min_price
    assert result.current_price <= sample_zone.max_price


def test_calculate_zone_price_respects_min_max(
    pricing_engine, sample_match, mock_rules_engine
):
    """Test that calculated price is clamped to min/max."""
    zone = Zone(
        id="zone_test",
        name="Test Zone",
        category="standard",
        capacity=1000,
        base_price=30.0,
        min_price=25.0,
        max_price=35.0,
        price_multiplier=1.0,
    )

    # Set high multipliers (within valid ranges) to force clamping to max_price
    # Valid ranges: competition_factor (1.0-3.0), rival_factor (0.8-2.0),
    # time_factor (0.5-2.0), inventory_factor (0.7-1.5)
    mock_rules_engine.get_competition_multiplier.return_value = 3.0  # max value
    mock_rules_engine.get_rival_multiplier.return_value = 2.0  # max value
    mock_rules_engine.get_time_decay_factor.return_value = 2.0  # max value
    mock_rules_engine.get_inventory_pressure_factor.return_value = 1.5  # max value

    result = pricing_engine._calculate_zone_price(sample_match, zone, datetime.now())

    # Price should be clamped to max_price due to high multipliers
    assert result.current_price == zone.max_price


def test_calculate_zone_price_includes_inventory_data(
    pricing_engine, sample_match, sample_zone, mock_inventory_manager
):
    """Test that zone pricing includes correct inventory data."""
    mock_inventory_manager.get_zone_inventory.return_value = (2000, 3000)

    result = pricing_engine._calculate_zone_price(sample_match, sample_zone, datetime.now())

    assert result.sold_tickets == 2000
    assert result.available_tickets == 3000
    assert result.capacity == sample_zone.capacity
    assert result.occupancy_percent == (2000 / sample_zone.capacity * 100)


# ============================================================================
# TESTS: _calculate_pricing_factors
# ============================================================================


def test_calculate_pricing_factors_basic(
    pricing_engine, sample_match, sample_zone, mock_demand_predictor, mock_rules_engine
):
    """Test basic pricing factors calculation."""
    current_datetime = datetime.now()
    occupancy_percent = 40.0

    result = pricing_engine._calculate_pricing_factors(
        sample_match, sample_zone, current_datetime, occupancy_percent
    )

    assert isinstance(result, PricingFactors)
    assert 0.0 <= result.demand_score <= 1.0
    assert result.time_factor > 0
    assert result.inventory_factor > 0
    assert result.competition_factor > 0
    assert result.rival_factor > 0


def test_calculate_pricing_factors_calls_dependencies(
    pricing_engine,
    sample_match,
    sample_zone,
    mock_demand_predictor,
    mock_rules_engine,
):
    """Test that pricing factors calls all dependencies correctly."""
    current_datetime = datetime.now()
    occupancy_percent = 40.0

    pricing_engine._calculate_pricing_factors(
        sample_match, sample_zone, current_datetime, occupancy_percent
    )

    # Verify all dependencies were called
    mock_demand_predictor.predict_demand.assert_called_once()
    mock_rules_engine.get_time_decay_factor.assert_called_once()
    mock_rules_engine.get_inventory_pressure_factor.assert_called_once_with(occupancy_percent)
    mock_rules_engine.get_competition_multiplier.assert_called_once_with(sample_match.competition)
    mock_rules_engine.get_rival_multiplier.assert_called_once_with(sample_match.away_team)
    mock_rules_engine.get_special_multipliers.assert_called_once_with(sample_match)


def test_calculate_pricing_factors_includes_special_conditions(
    pricing_engine, sample_match, sample_zone, mock_rules_engine
):
    """Test that special conditions are included in factors."""
    mock_rules_engine.get_special_multipliers.return_value = {
        "derby": 1.3,
        "holiday": 1.1,
    }

    result = pricing_engine._calculate_pricing_factors(
        sample_match, sample_zone, datetime.now(), 50.0
    )

    assert "derby" in result.special_conditions
    assert "holiday" in result.special_conditions
    assert result.special_conditions["derby"] == 1.3
    assert result.special_conditions["holiday"] == 1.1


# ============================================================================
# TESTS: should_update_price
# ============================================================================


def test_should_update_price_allowed(pricing_engine, mock_rules_engine):
    """Test price update is allowed when constraints are met."""
    mock_rules_engine.is_price_change_allowed.return_value = (True, "Allowed")

    should_update, reason = pricing_engine.should_update_price(
        "match_1", "zone_1", 30.0, 35.0, changes_today=0
    )

    assert should_update is True
    assert "approved" in reason.lower()


def test_should_update_price_too_small_change(pricing_engine):
    """Test price update is rejected for trivial changes."""
    should_update, reason = pricing_engine.should_update_price(
        "match_1", "zone_1", 30.0, 30.10, changes_today=0
    )

    assert should_update is False
    assert "too small" in reason.lower()


def test_should_update_price_below_threshold_percentage(pricing_engine):
    """Test price update is rejected when below percentage threshold."""
    # 0.20€ change on 30€ = 0.67%, below 1% threshold
    should_update, reason = pricing_engine.should_update_price(
        "match_1", "zone_1", 30.0, 30.20, changes_today=0
    )

    assert should_update is False
    assert "too small" in reason.lower()


def test_should_update_price_rules_engine_rejects(pricing_engine, mock_rules_engine):
    """Test price update is rejected when rules engine says no."""
    mock_rules_engine.is_price_change_allowed.return_value = (False, "Max changes reached")

    should_update, reason = pricing_engine.should_update_price(
        "match_1", "zone_1", 30.0, 40.0, changes_today=5
    )

    assert should_update is False
    assert "not allowed" in reason.lower()


def test_should_update_price_increase_vs_decrease(pricing_engine, mock_rules_engine):
    """Test price update correctly identifies increase vs decrease."""
    mock_rules_engine.is_price_change_allowed.return_value = (True, "Allowed")

    # Test increase
    should_update, reason = pricing_engine.should_update_price(
        "match_1", "zone_1", 30.0, 35.0
    )
    assert "increase" in reason.lower()

    # Test decrease
    should_update, reason = pricing_engine.should_update_price(
        "match_1", "zone_1", 30.0, 25.0
    )
    assert "decrease" in reason.lower()


# ============================================================================
# TESTS: calculate_all_upcoming_matches
# ============================================================================


def test_calculate_all_upcoming_matches_success(
    pricing_engine,
    sample_match,
    sample_zones,
    mock_match_repository,
    mock_zone_repository,
):
    """Test batch calculation for upcoming matches."""
    mock_match_repository.get_upcoming.return_value = [sample_match]
    mock_zone_repository.get_active_zones.return_value = sample_zones

    results = pricing_engine.calculate_all_upcoming_matches(days=30)

    assert len(results) == 1
    assert results[0].match_id == sample_match.id
    mock_match_repository.get_upcoming.assert_called_once_with(days=30)


def test_calculate_all_upcoming_matches_no_matches(
    pricing_engine, mock_match_repository, mock_zone_repository, sample_zones
):
    """Test batch calculation when no matches found."""
    mock_match_repository.get_upcoming.return_value = []
    mock_zone_repository.get_active_zones.return_value = sample_zones

    results = pricing_engine.calculate_all_upcoming_matches(days=30)

    assert len(results) == 0


def test_calculate_all_upcoming_matches_no_zones(
    pricing_engine, sample_match, mock_match_repository, mock_zone_repository
):
    """Test batch calculation when no zones found."""
    mock_match_repository.get_upcoming.return_value = [sample_match]
    mock_zone_repository.get_active_zones.return_value = []

    results = pricing_engine.calculate_all_upcoming_matches(days=30)

    assert len(results) == 0


def test_calculate_all_upcoming_matches_handles_errors(
    pricing_engine,
    sample_match,
    sample_zones,
    mock_match_repository,
    mock_zone_repository,
    caplog,
):
    """Test batch calculation continues on individual match errors."""
    match2 = Match(
        id="match_002",
        home_team="RCD Mallorca",
        away_team="Real Madrid",
        competition="la_liga",
        match_date=datetime.now() + timedelta(days=14),
        status=MatchStatus.SCHEDULED,
    )

    mock_match_repository.get_upcoming.return_value = [sample_match, match2]
    mock_zone_repository.get_active_zones.return_value = sample_zones

    # Make second match fail
    with patch.object(
        pricing_engine,
        "calculate_match_pricing",
        side_effect=[
            MatchPricing(
                match_id=sample_match.id,
                zones=[],
                total_capacity=8000,
                last_calculation=datetime.now(),
            ),
            Exception("Calculation failed"),
        ],
    ):
        results = pricing_engine.calculate_all_upcoming_matches(days=30)

    # Should have result for first match only
    assert len(results) == 1
    assert "Error calculating pricing" in caplog.text


# ============================================================================
# TESTS: save_pricing_to_history
# ============================================================================


def test_save_pricing_to_history_success(pricing_engine, mock_db_session):
    """Test successful save of pricing to history."""
    zone_pricing = ZonePricing(
        zone_id="zone_1",
        zone_name="North Stand",
        current_price=35.0,
        base_price=30.0,
        factors=PricingFactors(
            demand_score=0.75,
            time_factor=1.2,
            inventory_factor=1.1,
            competition_factor=1.5,
        ),
        last_updated=datetime.now(),
        sold_tickets=1000,
        available_tickets=4000,
        capacity=5000,
        occupancy_percent=20.0,
    )

    match_pricing = MatchPricing(
        match_id="match_001",
        zones=[zone_pricing],
        total_capacity=5000,
        last_calculation=datetime.now(),
    )

    pricing_engine.save_pricing_to_history(match_pricing)

    # Verify database session was used
    mock_db_session.add.assert_called()
    mock_db_session.commit.assert_called_once()


def test_save_pricing_to_history_multiple_zones(pricing_engine, mock_db_session):
    """Test save with multiple zones."""
    zone1 = ZonePricing(
        zone_id="zone_1",
        zone_name="North",
        current_price=35.0,
        base_price=30.0,
        factors=PricingFactors(
            demand_score=0.75,
            time_factor=1.2,
            inventory_factor=1.1,
            competition_factor=1.5,
        ),
        last_updated=datetime.now(),
        sold_tickets=1000,
        available_tickets=4000,
        capacity=5000,
        occupancy_percent=20.0,
    )

    zone2 = ZonePricing(
        zone_id="zone_2",
        zone_name="South",
        current_price=30.0,
        base_price=25.0,
        factors=PricingFactors(
            demand_score=0.65,
            time_factor=1.2,
            inventory_factor=1.0,
            competition_factor=1.5,
        ),
        last_updated=datetime.now(),
        sold_tickets=500,
        available_tickets=2500,
        capacity=3000,
        occupancy_percent=16.67,
    )

    match_pricing = MatchPricing(
        match_id="match_001",
        zones=[zone1, zone2],
        total_capacity=8000,
        last_calculation=datetime.now(),
    )

    pricing_engine.save_pricing_to_history(match_pricing)

    # Should add one entry per zone
    assert mock_db_session.add.call_count == 2
    mock_db_session.commit.assert_called_once()


def test_save_pricing_to_history_rollback_on_error(pricing_engine, mock_db_session):
    """Test that database rolls back on error."""
    mock_db_session.commit.side_effect = Exception("Database error")

    zone_pricing = ZonePricing(
        zone_id="zone_1",
        zone_name="North Stand",
        current_price=35.0,
        base_price=30.0,
        factors=PricingFactors(
            demand_score=0.75,
            time_factor=1.2,
            inventory_factor=1.1,
            competition_factor=1.5,
        ),
        last_updated=datetime.now(),
        sold_tickets=1000,
        available_tickets=4000,
        capacity=5000,
        occupancy_percent=20.0,
    )

    match_pricing = MatchPricing(
        match_id="match_001",
        zones=[zone_pricing],
        total_capacity=5000,
        last_calculation=datetime.now(),
    )

    with pytest.raises(Exception, match="Database error"):
        pricing_engine.save_pricing_to_history(match_pricing)

    mock_db_session.rollback.assert_called_once()


# ============================================================================
# TESTS: Edge Cases
# ============================================================================


def test_pricing_engine_with_high_demand_match(
    pricing_engine, sample_zone, mock_demand_predictor
):
    """Test pricing for high-demand match (e.g., Barcelona)."""
    high_demand_match = Match(
        id="match_high",
        home_team="RCD Mallorca",
        away_team="FC Barcelona",
        competition="la_liga",
        match_date=datetime.now() + timedelta(days=3),
        is_derby=True,
        away_position=1,
        status=MatchStatus.SCHEDULED,
    )

    mock_demand_predictor.predict_demand.return_value = 0.95

    result = pricing_engine._calculate_zone_price(
        high_demand_match, sample_zone, datetime.now()
    )

    # Should have high demand score
    assert result.factors.demand_score >= 0.9


def test_pricing_engine_with_low_demand_match(
    pricing_engine, sample_zone, mock_demand_predictor
):
    """Test pricing for low-demand match (e.g., bottom team)."""
    low_demand_match = Match(
        id="match_low",
        home_team="RCD Mallorca",
        away_team="Bottom Team",
        competition="friendly",
        match_date=datetime.now() + timedelta(days=60),
        is_derby=False,
        away_position=20,
        status=MatchStatus.SCHEDULED,
    )

    mock_demand_predictor.predict_demand.return_value = 0.25

    result = pricing_engine._calculate_zone_price(
        low_demand_match, sample_zone, datetime.now()
    )

    # Should have low demand score
    assert result.factors.demand_score <= 0.3


def test_pricing_engine_handles_zero_capacity_zone_gracefully(
    pricing_engine, sample_match, mock_inventory_manager
):
    """Test that engine handles edge case of zero capacity."""
    # Create zone with minimal capacity to test division by zero protection
    zone = Zone(
        id="zone_edge",
        name="Edge Case",
        category="standard",
        capacity=1,
        base_price=30.0,
        min_price=20.0,
        max_price=50.0,
        price_multiplier=1.0,
    )

    mock_inventory_manager.get_zone_inventory.return_value = (0, 1)

    result = pricing_engine._calculate_zone_price(sample_match, zone, datetime.now())

    assert result.occupancy_percent == 0.0
