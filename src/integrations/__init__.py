"""
External integrations package.

This package contains integrations with external APIs and services:
- Football Data API: Team statistics, standings, match details
- Weather API: Weather forecasts and historical data
- Google Analytics: User behavior metrics and conversion tracking
- Ticketing System: Inventory management and ticket reservations
"""

from src.integrations.football_data import FootballDataAPI
from src.integrations.weather_api import WeatherAPI
from src.integrations.analytics import GoogleAnalyticsIntegration
from src.integrations.ticketing_system import (
    TicketingSystemAPI,
    ReservationStatus,
)


__all__ = [
    "FootballDataAPI",
    "WeatherAPI",
    "GoogleAnalyticsIntegration",
    "TicketingSystemAPI",
    "ReservationStatus",
]
