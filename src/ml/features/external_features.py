"""
External Feature Extractor for Demand Prediction.

Extracts features from external data sources (weather, transport, etc.).
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.domain.models.match import Match

logger = logging.getLogger(__name__)


class ExternalFeatureExtractor:
    """
    Extracts features from external data sources for ML model input.

    Features include:
    - Weather conditions
    - Transport availability
    - External events

    Note: For MVP, many of these are placeholders with reasonable defaults.
    """

    def __init__(self, weather_api: Optional[Any] = None, transport_api: Optional[Any] = None):
        """
        Initialize the external feature extractor.

        Args:
            weather_api: Optional weather API client
            transport_api: Optional transport API client
        """
        self.weather_api = weather_api
        self.transport_api = transport_api
        logger.info("ExternalFeatureExtractor initialized")

    def extract_weather_features(self, match: Match) -> Dict[str, Any]:
        """
        Extract weather-related features.

        For MVP, returns placeholder values. In production, would call weather API.

        Args:
            match: Match object

        Returns:
            Dictionary with weather features:
            - temperature: float (Celsius)
            - precipitation_probability: float (0-1)
            - wind_speed: float (km/h)
            - is_rainy: bool
            - is_good_weather: bool
            - weather_score: float (0-1, 1=perfect weather)
        """
        features = {}

        if self.weather_api:
            # In production, fetch real weather data
            try:
                weather_data = self.weather_api.get_forecast(
                    lat=39.5950,  # Palma de Mallorca coordinates
                    lon=2.6505,
                    date=match.date
                )
                features["temperature"] = weather_data.get("temperature", 20.0)
                features["precipitation_probability"] = weather_data.get("precipitation_prob", 0.2)
                features["wind_speed"] = weather_data.get("wind_speed", 10.0)
            except Exception as e:
                logger.warning(f"Failed to fetch weather data: {e}, using defaults")
                features.update(self._get_default_weather(match))
        else:
            # MVP: Use seasonal defaults
            features.update(self._get_default_weather(match))

        # Derived features
        features["is_rainy"] = features["precipitation_probability"] > 0.5
        features["is_cold"] = features["temperature"] < 10
        features["is_hot"] = features["temperature"] > 30
        features["is_windy"] = features["wind_speed"] > 30

        # Weather score: 1.0 = perfect, 0.5 = neutral, 0.0 = terrible
        score = 1.0
        if features["is_rainy"]:
            score -= 0.3
        if features["is_cold"]:
            score -= 0.2
        if features["is_hot"]:
            score -= 0.1
        if features["is_windy"]:
            score -= 0.1
        features["weather_score"] = max(0.0, min(1.0, score))

        features["is_good_weather"] = features["weather_score"] >= 0.7

        logger.debug(f"Weather features for {match.id}: {features}")
        return features

    def _get_default_weather(self, match: Match) -> Dict[str, float]:
        """
        Get default weather based on season (Mallorca climate).

        Args:
            match: Match object

        Returns:
            Dictionary with default weather values
        """
        month = match.date.month

        # Mallorca average temperatures and conditions by month
        defaults = {
            1: {"temperature": 14, "precipitation_probability": 0.4, "wind_speed": 15},
            2: {"temperature": 14, "precipitation_probability": 0.35, "wind_speed": 15},
            3: {"temperature": 16, "precipitation_probability": 0.3, "wind_speed": 14},
            4: {"temperature": 18, "precipitation_probability": 0.25, "wind_speed": 13},
            5: {"temperature": 21, "precipitation_probability": 0.2, "wind_speed": 12},
            6: {"temperature": 25, "precipitation_probability": 0.1, "wind_speed": 11},
            7: {"temperature": 28, "precipitation_probability": 0.05, "wind_speed": 11},
            8: {"temperature": 28, "precipitation_probability": 0.1, "wind_speed": 11},
            9: {"temperature": 26, "precipitation_probability": 0.25, "wind_speed": 12},
            10: {"temperature": 22, "precipitation_probability": 0.35, "wind_speed": 13},
            11: {"temperature": 18, "precipitation_probability": 0.4, "wind_speed": 14},
            12: {"temperature": 15, "precipitation_probability": 0.4, "wind_speed": 15},
        }

        return defaults.get(month, {"temperature": 20, "precipitation_probability": 0.2, "wind_speed": 12})

    def extract_transport_features(self, match: Match) -> Dict[str, Any]:
        """
        Extract transport-related features.

        For MVP, returns reasonable defaults.

        Args:
            match: Match object

        Returns:
            Dictionary with transport features:
            - public_transport_available: bool
            - is_rush_hour: bool
            - transport_score: float (0-1, 1=excellent access)
        """
        features = {}

        # Son Moix stadium has good public transport access
        features["public_transport_available"] = True

        # Rush hour impacts (weekday evenings)
        hour = match.date.hour
        is_weekday = match.date.weekday() < 5
        features["is_rush_hour"] = is_weekday and (7 <= hour <= 9 or 17 <= hour <= 20)

        # Transport score
        score = 1.0
        if features["is_rush_hour"]:
            score -= 0.2
        features["transport_score"] = score

        logger.debug(f"Transport features for {match.id}: {features}")
        return features

    def extract_external_events_features(self, match: Match) -> Dict[str, Any]:
        """
        Extract features related to external events (concerts, festivals, etc.).

        For MVP, placeholder.

        Args:
            match: Match object

        Returns:
            Dictionary with external event features:
            - has_competing_event: bool
            - is_vacation_period: bool
        """
        features = {}

        month = match.date.month

        # Vacation periods in Spain
        features["is_summer_vacation"] = month in [7, 8]
        features["is_christmas_vacation"] = month == 12 and match.date.day >= 20
        features["is_easter_vacation"] = month == 4  # Simplified
        features["is_vacation_period"] = (
            features["is_summer_vacation"] or
            features["is_christmas_vacation"] or
            features["is_easter_vacation"]
        )

        # For MVP, assume no competing events
        features["has_competing_event"] = False

        logger.debug(f"External events features for {match.id}: {features}")
        return features

    def extract_all(self, match: Match) -> Dict[str, Any]:
        """
        Extract all external features.

        Args:
            match: Match object

        Returns:
            Dictionary with all external features combined
        """
        features = {}
        features.update(self.extract_weather_features(match))
        features.update(self.extract_transport_features(match))
        features.update(self.extract_external_events_features(match))

        logger.debug(f"All external features for {match.id}: {len(features)} features extracted")
        return features
