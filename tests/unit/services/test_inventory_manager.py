"""
Tests for Inventory Manager.

Comprehensive unit tests for the InventoryManager class and all its methods.
Updated to use InventoryCacheStrategy.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from src.domain.services.inventory_manager import InventoryManager
from src.domain.models.zone import Zone, ZoneCategory
from src.core.cache_strategies import InventoryCacheStrategy


@pytest.fixture
def mock_sale_repo():
    """Fixture to create a mock SaleRepository."""
    repo = Mock()
    repo.get_total_sold = Mock(return_value=100)
    repo.get_sales_velocity = Mock(return_value=(50, 2.0))
    return repo


@pytest.fixture
def mock_zone_repo():
    """Fixture to create a mock ZoneRepository."""
    repo = Mock()

    # Create sample zones
    zone1 = Zone(
        id="zone_001",
        name="Tribune Nord",
        category=ZoneCategory.STANDARD,
        capacity=5000,
        base_price=50.0,
        min_price=30.0,
        max_price=100.0,
        price_multiplier=1.0,
    )

    zone2 = Zone(
        id="zone_002",
        name="VIP Box",
        category=ZoneCategory.VIP,
        capacity=500,
        base_price=200.0,
        min_price=150.0,
        max_price=400.0,
        price_multiplier=2.0,
    )

    zone3 = Zone(
        id="zone_003",
        name="Tribune Sud",
        category=ZoneCategory.STANDARD,
        capacity=5000,
        base_price=45.0,
        min_price=25.0,
        max_price=90.0,
        price_multiplier=0.9,
    )

    repo.get_by_id = Mock(side_effect=lambda zone_id: {
        "zone_001": zone1,
        "zone_002": zone2,
        "zone_003": zone3,
    }.get(zone_id))

    repo.get_active_zones = Mock(return_value=[zone1, zone2, zone3])

    return repo


@pytest.fixture
def mock_cache_strategy():
    """Fixture to create a mock InventoryCacheStrategy."""
    cache = Mock(spec=InventoryCacheStrategy)
    cache.get = Mock(return_value=None)
    cache.set = Mock(return_value=True)
    cache.invalidate = Mock(return_value=True)
    cache.invalidate_match = Mock(return_value=3)
    cache.get_match_inventory = Mock(return_value={})
    return cache


@pytest.fixture
def inventory_manager(mock_sale_repo, mock_zone_repo, mock_cache_strategy):
    """Fixture to create an InventoryManager instance with cache strategy."""
    return InventoryManager(
        sale_repository=mock_sale_repo,
        zone_repository=mock_zone_repo,
        cache_strategy=mock_cache_strategy,
    )


class TestInventoryManagerInitialization:
    """Tests for InventoryManager initialization."""

    def test_initialization_success(self, inventory_manager):
        """Test successful initialization of InventoryManager with cache strategy."""
        assert inventory_manager is not None
        assert inventory_manager.cache is not None
        assert isinstance(inventory_manager.cache, (InventoryCacheStrategy, Mock))

    def test_initialization_with_custom_cache_strategy(self, mock_sale_repo, mock_zone_repo):
        """Test initialization with custom cache strategy."""
        custom_cache = Mock(spec=InventoryCacheStrategy)
        manager = InventoryManager(
            sale_repository=mock_sale_repo,
            zone_repository=mock_zone_repo,
            cache_strategy=custom_cache,
        )
        assert manager.cache is custom_cache


# TestCacheHelpers class removed - methods _get_cache_key, _get_from_cache,
# _set_in_cache no longer exist, replaced by InventoryCacheStrategy


class TestGetZoneInventory:
    """Tests for get_zone_inventory method."""

    def test_get_zone_inventory_without_cache(self, inventory_manager, mock_sale_repo, mock_zone_repo):
        """Test getting zone inventory without cache."""
        mock_sale_repo.get_total_sold.return_value = 3000

        sold, available = inventory_manager.get_zone_inventory(
            "match_001", "zone_001", use_cache=False
        )

        assert sold == 3000
        assert available == 2000  # 5000 capacity - 3000 sold
        mock_sale_repo.get_total_sold.assert_called_once_with("match_001", "zone_001")
        mock_zone_repo.get_by_id.assert_called_once_with("zone_001")

    def test_get_zone_inventory_with_cache_miss(self, inventory_manager, mock_sale_repo, mock_cache_strategy):
        """Test getting zone inventory with cache miss."""
        mock_cache_strategy.get.return_value = None
        mock_sale_repo.get_total_sold.return_value = 3000

        sold, available = inventory_manager.get_zone_inventory("match_001", "zone_001")

        assert sold == 3000
        assert available == 2000

        # Should have tried to get from cache and then set cache
        mock_cache_strategy.get.assert_called_once_with("match_001", "zone_001")
        mock_cache_strategy.set.assert_called_once_with("match_001", "zone_001", (3000, 2000))

    def test_get_zone_inventory_with_cache_hit(self, inventory_manager, mock_cache_strategy, mock_sale_repo):
        """Test getting zone inventory with cache hit."""
        # Cache returns list (JSON serialization converts tuples to lists)
        mock_cache_strategy.get.return_value = [3000, 2000]

        sold, available = inventory_manager.get_zone_inventory("match_001", "zone_001")

        assert sold == 3000
        assert available == 2000

        # Should NOT call sale repository when cache hits
        mock_sale_repo.get_total_sold.assert_not_called()
        mock_cache_strategy.get.assert_called_once_with("match_001", "zone_001")

    def test_get_zone_inventory_zero_available(self, inventory_manager, mock_sale_repo):
        """Test getting zone inventory when sold out."""
        mock_sale_repo.get_total_sold.return_value = 5000

        sold, available = inventory_manager.get_zone_inventory(
            "match_001", "zone_001", use_cache=False
        )

        assert sold == 5000
        assert available == 0

    def test_get_zone_inventory_oversold(self, inventory_manager, mock_sale_repo):
        """Test getting zone inventory when oversold (shouldn't happen but handle gracefully)."""
        mock_sale_repo.get_total_sold.return_value = 5500

        sold, available = inventory_manager.get_zone_inventory(
            "match_001", "zone_001", use_cache=False
        )

        assert sold == 5500
        assert available == 0  # Should clamp to 0, not negative

    def test_get_zone_inventory_invalid_zone(self, inventory_manager, mock_zone_repo):
        """Test getting inventory for non-existent zone."""
        mock_zone_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Zone .* not found"):
            inventory_manager.get_zone_inventory("match_001", "invalid_zone", use_cache=False)


class TestGetMatchInventory:
    """Tests for get_match_inventory method."""

    def test_get_match_inventory_without_cache(self, inventory_manager, mock_sale_repo):
        """Test getting match inventory without cache."""
        # Configure mock to return different values for different zones
        def get_total_sold_side_effect(match_id, zone_id):
            return {
                "zone_001": 3000,
                "zone_002": 400,
                "zone_003": 2500,
            }.get(zone_id, 0)

        mock_sale_repo.get_total_sold.side_effect = get_total_sold_side_effect

        inventory = inventory_manager.get_match_inventory("match_001", use_cache=False)

        assert len(inventory) == 3
        assert inventory["zone_001"] == (3000, 2000)
        assert inventory["zone_002"] == (400, 100)
        assert inventory["zone_003"] == (2500, 2500)

    def test_get_match_inventory_with_cache_hit(self, inventory_manager, mock_cache_strategy, mock_zone_repo, mock_sale_repo):
        """Test getting match inventory with partial cache hit."""
        # Cache returns lists (JSON serialization converts tuples to lists)
        # Only zone_001 and zone_002 are cached
        cached_data = {
            "zone_001": [3000, 2000],
            "zone_002": [400, 100],
        }
        mock_cache_strategy.get_match_inventory.return_value = cached_data

        # zone_003 is not cached, so it will be fetched from database
        mock_sale_repo.get_total_sold.return_value = 100

        inventory = inventory_manager.get_match_inventory("match_001")

        # Should have all 3 zones (2 from cache, 1 from DB)
        assert len(inventory) == 3
        assert inventory["zone_001"] == (3000, 2000)
        assert inventory["zone_002"] == (400, 100)
        assert inventory["zone_003"] == (100, 4900)  # 100 sold, 4900 available from 5000 capacity

        # Should use cache batch operation
        zone_ids = ["zone_001", "zone_002", "zone_003"]
        mock_cache_strategy.get_match_inventory.assert_called_once_with("match_001", zone_ids)

        # zone_003 is missing from cache, so only 1 call to database
        assert mock_sale_repo.get_total_sold.call_count == 1


class TestGetTotalOccupancy:
    """Tests for get_total_occupancy method."""

    def test_get_total_occupancy(self, inventory_manager, mock_sale_repo):
        """Test calculating total occupancy."""
        def get_total_sold_side_effect(match_id, zone_id):
            return {
                "zone_001": 3000,  # 60% of 5000
                "zone_002": 250,   # 50% of 500
                "zone_003": 2500,  # 50% of 5000
            }.get(zone_id, 0)

        mock_sale_repo.get_total_sold.side_effect = get_total_sold_side_effect

        occupancy = inventory_manager.get_total_occupancy("match_001")

        # Total sold: 3000 + 250 + 2500 = 5750
        # Total capacity: 5000 + 500 + 5000 = 10500
        # Occupancy: 5750 / 10500 = 0.547619...
        assert occupancy == pytest.approx(0.5476, abs=0.01)

    def test_get_total_occupancy_empty_stadium(self, inventory_manager, mock_sale_repo):
        """Test calculating occupancy when no tickets sold."""
        mock_sale_repo.get_total_sold.return_value = 0

        occupancy = inventory_manager.get_total_occupancy("match_001")

        assert occupancy == 0.0


class TestGetZoneOccupancy:
    """Tests for get_zone_occupancy method."""

    def test_get_zone_occupancy(self, inventory_manager, mock_sale_repo):
        """Test calculating zone occupancy."""
        mock_sale_repo.get_total_sold.return_value = 3000

        occupancy = inventory_manager.get_zone_occupancy("match_001", "zone_001")

        # 3000 sold / 5000 capacity = 0.6
        assert occupancy == 0.6

    def test_get_zone_occupancy_sold_out(self, inventory_manager, mock_sale_repo):
        """Test calculating occupancy for sold out zone."""
        mock_sale_repo.get_total_sold.return_value = 5000

        occupancy = inventory_manager.get_zone_occupancy("match_001", "zone_001")

        assert occupancy == 1.0

    def test_get_zone_occupancy_empty(self, inventory_manager, mock_sale_repo):
        """Test calculating occupancy for empty zone."""
        mock_sale_repo.get_total_sold.return_value = 0

        occupancy = inventory_manager.get_zone_occupancy("match_001", "zone_001")

        assert occupancy == 0.0


class TestGetSalesVelocity:
    """Tests for get_sales_velocity method."""

    def test_get_sales_velocity_with_zone(self, inventory_manager, mock_sale_repo):
        """Test calculating sales velocity for a zone."""
        mock_sale_repo.get_sales_velocity.return_value = (48, 2.0)

        velocity = inventory_manager.get_sales_velocity("match_001", "zone_001", hours=24)

        assert velocity == 2.0
        mock_sale_repo.get_sales_velocity.assert_called_once_with("match_001", "zone_001", 24)

    def test_get_sales_velocity_all_zones(self, inventory_manager, mock_sale_repo):
        """Test calculating sales velocity for entire match."""
        mock_sale_repo.get_sales_velocity.return_value = (120, 5.0)

        velocity = inventory_manager.get_sales_velocity("match_001", None, hours=24)

        assert velocity == 5.0
        mock_sale_repo.get_sales_velocity.assert_called_once_with("match_001", None, 24)

    def test_get_sales_velocity_different_time_window(self, inventory_manager, mock_sale_repo):
        """Test calculating sales velocity with different time window."""
        mock_sale_repo.get_sales_velocity.return_value = (60, 10.0)

        velocity = inventory_manager.get_sales_velocity("match_001", "zone_001", hours=6)

        assert velocity == 10.0
        mock_sale_repo.get_sales_velocity.assert_called_once_with("match_001", "zone_001", 6)


class TestPredictSelloutTime:
    """Tests for predict_sellout_time method."""

    def test_predict_sellout_time_normal(self, inventory_manager, mock_sale_repo):
        """Test predicting sellout time with normal velocity."""
        mock_sale_repo.get_total_sold.return_value = 3000
        mock_sale_repo.get_sales_velocity.return_value = (48, 2.0)  # 2 tickets/hour

        sellout_time = inventory_manager.predict_sellout_time("match_001", "zone_001")

        # 2000 tickets remaining / 2 tickets/hour = 1000 hours
        assert sellout_time is not None
        expected_time = datetime.now() + timedelta(hours=1000)

        # Allow some tolerance for test execution time
        assert abs((sellout_time - expected_time).total_seconds()) < 10

    def test_predict_sellout_time_already_sold_out(self, inventory_manager, mock_sale_repo):
        """Test prediction when zone is already sold out."""
        mock_sale_repo.get_total_sold.return_value = 5000

        sellout_time = inventory_manager.predict_sellout_time("match_001", "zone_001")

        # Should return current time
        assert sellout_time is not None
        assert abs((sellout_time - datetime.now()).total_seconds()) < 10

    def test_predict_sellout_time_zero_velocity(self, inventory_manager, mock_sale_repo):
        """Test prediction when velocity is zero."""
        mock_sale_repo.get_total_sold.return_value = 1000
        mock_sale_repo.get_sales_velocity.return_value = (0, 0.0)

        sellout_time = inventory_manager.predict_sellout_time("match_001", "zone_001")

        assert sellout_time is None

    def test_predict_sellout_time_negative_velocity(self, inventory_manager, mock_sale_repo):
        """Test prediction when velocity is negative (shouldn't happen but handle gracefully)."""
        mock_sale_repo.get_total_sold.return_value = 1000
        mock_sale_repo.get_sales_velocity.return_value = (0, -1.0)

        sellout_time = inventory_manager.predict_sellout_time("match_001", "zone_001")

        assert sellout_time is None


class TestCheckInventoryAlerts:
    """Tests for check_inventory_alerts method."""

    def test_check_inventory_alerts_high_occupancy(self, inventory_manager, mock_sale_repo):
        """Test alerts for high occupancy zones."""
        def get_total_sold_side_effect(match_id, zone_id):
            return {
                "zone_001": 4800,  # 96% occupancy
                "zone_002": 250,   # 50% occupancy
                "zone_003": 1000,  # 20% occupancy
            }.get(zone_id, 0)

        mock_sale_repo.get_total_sold.side_effect = get_total_sold_side_effect
        mock_sale_repo.get_sales_velocity.return_value = (10, 1.0)

        alerts = inventory_manager.check_inventory_alerts("match_001")

        # Should have at least one high occupancy alert for zone_001
        high_occupancy_alerts = [a for a in alerts if a["type"] == "high_occupancy"]
        assert len(high_occupancy_alerts) > 0
        assert high_occupancy_alerts[0]["zone_id"] == "zone_001"
        assert high_occupancy_alerts[0]["severity"] == "high"

    def test_check_inventory_alerts_low_occupancy(self, inventory_manager, mock_sale_repo):
        """Test alerts for low occupancy zones."""
        def get_total_sold_side_effect(match_id, zone_id):
            return {
                "zone_001": 500,   # 10% occupancy
                "zone_002": 250,   # 50% occupancy
                "zone_003": 500,   # 10% occupancy
            }.get(zone_id, 0)

        mock_sale_repo.get_total_sold.side_effect = get_total_sold_side_effect
        mock_sale_repo.get_sales_velocity.return_value = (5, 0.5)

        alerts = inventory_manager.check_inventory_alerts("match_001")

        # Should have low occupancy alerts
        low_occupancy_alerts = [a for a in alerts if a["type"] == "low_occupancy"]
        assert len(low_occupancy_alerts) >= 2  # zone_001 and zone_003

    def test_check_inventory_alerts_high_velocity(self, inventory_manager, mock_sale_repo):
        """Test alerts for high sales velocity."""
        def get_total_sold_side_effect(match_id, zone_id):
            return {
                "zone_001": 2500,  # 50% occupancy
                "zone_002": 250,   # 50% occupancy
                "zone_003": 2500,  # 50% occupancy
            }.get(zone_id, 0)

        def get_velocity_side_effect(match_id, zone_id, hours):
            if hours == 6 and zone_id == "zone_001":
                return (75, 12.5)  # High velocity
            return (10, 1.0)

        mock_sale_repo.get_total_sold.side_effect = get_total_sold_side_effect
        mock_sale_repo.get_sales_velocity.side_effect = get_velocity_side_effect

        alerts = inventory_manager.check_inventory_alerts("match_001")

        # Should have high velocity alert for zone_001
        high_velocity_alerts = [a for a in alerts if a["type"] == "high_velocity"]
        assert len(high_velocity_alerts) > 0


class TestCacheManagement:
    """Tests for cache management methods."""

    def test_invalidate_cache_specific_zone(self, inventory_manager, mock_cache_strategy):
        """Test invalidating cache for a specific zone."""
        inventory_manager.invalidate_cache("match_001", "zone_001")

        # Should call cache_strategy.invalidate with match_id and zone_id
        mock_cache_strategy.invalidate.assert_called_once_with("match_001", "zone_001")

    def test_invalidate_cache_entire_match(self, inventory_manager, mock_cache_strategy):
        """Test invalidating cache for entire match."""
        mock_cache_strategy.invalidate_match.return_value = 3

        inventory_manager.invalidate_cache("match_001")

        # Should call cache_strategy.invalidate_match to delete all zones
        mock_cache_strategy.invalidate_match.assert_called_once_with("match_001")

    def test_warm_cache(self, inventory_manager, mock_sale_repo):
        """Test warming cache for multiple matches."""
        def get_total_sold_side_effect(match_id, zone_id):
            return {
                "zone_001": 1000,
                "zone_002": 100,
                "zone_003": 1000,
            }.get(zone_id, 0)

        mock_sale_repo.get_total_sold.side_effect = get_total_sold_side_effect

        match_ids = ["match_001", "match_002", "match_003"]
        inventory_manager.warm_cache(match_ids)

        # Should have called get_match_inventory for each match
        # Each call processes 3 zones, so 3 matches * 3 zones = 9 get_total_sold calls
        assert mock_sale_repo.get_total_sold.call_count == 9


class TestGetInventorySummary:
    """Tests for get_inventory_summary method."""

    def test_get_inventory_summary(self, inventory_manager, mock_sale_repo):
        """Test getting comprehensive inventory summary."""
        def get_total_sold_side_effect(match_id, zone_id):
            return {
                "zone_001": 3000,  # 60% occupancy
                "zone_002": 400,   # 80% occupancy
                "zone_003": 1500,  # 30% occupancy
            }.get(zone_id, 0)

        mock_sale_repo.get_total_sold.side_effect = get_total_sold_side_effect
        mock_sale_repo.get_sales_velocity.return_value = (10, 1.0)

        summary = inventory_manager.get_inventory_summary("match_001")

        assert summary["match_id"] == "match_001"
        assert summary["total_sold"] == 4900
        assert summary["total_available"] == 5600
        assert summary["total_capacity"] == 10500
        assert "overall_occupancy" in summary
        assert "zones" in summary
        assert len(summary["zones"]) == 3
        assert "alerts" in summary
        assert "timestamp" in summary

    def test_get_inventory_summary_zones_sorted(self, inventory_manager, mock_sale_repo):
        """Test that zones in summary are sorted by occupancy."""
        def get_total_sold_side_effect(match_id, zone_id):
            return {
                "zone_001": 3000,  # 60% occupancy
                "zone_002": 450,   # 90% occupancy
                "zone_003": 1000,  # 20% occupancy
            }.get(zone_id, 0)

        mock_sale_repo.get_total_sold.side_effect = get_total_sold_side_effect
        mock_sale_repo.get_sales_velocity.return_value = (10, 1.0)

        summary = inventory_manager.get_inventory_summary("match_001")

        zones = summary["zones"]
        # Should be sorted by occupancy descending
        assert zones[0]["zone_id"] == "zone_002"  # 90%
        assert zones[1]["zone_id"] == "zone_001"  # 60%
        assert zones[2]["zone_id"] == "zone_003"  # 20%


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handle_cache_connection_error(self, inventory_manager, mock_cache_strategy, mock_sale_repo):
        """Test graceful handling of cache connection errors."""
        mock_cache_strategy.get.side_effect = Exception("Cache connection error")
        mock_sale_repo.get_total_sold.return_value = 1000

        # Should fall back to database without crashing
        sold, available = inventory_manager.get_zone_inventory("match_001", "zone_001")

        assert sold == 1000
        assert available == 4000

    def test_handle_repository_error(self, inventory_manager, mock_sale_repo):
        """Test handling of repository errors."""
        mock_sale_repo.get_total_sold.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            inventory_manager.get_zone_inventory("match_001", "zone_001", use_cache=False)
