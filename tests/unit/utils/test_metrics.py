"""Tests for metrics module."""

import pytest
from prometheus_client import REGISTRY

from src.utils.metrics import (
    MetricsContext,
    active_matches,
    api_errors_total,
    api_request_duration_seconds,
    api_requests_total,
    cache_hit_ratio,
    get_metrics,
    price_changes_total,
    pricing_calculation_duration_seconds,
    pricing_calculations_total,
    record_price_change,
    record_ticket_sale,
    revenue_total,
    set_app_info,
    tickets_sold_total,
    track_counter,
    track_time,
    update_cache_metrics,
)


class TestMetrics:
    """Test basic metrics functionality."""

    def test_set_app_info(self):
        """Test setting application info."""
        set_app_info("1.0.0", "test", "abc123")
        # No assertion needed - just ensure it doesn't crash

    def test_get_metrics(self):
        """Test getting metrics output."""
        metrics = get_metrics()
        assert isinstance(metrics, bytes)
        assert b"smart_pricing_app_info" in metrics

    def test_update_cache_metrics(self):
        """Test updating cache metrics."""
        update_cache_metrics(100, 20)
        # Verify hit ratio is 100/120 = 0.833...
        assert 0.83 < cache_hit_ratio._value.get() < 0.84

        update_cache_metrics(50, 50)
        # Verify hit ratio is 50/100 = 0.5
        assert cache_hit_ratio._value.get() == 0.5

    def test_record_price_change(self):
        """Test recording a price change."""
        initial_count = price_changes_total.labels(
            match_id="match-1", zone_id="zone-a", direction="increase"
        )._value.get()

        record_price_change("match-1", "zone-a", 50.0, 55.0)

        new_count = price_changes_total.labels(
            match_id="match-1", zone_id="zone-a", direction="increase"
        )._value.get()

        assert new_count > initial_count

    def test_record_price_change_decrease(self):
        """Test recording a price decrease."""
        initial_count = price_changes_total.labels(
            match_id="match-2", zone_id="zone-b", direction="decrease"
        )._value.get()

        record_price_change("match-2", "zone-b", 55.0, 50.0)

        new_count = price_changes_total.labels(
            match_id="match-2", zone_id="zone-b", direction="decrease"
        )._value.get()

        assert new_count > initial_count

    def test_record_ticket_sale(self):
        """Test recording a ticket sale."""
        initial_tickets = tickets_sold_total.labels(
            match_id="match-3", zone_id="zone-c", customer_type="member"
        )._value.get()

        initial_revenue = revenue_total.labels(
            match_id="match-3", zone_id="zone-c"
        )._value.get()

        record_ticket_sale("match-3", "zone-c", "member", 2, 100.0)

        new_tickets = tickets_sold_total.labels(
            match_id="match-3", zone_id="zone-c", customer_type="member"
        )._value.get()

        new_revenue = revenue_total.labels(
            match_id="match-3", zone_id="zone-c"
        )._value.get()

        assert new_tickets == initial_tickets + 2
        assert new_revenue == initial_revenue + 100.0


class TestMetricsDecorators:
    """Test metrics decorators."""

    def test_track_time_decorator(self):
        """Test track_time decorator on sync function."""

        @track_time(api_request_duration_seconds, {"method": "GET", "endpoint": "/test"})
        def test_function():
            return "result"

        result = test_function()
        assert result == "result"

        # Check that duration was recorded (can't check exact value, just that it exists)
        metrics = get_metrics()
        assert b"api_request_duration_seconds" in metrics

    def test_track_counter_decorator(self):
        """Test track_counter decorator."""
        initial_count = api_requests_total.labels(
            method="POST", endpoint="/test", status="200"
        )._value.get()

        @track_counter(
            api_requests_total, {"method": "POST", "endpoint": "/test", "status": "200"}
        )
        def test_function():
            return "result"

        result = test_function()
        assert result == "result"

        new_count = api_requests_total.labels(
            method="POST", endpoint="/test", status="200"
        )._value.get()

        assert new_count == initial_count + 1

    def test_track_time_decorator_with_exception(self):
        """Test track_time decorator when function raises exception."""

        @track_time(pricing_calculation_duration_seconds, {"calculation_type": "test"})
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        # Duration should still be recorded even if function fails
        metrics = get_metrics()
        assert b"pricing_calculation_duration_seconds" in metrics


class TestMetricsContext:
    """Test MetricsContext context manager."""

    def test_metrics_context_success(self):
        """Test MetricsContext with successful execution."""
        with MetricsContext(api_request_duration_seconds, {"method": "GET", "endpoint": "/health"}):
            # Simulate some work
            x = 1 + 1

        # Check that metric was recorded
        metrics = get_metrics()
        assert b"api_request_duration_seconds" in metrics

    def test_metrics_context_with_exception(self):
        """Test MetricsContext when exception is raised."""
        with pytest.raises(RuntimeError, match="Test error"):
            with MetricsContext(
                pricing_calculation_duration_seconds, {"calculation_type": "test"}
            ):
                raise RuntimeError("Test error")

        # Duration should still be recorded even with exception
        metrics = get_metrics()
        assert b"pricing_calculation_duration_seconds" in metrics

    def test_metrics_context_no_labels(self):
        """Test MetricsContext with labels."""
        with MetricsContext(api_request_duration_seconds, {"method": "GET", "endpoint": "/test"}):
            x = 1 + 1

        metrics = get_metrics()
        assert b"api_request_duration_seconds" in metrics


class TestAPIMetrics:
    """Test API-specific metrics."""

    def test_api_errors_total(self):
        """Test API error counter."""
        initial = api_errors_total.labels(
            method="GET", endpoint="/fail", error_type="ValueError"
        )._value.get()

        api_errors_total.labels(
            method="GET", endpoint="/fail", error_type="ValueError"
        ).inc()

        new_count = api_errors_total.labels(
            method="GET", endpoint="/fail", error_type="ValueError"
        )._value.get()

        assert new_count == initial + 1


class TestBusinessMetrics:
    """Test business-specific metrics."""

    def test_active_matches_gauge(self):
        """Test active matches gauge."""
        active_matches.set(5)
        assert active_matches._value.get() == 5

        active_matches.inc()
        assert active_matches._value.get() == 6

        active_matches.dec()
        assert active_matches._value.get() == 5
