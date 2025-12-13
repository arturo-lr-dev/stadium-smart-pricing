"""
Demand Predictor for ticket demand estimation.

Uses ML model for demand prediction with heuristic fallback.
Phase 7 implementation - ML-based demand prediction.
"""

import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from src.domain.models.match import Match
from src.domain.models.zone import Zone

logger = logging.getLogger(__name__)


class DemandPredictor:
    """
    Demand Predictor for estimating ticket demand.

    Uses trained ML model for predictions. Falls back to heuristic-based
    predictions if model is not available.

    The demand score ranges from 0.0 to 1.0, where:
    - 0.0-0.3: Low demand
    - 0.3-0.6: Medium demand
    - 0.6-0.85: High demand
    - 0.85-1.0: Very high demand
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the Demand Predictor.

        Args:
            model_path: Path to trained ML model. If None, uses heuristics.
        """
        self.model = None
        self.model_path = model_path
        self.use_ml = False

        # Try to load ML model
        if model_path and Path(model_path).exists():
            try:
                from src.ml.models.demand_model import DemandModel
                self.model = DemandModel()
                self.model.load(model_path)
                self.use_ml = True
                logger.info(f"DemandPredictor initialized with ML model from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load ML model: {e}. Using heuristic fallback.")
                self.model = None
                self.use_ml = False
        else:
            logger.info("DemandPredictor initialized (heuristic mode - no model provided)")

    def predict_demand(
        self,
        match: Match,
        zone: Zone,
        days_to_match: int,
        current_occupancy: float = 0.0,
    ) -> float:
        """
        Predict demand score for a match and zone.

        Uses ML model if available, otherwise falls back to heuristics.

        Args:
            match: Match object
            zone: Zone object
            days_to_match: Days until the match
            current_occupancy: Current occupancy percentage (0-100)

        Returns:
            Demand score between 0.0 and 1.0
        """
        # Use ML model if available
        if self.use_ml and self.model:
            try:
                demand_score = self.model.predict_demand(match, zone, days_to_match)
                logger.debug(
                    f"ML predicted demand for match {match.id}, zone {zone.id}: "
                    f"{demand_score:.3f}"
                )
                return demand_score
            except Exception as e:
                logger.warning(
                    f"ML prediction failed: {e}. Falling back to heuristics."
                )
                # Fall through to heuristic method

        # Heuristic fallback
        demand_score = self._predict_demand_heuristic(
            match, zone, days_to_match, current_occupancy
        )

        logger.debug(
            f"Heuristic predicted demand for match {match.id}, zone {zone.id}: "
            f"{demand_score:.3f} (days_to_match={days_to_match}, "
            f"occupancy={current_occupancy:.1f}%)"
        )

        return demand_score

    def _predict_demand_heuristic(
        self,
        match: Match,
        zone: Zone,
        days_to_match: int,
        current_occupancy: float = 0.0,
    ) -> float:
        """
        Heuristic-based demand prediction (fallback method).

        Factors considered:
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
        Reload ML model from disk.

        Args:
            model_path: Path to model file. If None, uses self.model_path
        """
        path = model_path or self.model_path

        if not path:
            logger.warning("No model path provided, cannot reload model")
            return

        if not Path(path).exists():
            logger.error(f"Model file not found: {path}")
            return

        try:
            from src.ml.models.demand_model import DemandModel
            self.model = DemandModel()
            self.model.load(path)
            self.use_ml = True
            self.model_path = path
            logger.info(f"ML model reloaded from {path}")
        except Exception as e:
            logger.error(f"Failed to reload ML model: {e}")
            self.model = None
            self.use_ml = False

    def get_model_info(self) -> dict:
        """
        Get information about the current model.

        Returns:
            Dictionary with model information
        """
        if self.use_ml and self.model:
            info = self.model.get_model_info()
            info['predictor_mode'] = 'ml'
            info['model_path'] = self.model_path
        else:
            info = {
                'predictor_mode': 'heuristic',
                'model_path': None,
                'is_trained': False,
            }

        return info
