"""Unit tests for ZoneRepository."""

import pytest

from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.models.zone import Zone


class TestZoneRepository:
    """Test suite for ZoneRepository."""

    def test_create_zone(self, test_db_session, sample_zone_data):
        """Test creating a zone."""
        repo = ZoneRepository(test_db_session)
        zone = Zone(**sample_zone_data)

        created_zone = repo.create(zone)

        assert created_zone.id == sample_zone_data["id"]
        assert created_zone.name == sample_zone_data["name"]
        assert created_zone.category == sample_zone_data["category"]

    def test_get_by_id(self, test_db_session, create_zone):
        """Test getting zone by ID."""
        repo = ZoneRepository(test_db_session)

        zone = repo.get_by_id(create_zone.id)

        assert zone is not None
        assert zone.id == create_zone.id

    def test_get_by_category(self, test_db_session, sample_zone_data):
        """Test getting zones by category."""
        repo = ZoneRepository(test_db_session)

        # Create zones with different categories
        for i, category in enumerate(["standard", "vip", "standard"]):
            data = sample_zone_data.copy()
            data["id"] = f"zone_{i}"
            data["category"] = category
            zone = Zone(**data)
            repo.create(zone)

        zones = repo.get_by_category("standard")

        assert len(zones) == 2

    def test_get_active_zones(self, test_db_session, sample_zone_data):
        """Test getting active zones."""
        repo = ZoneRepository(test_db_session)

        # Create zones with different active status
        for i in range(3):
            data = sample_zone_data.copy()
            data["id"] = f"zone_{i}"
            data["is_active"] = i != 1  # False for zone_1
            zone = Zone(**data)
            repo.create(zone)

        active_zones = repo.get_active_zones()

        assert len(active_zones) == 2

    def test_get_inactive_zones(self, test_db_session, sample_zone_data):
        """Test getting inactive zones."""
        repo = ZoneRepository(test_db_session)

        # Create zones with different active status
        for i in range(3):
            data = sample_zone_data.copy()
            data["id"] = f"zone_{i}"
            data["is_active"] = i != 1  # False for zone_1
            zone = Zone(**data)
            repo.create(zone)

        inactive_zones = repo.get_inactive_zones()

        assert len(inactive_zones) == 1

    def test_get_by_price_range(self, test_db_session, sample_zone_data):
        """Test getting zones by price range."""
        repo = ZoneRepository(test_db_session)

        # Create zones with different base prices
        for i, price in enumerate([25.0, 35.0, 45.0]):
            data = sample_zone_data.copy()
            data["id"] = f"zone_{i}"
            data["base_price"] = price
            data["min_price"] = price - 10
            data["max_price"] = price + 10
            zone = Zone(**data)
            repo.create(zone)

        zones = repo.get_by_price_range(30.0, 40.0)

        assert len(zones) == 1
        assert zones[0].base_price == 35.0

    def test_get_total_capacity(self, test_db_session, sample_zone_data):
        """Test getting total stadium capacity."""
        repo = ZoneRepository(test_db_session)

        # Create zones with different capacities
        for i in range(3):
            data = sample_zone_data.copy()
            data["id"] = f"zone_{i}"
            data["capacity"] = 1000 * (i + 1)  # 1000, 2000, 3000
            zone = Zone(**data)
            repo.create(zone)

        total = repo.get_total_capacity()

        assert total == 6000

    def test_activate_zone(self, test_db_session, sample_zone_data):
        """Test activating a zone."""
        repo = ZoneRepository(test_db_session)

        # Create inactive zone
        data = sample_zone_data.copy()
        data["is_active"] = False
        zone = Zone(**data)
        created = repo.create(zone)

        activated = repo.activate_zone(created.id)

        assert activated is not None
        assert activated.is_active is True

    def test_deactivate_zone(self, test_db_session, create_zone):
        """Test deactivating a zone."""
        repo = ZoneRepository(test_db_session)

        deactivated = repo.deactivate_zone(create_zone.id)

        assert deactivated is not None
        assert deactivated.is_active is False

    def test_update_prices(self, test_db_session, create_zone):
        """Test updating zone prices."""
        repo = ZoneRepository(test_db_session)

        updated = repo.update_prices(
            create_zone.id, base_price=35.0, min_price=25.0, max_price=55.0
        )

        assert updated is not None
        assert updated.base_price == 35.0
        assert updated.min_price == 25.0
        assert updated.max_price == 55.0

    def test_update_prices_invalid_constraints(self, test_db_session, create_zone):
        """Test updating prices with invalid constraints."""
        repo = ZoneRepository(test_db_session)

        with pytest.raises(ValueError):
            repo.update_prices(
                create_zone.id, base_price=60.0, min_price=25.0, max_price=55.0
            )

    def test_delete_zone(self, test_db_session, create_zone):
        """Test deleting a zone."""
        repo = ZoneRepository(test_db_session)

        result = repo.delete(create_zone.id)

        assert result is True
        assert repo.get_by_id(create_zone.id) is None
