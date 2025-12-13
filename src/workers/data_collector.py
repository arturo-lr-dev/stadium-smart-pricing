"""Data collection worker for the Smart Pricing System.

This worker periodically collects data from external APIs:
- Football statistics and standings
- Weather forecasts
- Analytics data

Implements rate limiting and retry logic with exponential backoff.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.core.database import get_db_session
from src.core.dependencies import get_redis_client
from src.domain.models.db_models import ExternalDataDB
from src.domain.repositories.match_repository import MatchRepository
from src.workers.base_worker import BaseWorker

logger = logging.getLogger(__name__)


class DataCollectorWorker(BaseWorker):
    """Worker that periodically collects data from external APIs.

    This worker:
    - Fetches football statistics and team standings
    - Fetches weather forecasts for match dates
    - Fetches analytics data (page views, conversions)
    - Implements rate limiting to avoid API throttling
    - Caches data in Redis and PostgreSQL
    - Handles API errors with exponential backoff

    Attributes:
        collection_interval: Seconds between collection cycles
        db: Database session
        redis: Redis client
        football_api: Football data API client (placeholder)
        weather_api: Weather API client (placeholder)
        analytics_api: Analytics API client (placeholder)
    """

    def __init__(
        self,
        collection_interval: int = 3600,  # 1 hour default
        max_consecutive_errors: int = 5,
    ):
        """Initialize the data collector worker.

        Args:
            collection_interval: Seconds between collection cycles
            max_consecutive_errors: Maximum consecutive errors before shutdown
        """
        super().__init__(name="DataCollectorWorker", max_consecutive_errors=max_consecutive_errors)
        self.collection_interval = collection_interval
        self.db: Optional[Session] = None
        self.redis = None

        # API clients (placeholders for now - Phase 10)
        self.football_api = None
        self.weather_api = None
        self.analytics_api = None

        # Metrics
        self.total_api_calls = 0
        self.successful_api_calls = 0
        self.failed_api_calls = 0
        self.total_execution_time = 0.0

        # Rate limiting
        self.api_call_timestamps: Dict[str, List[datetime]] = {
            "football": [],
            "weather": [],
            "analytics": [],
        }
        self.rate_limits = {
            "football": {"calls": 100, "period": 3600},  # 100 calls per hour
            "weather": {"calls": 1000, "period": 3600},  # 1000 calls per hour
            "analytics": {"calls": 10000, "period": 3600},  # 10000 calls per hour
        }

        logger.info(f"DataCollectorWorker configured with collection_interval={collection_interval}s")

    def _initialize_dependencies(self) -> None:
        """Initialize dependencies (DB, Redis, API clients)."""
        logger.info("Initializing dependencies...")

        try:
            # Get database session
            self.db = next(get_db_session())
            logger.info("Database connection established")

            # Get Redis client
            self.redis = get_redis_client()
            logger.info("Redis connection established")

            # Initialize API clients (Phase 10 - for now just log)
            logger.info("API clients initialization deferred to Phase 10")
            # self.football_api = FootballDataAPI()
            # self.weather_api = WeatherAPI()
            # self.analytics_api = GoogleAnalyticsIntegration()

        except Exception as e:
            logger.error(f"Failed to initialize dependencies: {e}", exc_info=True)
            raise

    def _cleanup_dependencies(self) -> None:
        """Cleanup dependencies."""
        logger.info("Cleaning up dependencies...")

        if self.db:
            self.db.close()
            logger.info("Database connection closed")

    def run(self) -> None:
        """Main worker loop.

        Continuously:
        1. Collects football data
        2. Collects weather data
        3. Collects analytics data
        4. Stores in cache and DB
        5. Sleeps until next cycle
        """
        logger.info(f"Starting {self.name} main loop")

        # Initialize dependencies
        self._initialize_dependencies()

        try:
            while self.running:
                cycle_start = time.time()

                try:
                    # Update heartbeat
                    self.heartbeat()

                    # Execute data collection cycle
                    self._execute_collection_cycle()

                    # Reset error count on successful execution
                    self.reset_error_count()

                    # Calculate execution time
                    execution_time = time.time() - cycle_start
                    self.total_execution_time += execution_time

                    logger.info(
                        f"Collection cycle completed in {execution_time:.2f}s. "
                        f"Total API calls: {self.total_api_calls}, "
                        f"Successful: {self.successful_api_calls}, "
                        f"Failed: {self.failed_api_calls}"
                    )

                    # Sleep until next cycle
                    if self.running:
                        logger.info(f"Sleeping for {self.collection_interval} seconds...")
                        self.sleep(self.collection_interval)

                except Exception as e:
                    self.handle_error(e)

                    # Exponential backoff on error
                    backoff_time = min(60 * (2 ** self.error_count), 600)  # Max 10 min
                    logger.info(f"Backing off for {backoff_time} seconds after error...")
                    self.sleep(backoff_time)

        finally:
            self._cleanup_dependencies()

    def _execute_collection_cycle(self) -> None:
        """Execute a single data collection cycle."""
        logger.info("Starting data collection cycle...")

        # Collect football data
        self._collect_football_data()

        # Collect weather data
        self._collect_weather_data()

        # Collect analytics data
        self._collect_analytics_data()

        logger.info("Data collection cycle completed")

    def _check_rate_limit(self, api_name: str) -> bool:
        """Check if API call is allowed under rate limit.

        Args:
            api_name: Name of the API (football, weather, analytics)

        Returns:
            True if call is allowed, False otherwise
        """
        now = datetime.now()
        rate_limit = self.rate_limits.get(api_name)

        if not rate_limit:
            return True

        # Clean old timestamps
        cutoff = now - timedelta(seconds=rate_limit["period"])
        self.api_call_timestamps[api_name] = [
            ts for ts in self.api_call_timestamps[api_name]
            if ts > cutoff
        ]

        # Check if under limit
        current_calls = len(self.api_call_timestamps[api_name])
        if current_calls >= rate_limit["calls"]:
            logger.warning(
                f"Rate limit exceeded for {api_name}: "
                f"{current_calls}/{rate_limit['calls']} calls in last {rate_limit['period']}s"
            )
            return False

        return True

    def _record_api_call(self, api_name: str) -> None:
        """Record an API call timestamp.

        Args:
            api_name: Name of the API
        """
        self.api_call_timestamps[api_name].append(datetime.now())
        self.total_api_calls += 1

    def _collect_football_data(self) -> None:
        """Collect football statistics and standings data.

        This is a placeholder for Phase 10 implementation.
        """
        logger.info("Collecting football data...")

        try:
            # Check rate limit
            if not self._check_rate_limit("football"):
                logger.warning("Skipping football data collection due to rate limit")
                return

            # Placeholder for actual API call
            # In Phase 10, this will call the FootballDataAPI
            logger.info("Football API integration deferred to Phase 10")

            # Example of what would happen:
            # data = self.football_api.get_team_standings(league="LaLiga", season="2024")
            # self._store_external_data("football", "team_standings_laliga", data)
            # self._record_api_call("football")
            # self.successful_api_calls += 1

        except Exception as e:
            logger.error(f"Failed to collect football data: {e}", exc_info=True)
            self.failed_api_calls += 1

    def _collect_weather_data(self) -> None:
        """Collect weather forecast data for upcoming matches.

        This is a placeholder for Phase 10 implementation.
        """
        logger.info("Collecting weather data...")

        try:
            # Check rate limit
            if not self._check_rate_limit("weather"):
                logger.warning("Skipping weather data collection due to rate limit")
                return

            # Get upcoming matches
            match_repo = MatchRepository(self.db)
            matches = match_repo.get_upcoming(days=7)

            logger.info(f"Found {len(matches)} upcoming matches for weather forecast")

            # Placeholder for actual API calls
            # In Phase 10, this will call the WeatherAPI for each match
            logger.info("Weather API integration deferred to Phase 10")

            # Example of what would happen:
            # for match in matches:
            #     forecast = self.weather_api.get_forecast(
            #         lat=39.5937, lon=2.6499, date=match.date
            #     )
            #     self._store_external_data("weather", f"forecast_{match.id}", forecast)
            #     self._record_api_call("weather")
            #     self.successful_api_calls += 1

        except Exception as e:
            logger.error(f"Failed to collect weather data: {e}", exc_info=True)
            self.failed_api_calls += 1

    def _collect_analytics_data(self) -> None:
        """Collect analytics data (page views, conversions, etc.).

        This is a placeholder for Phase 10 implementation.
        """
        logger.info("Collecting analytics data...")

        try:
            # Check rate limit
            if not self._check_rate_limit("analytics"):
                logger.warning("Skipping analytics data collection due to rate limit")
                return

            # Placeholder for actual API call
            # In Phase 10, this will call the GoogleAnalyticsIntegration
            logger.info("Analytics API integration deferred to Phase 10")

            # Example of what would happen:
            # data = self.analytics_api.get_page_views(
            #     match_id="match123", date_range=(start_date, end_date)
            # )
            # self._store_external_data("analytics", f"pageviews_match123", data)
            # self._record_api_call("analytics")
            # self.successful_api_calls += 1

        except Exception as e:
            logger.error(f"Failed to collect analytics data: {e}", exc_info=True)
            self.failed_api_calls += 1

    def _store_external_data(self, source: str, data_key: str, data_value: dict) -> None:
        """Store external data in database.

        Args:
            source: Data source (football, weather, analytics)
            data_key: Unique key for the data
            data_value: Data to store
        """
        try:
            # Store in PostgreSQL
            external_data = ExternalDataDB(
                source=source,
                data_key=data_key,
                data_value=data_value,
                fetched_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=6)  # 6 hour TTL
            )

            self.db.add(external_data)
            self.db.commit()

            logger.debug(f"Stored external data: {source}:{data_key}")

            # Also cache in Redis for faster access
            cache_key = f"external:{source}:{data_key}"
            self.redis.setex(cache_key, 21600, str(data_value))  # 6 hours

        except Exception as e:
            logger.error(f"Failed to store external data {source}:{data_key}: {e}", exc_info=True)
            self.db.rollback()

    def get_metrics(self) -> dict:
        """Get worker metrics.

        Returns:
            Dictionary with worker metrics
        """
        return {
            "worker_name": self.name,
            "running": self.running,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "total_api_calls": self.total_api_calls,
            "successful_api_calls": self.successful_api_calls,
            "failed_api_calls": self.failed_api_calls,
            "success_rate": (
                self.successful_api_calls / self.total_api_calls
                if self.total_api_calls > 0 else 0
            ),
            "total_execution_time": self.total_execution_time,
            "error_count": self.error_count,
            "is_healthy": self.is_healthy(),
        }
