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

from src.core.config import get_settings
from src.core.database import get_db_session
from src.core.dependencies import get_redis_client
from src.domain.models.db_models import ExternalDataDB
from src.domain.repositories.match_repository import MatchRepository
from src.integrations import FootballDataAPI, WeatherAPI, GoogleAnalyticsIntegration
from src.workers.base_worker import BaseWorker

logger = logging.getLogger(__name__)


class DataCollectorWorker(BaseWorker):
    """Worker that periodically collects data from external APIs.

    This worker:
    - Fetches football statistics and team standings via FootballDataAPI
    - Fetches weather forecasts for match dates via WeatherAPI
    - Fetches analytics data (page views, conversions) via GoogleAnalyticsIntegration
    - Implements rate limiting to avoid API throttling
    - Caches data in Redis and PostgreSQL
    - Handles API errors with exponential backoff

    Attributes:
        collection_interval: Seconds between collection cycles
        db: Database session
        redis: Redis client
        football_api: Football data API client (FootballDataAPI)
        weather_api: Weather API client (WeatherAPI)
        analytics_api: Analytics API client (GoogleAnalyticsIntegration)
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

        # API clients (initialized in _initialize_dependencies)
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
            self.db = get_db_session()
            logger.info("Database connection established")

            # Get Redis client
            self.redis = get_redis_client()
            logger.info("Redis connection established")

            # Initialize API clients (Phase 10)
            settings = get_settings()

            # Football Data API
            if settings.FOOTBALL_DATA_API_KEY:
                self.football_api = FootballDataAPI(api_key=settings.FOOTBALL_DATA_API_KEY)
                logger.info("Football Data API client initialized")
            else:
                logger.warning("Football Data API key not configured, skipping initialization")

            # Weather API
            if settings.WEATHER_API_KEY:
                self.weather_api = WeatherAPI(api_key=settings.WEATHER_API_KEY)
                logger.info("Weather API client initialized")
            else:
                logger.warning("Weather API key not configured, skipping initialization")

            # Google Analytics (uses mock mode if not configured)
            self.analytics_api = GoogleAnalyticsIntegration(
                property_id=settings.GA_PROPERTY_ID
            )
            logger.info(f"Google Analytics client initialized (mock_mode={self.analytics_api.mock_mode})")

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
        """Collect football statistics and standings data."""
        logger.info("Collecting football data...")

        if not self.football_api:
            logger.debug("Football API not initialized, skipping")
            return

        try:
            # Check rate limit
            if not self._check_rate_limit("football"):
                logger.warning("Skipping football data collection due to rate limit")
                return

            # Get current season
            current_year = datetime.now().year
            season = str(current_year)

            # Collect La Liga standings
            logger.info(f"Fetching La Liga standings for season {season}...")
            standings = self.football_api.get_team_standings(league="PD", season=season)
            self._store_external_data("football", f"standings_laliga_{season}", standings)
            self._record_api_call("football")
            self.successful_api_calls += 1
            logger.info(f"Successfully collected La Liga standings ({len(standings.get('standings', []))} teams)")

            # Get upcoming matches from DB to fetch team stats
            match_repo = MatchRepository(self.db)
            upcoming_matches = match_repo.get_upcoming(days=30)

            # Collect stats for teams in upcoming matches (limit to avoid rate limiting)
            teams_collected = set()
            for match in upcoming_matches[:5]:  # Limit to 5 matches per cycle
                for team_name in [match.home_team, match.away_team]:
                    if team_name not in teams_collected:
                        # Note: In production, you'd need team IDs from a mapping
                        # For now, we just log the intent
                        logger.debug(f"Would collect stats for team: {team_name}")
                        teams_collected.add(team_name)

        except Exception as e:
            logger.error(f"Failed to collect football data: {e}", exc_info=True)
            self.failed_api_calls += 1

    def _collect_weather_data(self) -> None:
        """Collect weather forecast data for upcoming matches."""
        logger.info("Collecting weather data...")

        if not self.weather_api:
            logger.debug("Weather API not initialized, skipping")
            return

        try:
            # Check rate limit
            if not self._check_rate_limit("weather"):
                logger.warning("Skipping weather data collection due to rate limit")
                return

            # Get upcoming matches (limit to 5 days to stay within API forecast limits)
            match_repo = MatchRepository(self.db)
            matches = match_repo.get_upcoming(days=5)

            logger.info(f"Found {len(matches)} upcoming matches for weather forecast")

            # Get stadium location from settings
            settings = get_settings()
            stadium_lat = settings.stadium_latitude
            stadium_lon = settings.stadium_longitude

            # Fetch weather forecast for each match
            forecasts_collected = 0
            for match in matches:
                try:
                    logger.info(f"Fetching weather forecast for match {match.id} on {match.date}")

                    forecast = self.weather_api.get_forecast(
                        lat=stadium_lat,
                        lon=stadium_lon,
                        date=match.date
                    )

                    # Store forecast data
                    self._store_external_data("weather", f"forecast_{match.id}", forecast)
                    self._record_api_call("weather")
                    self.successful_api_calls += 1
                    forecasts_collected += 1

                    # Calculate weather factor for logging
                    weather_factor = self.weather_api.calculate_weather_factor(forecast)
                    logger.info(
                        f"Weather forecast for {match.id}: "
                        f"{forecast['temperature']}°C, "
                        f"{forecast['precipitation_probability']:.0%} rain, "
                        f"factor={weather_factor:.3f}"
                    )

                except Exception as e:
                    logger.warning(f"Failed to fetch weather for match {match.id}: {e}")
                    continue

            logger.info(f"Successfully collected {forecasts_collected} weather forecasts")

        except Exception as e:
            logger.error(f"Failed to collect weather data: {e}", exc_info=True)
            self.failed_api_calls += 1

    def _collect_analytics_data(self) -> None:
        """Collect analytics data (page views, conversions, etc.)."""
        logger.info("Collecting analytics data...")

        if not self.analytics_api:
            logger.debug("Analytics API not initialized, skipping")
            return

        try:
            # Check rate limit
            if not self._check_rate_limit("analytics"):
                logger.warning("Skipping analytics data collection due to rate limit")
                return

            # Get upcoming matches to collect analytics
            match_repo = MatchRepository(self.db)
            matches = match_repo.get_upcoming(days=30)

            logger.info(f"Collecting analytics for {len(matches)} upcoming matches")

            # Date range for analytics: last 7 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            date_range = (start_date, end_date)

            # Collect metrics for each match
            metrics_collected = 0
            for match in matches[:10]:  # Limit to 10 matches per cycle
                try:
                    logger.info(f"Fetching analytics for match {match.id}")

                    # Get all demand metrics in one call
                    metrics = self.analytics_api.get_demand_metrics(
                        match_id=match.id,
                        date_range=date_range
                    )

                    # Store metrics
                    self._store_external_data("analytics", f"metrics_{match.id}", metrics)
                    self._record_api_call("analytics")
                    self.successful_api_calls += 1
                    metrics_collected += 1

                    logger.info(
                        f"Analytics for {match.id}: "
                        f"{metrics['page_views']} views, "
                        f"{metrics['cart_additions']} cart adds, "
                        f"{metrics['conversion_rate']:.2%} conversion"
                    )

                except Exception as e:
                    logger.warning(f"Failed to fetch analytics for match {match.id}: {e}")
                    continue

            logger.info(f"Successfully collected analytics for {metrics_collected} matches")

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
