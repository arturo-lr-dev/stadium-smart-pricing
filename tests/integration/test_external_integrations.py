"""
Integration tests for external API integrations.

Tests for Football Data API, Weather API, Google Analytics,
and Ticketing System integrations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.integrations import (
    FootballDataAPI,
    WeatherAPI,
    GoogleAnalyticsIntegration,
    TicketingSystemAPI,
    ReservationStatus,
)
from src.core.exceptions import ExternalAPIError


class TestFootballDataAPI:
    """Tests for Football Data API integration."""

    def test_init(self):
        """Test API client initialization."""
        api = FootballDataAPI(api_key="test_key")
        assert api.api_key == "test_key"
        assert api.base_url == "https://api.football-data.org/v4"
        assert api.cache_ttl == 21600  # 6 hours

    def test_cache_operations(self):
        """Test cache get and set operations."""
        api = FootballDataAPI(api_key="test_key")

        # Set cache
        api._set_cache("test_key", {"data": "value"})

        # Get from cache
        result = api._get_from_cache("test_key")
        assert result == {"data": "value"}

        # Get non-existent key
        result = api._get_from_cache("nonexistent")
        assert result is None

    def test_rate_limiting(self):
        """Test rate limiting logic."""
        api = FootballDataAPI(api_key="test_key")
        api.rate_limit = 5

        # Make requests up to limit
        for _ in range(5):
            api._apply_rate_limit()

        # This should trigger rate limiting (sleep)
        # We can't easily test sleep, but we can verify the logic doesn't crash
        api._apply_rate_limit()

    @patch("src.integrations.football_data.httpx.Client")
    def test_get_team_standings_success(self, mock_client):
        """Test successful team standings retrieval."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "standings": [
                {
                    "position": 1,
                    "team": {"name": "Real Madrid", "id": "123"},
                    "points": 75,
                }
            ]
        }
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        api = FootballDataAPI(api_key="test_key")
        result = api.get_team_standings("PD", "2024")

        assert "standings" in result
        assert len(result["standings"]) == 1
        assert result["standings"][0]["team"]["name"] == "Real Madrid"

    @patch("src.integrations.football_data.httpx.Client")
    def test_get_team_standings_cached(self, mock_client):
        """Test that cached standings are returned without API call."""
        api = FootballDataAPI(api_key="test_key")

        # Set cache
        cached_data = {"standings": [{"position": 1}]}
        api._set_cache("standings:PD:2024", cached_data)

        # Call method
        result = api.get_team_standings("PD", "2024")

        # Should return cached data without making API call
        assert result == cached_data
        mock_client.assert_not_called()

    @patch("src.integrations.football_data.httpx.Client")
    def test_api_error_handling(self, mock_client):
        """Test handling of API errors."""
        # Mock 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        api = FootballDataAPI(api_key="test_key")

        with pytest.raises(ExternalAPIError) as exc_info:
            api.get_team_stats("123")

        assert "authentication failed" in str(exc_info.value).lower()

    def test_clear_cache(self):
        """Test cache clearing."""
        api = FootballDataAPI(api_key="test_key")

        # Add to cache
        api._set_cache("key1", "value1")
        api._set_cache("key2", "value2")

        # Clear cache
        api.clear_cache()

        # Verify cache is empty
        assert api._get_from_cache("key1") is None
        assert api._get_from_cache("key2") is None


class TestWeatherAPI:
    """Tests for Weather API integration."""

    def test_init(self):
        """Test API client initialization."""
        api = WeatherAPI(api_key="test_key")
        assert api.api_key == "test_key"
        assert api.cache_ttl == 3600  # 1 hour

    @patch("src.integrations.weather_api.httpx.Client")
    def test_get_forecast_success(self, mock_client):
        """Test successful weather forecast retrieval."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [
                {
                    "dt": int((datetime.utcnow() + timedelta(days=2)).timestamp()),
                    "main": {"temp": 22.5, "humidity": 65},
                    "weather": [{"main": "Clear", "description": "clear sky"}],
                    "wind": {"speed": 3.5},
                    "pop": 0.1,
                }
            ]
        }
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        api = WeatherAPI(api_key="test_key")
        forecast_date = datetime.utcnow() + timedelta(days=2)
        result = api.get_forecast(39.59, 2.63, forecast_date)

        assert result["temperature"] == 22.5
        assert result["weather_condition"] == "Clear"
        assert result["precipitation_probability"] == 0.1

    def test_get_forecast_beyond_5_days(self):
        """Test forecast request for dates beyond 5 days uses historical average."""
        api = WeatherAPI(api_key="test_key")
        forecast_date = datetime.utcnow() + timedelta(days=10)

        result = api.get_forecast(39.59, 2.63, forecast_date)

        # Should return historical average data
        assert "temperature" in result
        assert "precipitation_probability" in result
        assert "description" in result

    def test_calculate_weather_factor_good_weather(self):
        """Test weather factor calculation for good weather."""
        api = WeatherAPI(api_key="test_key")

        weather_data = {
            "temperature": 22.0,  # Optimal
            "precipitation_probability": 0.1,  # Low rain
            "wind_speed": 3.0,  # Calm
        }

        factor = api.calculate_weather_factor(weather_data)

        # Good weather should be close to 1.0
        assert 0.95 <= factor <= 1.05

    def test_calculate_weather_factor_bad_weather(self):
        """Test weather factor calculation for bad weather."""
        api = WeatherAPI(api_key="test_key")

        weather_data = {
            "temperature": 8.0,  # Cold
            "precipitation_probability": 0.8,  # High rain
            "wind_speed": 18.0,  # Very windy
        }

        factor = api.calculate_weather_factor(weather_data)

        # Bad weather should reduce factor below 1.0
        assert factor < 1.0
        assert factor >= 0.9  # Within bounds

    def test_default_weather(self):
        """Test default weather fallback."""
        api = WeatherAPI(api_key="test_key")

        result = api._get_default_weather()

        assert result["temperature"] == 20.0
        assert result["weather_condition"] == "Clear"
        assert result["precipitation_probability"] == 0.1


class TestGoogleAnalyticsIntegration:
    """Tests for Google Analytics integration."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        api = GoogleAnalyticsIntegration(property_id="mock")
        assert api.mock_mode is True

    def test_get_page_views_mock(self):
        """Test page views retrieval in mock mode."""
        api = GoogleAnalyticsIntegration(property_id="mock")

        date_range = (
            datetime.utcnow() - timedelta(days=7),
            datetime.utcnow(),
        )

        views = api.get_page_views("match_123", date_range)

        assert isinstance(views, int)
        assert views > 0

    def test_get_cart_additions_mock(self):
        """Test cart additions retrieval in mock mode."""
        api = GoogleAnalyticsIntegration(property_id="mock")

        date_range = (
            datetime.utcnow() - timedelta(days=7),
            datetime.utcnow(),
        )

        additions = api.get_cart_additions("match_123", date_range)

        assert isinstance(additions, int)
        assert additions > 0

    def test_get_cart_abandonments_mock(self):
        """Test cart abandonments retrieval in mock mode."""
        api = GoogleAnalyticsIntegration(property_id="mock")

        date_range = (
            datetime.utcnow() - timedelta(days=7),
            datetime.utcnow(),
        )

        abandonments = api.get_cart_abandonments("match_123", date_range)

        assert isinstance(abandonments, int)
        assert abandonments >= 0

    def test_get_conversion_rate(self):
        """Test conversion rate calculation."""
        api = GoogleAnalyticsIntegration(property_id="mock")

        conversion_rate = api.get_conversion_rate("match_123")

        assert isinstance(conversion_rate, float)
        assert 0.0 <= conversion_rate <= 0.5

    def test_get_demand_metrics(self):
        """Test getting all demand metrics at once."""
        api = GoogleAnalyticsIntegration(property_id="mock")

        date_range = (
            datetime.utcnow() - timedelta(days=7),
            datetime.utcnow(),
        )

        metrics = api.get_demand_metrics("match_123", date_range)

        assert "page_views" in metrics
        assert "cart_additions" in metrics
        assert "cart_abandonments" in metrics
        assert "conversion_rate" in metrics

        # Validate types
        assert isinstance(metrics["page_views"], int)
        assert isinstance(metrics["cart_additions"], int)
        assert isinstance(metrics["cart_abandonments"], int)
        assert isinstance(metrics["conversion_rate"], float)

    def test_cache_functionality(self):
        """Test that caching works correctly."""
        api = GoogleAnalyticsIntegration(property_id="mock")

        date_range = (
            datetime.utcnow() - timedelta(days=7),
            datetime.utcnow(),
        )

        # First call
        views1 = api.get_page_views("match_123", date_range)

        # Second call (should be cached)
        views2 = api.get_page_views("match_123", date_range)

        # Should return same value from cache
        assert views1 == views2


class TestTicketingSystemAPI:
    """Tests for Ticketing System API integration."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        api = TicketingSystemAPI(api_key="mock")
        assert api.mock_mode is True

    def test_get_available_inventory(self):
        """Test getting available inventory."""
        api = TicketingSystemAPI(api_key="mock")

        inventory = api.get_available_inventory("match_123")

        assert isinstance(inventory, dict)
        assert len(inventory) > 0
        # All values should be positive integers
        for zone_id, count in inventory.items():
            assert isinstance(count, int)
            assert count > 0

    def test_reserve_tickets_success(self):
        """Test successful ticket reservation."""
        api = TicketingSystemAPI(api_key="mock")

        reservation_id = api.reserve_tickets(
            match_id="match_123",
            zone_id="zone_vip_1",
            quantity=2,
            customer_email="test@example.com",
        )

        assert isinstance(reservation_id, str)
        assert len(reservation_id) > 0

    def test_reserve_tickets_insufficient_inventory(self):
        """Test reservation fails with insufficient inventory."""
        api = TicketingSystemAPI(api_key="mock")

        # Reserve a huge number that exceeds inventory
        with pytest.raises(ExternalAPIError) as exc_info:
            api.reserve_tickets(
                match_id="match_123",
                zone_id="zone_vip_1",
                quantity=10000,
            )

        assert "insufficient inventory" in str(exc_info.value).lower()

    def test_confirm_purchase_success(self):
        """Test successful purchase confirmation."""
        api = TicketingSystemAPI(api_key="mock")

        # First, create a reservation
        reservation_id = api.reserve_tickets(
            match_id="match_123",
            zone_id="zone_vip_1",
            quantity=2,
        )

        # Then confirm it
        result = api.confirm_purchase(reservation_id, "payment_123")

        assert result is True

    def test_confirm_purchase_nonexistent_reservation(self):
        """Test confirming a non-existent reservation fails."""
        api = TicketingSystemAPI(api_key="mock")

        with pytest.raises(ExternalAPIError) as exc_info:
            api.confirm_purchase("nonexistent_id", "payment_123")

        assert "not found" in str(exc_info.value).lower()

    def test_cancel_reservation_success(self):
        """Test successful reservation cancellation."""
        api = TicketingSystemAPI(api_key="mock")

        # Create a reservation
        reservation_id = api.reserve_tickets(
            match_id="match_123",
            zone_id="zone_vip_1",
            quantity=2,
        )

        # Cancel it
        result = api.cancel_reservation(reservation_id)

        assert result is True

        # Verify status is cancelled
        status = api.get_reservation_status(reservation_id)
        assert status["status"] == ReservationStatus.CANCELLED

    def test_cancel_confirmed_reservation_fails(self):
        """Test that confirmed reservations cannot be cancelled."""
        api = TicketingSystemAPI(api_key="mock")

        # Create and confirm a reservation
        reservation_id = api.reserve_tickets(
            match_id="match_123",
            zone_id="zone_vip_1",
            quantity=2,
        )
        api.confirm_purchase(reservation_id, "payment_123")

        # Try to cancel it (should fail)
        with pytest.raises(ExternalAPIError) as exc_info:
            api.cancel_reservation(reservation_id)

        assert "cannot cancel" in str(exc_info.value).lower()

    def test_get_reservation_status(self):
        """Test getting reservation status."""
        api = TicketingSystemAPI(api_key="mock")

        # Create a reservation
        reservation_id = api.reserve_tickets(
            match_id="match_123",
            zone_id="zone_vip_1",
            quantity=2,
        )

        # Get status
        status = api.get_reservation_status(reservation_id)

        assert status["reservation_id"] == reservation_id
        assert status["status"] == ReservationStatus.PENDING
        assert status["match_id"] == "match_123"
        assert status["zone_id"] == "zone_vip_1"
        assert status["quantity"] == 2

    def test_inventory_decreases_on_reservation(self):
        """Test that inventory decreases when tickets are reserved."""
        api = TicketingSystemAPI(api_key="mock")

        # Get initial inventory
        initial_inventory = api.get_available_inventory("match_123")
        initial_count = initial_inventory["zone_vip_1"]

        # Reserve tickets
        api.reserve_tickets(
            match_id="match_123",
            zone_id="zone_vip_1",
            quantity=5,
        )

        # Get updated inventory
        updated_inventory = api.get_available_inventory("match_123")
        updated_count = updated_inventory["zone_vip_1"]

        # Inventory should have decreased by 5
        assert updated_count == initial_count - 5

    def test_inventory_restores_on_cancellation(self):
        """Test that inventory is restored when reservation is cancelled."""
        api = TicketingSystemAPI(api_key="mock")

        # Get initial inventory
        initial_inventory = api.get_available_inventory("match_123")
        initial_count = initial_inventory["zone_vip_1"]

        # Reserve and then cancel
        reservation_id = api.reserve_tickets(
            match_id="match_123",
            zone_id="zone_vip_1",
            quantity=5,
        )
        api.cancel_reservation(reservation_id)

        # Get final inventory
        final_inventory = api.get_available_inventory("match_123")
        final_count = final_inventory["zone_vip_1"]

        # Inventory should be restored
        assert final_count == initial_count

    def test_clear_expired_reservations(self):
        """Test clearing of expired reservations."""
        api = TicketingSystemAPI(api_key="mock")
        api.reservation_ttl = 0  # Expire immediately

        # Create a reservation
        reservation_id = api.reserve_tickets(
            match_id="match_123",
            zone_id="zone_vip_1",
            quantity=2,
        )

        # Clear expired reservations
        cleared = api.clear_expired_reservations()

        assert cleared == 1

        # Check status is expired
        status = api.get_reservation_status(reservation_id)
        assert status["status"] == ReservationStatus.EXPIRED
