"""
Match Feature Extractor for Demand Prediction.

Extracts features related to match characteristics, competition, and teams.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.domain.models.match import Match, CompetitionType

logger = logging.getLogger(__name__)


class MatchFeatureExtractor:
    """
    Extracts features from Match objects for ML model input.

    Features include:
    - Competition characteristics
    - Rival team importance
    - Home team performance
    - Special match flags (derby, etc.)
    """

    def __init__(self):
        """Initialize the match feature extractor."""
        logger.info("MatchFeatureExtractor initialized")

    def extract_competition_features(self, match: Match) -> Dict[str, Any]:
        """
        Extract features related to competition type and importance.

        Args:
            match: Match object

        Returns:
            Dictionary with competition features:
            - competition_laliga: bool
            - competition_copa: bool
            - competition_champions: bool
            - competition_friendly: bool
            - competition_europa: bool
            - competition_playoff: bool
            - is_derby: bool
            - match_importance: float (0-1, higher for more important competitions)
        """
        features = {
            "competition_laliga": match.competition == CompetitionType.LA_LIGA,
            "competition_copa": match.competition == CompetitionType.COPA_DEL_REY,
            "competition_champions": match.competition == CompetitionType.CHAMPIONS_LEAGUE,
            "competition_friendly": match.competition == CompetitionType.FRIENDLY,
            "competition_europa": match.competition == CompetitionType.EUROPA_LEAGUE,
            "competition_supercup": match.competition == CompetitionType.SUPER_CUP,
            "is_derby": match.is_derby,
        }

        # Calculate match importance based on competition
        importance_map = {
            CompetitionType.CHAMPIONS_LEAGUE: 1.0,
            CompetitionType.LA_LIGA: 0.9,
            CompetitionType.COPA_DEL_REY: 0.7,
            CompetitionType.EUROPA_LEAGUE: 0.8,
            CompetitionType.SUPER_CUP: 0.85,
            CompetitionType.FRIENDLY: 0.3,
        }
        features["match_importance"] = importance_map.get(match.competition, 0.5)

        # Boost importance if it's a derby
        if match.is_derby:
            features["match_importance"] = min(1.0, features["match_importance"] * 1.2)

        logger.debug(f"Competition features for {match.id}: {features}")
        return features

    def extract_rival_features(self, match: Match) -> Dict[str, Any]:
        """
        Extract features related to rival team characteristics.

        Args:
            match: Match object

        Returns:
            Dictionary with rival features:
            - rival_position: int (league position, normalized 0-1, lower is better)
            - rival_is_top_team: bool (top 4)
            - rival_is_bottom_team: bool (bottom 3)
            - rival_is_big_club: bool (traditional big clubs)
        """
        features = {}

        # Rival position features
        if match.away_position is not None:
            features["rival_position"] = match.away_position
            # Normalize: lower position (1) is better, normalize to 0-1 range
            features["rival_position_normalized"] = (20 - match.away_position) / 20.0
            features["rival_is_top_team"] = match.away_position <= 4
            features["rival_is_bottom_team"] = match.away_position >= 18
        else:
            # Unknown position - use neutral values
            features["rival_position"] = 10
            features["rival_position_normalized"] = 0.5
            features["rival_is_top_team"] = False
            features["rival_is_bottom_team"] = False

        # Big clubs that attract more fans (Spanish league examples)
        big_clubs = {
            "Real Madrid", "FC Barcelona", "Atlético Madrid",
            "Sevilla FC", "Athletic Club", "Valencia CF", "Real Betis"
        }
        features["rival_is_big_club"] = match.away_team in big_clubs

        logger.debug(f"Rival features for {match.id} vs {match.away_team}: {features}")
        return features

    def extract_home_team_features(self, match: Match) -> Dict[str, Any]:
        """
        Extract features related to home team performance.

        Args:
            match: Match object

        Returns:
            Dictionary with home team features:
            - home_position: int (league position)
            - home_is_top_team: bool
            - home_fighting_relegation: bool
            - home_fighting_europe: bool
        """
        features = {}

        if match.home_position is not None:
            features["home_position"] = match.home_position
            features["home_position_normalized"] = (20 - match.home_position) / 20.0
            features["home_is_top_team"] = match.home_position <= 6
            features["home_fighting_relegation"] = match.home_position >= 15
            features["home_fighting_europe"] = 4 <= match.home_position <= 7
        else:
            # Unknown position - use neutral values
            features["home_position"] = 10
            features["home_position_normalized"] = 0.5
            features["home_is_top_team"] = False
            features["home_fighting_relegation"] = False
            features["home_fighting_europe"] = False

        logger.debug(f"Home team features for {match.id}: {features}")
        return features

    def extract_all(self, match: Match) -> Dict[str, Any]:
        """
        Extract all match-related features.

        Args:
            match: Match object

        Returns:
            Dictionary with all match features combined
        """
        features = {}
        features.update(self.extract_competition_features(match))
        features.update(self.extract_rival_features(match))
        features.update(self.extract_home_team_features(match))

        logger.debug(f"All match features for {match.id}: {len(features)} features extracted")
        return features
