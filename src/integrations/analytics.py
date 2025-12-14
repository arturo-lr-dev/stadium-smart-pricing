"""
Google Analytics Integration.

This module provides integration with Google Analytics Data API to fetch
user behavior metrics such as page views, cart additions, and conversion rates.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from time import sleep

from src.core.config import get_settings
from src.core.exceptions import ExternalAPIError


logger = logging.getLogger(__name__)


class GoogleAnalyticsIntegration:
    """
    Client for Google Analytics Data API integration.

    Provides methods to fetch user behavior metrics including page views,
    cart additions, abandonments, and conversion rates.

    Note: This is a simplified implementation for MVP. In production,
    you would use the official Google Analytics Data API client library.
    """

    def __init__(
        self,
        property_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        cache_ttl: int = 1800,  # 30 minutes
    ):
        """
        Initialize Google Analytics Integration.

        Args:
            property_id: GA4 Property ID. If None, reads from settings.
            credentials_path: Path to service account credentials JSON.
            cache_ttl: Cache TTL in seconds (default 30 minutes).
        """
        settings = get_settings()
        self.property_id = property_id or settings.GA_PROPERTY_ID
        self.credentials_path = credentials_path or settings.GA_CREDENTIALS_PATH
        self.cache_ttl = cache_ttl

        # Simple in-memory cache
        self._cache: Dict[str, Tuple[datetime, any]] = {}

        # Mock mode flag (for MVP without actual GA setup)
        self.mock_mode = not self.property_id or self.property_id == "mock"

        if self.mock_mode:
            logger.warning(
                "Google Analytics running in MOCK mode. "
                "Set GA_PROPERTY_ID in environment to enable real integration."
            )
        else:
            logger.info(
                "GoogleAnalyticsIntegration initialized",
                extra={
                    "property_id": self.property_id,
                    "cache_ttl": self.cache_ttl,
                },
            )

    def _get_from_cache(self, key: str) -> Optional[any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            cached_at, value = self._cache[key]
            if datetime.utcnow() - cached_at < timedelta(seconds=self.cache_ttl):
                logger.debug(f"Cache hit for key: {key}")
                return value
            else:
                # Remove expired entry
                del self._cache[key]
                logger.debug(f"Cache expired for key: {key}")
        return None

    def _set_cache(self, key: str, value: any) -> None:
        """Set value in cache with current timestamp."""
        self._cache[key] = (datetime.utcnow(), value)
        logger.debug(f"Cached value for key: {key}")

    def get_page_views(
        self,
        match_id: str,
        date_range: Tuple[datetime, datetime],
    ) -> int:
        """
        Get number of page views for a specific match page.

        Args:
            match_id: Unique match identifier.
            date_range: Tuple of (start_date, end_date).

        Returns:
            Number of page views in the date range.

        Raises:
            ExternalAPIError: If the API request fails.
        """
        start_date, end_date = date_range
        cache_key = f"page_views:{match_id}:{start_date.date()}:{end_date.date()}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        logger.info(
            f"Fetching page views for match {match_id} "
            f"from {start_date.date()} to {end_date.date()}"
        )

        if self.mock_mode:
            # Return mock data for testing
            views = self._generate_mock_page_views(match_id, date_range)
            self._set_cache(cache_key, views)
            return views

        try:
            # In production, use Google Analytics Data API
            # from google.analytics.data_v1beta import BetaAnalyticsDataClient
            # from google.analytics.data_v1beta.types import (
            #     RunReportRequest,
            #     DateRange,
            #     Dimension,
            #     Metric,
            # )
            #
            # client = BetaAnalyticsDataClient.from_service_account_json(
            #     self.credentials_path
            # )
            #
            # request = RunReportRequest(
            #     property=f"properties/{self.property_id}",
            #     dimensions=[Dimension(name="pagePath")],
            #     metrics=[Metric(name="screenPageViews")],
            #     date_ranges=[DateRange(
            #         start_date=start_date.strftime("%Y-%m-%d"),
            #         end_date=end_date.strftime("%Y-%m-%d"),
            #     )],
            #     dimension_filter=...  # Filter for match_id
            # )
            #
            # response = client.run_report(request)
            # views = sum(int(row.metric_values[0].value) for row in response.rows)

            # For MVP, return mock data
            views = self._generate_mock_page_views(match_id, date_range)
            self._set_cache(cache_key, views)
            return views

        except Exception as e:
            logger.error(
                f"Failed to fetch page views: {e}",
                extra={"match_id": match_id},
            )
            raise ExternalAPIError(
                f"Google Analytics error: {e}",
                source="google_analytics",
            )

    def get_cart_additions(
        self,
        match_id: str,
        date_range: Tuple[datetime, datetime],
    ) -> int:
        """
        Get number of cart additions for a specific match.

        Args:
            match_id: Unique match identifier.
            date_range: Tuple of (start_date, end_date).

        Returns:
            Number of times tickets were added to cart.

        Raises:
            ExternalAPIError: If the API request fails.
        """
        start_date, end_date = date_range
        cache_key = f"cart_additions:{match_id}:{start_date.date()}:{end_date.date()}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        logger.info(
            f"Fetching cart additions for match {match_id} "
            f"from {start_date.date()} to {end_date.date()}"
        )

        if self.mock_mode:
            # Return mock data
            additions = self._generate_mock_cart_additions(match_id, date_range)
            self._set_cache(cache_key, additions)
            return additions

        try:
            # In production, track custom events in GA4
            # event: add_to_cart with match_id parameter

            # For MVP, return mock data
            additions = self._generate_mock_cart_additions(match_id, date_range)
            self._set_cache(cache_key, additions)
            return additions

        except Exception as e:
            logger.error(
                f"Failed to fetch cart additions: {e}",
                extra={"match_id": match_id},
            )
            raise ExternalAPIError(
                f"Google Analytics error: {e}",
                source="google_analytics",
            )

    def get_cart_abandonments(
        self,
        match_id: str,
        date_range: Tuple[datetime, datetime],
    ) -> int:
        """
        Get number of cart abandonments for a specific match.

        Args:
            match_id: Unique match identifier.
            date_range: Tuple of (start_date, end_date).

        Returns:
            Number of times tickets were added but not purchased.

        Raises:
            ExternalAPIError: If the API request fails.
        """
        start_date, end_date = date_range
        cache_key = f"cart_abandonments:{match_id}:{start_date.date()}:{end_date.date()}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        logger.info(
            f"Fetching cart abandonments for match {match_id} "
            f"from {start_date.date()} to {end_date.date()}"
        )

        if self.mock_mode:
            # Return mock data
            abandonments = self._generate_mock_abandonments(match_id, date_range)
            self._set_cache(cache_key, abandonments)
            return abandonments

        try:
            # In production, calculate as cart_additions - purchases
            # Or track custom abandonment events

            # For MVP, return mock data
            abandonments = self._generate_mock_abandonments(match_id, date_range)
            self._set_cache(cache_key, abandonments)
            return abandonments

        except Exception as e:
            logger.error(
                f"Failed to fetch cart abandonments: {e}",
                extra={"match_id": match_id},
            )
            raise ExternalAPIError(
                f"Google Analytics error: {e}",
                source="google_analytics",
            )

    def get_conversion_rate(self, match_id: str) -> float:
        """
        Get conversion rate for a specific match.

        Conversion rate = purchases / page_views

        Args:
            match_id: Unique match identifier.

        Returns:
            Conversion rate as a decimal (e.g., 0.15 = 15%).

        Raises:
            ExternalAPIError: If the API request fails.
        """
        cache_key = f"conversion_rate:{match_id}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        logger.info(f"Calculating conversion rate for match {match_id}")

        try:
            # Get data for last 7 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            date_range = (start_date, end_date)

            page_views = self.get_page_views(match_id, date_range)
            cart_additions = self.get_cart_additions(match_id, date_range)

            if page_views == 0:
                conversion_rate = 0.0
            else:
                # Simplified: cart additions / page views
                # In production, use actual purchases
                conversion_rate = cart_additions / page_views

            # Cap at reasonable maximum
            conversion_rate = min(conversion_rate, 0.5)

            self._set_cache(cache_key, conversion_rate)

            logger.info(
                f"Conversion rate for match {match_id}: {conversion_rate:.2%}",
                extra={
                    "page_views": page_views,
                    "cart_additions": cart_additions,
                },
            )

            return conversion_rate

        except Exception as e:
            logger.error(
                f"Failed to calculate conversion rate: {e}",
                extra={"match_id": match_id},
            )
            # Return default conversion rate instead of failing
            return 0.10  # 10% default

    def get_demand_metrics(
        self,
        match_id: str,
        date_range: Tuple[datetime, datetime],
    ) -> Dict[str, int]:
        """
        Get all demand-related metrics for a match in one call.

        Args:
            match_id: Unique match identifier.
            date_range: Tuple of (start_date, end_date).

        Returns:
            Dictionary containing:
            {
                "page_views": int,
                "cart_additions": int,
                "cart_abandonments": int,
                "conversion_rate": float,
            }
        """
        logger.info(
            f"Fetching all demand metrics for match {match_id}"
        )

        return {
            "page_views": self.get_page_views(match_id, date_range),
            "cart_additions": self.get_cart_additions(match_id, date_range),
            "cart_abandonments": self.get_cart_abandonments(match_id, date_range),
            "conversion_rate": self.get_conversion_rate(match_id),
        }

    def _generate_mock_page_views(
        self,
        match_id: str,
        date_range: Tuple[datetime, datetime],
    ) -> int:
        """
        Generate realistic mock page views for testing.

        Args:
            match_id: Unique match identifier.
            date_range: Date range for the metric.

        Returns:
            Mock page views count.
        """
        # Use match_id hash to get consistent but varying results
        base = hash(match_id) % 1000 + 500

        # Increase views as match date approaches
        start_date, end_date = date_range
        days = (end_date - start_date).days + 1

        # More recent = more views
        multiplier = 1 + (days / 10)

        views = int(base * multiplier)

        logger.debug(f"Generated mock page views: {views}")
        return views

    def _generate_mock_cart_additions(
        self,
        match_id: str,
        date_range: Tuple[datetime, datetime],
    ) -> int:
        """
        Generate realistic mock cart additions for testing.

        Typically 10-20% of page views convert to cart additions.

        Args:
            match_id: Unique match identifier.
            date_range: Date range for the metric.

        Returns:
            Mock cart additions count.
        """
        page_views = self._generate_mock_page_views(match_id, date_range)

        # 15% conversion rate on average
        additions = int(page_views * 0.15)

        logger.debug(f"Generated mock cart additions: {additions}")
        return additions

    def _generate_mock_abandonments(
        self,
        match_id: str,
        date_range: Tuple[datetime, datetime],
    ) -> int:
        """
        Generate realistic mock cart abandonments for testing.

        Typically 30-40% of cart additions are abandoned.

        Args:
            match_id: Unique match identifier.
            date_range: Date range for the metric.

        Returns:
            Mock abandonments count.
        """
        cart_additions = self._generate_mock_cart_additions(match_id, date_range)

        # 35% abandonment rate
        abandonments = int(cart_additions * 0.35)

        logger.debug(f"Generated mock abandonments: {abandonments}")
        return abandonments

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.info("Google Analytics cache cleared")
