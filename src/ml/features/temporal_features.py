"""
Temporal Feature Extractor for Demand Prediction.

Extracts time-based features from match dates.
"""

import logging
from typing import Dict, Any
from datetime import datetime
import calendar

logger = logging.getLogger(__name__)


class TemporalFeatureExtractor:
    """
    Extracts temporal features from match dates for ML model input.

    Features include:
    - Day of week
    - Weekend/weekday flags
    - Holiday flags
    - Month and season information
    - Hour of day
    """

    # Spanish national holidays (simplified - doesn't include regional ones)
    NATIONAL_HOLIDAYS = [
        (1, 1),   # New Year
        (1, 6),   # Epiphany
        (5, 1),   # Labor Day
        (8, 15),  # Assumption of Mary
        (10, 12), # National Day
        (11, 1),  # All Saints
        (12, 6),  # Constitution Day
        (12, 8),  # Immaculate Conception
        (12, 25), # Christmas
    ]

    def __init__(self):
        """Initialize the temporal feature extractor."""
        logger.info("TemporalFeatureExtractor initialized")

    def extract_date_features(self, match_date: datetime) -> Dict[str, Any]:
        """
        Extract features from match date and time.

        Args:
            match_date: Match datetime

        Returns:
            Dictionary with date/time features:
            - day_of_week: int (0=Monday, 6=Sunday)
            - is_weekend: bool
            - is_friday: bool
            - is_saturday: bool
            - is_sunday: bool
            - is_weekday: bool
            - is_holiday: bool
            - hour: int (0-23)
            - is_evening: bool (18-22)
            - is_afternoon: bool (14-18)
            - is_night: bool (20-23)
        """
        features = {}

        # Day of week
        day_of_week = match_date.weekday()  # 0=Monday, 6=Sunday
        features["day_of_week"] = day_of_week
        features["is_monday"] = day_of_week == 0
        features["is_tuesday"] = day_of_week == 1
        features["is_wednesday"] = day_of_week == 2
        features["is_thursday"] = day_of_week == 3
        features["is_friday"] = day_of_week == 4
        features["is_saturday"] = day_of_week == 5
        features["is_sunday"] = day_of_week == 6

        # Weekend/weekday
        features["is_weekend"] = day_of_week >= 5  # Saturday or Sunday
        features["is_weekday"] = day_of_week < 5

        # Holiday
        features["is_holiday"] = self._is_holiday(match_date)

        # Hour of day
        hour = match_date.hour
        features["hour"] = hour
        features["is_morning"] = 6 <= hour < 14
        features["is_afternoon"] = 14 <= hour < 18
        features["is_evening"] = 18 <= hour < 22
        features["is_night"] = hour >= 20 or hour < 6

        # Prime time for football (evening/night on weekend)
        features["is_prime_time"] = features["is_weekend"] and features["is_evening"]

        logger.debug(f"Date features for {match_date}: {features}")
        return features

    def extract_season_features(self, match_date: datetime) -> Dict[str, Any]:
        """
        Extract season-related features.

        Args:
            match_date: Match datetime

        Returns:
            Dictionary with season features:
            - month: int (1-12)
            - season: str (e.g., "2023/2024")
            - is_season_start: bool (Aug-Oct)
            - is_season_mid: bool (Nov-Feb)
            - is_season_end: bool (Mar-May)
            - matchday_estimate: int (rough estimate based on date)
        """
        features = {}

        month = match_date.month
        features["month"] = month

        # Season (football season runs Aug-May)
        year = match_date.year
        if month >= 8:
            season = f"{year}/{year+1}"
        else:
            season = f"{year-1}/{year}"
        features["season"] = season

        # Season periods
        features["is_season_start"] = month in [8, 9, 10]
        features["is_season_mid"] = month in [11, 12, 1, 2]
        features["is_season_end"] = month in [3, 4, 5]
        features["is_summer"] = month in [6, 7]  # Pre-season/friendly period

        # Rough matchday estimate (LaLiga has ~38 matchdays)
        # Aug=1, Sept=4, Oct=8, Nov=12, Dec=16, Jan=19, Feb=23, Mar=27, Apr=32, May=36
        matchday_map = {
            8: 2, 9: 5, 10: 9, 11: 13, 12: 17,
            1: 20, 2: 24, 3: 28, 4: 33, 5: 37
        }
        features["matchday_estimate"] = matchday_map.get(month, 20)

        # Month one-hot encoding
        for m in range(1, 13):
            features[f"month_{m}"] = month == m

        logger.debug(f"Season features for {match_date}: season={season}, matchday_est={features['matchday_estimate']}")
        return features

    def _is_holiday(self, date: datetime) -> bool:
        """
        Check if a date is a Spanish national holiday.

        Args:
            date: Date to check

        Returns:
            True if it's a holiday
        """
        date_tuple = (date.month, date.day)
        is_holiday = date_tuple in self.NATIONAL_HOLIDAYS

        # Also check for Easter-related holidays (simplified - using fixed dates)
        # In reality, these change each year
        if date.month == 4 and date.day in [6, 7]:  # Good Friday, Easter
            is_holiday = True

        return is_holiday

    def extract_all(self, match_date: datetime) -> Dict[str, Any]:
        """
        Extract all temporal features.

        Args:
            match_date: Match datetime

        Returns:
            Dictionary with all temporal features combined
        """
        features = {}
        features.update(self.extract_date_features(match_date))
        features.update(self.extract_season_features(match_date))

        logger.debug(f"All temporal features for {match_date}: {len(features)} features extracted")
        return features
