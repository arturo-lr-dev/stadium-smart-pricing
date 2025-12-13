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
        """Initialize the match feature extractor with configuration."""
        from src.core.config import get_settings
        self.settings = get_settings()
        self.pricing_rules = self.settings.get_yaml_config("pricing_rules")
        self.competitions_config = self.settings.get_yaml_config("competitions")
        logger.info("MatchFeatureExtractor initialized with config")

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

        # Calculate match importance based on competition using config
        # Use "competition_multipliers" from pricing_rules.yaml
        comp_multipliers = self.pricing_rules.get("competition_multipliers", {})
        
        # Map CompetitionType enum to config keys
        # This is a heuristic mapping based on known keys in config
        comp_key_map = {
            CompetitionType.CHAMPIONS_LEAGUE: "UEFA_Champions_League",
            CompetitionType.LA_LIGA: "LaLiga",
            CompetitionType.COPA_DEL_REY: "Copa_del_Rey",
            CompetitionType.EUROPA_LEAGUE: "UEFA_Europa_League",
            CompetitionType.SUPER_CUP: "Supercopa",
            CompetitionType.FRIENDLY: "Amistoso",
        }
        
        config_key = comp_key_map.get(match.competition)
        base_multiplier = 1.0
        
        if config_key:
            # Handle nested dicts (e.g. Copa_del_Rey) by taking a default or average if needed
            # For simplicity, if it's a dict, we take a representative value or 1.0
            val = comp_multipliers.get(config_key)
            if isinstance(val, dict):
                # For Copa, take a middle ground or 'octavos' as representative baseline if available
                base_multiplier = val.get("octavos", 1.2)
            elif isinstance(val, (int, float)):
                base_multiplier = float(val)

        # Normalize importance: arbitrary max multiplier around 3.0 -> 1.0
        # Multipliers range from ~0.6 (Friendly) to 3.0 (UCL)
        features["match_importance"] = min(1.0, base_multiplier / 3.0)

        # Boost importance if it's a derby
        if match.is_derby:
             # Use derby_multiplier if available
            derby_mult = self.pricing_rules.get("rival_multipliers", {}).get("derby_multiplier", 1.2) 
            # Slightly adjust importance based on derby multiplier relative to normal
            features["match_importance"] = min(1.0, features["match_importance"] * (derby_mult / 1.8)) # 1.8 is approx avg multiplier

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
        
        # Get feature engineering config
        fe_config = self.pricing_rules.get("feature_engineering", {})
        rival_config = fe_config.get("rival_position", {})

        top_threshold = rival_config.get("top_team_threshold", 4)
        bottom_threshold = rival_config.get("bottom_team_threshold", 18)
        norm_factor = self.settings.stadium_capacity # Not correct, using league size
        # Hardcoding league size as 20 for standard logic if not in config, or add to config
        # For now assume 20 as in original
        LEAGUE_SIZE = 20.0 

        # Rival position features
        if match.away_position is not None:
            features["rival_position"] = match.away_position
            # Normalize: lower position (1) is better, normalize to 0-1 range
            features["rival_position_normalized"] = (LEAGUE_SIZE - match.away_position) / LEAGUE_SIZE
            features["rival_is_top_team"] = match.away_position <= top_threshold
            features["rival_is_bottom_team"] = match.away_position >= bottom_threshold
        else:
            # Unknown position - use neutral values
            features["rival_position"] = 10
            features["rival_position_normalized"] = 0.5
            features["rival_is_top_team"] = False
            features["rival_is_bottom_team"] = False

        # Big clubs: check rival multipliers for high values
        rival_multipliers = self.pricing_rules.get("rival_multipliers", {})
        
        # Identify if rival is a "big club" based on having a specific high multiplier
        # Any team with multiplier >= 1.6 (Real Sociedad level) can be considered big/important
        is_big_club = False
        if match.away_team in rival_multipliers:
            mult = rival_multipliers[match.away_team]
            if isinstance(mult, (int, float)) and mult >= 1.6:
                is_big_club = True
                
        features["rival_is_big_club"] = is_big_club

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
        
        # Get feature engineering config
        fe_config = self.pricing_rules.get("feature_engineering", {})
        home_config = fe_config.get("home_position", {})
        
        top_threshold = home_config.get("top_team_threshold", 6)
        relegation_threshold = home_config.get("relegation_threshold", 15)
        europe_min = home_config.get("europe_min", 4)
        europe_max = home_config.get("europe_max", 7)
        LEAGUE_SIZE = 20.0

        if match.home_position is not None:
            features["home_position"] = match.home_position
            features["home_position_normalized"] = (LEAGUE_SIZE - match.home_position) / LEAGUE_SIZE
            features["home_is_top_team"] = match.home_position <= top_threshold
            features["home_fighting_relegation"] = match.home_position >= relegation_threshold
            features["home_fighting_europe"] = europe_min <= match.home_position <= europe_max
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
