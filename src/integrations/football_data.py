"""
Football Data API Integration.

This module provides integration with external football data APIs to fetch
team statistics, standings, match details, and recent form data.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from time import sleep

import httpx

from src.core.cache_strategies import ExternalDataCacheStrategy
from src.core.config import get_settings
from src.core.exceptions import ExternalAPIError


logger = logging.getLogger(__name__)


class FootballDataAPI:
    """
    Client for Football Data API integration.

    Provides methods to fetch team standings, statistics, match details,
    and recent form. Includes caching, rate limiting, and retry logic.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.football-data.org/v4",
        cache_strategy: Optional[ExternalDataCacheStrategy] = None,
    ):
        """
        Initialize Football Data API client.

        Args:
            api_key: API key for authentication. If None, reads from settings.
            base_url: Base URL for the API.
            cache_strategy: Optional ExternalDataCacheStrategy for caching (default creates new instance).
        """
        settings = get_settings()
        self.api_key = api_key or settings.FOOTBALL_DATA_API_KEY
        self.base_url = base_url.rstrip("/")
        self.cache = cache_strategy or ExternalDataCacheStrategy()

        # Rate limiting configuration
        config = settings.load_yaml_config("config/base.yaml")
        api_config = config.get("external_apis", {})
        self.rate_limit = api_config.get("rate_limits", {}).get("football_data", 10)

        # Retry configuration
        retry_config = api_config.get("retry", {})
        self.max_attempts = retry_config.get("max_attempts", 3)
        self.backoff_factor = retry_config.get("backoff_factor", 2)
        self.max_delay = retry_config.get("max_delay", 60)

        # Timeouts
        timeout_config = api_config.get("timeouts", {})
        connect_timeout = timeout_config.get("connect", 5.0)
        read_timeout = timeout_config.get("read", 30.0)
        self.timeout = httpx.Timeout(timeout=30.0, connect=connect_timeout, read=read_timeout)

        # Rate limiting state
        self._request_times: List[datetime] = []

        logger.info(
            "FootballDataAPI initialized",
            extra={
                "base_url": self.base_url,
                "rate_limit": self.rate_limit,
            },
        )

    def _get_from_cache(self, key: str) -> Optional[any]:
        """
        Get value from cache.

        Args:
            key: Cache key identifier

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        try:
            cached = self.cache.get("football_stats", key)
            if cached:
                logger.debug(f"Cache hit for key: {key}")
                return cached
        except Exception as e:
            logger.warning(f"Cache error in _get_from_cache: {e}")
        return None

    def _set_cache(self, key: str, value: any) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key identifier
            value: Value to cache
        """
        try:
            self.cache.set("football_stats", key, value)
            logger.debug(f"Cached value for key: {key}")
        except Exception as e:
            logger.warning(f"Failed to cache value: {e}")

    def _apply_rate_limit(self) -> None:
        """
        Apply rate limiting by sleeping if necessary.

        Tracks request times and ensures we don't exceed the configured
        rate limit (requests per minute).
        """
        now = datetime.utcnow()

        # Remove requests older than 1 minute
        cutoff = now - timedelta(minutes=1)
        self._request_times = [t for t in self._request_times if t > cutoff]

        # Check if we need to wait
        if len(self._request_times) >= self.rate_limit:
            oldest = self._request_times[0]
            sleep_time = 60 - (now - oldest).total_seconds()
            if sleep_time > 0:
                logger.warning(
                    f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds"
                )
                sleep(sleep_time)

        # Record this request
        self._request_times.append(datetime.utcnow())

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        cache_key: Optional[str] = None,
    ) -> Dict:
        """
        Make HTTP request to the API with retry and error handling.

        Args:
            endpoint: API endpoint (relative to base_url).
            params: Query parameters.
            cache_key: Cache key for this request. If None, caching is disabled.

        Returns:
            Response JSON as dictionary.

        Raises:
            ExternalAPIError: If the request fails after all retries.
        """
        # Check cache first
        if cache_key:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {"X-Auth-Token": self.api_key} if self.api_key else {}

        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                # Apply rate limiting
                self._apply_rate_limit()

                # Make request
                logger.debug(
                    f"Making request to {url} (attempt {attempt + 1}/{self.max_attempts})"
                )

                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, headers=headers, params=params or {})

                # Handle HTTP errors
                if response.status_code == 401:
                    raise ExternalAPIError(api_name="football_data", message="Football Data API authentication failed. Check API key.", details={"status_code": 401},
                    )
                elif response.status_code == 429:
                    # Rate limited by API - wait and retry
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"API rate limited. Waiting {retry_after} seconds")
                    sleep(min(retry_after, self.max_delay))
                    continue
                elif response.status_code >= 500:
                    # Server error - retry
                    logger.warning(
                        f"Server error {response.status_code}. Retrying..."
                    )
                    if attempt < self.max_attempts - 1:
                        delay = min(
                            self.backoff_factor ** attempt,
                            self.max_delay,
                        )
                        sleep(delay)
                        continue
                    else:
                        raise ExternalAPIError(api_name="football_data", message=f"Football Data API server error: {response.status_code}",
                            status_code=response.status_code,
                        )
                elif response.status_code != 200:
                    raise ExternalAPIError(api_name="football_data", message=f"Football Data API error: {response.status_code} - {response.text}",
                        status_code=response.status_code,
                    )

                # Parse response
                data = response.json()

                # Cache successful response
                if cache_key:
                    self._set_cache(cache_key, data)

                logger.info(
                    "Football Data API request successful",
                    extra={
                        "endpoint": endpoint,
                        "status": response.status_code,
                        "attempt": attempt + 1,
                    },
                )

                return data

            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"Request timeout (attempt {attempt + 1})")
                if attempt < self.max_attempts - 1:
                    delay = min(self.backoff_factor ** attempt, self.max_delay)
                    sleep(delay)

            except httpx.RequestError as e:
                last_exception = e
                logger.warning(f"Request error: {e} (attempt {attempt + 1})")
                if attempt < self.max_attempts - 1:
                    delay = min(self.backoff_factor ** attempt, self.max_delay)
                    sleep(delay)

            except ExternalAPIError:
                # Re-raise our custom errors immediately
                raise

        # If we get here, all retries failed
        raise ExternalAPIError(api_name="football_data", message=f"Football Data API request failed after {self.max_attempts} attempts: {last_exception}",
        )

    def get_team_standings(self, league: str, season: str) -> Dict:
        """
        Get team standings for a specific league and season.

        Args:
            league: League code (e.g., "PD" for La Liga, "CL" for Champions League).
            season: Season year (e.g., "2024").

        Returns:
            Dictionary containing standings data with structure:
            {
                "standings": [
                    {
                        "position": int,
                        "team": {"name": str, "id": str},
                        "points": int,
                        "playedGames": int,
                        ...
                    }
                ]
            }

        Raises:
            ExternalAPIError: If the API request fails.
        """
        cache_key = f"standings:{league}:{season}"
        endpoint = f"/competitions/{league}/standings"
        params = {"season": season}

        logger.info(f"Fetching standings for {league} season {season}")

        try:
            data = self._make_request(endpoint, params, cache_key)
            return data
        except ExternalAPIError as e:
            logger.error(
                f"Failed to fetch standings: {e}",
                extra={"league": league, "season": season},
            )
            raise

    def get_team_stats(self, team_id: str) -> Dict:
        """
        Get detailed statistics for a specific team.

        Args:
            team_id: Unique team identifier.

        Returns:
            Dictionary containing team statistics:
            {
                "id": str,
                "name": str,
                "founded": int,
                "venue": str,
                ...
            }

        Raises:
            ExternalAPIError: If the API request fails.
        """
        cache_key = f"team_stats:{team_id}"
        endpoint = f"/teams/{team_id}"

        logger.info(f"Fetching team stats for team {team_id}")

        try:
            data = self._make_request(endpoint, cache_key=cache_key)
            return data
        except ExternalAPIError as e:
            logger.error(f"Failed to fetch team stats: {e}", extra={"team_id": team_id})
            raise

    def get_match_details(self, match_id: str) -> Dict:
        """
        Get detailed information about a specific match.

        Args:
            match_id: Unique match identifier.

        Returns:
            Dictionary containing match details:
            {
                "id": str,
                "homeTeam": {"name": str, "id": str},
                "awayTeam": {"name": str, "id": str},
                "utcDate": str,
                "status": str,
                "competition": {...},
                ...
            }

        Raises:
            ExternalAPIError: If the API request fails.
        """
        cache_key = f"match:{match_id}"
        endpoint = f"/matches/{match_id}"

        logger.info(f"Fetching match details for match {match_id}")

        try:
            data = self._make_request(endpoint, cache_key=cache_key)
            return data
        except ExternalAPIError as e:
            logger.error(
                f"Failed to fetch match details: {e}",
                extra={"match_id": match_id},
            )
            raise

    def get_team_recent_form(self, team_id: str, matches: int = 5) -> List[Dict]:
        """
        Get recent match results for a team.

        Args:
            team_id: Unique team identifier.
            matches: Number of recent matches to fetch (default 5).

        Returns:
            List of match dictionaries, most recent first:
            [
                {
                    "id": str,
                    "homeTeam": {...},
                    "awayTeam": {...},
                    "score": {...},
                    "utcDate": str,
                    ...
                }
            ]

        Raises:
            ExternalAPIError: If the API request fails.
        """
        cache_key = f"recent_form:{team_id}:{matches}"
        endpoint = f"/teams/{team_id}/matches"
        params = {
            "status": "FINISHED",
            "limit": matches,
        }

        logger.info(f"Fetching recent form for team {team_id} (last {matches} matches)")

        try:
            data = self._make_request(endpoint, params, cache_key)

            # Extract matches from response
            recent_matches = data.get("matches", [])

            # Sort by date (most recent first)
            recent_matches.sort(
                key=lambda m: m.get("utcDate", ""),
                reverse=True,
            )

            return recent_matches[:matches]

        except ExternalAPIError as e:
            logger.error(
                f"Failed to fetch recent form: {e}",
                extra={"team_id": team_id, "matches": matches},
            )
            raise

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.info("Football Data API cache cleared")
