"""Price update worker for the Smart Pricing System.

This worker periodically calculates and updates prices for upcoming matches,
stores them in cache (Redis) and historical data (PostgreSQL).
"""

import logging
import time
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.database import get_db_session
from src.core.dependencies import get_pricing_engine, get_redis_client
from src.domain.models.match import Match
from src.domain.models.pricing import MatchPricing
from src.domain.models.zone import Zone
from src.domain.repositories.match_repository import MatchRepository
from src.domain.repositories.pricing_repository import PricingHistoryRepository
from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.services.pricing_engine import PricingEngine
from src.workers.base_worker import BaseWorker

logger = logging.getLogger(__name__)


class PriceUpdaterWorker(BaseWorker):
    """Worker that periodically updates prices for upcoming matches.

    This worker:
    - Fetches upcoming matches (configurable days ahead)
    - Calculates optimal pricing for each match and zone
    - Decides whether to update prices based on rules
    - Stores updated prices in Redis cache
    - Stores pricing history in PostgreSQL
    - Handles errors with exponential backoff

    Attributes:
        update_interval: Seconds between update cycles
        lookback_days: Number of days to look ahead for matches
        pricing_engine: PricingEngine instance
        db: Database session
        redis: Redis client
    """

    def __init__(
        self,
        update_interval: int = 300,  # 5 minutes default
        lookback_days: int = 30,
        max_consecutive_errors: int = 5,
    ):
        """Initialize the price updater worker.

        Args:
            update_interval: Seconds between update cycles
            lookback_days: Number of days to look ahead for matches
            max_consecutive_errors: Maximum consecutive errors before shutdown
        """
        super().__init__(name="PriceUpdaterWorker", max_consecutive_errors=max_consecutive_errors)
        self.update_interval = update_interval
        self.lookback_days = lookback_days
        self.pricing_engine: Optional[PricingEngine] = None
        self.db: Optional[Session] = None
        self.redis = None

        # Metrics
        self.matches_processed = 0
        self.prices_updated = 0
        self.total_execution_time = 0.0

        logger.info(
            f"PriceUpdaterWorker configured with "
            f"update_interval={update_interval}s, lookback_days={lookback_days}"
        )

    def _initialize_dependencies(self) -> None:
        """Initialize dependencies (DB, Redis, PricingEngine)."""
        logger.info("Initializing dependencies...")

        try:
            # Get database session
            self.db = next(get_db_session())
            logger.info("Database connection established")

            # Get Redis client
            self.redis = get_redis_client()
            logger.info("Redis connection established")

            # Get pricing engine
            self.pricing_engine = get_pricing_engine(db=self.db)
            logger.info("PricingEngine initialized")

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
        1. Fetches upcoming matches
        2. Calculates pricing for each match
        3. Updates prices if necessary
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

                    # Execute pricing update cycle
                    self._execute_update_cycle()

                    # Reset error count on successful execution
                    self.reset_error_count()

                    # Calculate execution time
                    execution_time = time.time() - cycle_start
                    self.total_execution_time += execution_time

                    logger.info(
                        f"Update cycle completed in {execution_time:.2f}s. "
                        f"Total matches processed: {self.matches_processed}, "
                        f"Prices updated: {self.prices_updated}"
                    )

                    # Sleep until next cycle
                    if self.running:
                        logger.info(f"Sleeping for {self.update_interval} seconds...")
                        self.sleep(self.update_interval)

                except Exception as e:
                    self.handle_error(e)

                    # Exponential backoff on error
                    backoff_time = min(60 * (2 ** self.error_count), 600)  # Max 10 min
                    logger.info(f"Backing off for {backoff_time} seconds after error...")
                    self.sleep(backoff_time)

        finally:
            self._cleanup_dependencies()

    def _execute_update_cycle(self) -> None:
        """Execute a single pricing update cycle."""
        logger.info("Starting pricing update cycle...")

        # Fetch upcoming matches
        matches = self._fetch_upcoming_matches()
        logger.info(f"Found {len(matches)} upcoming matches")

        if not matches:
            logger.info("No upcoming matches to process")
            return

        # Fetch all zones
        zones = self._fetch_zones()
        logger.info(f"Loaded {len(zones)} zones")

        # Process each match
        for match in matches:
            try:
                self._process_match(match, zones)
                self.matches_processed += 1
            except Exception as e:
                logger.error(f"Failed to process match {match.id}: {e}", exc_info=True)
                # Continue with next match instead of failing entire cycle
                continue

    def _fetch_upcoming_matches(self) -> List[Match]:
        """Fetch upcoming matches from the database.

        Returns:
            List of upcoming matches
        """
        try:
            match_repo = MatchRepository(self.db)
            matches = match_repo.get_upcoming(days=self.lookback_days)
            return matches
        except Exception as e:
            logger.error(f"Failed to fetch upcoming matches: {e}", exc_info=True)
            return []

    def _fetch_zones(self) -> List[Zone]:
        """Fetch all active zones from the database.

        Returns:
            List of active zones
        """
        try:
            zone_repo = ZoneRepository(self.db)
            zones = zone_repo.get_active_zones()
            return zones
        except Exception as e:
            logger.error(f"Failed to fetch zones: {e}", exc_info=True)
            return []

    def _process_match(self, match: Match, zones: List[Zone]) -> None:
        """Process a single match: calculate pricing and update if necessary.

        Args:
            match: Match to process
            zones: List of available zones
        """
        logger.info(f"Processing match {match.id}: {match.home_team} vs {match.away_team}")

        # Calculate pricing
        match_pricing = self.pricing_engine.calculate_match_pricing(
            match=match,
            zones=zones,
            current_datetime=datetime.now()
        )

        logger.info(
            f"Calculated pricing for match {match.id}: "
            f"avg_price={match_pricing.avg_price:.2f}, "
            f"total_revenue={match_pricing.total_revenue:.2f}"
        )

        # Store in cache (Redis)
        self._cache_pricing(match.id, match_pricing)

        # Store in historical data (PostgreSQL)
        self._save_pricing_history(match_pricing)

        logger.info(f"Successfully processed match {match.id}")

    def _cache_pricing(self, match_id: str, pricing: MatchPricing) -> None:
        """Cache pricing data in Redis.

        Args:
            match_id: Match identifier
            pricing: MatchPricing object to cache
        """
        try:
            cache_key = f"pricing:match:{match_id}"
            cache_ttl = 300  # 5 minutes

            # Convert to dict for caching
            pricing_dict = pricing.model_dump()

            # Store in Redis
            self.redis.setex(
                cache_key,
                cache_ttl,
                str(pricing_dict)  # Simple string serialization for now
            )

            logger.debug(f"Cached pricing for match {match_id} with TTL={cache_ttl}s")
            self.prices_updated += 1

        except Exception as e:
            logger.error(f"Failed to cache pricing for match {match_id}: {e}", exc_info=True)
            # Don't raise - caching failure shouldn't stop the worker

    def _save_pricing_history(self, pricing: MatchPricing) -> None:
        """Save pricing to historical database.

        Args:
            pricing: MatchPricing object to save
        """
        try:
            pricing_repo = PricingHistoryRepository(self.db)
            pricing_repo.save_pricing(pricing)
            self.db.commit()

            logger.debug(f"Saved pricing history for match {pricing.match_id}")

        except Exception as e:
            logger.error(f"Failed to save pricing history for match {pricing.match_id}: {e}", exc_info=True)
            self.db.rollback()
            # Don't raise - history saving failure shouldn't stop the worker

    def get_metrics(self) -> dict:
        """Get worker metrics.

        Returns:
            Dictionary with worker metrics
        """
        return {
            "worker_name": self.name,
            "running": self.running,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "matches_processed": self.matches_processed,
            "prices_updated": self.prices_updated,
            "total_execution_time": self.total_execution_time,
            "error_count": self.error_count,
            "is_healthy": self.is_healthy(),
        }
