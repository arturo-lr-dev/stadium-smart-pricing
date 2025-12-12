"""
Tests for Rules Engine.

Comprehensive unit tests for the RulesEngine class and all its methods.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, mock_open

from src.domain.services.rules_engine import RulesEngine
from src.domain.models.match import Match, MatchStatus


@pytest.fixture
def rules_engine():
    """Fixture to create a RulesEngine instance."""
    return RulesEngine(config_path="config/pricing_rules.yaml")


@pytest.fixture
def sample_match():
    """Fixture to create a sample match."""
    match_date = datetime.now() + timedelta(days=14)
    return Match(
        id="match_001",
        home_team="RCD Mallorca",
        away_team="FC Barcelona",
        competition="LaLiga",
        match_date=match_date,
        venue="Son Moix",
        capacity=23142,
        is_derby=False,
        is_holiday=False,
        home_position=12,
        away_position=2,
        status=MatchStatus.SCHEDULED,
    )


@pytest.fixture
def derby_match():
    """Fixture to create a derby match."""
    match_date = datetime.now() + timedelta(days=7)
    return Match(
        id="match_002",
        home_team="RCD Mallorca",
        away_team="Real Madrid",
        competition="LaLiga",
        match_date=match_date,
        venue="Son Moix",
        capacity=23142,
        is_derby=True,
        is_holiday=True,
        home_position=12,
        away_position=1,
        status=MatchStatus.ON_SALE,
    )


class TestRulesEngineInitialization:
    """Tests for RulesEngine initialization."""

    def test_initialization_success(self, rules_engine):
        """Test successful initialization of RulesEngine."""
        assert rules_engine is not None
        assert isinstance(rules_engine.rules, dict)
        assert len(rules_engine.rules) > 0

    def test_initialization_with_missing_file(self):
        """Test initialization with non-existent config file."""
        with pytest.raises(FileNotFoundError):
            RulesEngine(config_path="nonexistent_file.yaml")

    def test_initialization_validates_required_sections(self, rules_engine):
        """Test that required sections are present after initialization."""
        required_sections = [
            "competition_multipliers",
            "rival_multipliers",
            "time_decay_factors",
            "inventory_pressure_factors",
            "special_conditions",
            "constraints",
        ]

        for section in required_sections:
            assert section in rules_engine.rules

    def test_reload_rules(self, rules_engine):
        """Test reloading rules from config file."""
        initial_rules = rules_engine.rules.copy()
        rules_engine.reload_rules()
        assert rules_engine.rules == initial_rules


class TestCompetitionMultipliers:
    """Tests for competition multiplier methods."""

    def test_get_competition_multiplier_laliga(self, rules_engine):
        """Test LaLiga base multiplier."""
        multiplier = rules_engine.get_competition_multiplier("LaLiga")
        assert multiplier == 1.0

    def test_get_competition_multiplier_laliga_vs_top3(self, rules_engine):
        """Test LaLiga multiplier against top 3 teams."""
        context = {"away_position": 2}
        multiplier = rules_engine.get_competition_multiplier("LaLiga", context)
        assert multiplier == 2.5

    def test_get_competition_multiplier_laliga_vs_top10(self, rules_engine):
        """Test LaLiga multiplier against top 10 teams."""
        context = {"away_position": 7}
        multiplier = rules_engine.get_competition_multiplier("LaLiga", context)
        assert multiplier == 1.5

    def test_get_competition_multiplier_laliga_vs_bottom3(self, rules_engine):
        """Test LaLiga multiplier against bottom 3 teams."""
        context = {"away_position": 19}
        multiplier = rules_engine.get_competition_multiplier("LaLiga", context)
        assert multiplier == 0.8

    def test_get_competition_multiplier_champions_league(self, rules_engine):
        """Test Champions League multiplier."""
        multiplier = rules_engine.get_competition_multiplier("UEFA_Champions_League")
        assert multiplier == 3.0

    def test_get_competition_multiplier_copa_rey_semifinal(self, rules_engine):
        """Test Copa del Rey with stage context."""
        context = {"stage": "semifinal"}
        multiplier = rules_engine.get_competition_multiplier("Copa_del_Rey", context)
        assert multiplier == 2.0

    def test_get_competition_multiplier_copa_rey_final(self, rules_engine):
        """Test Copa del Rey final stage."""
        context = {"stage": "final"}
        multiplier = rules_engine.get_competition_multiplier("Copa_del_Rey", context)
        assert multiplier == 3.0

    def test_get_competition_multiplier_friendly(self, rules_engine):
        """Test friendly match multiplier."""
        multiplier = rules_engine.get_competition_multiplier("Amistoso")
        assert multiplier == 0.6

    def test_get_competition_multiplier_unknown(self, rules_engine):
        """Test unknown competition defaults to 1.0."""
        multiplier = rules_engine.get_competition_multiplier("Unknown_Competition")
        assert multiplier == 1.0


class TestRivalMultipliers:
    """Tests for rival multiplier methods."""

    def test_get_rival_multiplier_real_madrid(self, rules_engine):
        """Test Real Madrid rival multiplier."""
        multiplier = rules_engine.get_rival_multiplier("Real Madrid")
        assert multiplier == 3.0

    def test_get_rival_multiplier_barcelona(self, rules_engine):
        """Test FC Barcelona rival multiplier."""
        multiplier = rules_engine.get_rival_multiplier("FC Barcelona")
        assert multiplier == 3.0

    def test_get_rival_multiplier_atletico(self, rules_engine):
        """Test Atlético Madrid rival multiplier."""
        multiplier = rules_engine.get_rival_multiplier("Atlético Madrid")
        assert multiplier == 2.5

    def test_get_rival_multiplier_mid_table_team(self, rules_engine):
        """Test multiplier for mid-table team."""
        multiplier = rules_engine.get_rival_multiplier("Celta de Vigo")
        assert multiplier == 1.2

    def test_get_rival_multiplier_unknown_team(self, rules_engine):
        """Test multiplier for unknown team defaults to 1.0."""
        multiplier = rules_engine.get_rival_multiplier("Unknown Team")
        assert multiplier == 1.0

    def test_get_rival_multiplier_relegation_zone(self, rules_engine):
        """Test relegation zone penalty."""
        multiplier = rules_engine.get_rival_multiplier(
            "Unknown Team", is_relegation_zone=True
        )
        assert multiplier == 0.85


class TestTimeDecayFactors:
    """Tests for time decay factor methods."""

    def test_get_time_decay_factor_60_days(self, rules_engine):
        """Test early bird pricing (>60 days)."""
        factor = rules_engine.get_time_decay_factor(65)
        assert factor == 0.75

    def test_get_time_decay_factor_45_days(self, rules_engine):
        """Test advance sale (30-59 days)."""
        factor = rules_engine.get_time_decay_factor(45)
        assert factor == 0.85

    def test_get_time_decay_factor_25_days(self, rules_engine):
        """Test late advance sale (21-29 days)."""
        factor = rules_engine.get_time_decay_factor(25)
        assert factor == 0.95

    def test_get_time_decay_factor_14_days(self, rules_engine):
        """Test base pricing (14-20 days)."""
        factor = rules_engine.get_time_decay_factor(14)
        assert factor == 1.0

    def test_get_time_decay_factor_7_days(self, rules_engine):
        """Test last week pricing (7-13 days)."""
        factor = rules_engine.get_time_decay_factor(10)
        assert factor == 1.1

    def test_get_time_decay_factor_3_days(self, rules_engine):
        """Test last days pricing (3-6 days)."""
        factor = rules_engine.get_time_decay_factor(4)
        assert factor == 1.25

    def test_get_time_decay_factor_1_day(self, rules_engine):
        """Test 48h before match (1-2 days)."""
        factor = rules_engine.get_time_decay_factor(1)
        assert factor == 1.4

    def test_get_time_decay_factor_match_day(self, rules_engine):
        """Test match day pricing (0 days)."""
        factor = rules_engine.get_time_decay_factor(0)
        assert factor == 1.5

    def test_get_time_decay_factor_negative(self, rules_engine):
        """Test negative days (past match) defaults to 1.0."""
        factor = rules_engine.get_time_decay_factor(-5)
        assert factor == 1.0


class TestInventoryPressureFactors:
    """Tests for inventory pressure factor methods."""

    def test_get_inventory_pressure_factor_critical_low(self, rules_engine):
        """Test critical low occupancy (0-20%)."""
        factor = rules_engine.get_inventory_pressure_factor(0.15)
        assert factor == 0.80

    def test_get_inventory_pressure_factor_low(self, rules_engine):
        """Test low occupancy (20-40%)."""
        factor = rules_engine.get_inventory_pressure_factor(0.30)
        assert factor == 0.90

    def test_get_inventory_pressure_factor_medium(self, rules_engine):
        """Test medium occupancy (40-60%)."""
        factor = rules_engine.get_inventory_pressure_factor(0.50)
        assert factor == 1.0

    def test_get_inventory_pressure_factor_good(self, rules_engine):
        """Test good occupancy (60-75%)."""
        factor = rules_engine.get_inventory_pressure_factor(0.70)
        assert factor == 1.05

    def test_get_inventory_pressure_factor_high(self, rules_engine):
        """Test high occupancy (75-85%)."""
        factor = rules_engine.get_inventory_pressure_factor(0.80)
        assert factor == 1.15

    def test_get_inventory_pressure_factor_very_high(self, rules_engine):
        """Test very high occupancy (85-92%)."""
        factor = rules_engine.get_inventory_pressure_factor(0.90)
        assert factor == 1.30

    def test_get_inventory_pressure_factor_almost_sold_out(self, rules_engine):
        """Test almost sold out (92-97%)."""
        factor = rules_engine.get_inventory_pressure_factor(0.95)
        assert factor == 1.50

    def test_get_inventory_pressure_factor_last_tickets(self, rules_engine):
        """Test last tickets (97-100%)."""
        factor = rules_engine.get_inventory_pressure_factor(0.98)
        assert factor == 1.75

    def test_get_inventory_pressure_factor_bounds(self, rules_engine):
        """Test occupancy bounds are respected."""
        # Test below 0
        factor = rules_engine.get_inventory_pressure_factor(-0.1)
        assert factor == 0.80  # Should use 0.0

        # Test above 1.0
        factor = rules_engine.get_inventory_pressure_factor(1.5)
        assert factor == 1.75  # Should use 1.0


class TestSpecialConditionsMultipliers:
    """Tests for special conditions multiplier methods."""

    def test_get_special_multipliers_holiday(self, rules_engine, derby_match):
        """Test holiday multiplier."""
        multipliers = rules_engine.get_special_multipliers(derby_match)
        assert "holiday" in multipliers
        assert multipliers["holiday"] == 1.20

    def test_get_special_multipliers_weekday(self, rules_engine, sample_match):
        """Test weekday multiplier."""
        multipliers = rules_engine.get_special_multipliers(sample_match)
        assert "weekday" in multipliers

    def test_get_special_multipliers_derby(self, rules_engine, derby_match):
        """Test derby multiplier."""
        multipliers = rules_engine.get_special_multipliers(derby_match)
        assert "derby" in multipliers
        assert multipliers["derby"] == 2.0

    def test_get_special_multipliers_match_time(self, rules_engine, sample_match):
        """Test match time multiplier."""
        multipliers = rules_engine.get_special_multipliers(sample_match)
        assert "match_time" in multipliers
        # Value depends on match time

    def test_get_special_multipliers_no_special_conditions(self, rules_engine, sample_match):
        """Test match with minimal special conditions."""
        multipliers = rules_engine.get_special_multipliers(sample_match)
        # Should have at least weekday and match_time
        assert len(multipliers) >= 2

    def test_get_weather_factor_excellent(self, rules_engine):
        """Test excellent weather factor."""
        factor = rules_engine.get_weather_factor("excellent")
        assert factor == 1.05

    def test_get_weather_factor_good(self, rules_engine):
        """Test good weather factor."""
        factor = rules_engine.get_weather_factor("good")
        assert factor == 1.0

    def test_get_weather_factor_fair(self, rules_engine):
        """Test fair weather factor."""
        factor = rules_engine.get_weather_factor("fair")
        assert factor == 0.95

    def test_get_weather_factor_poor(self, rules_engine):
        """Test poor weather factor."""
        factor = rules_engine.get_weather_factor("poor")
        assert factor == 0.85


class TestPriceChangeValidation:
    """Tests for price change validation methods."""

    def test_is_price_change_allowed_valid_increase(self, rules_engine):
        """Test valid price increase."""
        allowed, reason = rules_engine.is_price_change_allowed(
            current_price=50.0,
            new_price=55.0,
            changes_today=2,
            hours_since_last_change=3.0,
            hours_to_match=48.0,
        )
        assert allowed is True

    def test_is_price_change_allowed_valid_decrease(self, rules_engine):
        """Test valid price decrease."""
        allowed, reason = rules_engine.is_price_change_allowed(
            current_price=50.0,
            new_price=45.0,
            changes_today=2,
            hours_since_last_change=3.0,
            hours_to_match=48.0,
        )
        assert allowed is True

    def test_is_price_change_not_allowed_daily_limit(self, rules_engine):
        """Test rejection due to daily change limit."""
        allowed, reason = rules_engine.is_price_change_allowed(
            current_price=50.0,
            new_price=55.0,
            changes_today=5,  # Reached limit
            hours_since_last_change=3.0,
            hours_to_match=48.0,
        )
        assert allowed is False
        assert "Daily change limit" in reason

    def test_is_price_change_not_allowed_min_hours(self, rules_engine):
        """Test rejection due to minimum hours between changes."""
        allowed, reason = rules_engine.is_price_change_allowed(
            current_price=50.0,
            new_price=55.0,
            changes_today=2,
            hours_since_last_change=1.0,  # Too soon
            hours_to_match=48.0,
        )
        assert allowed is False
        assert "Minimum" in reason and "required between changes" in reason

    def test_is_price_change_not_allowed_blackout_period(self, rules_engine):
        """Test rejection due to blackout period."""
        allowed, reason = rules_engine.is_price_change_allowed(
            current_price=50.0,
            new_price=55.0,
            changes_today=2,
            hours_since_last_change=3.0,
            hours_to_match=20.0,  # Within 24h blackout
        )
        assert allowed is False
        assert "blackout period" in reason.lower()

    def test_is_price_change_not_allowed_excessive_increase(self, rules_engine):
        """Test rejection due to excessive price increase."""
        allowed, reason = rules_engine.is_price_change_allowed(
            current_price=50.0,
            new_price=65.0,  # 30% increase
            changes_today=2,
            hours_since_last_change=3.0,
            hours_to_match=48.0,
        )
        assert allowed is False
        assert "Increase exceeds" in reason

    def test_is_price_change_not_allowed_excessive_decrease(self, rules_engine):
        """Test rejection due to excessive price decrease."""
        allowed, reason = rules_engine.is_price_change_allowed(
            current_price=50.0,
            new_price=35.0,  # 30% decrease
            changes_today=2,
            hours_since_last_change=3.0,
            hours_to_match=48.0,
        )
        assert allowed is False
        assert "Decrease exceeds" in reason

    def test_is_price_change_not_allowed_trivial_change(self, rules_engine):
        """Test rejection due to trivial change amount."""
        allowed, reason = rules_engine.is_price_change_allowed(
            current_price=50.0,
            new_price=50.25,  # Only 0.25 change
            changes_today=2,
            hours_since_last_change=3.0,
            hours_to_match=48.0,
        )
        assert allowed is False
        assert "less than minimum" in reason.lower()


class TestDynamicStrategies:
    """Tests for dynamic strategy methods."""

    def test_get_dynamic_strategy_velocity_based(self, rules_engine):
        """Test retrieving velocity-based strategy."""
        strategy = rules_engine.get_dynamic_strategy("velocity_based")
        assert strategy is not None
        assert "enabled" in strategy
        assert "thresholds" in strategy

    def test_get_dynamic_strategy_last_minute(self, rules_engine):
        """Test retrieving last-minute strategy."""
        strategy = rules_engine.get_dynamic_strategy("last_minute")
        assert strategy is not None
        assert "enabled" in strategy

    def test_get_dynamic_strategy_unknown(self, rules_engine):
        """Test retrieving unknown strategy returns None."""
        strategy = rules_engine.get_dynamic_strategy("unknown_strategy")
        assert strategy is None

    def test_get_velocity_multiplier_very_high(self, rules_engine):
        """Test velocity multiplier for very high sales."""
        multiplier = rules_engine.get_velocity_multiplier(60.0)
        assert multiplier == 1.20

    def test_get_velocity_multiplier_high(self, rules_engine):
        """Test velocity multiplier for high sales."""
        multiplier = rules_engine.get_velocity_multiplier(30.0)
        assert multiplier == 1.10

    def test_get_velocity_multiplier_medium(self, rules_engine):
        """Test velocity multiplier for medium sales."""
        multiplier = rules_engine.get_velocity_multiplier(15.0)
        assert multiplier == 1.0

    def test_get_velocity_multiplier_low(self, rules_engine):
        """Test velocity multiplier for low sales."""
        multiplier = rules_engine.get_velocity_multiplier(7.0)
        assert multiplier == 0.95

    def test_get_velocity_multiplier_very_low(self, rules_engine):
        """Test velocity multiplier for very low sales."""
        multiplier = rules_engine.get_velocity_multiplier(2.0)
        assert multiplier == 0.85


class TestConstraintsAndLimits:
    """Tests for constraints and limits methods."""

    def test_get_constraints(self, rules_engine):
        """Test retrieving all constraints."""
        constraints = rules_engine.get_constraints()
        assert constraints is not None
        assert "max_price_increase_percent" in constraints
        assert "max_price_decrease_percent" in constraints
        assert "max_changes_per_day" in constraints
        assert "min_hours_between_changes" in constraints

    def test_constraints_values(self, rules_engine):
        """Test constraint values are as expected."""
        constraints = rules_engine.get_constraints()
        assert constraints["max_price_increase_percent"] == 20
        assert constraints["max_price_decrease_percent"] == 25
        assert constraints["max_changes_per_day"] == 5
        assert constraints["min_hours_between_changes"] == 2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_get_competition_multiplier_with_none(self, rules_engine):
        """Test competition multiplier with None competition."""
        # Should not crash, return default
        multiplier = rules_engine.get_competition_multiplier("")
        assert multiplier == 1.0

    def test_get_rival_multiplier_with_empty_string(self, rules_engine):
        """Test rival multiplier with empty string."""
        multiplier = rules_engine.get_rival_multiplier("")
        assert multiplier == 1.0

    def test_get_time_decay_factor_extreme_values(self, rules_engine):
        """Test time decay with extreme values."""
        # Very large positive value
        factor = rules_engine.get_time_decay_factor(1000)
        assert isinstance(factor, float)

        # Negative value
        factor = rules_engine.get_time_decay_factor(-100)
        assert isinstance(factor, float)

    def test_get_inventory_pressure_factor_negative(self, rules_engine):
        """Test inventory pressure with negative occupancy."""
        factor = rules_engine.get_inventory_pressure_factor(-0.5)
        assert isinstance(factor, float)
        assert factor > 0

    def test_get_special_multipliers_with_past_match(self, rules_engine):
        """Test special multipliers with past match date."""
        past_match = Match(
            id="match_past",
            home_team="RCD Mallorca",
            away_team="FC Barcelona",
            competition="LaLiga",
            match_date=datetime.now() - timedelta(days=7),
            venue="Son Moix",
            capacity=23142,
            status=MatchStatus.COMPLETED,
        )
        multipliers = rules_engine.get_special_multipliers(past_match)
        assert isinstance(multipliers, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
