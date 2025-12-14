"""
Weather API Integration.

This module provides integration with external weather APIs to fetch
weather forecasts and historical weather data for match planning.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from time import sleep

import httpx

from src.core.config import get_settings
from src.core.exceptions import ExternalAPIError


logger = logging.getLogger(__name__)


class WeatherAPI:
    """
    Client for Weather API integration (OpenWeatherMap).

    Provides methods to fetch weather forecasts and historical data.
    Includes caching, rate limiting, and fallback mechanisms.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openweathermap.org/data/2.5",
        cache_ttl: int = 3600,  # 1 hour
    ):
        """
        Initialize Weather API client.

        Args:
            api_key: API key for authentication. If None, reads from settings.
            base_url: Base URL for the API.
            cache_ttl: Cache TTL in seconds (default 1 hour).
        """
        settings = get_settings()
        self.api_key = api_key or settings.WEATHER_API_KEY
        self.base_url = base_url.rstrip("/")
        self.cache_ttl = cache_ttl

        # Rate limiting configuration
        config = settings.load_yaml_config("config/base.yaml")
        api_config = config.get("external_apis", {})
        self.rate_limit = api_config.get("rate_limits", {}).get("weather_api", 60)

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

        # Simple in-memory cache (could be upgraded to Redis)
        self._cache: Dict[str, tuple[datetime, any]] = {}

        # Rate limiting state
        self._request_times: list[datetime] = []

        logger.info(
            "WeatherAPI initialized",
            extra={
                "base_url": self.base_url,
                "rate_limit": self.rate_limit,
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

        # Add API key to params
        request_params = params.copy() if params else {}
        if self.api_key:
            request_params["appid"] = self.api_key
        request_params["units"] = "metric"  # Use Celsius

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
                    response = client.get(url, params=request_params)

                # Handle HTTP errors
                if response.status_code == 401:
                    raise ExternalAPIError(api_name="weather_api", message="Weather API authentication failed. Check API key.", details={"status_code": 401},
                    )
                elif response.status_code == 429:
                    # Rate limited by API - wait and retry
                    logger.warning("API rate limited. Waiting before retry...")
                    if attempt < self.max_attempts - 1:
                        delay = min(
                            self.backoff_factor ** attempt,
                            self.max_delay,
                        )
                        sleep(delay)
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
                        raise ExternalAPIError(api_name="weather_api", message=f"Weather API server error: {response.status_code}",
                            status_code=response.status_code,
                        )
                elif response.status_code != 200:
                    raise ExternalAPIError(api_name="weather_api", message=f"Weather API error: {response.status_code} - {response.text}",
                        status_code=response.status_code,
                    )

                # Parse response
                data = response.json()

                # Cache successful response
                if cache_key:
                    self._set_cache(cache_key, data)

                logger.info(
                    "Weather API request successful",
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
        raise ExternalAPIError(api_name="weather_api", message=f"Weather API request failed after {self.max_attempts} attempts: {last_exception}",
        )

    def get_forecast(self, lat: float, lon: float, date: datetime) -> Dict:
        """
        Get weather forecast for a specific location and date.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            date: Date/time for which to get the forecast.

        Returns:
            Dictionary containing weather forecast:
            {
                "temperature": float,  # in Celsius
                "precipitation_probability": float,  # 0-1
                "wind_speed": float,  # in m/s
                "weather_condition": str,  # e.g., "Clear", "Rain", "Clouds"
                "description": str,  # detailed description
                "humidity": float,  # percentage
                "forecast_date": str,  # ISO format
            }

        Raises:
            ExternalAPIError: If the API request fails.
        """
        cache_key = f"forecast:{lat:.3f},{lon:.3f}:{date.strftime('%Y%m%d%H')}"

        logger.info(
            f"Fetching weather forecast for ({lat}, {lon}) on {date.isoformat()}"
        )

        # Determine which endpoint to use based on how far in the future
        days_ahead = (date.date() - datetime.utcnow().date()).days

        try:
            if days_ahead <= 5:
                # Use 5-day forecast API
                endpoint = "forecast"
                params = {"lat": lat, "lon": lon}

                data = self._make_request(endpoint, params, cache_key)

                # Find the forecast closest to the requested date
                target_timestamp = int(date.timestamp())
                closest_forecast = None
                min_diff = float("inf")

                for forecast in data.get("list", []):
                    forecast_timestamp = forecast.get("dt", 0)
                    diff = abs(forecast_timestamp - target_timestamp)
                    if diff < min_diff:
                        min_diff = diff
                        closest_forecast = forecast

                if not closest_forecast:
                    # Use fallback data
                    logger.warning("No forecast data available, using defaults")
                    return self._get_default_weather()

                # Extract relevant data
                main = closest_forecast.get("main", {})
                weather = closest_forecast.get("weather", [{}])[0]
                wind = closest_forecast.get("wind", {})
                pop = closest_forecast.get("pop", 0.0)  # Probability of precipitation

                return {
                    "temperature": main.get("temp", 20.0),
                    "precipitation_probability": pop,
                    "wind_speed": wind.get("speed", 0.0),
                    "weather_condition": weather.get("main", "Clear"),
                    "description": weather.get("description", "clear sky"),
                    "humidity": main.get("humidity", 50),
                    "forecast_date": date.isoformat(),
                }

            else:
                # For dates beyond 5 days, use fallback/historical average
                logger.warning(
                    f"Forecast requested for {days_ahead} days ahead. Using historical average."
                )
                return self._get_historical_average(lat, lon, date)

        except ExternalAPIError as e:
            logger.error(
                f"Failed to fetch weather forecast: {e}",
                extra={"lat": lat, "lon": lon, "date": date.isoformat()},
            )
            # Return default weather instead of failing
            logger.warning("Falling back to default weather data")
            return self._get_default_weather()

    def get_historical_weather(self, lat: float, lon: float, date: datetime) -> Dict:
        """
        Get historical weather data for a specific location and date.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            date: Historical date for which to get weather data.

        Returns:
            Dictionary containing historical weather data with same structure
            as get_forecast().

        Raises:
            ExternalAPIError: If the API request fails.
        """
        cache_key = f"historical:{lat:.3f},{lon:.3f}:{date.strftime('%Y%m%d')}"

        logger.info(
            f"Fetching historical weather for ({lat}, {lon}) on {date.isoformat()}"
        )

        # Note: OpenWeatherMap historical API requires a paid plan
        # For MVP, we use a fallback approach
        return self._get_historical_average(lat, lon, date)

    def _get_historical_average(self, lat: float, lon: float, date: datetime) -> Dict:
        """
        Get historical average weather for a location and month.

        This is a fallback method that provides reasonable estimates
        based on the month and location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            date: Date to get historical average for.

        Returns:
            Dictionary with estimated weather data.
        """
        # For Palma de Mallorca (and similar Mediterranean climates)
        # Provide seasonal averages
        month = date.month

        # Monthly averages for Palma de Mallorca
        monthly_temps = {
            1: 14, 2: 14, 3: 16, 4: 18, 5: 21, 6: 25,
            7: 28, 8: 29, 9: 26, 10: 22, 11: 17, 12: 15,
        }

        monthly_rain_prob = {
            1: 0.3, 2: 0.3, 3: 0.25, 4: 0.2, 5: 0.15, 6: 0.1,
            7: 0.05, 8: 0.1, 9: 0.2, 10: 0.3, 11: 0.35, 12: 0.3,
        }

        temp = monthly_temps.get(month, 20)
        rain_prob = monthly_rain_prob.get(month, 0.2)

        logger.info(
            f"Using historical average for month {month}: {temp}°C, {rain_prob*100}% rain probability"
        )

        return {
            "temperature": temp,
            "precipitation_probability": rain_prob,
            "wind_speed": 3.5,  # Average wind speed
            "weather_condition": "Clouds" if rain_prob > 0.3 else "Clear",
            "description": "historical average",
            "humidity": 65,
            "forecast_date": date.isoformat(),
        }

    def _get_default_weather(self) -> Dict:
        """
        Get default weather data as fallback.

        Returns:
            Dictionary with neutral weather conditions.
        """
        logger.info("Using default weather data")
        return {
            "temperature": 20.0,
            "precipitation_probability": 0.1,
            "wind_speed": 2.0,
            "weather_condition": "Clear",
            "description": "default fallback",
            "humidity": 60,
            "forecast_date": datetime.utcnow().isoformat(),
        }

    def calculate_weather_factor(self, weather_data: Dict) -> float:
        """
        Calculate weather impact factor for pricing (0.9 - 1.1).

        Good weather increases factor slightly (more demand).
        Bad weather decreases factor (less demand).

        Args:
            weather_data: Weather data dictionary from get_forecast().

        Returns:
            Weather factor between 0.9 and 1.1.
        """
        factor = 1.0

        # Temperature impact (optimal is 18-25°C)
        temp = weather_data.get("temperature", 20)
        if temp < 10:
            factor -= 0.05  # Very cold
        elif temp < 15:
            factor -= 0.03  # Cold
        elif temp > 30:
            factor -= 0.05  # Very hot
        elif temp > 28:
            factor -= 0.02  # Hot

        # Precipitation impact
        rain_prob = weather_data.get("precipitation_probability", 0)
        if rain_prob > 0.7:
            factor -= 0.08  # Very likely rain
        elif rain_prob > 0.5:
            factor -= 0.05  # Likely rain
        elif rain_prob > 0.3:
            factor -= 0.02  # Possible rain

        # Wind impact
        wind_speed = weather_data.get("wind_speed", 0)
        if wind_speed > 15:
            factor -= 0.03  # Very windy

        # Ensure factor stays within bounds
        factor = max(0.9, min(1.1, factor))

        logger.debug(
            f"Weather factor calculated: {factor}",
            extra={
                "temperature": temp,
                "rain_probability": rain_prob,
                "wind_speed": wind_speed,
            },
        )

        return factor

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.info("Weather API cache cleared")
