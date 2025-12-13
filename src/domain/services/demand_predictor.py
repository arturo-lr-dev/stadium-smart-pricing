"""
Demand Predictor for ticket demand estimation.

This module contains a basic DemandPredictor that uses heuristics to estimate demand.
A full ML-based predictor will be implemented in Phase 7.
"""

import logging
from datetime import datetime
from typing import Optional

from src.domain.models.match import Match
from src.domain.models.zone import Zone

logger = logging.getLogger(__name__)


class DemandPredictor:
    """
    Demand Predictor for estimating ticket demand.

    This is a basic heuristic-based predictor. A full ML-based predictor
    will be implemented in Phase 7 (ML - Demand Prediction).

    The demand score ranges from 0.0 to 1.0, where:
    - 0.0-0.3: Low demand
    - 0.3-0.6: Medium demand
    - 0.6-0.85: High demand
    - 0.85-1.0: Very high demand
    """

    def __init__(self):
        """Initialize the Demand Predictor."""
        logger.info("DemandPredictor initialized (heuristic mode)")

    def predict_demand(
        self,
        match: Match,
        zone: Zone,
        days_to_match: int,
        current_occupancy: float = 0.0,
    ) -> float:
        """
        Predict demand score for a match and zone.

        This is a simplified heuristic-based prediction. Factors considered:
        - Match importance (competition, derby, team positions)
        - Time until match
        - Zone category
        - Current occupancy

        Args:
            match: Match object
            zone: Zone object
            days_to_match: Days until the match
            current_occupancy: Current occupancy percentage (0-100)

        Returns:
            Demand score between 0.0 and 1.0
        """
        # Start with base demand
        demand_score = 0.5

        # Factor 1: Competition importance
        competition_boost = self._get_competition_boost(match.competition)
        demand_score += competition_boost

        # Factor 2: Derby bonus
        if match.is_derby:
            demand_score += 0.15
            logger.debug(f"Derby match, adding 0.15 to demand score")

        # Factor 3: Team positions (if available)
        if match.away_position:
            if match.away_position <= 3:
                demand_score += 0.15  # Top 3 team
            elif match.away_position <= 6:
                demand_score += 0.10  # Top 6 team
            elif match.away_position >= 18:
                demand_score -= 0.05  # Bottom team

        # Factor 4: Zone category
        zone_boost = self._get_zone_category_boost(zone.category)
        demand_score += zone_boost

        # Factor 5: Holiday/Weekend
        if match.is_holiday:
            demand_score += 0.05

        # Factor 6: Time urgency (closer to match = higher demand)
        time_boost = self._get_time_urgency_boost(days_to_match)
        demand_score += time_boost

        # Factor 7: Current occupancy influences future demand
        occupancy_boost = self._get_occupancy_boost(current_occupancy)
        demand_score += occupancy_boost

        # Clamp to valid range [0.0, 1.0]
        demand_score = max(0.0, min(1.0, demand_score))

        logger.debug(
            f"Predicted demand for match {match.id}, zone {zone.id}: {demand_score:.3f} "
            f"(days_to_match={days_to_match}, occupancy={current_occupancy:.1f}%)"
        )

        return demand_score

    def _get_competition_boost(self, competition: str) -> float:
        """
        Get demand boost based on competition type.

        Args:
            competition: Competition name

        Returns:
            Boost value
        """
        competition_lower = competition.lower()

        boosts = {
            "champions_league": 0.25,
            "europa_league": 0.15,
            "copa_del_rey": 0.12,
            "la_liga": 0.08,
            "super_cup": 0.20,
            "friendly": -0.15,
        }

        for comp_key, boost in boosts.items():
            if comp_key in competition_lower:
                return boost

        return 0.0  # Default for unknown competitions

    def _get_zone_category_boost(self, category: str) -> float:
        """
        Get demand boost based on zone category.

        VIP and Premium zones tend to have different demand patterns.

        Args:
            category: Zone category

        Returns:
            Boost value
        """
        category_lower = category.lower()

        boosts = {
            "vip": 0.10,  # VIP zones have consistent demand
            "premium": 0.05,
            "standard": 0.0,
            "reduced": -0.05,  # Reduced price zones
            "family": 0.02,
            "student": -0.03,
        }

        return boosts.get(category_lower, 0.0)

    def _get_time_urgency_boost(self, days_to_match: int) -> float:
        """
        Get demand boost based on time until match.

        Demand typically increases as match approaches.

        Args:
            days_to_match: Days until the match

        Returns:
            Boost value
        """
        if days_to_match < 0:
            return 0.0  # Match has passed

        if days_to_match <= 3:
            return 0.15  # Very close to match
        elif days_to_match <= 7:
            return 0.10  # Within a week
        elif days_to_match <= 14:
            return 0.05  # Within two weeks
        elif days_to_match <= 30:
            return 0.0  # Normal
        else:
            return -0.05  # Very far away

    def _get_occupancy_boost(self, occupancy_percent: float) -> float:
        """
        Get demand boost based on current occupancy.

        High occupancy indicates high demand (scarcity effect).
        Low occupancy might indicate low interest.

        Args:
            occupancy_percent: Current occupancy percentage (0-100)

        Returns:
            Boost value
        """
        if occupancy_percent >= 80:
            return 0.15  # High occupancy = high demand
        elif occupancy_percent >= 60:
            return 0.10
        elif occupancy_percent >= 40:
            return 0.05
        elif occupancy_percent >= 20:
            return 0.0
        else:
            return -0.05  # Very low occupancy

    def reload_model(self, model_path: Optional[str] = None) -> None:
        """
        Reload ML model (placeholder for Phase 7).

        Args:
            model_path: Path to model file (not used in heuristic mode)
        """
        logger.info("reload_model called (no-op in heuristic mode)")
        # This will be implemented in Phase 7 when we add ML models
        pass
