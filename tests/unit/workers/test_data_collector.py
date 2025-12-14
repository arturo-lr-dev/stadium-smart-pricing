"""Unit tests for DataCollectorWorker."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.workers.data_collector import DataCollectorWorker


@pytest.fixture
def mock_dependencies():
    """Mock all dependencies for DataCollectorWorker."""
    with patch("src.workers.data_collector.get_db_session") as mock_db_session, \
         patch("src.workers.data_collector.get_redis_client") as mock_redis, \
         patch("src.workers.data_collector.MatchRepository") as mock_match_repo:

        # Mock database session
        db_mock = MagicMock()
        mock_db_session.return_value = iter([db_mock])

        # Mock Redis client
        redis_mock = MagicMock()
        mock_redis.return_value = redis_mock

        # Mock match repository
        match_repo_mock = MagicMock()
        mock_match_repo.return_value = match_repo_mock

        yield {
            "db": db_mock,
            "redis": redis_mock,
            "match_repo": match_repo_mock,
        }


def test_worker_initialization():
    """Test worker initialization."""
    worker = DataCollectorWorker(
        collection_interval=3600,
        max_consecutive_errors=5
    )

    assert worker.name == "DataCollectorWorker"
    assert worker.collection_interval == 3600
    assert worker.max_consecutive_errors == 5
    assert worker.total_api_calls == 0
    assert worker.successful_api_calls == 0
    assert worker.failed_api_calls == 0


def test_check_rate_limit_allowed():
    """Test rate limit check when calls are allowed."""
    worker = DataCollectorWorker(collection_interval=1)

    # Should be allowed (no calls yet)
    assert worker._check_rate_limit("football") is True


def test_check_rate_limit_exceeded():
    """Test rate limit check when limit is exceeded."""
    worker = DataCollectorWorker(collection_interval=1)

    # Simulate 100 API calls (at the limit)
    now = datetime.now()
    worker.api_call_timestamps["football"] = [now for _ in range(100)]

    # Should be blocked
    assert worker._check_rate_limit("football") is False


def test_check_rate_limit_old_timestamps_cleaned():
    """Test that old timestamps are cleaned up."""
    worker = DataCollectorWorker(collection_interval=1)

    # Add old timestamps (more than 1 hour ago)
    old_time = datetime.now() - timedelta(hours=2)
    worker.api_call_timestamps["football"] = [old_time for _ in range(50)]

    # Should be allowed (old timestamps should be removed)
    assert worker._check_rate_limit("football") is True
    assert len(worker.api_call_timestamps["football"]) == 0


def test_record_api_call():
    """Test recording API call."""
    worker = DataCollectorWorker(collection_interval=1)

    initial_count = worker.total_api_calls

    worker._record_api_call("football")

    assert worker.total_api_calls == initial_count + 1
    assert len(worker.api_call_timestamps["football"]) == 1


def test_collect_football_data_rate_limited():
    """Test football data collection when rate limited."""
    worker = DataCollectorWorker(collection_interval=1)

    # Exceed rate limit
    now = datetime.now()
    worker.api_call_timestamps["football"] = [now for _ in range(100)]

    # Should skip collection
    worker._collect_football_data()

    assert worker.failed_api_calls == 0  # Not counted as failure


def test_collect_weather_data(mock_dependencies):
    """Test weather data collection."""
    worker = DataCollectorWorker(collection_interval=1)
    worker.db = mock_dependencies["db"]
    worker.weather_api = None  # Simulate no weather API configured

    # Mock upcoming matches
    mock_dependencies["match_repo"].get_upcoming.return_value = []

    with patch("src.workers.data_collector.MatchRepository", return_value=mock_dependencies["match_repo"]):
        worker._collect_weather_data()

    # Should complete without error (but skip collection since weather_api is None)
    # No assertions needed as the method should return early when weather_api is None


def test_store_external_data(mock_dependencies):
    """Test storing external data."""
    worker = DataCollectorWorker(collection_interval=1)
    worker.db = mock_dependencies["db"]
    worker.redis = mock_dependencies["redis"]

    # Mock query to return None (no existing record)
    mock_dependencies["db"].query.return_value.filter_by.return_value.first.return_value = None

    data = {"temperature": 25, "condition": "sunny"}

    worker._store_external_data("weather", "forecast_match1", data)

    # Verify query was called to check for existing record
    mock_dependencies["db"].query.assert_called_once()

    # Verify data was added to DB (for new record)
    mock_dependencies["db"].add.assert_called_once()
    mock_dependencies["db"].commit.assert_called_once()

    # Verify data was cached in Redis
    mock_dependencies["redis"].setex.assert_called_once()


def test_get_metrics():
    """Test getting worker metrics."""
    worker = DataCollectorWorker(collection_interval=3600)
    worker.total_api_calls = 100
    worker.successful_api_calls = 95
    worker.failed_api_calls = 5
    worker.total_execution_time = 250.5
    worker.error_count = 1

    metrics = worker.get_metrics()

    assert metrics["worker_name"] == "DataCollectorWorker"
    assert metrics["running"] is False
    assert metrics["total_api_calls"] == 100
    assert metrics["successful_api_calls"] == 95
    assert metrics["failed_api_calls"] == 5
    assert metrics["success_rate"] == 0.95
    assert metrics["total_execution_time"] == 250.5
    assert metrics["error_count"] == 1
    assert "is_healthy" in metrics


def test_execute_collection_cycle():
    """Test full collection cycle."""
    worker = DataCollectorWorker(collection_interval=1)

    # Mock the collection methods
    with patch.object(worker, "_collect_football_data") as mock_football, \
         patch.object(worker, "_collect_weather_data") as mock_weather, \
         patch.object(worker, "_collect_analytics_data") as mock_analytics:

        worker._execute_collection_cycle()

        # Verify all collection methods were called
        mock_football.assert_called_once()
        mock_weather.assert_called_once()
        mock_analytics.assert_called_once()


def test_rate_limits_configuration():
    """Test that rate limits are properly configured."""
    worker = DataCollectorWorker(collection_interval=1)

    # Check rate limits exist for all APIs
    assert "football" in worker.rate_limits
    assert "weather" in worker.rate_limits
    assert "analytics" in worker.rate_limits

    # Check structure
    assert "calls" in worker.rate_limits["football"]
    assert "period" in worker.rate_limits["football"]
