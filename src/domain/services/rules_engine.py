"""
Rules Engine for dynamic pricing.

This module contains the RulesEngine class that manages all pricing rules,
multipliers, and constraints from YAML configuration files.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from src.domain.models.match import Match

logger = logging.getLogger(__name__)

# Import here to avoid circular dependency
try:
    from src.integrations.football_data import FootballDataAPI
except ImportError:
    FootballDataAPI = None


class RulesEngine:
    """
    Rules Engine for calculating pricing multipliers.

    This class loads pricing rules from YAML configuration and provides
    methods to calculate various pricing factors based on match characteristics.
    """

    def __init__(
        self,
        config_path: str = "config/pricing_rules.yaml",
        football_api: Optional["FootballDataAPI"] = None,
        db_session: Optional[Any] = None,
    ):
        """
        Initialize the Rules Engine.

        Args:
            config_path: Path to the pricing rules YAML file
            football_api: Optional Football Data API client for team performance data
            db_session: Optional database session for team lookups
        """
        self.config_path = Path(config_path)
        self.rules: Dict[str, Any] = {}
        self.football_api = football_api
        self.db_session = db_session
        self._load_rules()
        logger.info(f"RulesEngine initialized with config from {config_path}")

    def _load_rules(self) -> None:
        """
        Load pricing rules from YAML file.

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.rules = yaml.safe_load(f)

            self._validate_rules()
            logger.info(f"Successfully loaded {len(self.rules)} rule sections")

        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading rules: {e}")
            raise

    def _validate_rules(self) -> None:
        """
        Validate that all required rule sections exist.

        Raises:
            ValueError: If required sections are missing
        """
        required_sections = [
            "competition_multipliers",
            "rival_multipliers",
            "time_decay_factors",
            "inventory_pressure_factors",
            "special_conditions",
            "constraints",
        ]

        missing = [section for section in required_sections if section not in self.rules]

        if missing:
            raise ValueError(f"Missing required rule sections: {missing}")

        logger.debug("All required rule sections present")

    def reload_rules(self) -> None:
        """
        Reload rules from configuration file.

        This allows hot-reloading of configuration without restarting the service.
        """
        logger.info("Reloading pricing rules...")
        self._load_rules()
        logger.info("Rules reloaded successfully")

    def get_competition_multiplier(
        self, competition: str, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Get pricing multiplier for a competition type.

        Args:
            competition: Competition name (e.g., "LaLiga", "Copa_del_Rey")
            context: Additional context (e.g., stage, rival_position)

        Returns:
            Competition multiplier (default: 1.0)
        """
        multipliers = self.rules.get("competition_multipliers", {})

        # Check for LaLiga special cases FIRST (before simple value)
        if competition == "LaLiga" and context:
            away_position = context.get("away_position")
            if away_position:
                if away_position <= 3:
                    multiplier = multipliers.get("LaLiga_vs_top3", 2.5)
                    logger.debug(f"LaLiga vs top 3 multiplier: {multiplier}")
                    return float(multiplier)
                elif away_position <= 10:
                    multiplier = multipliers.get("LaLiga_vs_top10", 1.5)
                    logger.debug(f"LaLiga vs top 10 multiplier: {multiplier}")
                    return float(multiplier)
                elif away_position >= 18:
                    multiplier = multipliers.get("LaLiga_vs_bottom3", 0.8)
                    logger.debug(f"LaLiga vs bottom 3 multiplier: {multiplier}")
                    return float(multiplier)

        # Try exact match
        if competition in multipliers:
            value = multipliers[competition]

            # Handle nested structures (like Copa del Rey stages)
            if isinstance(value, dict) and context:
                stage = context.get("stage", "")
                if stage and stage in value:
                    multiplier = value[stage]
                    logger.debug(
                        f"Competition multiplier for {competition} ({stage}): {multiplier}"
                    )
                    return float(multiplier)

                # Return first value if stage not found
                if value:
                    multiplier = list(value.values())[0]
                    logger.debug(
                        f"Competition multiplier for {competition} (default stage): {multiplier}"
                    )
                    return float(multiplier)

            # Simple value
            if isinstance(value, (int, float)):
                logger.debug(f"Competition multiplier for {competition}: {value}")
                return float(value)

        # Default fallback
        logger.debug(f"Using default competition multiplier for {competition}: 1.0")
        return 1.0

    def get_rival_multiplier(
        self,
        rival_team: str,
        is_relegation_zone: bool = False,
        competition: str = "LaLiga",
        season: Optional[str] = None
    ) -> float:
        """
        Get pricing multiplier for a rival team.

        This method first checks if the Football Data API is available to get
        the rival's current position in the standings. If available, it applies
        dynamic multipliers based on position. Otherwise, it falls back to
        static multipliers from the config.

        Args:
            rival_team: Name of the rival team
            is_relegation_zone: Whether rival is in relegation zone (manual override)
            competition: Competition name (e.g., "LaLiga")
            season: Season year (e.g., "2024"). If None, uses current year.

        Returns:
            Rival multiplier (default: 1.0)
        """
        multipliers = self.rules.get("rival_multipliers", {})

        # Check for specific team multiplier first (highest priority)
        if rival_team in multipliers:
            multiplier = float(multipliers[rival_team])
            logger.debug(f"Static rival multiplier for {rival_team}: {multiplier}")
            return multiplier

        # Try to get dynamic multiplier based on current standings from API
        if self.football_api and competition == "LaLiga":
            try:
                rival_position = self._get_team_position(rival_team, competition, season)

                if rival_position:
                    logger.debug(f"Rival {rival_team} is at position {rival_position}")

                    # Apply dynamic multipliers based on position
                    if rival_position <= 3:
                        # Top 3 teams (likely Real Madrid, Barcelona, Atlético)
                        multiplier = 2.5
                        logger.debug(f"Top 3 rival multiplier for {rival_team}: {multiplier}")
                        return multiplier
                    elif rival_position <= 10:
                        # Top 10 teams (strong mid-table teams)
                        multiplier = 1.5
                        logger.debug(f"Top 10 rival multiplier for {rival_team}: {multiplier}")
                        return multiplier
                    elif rival_position >= 18:
                        # Bottom 3 teams (relegation zone)
                        multiplier = float(multipliers.get("relegation_zone_penalty", 0.85))
                        logger.debug(f"Bottom 3 rival multiplier for {rival_team}: {multiplier}")
                        return multiplier
                    else:
                        # Mid-table teams (11-17)
                        multiplier = 1.1
                        logger.debug(f"Mid-table rival multiplier for {rival_team}: {multiplier}")
                        return multiplier

            except Exception as e:
                logger.warning(
                    f"Failed to get dynamic rival multiplier from API for {rival_team}: {e}. "
                    "Falling back to manual check."
                )

        # Apply relegation zone penalty if manually specified
        if is_relegation_zone:
            multiplier = float(multipliers.get("relegation_zone_penalty", 0.85))
            logger.debug(
                f"Manual relegation zone penalty for {rival_team}: {multiplier}"
            )
            return multiplier

        # Default
        logger.debug(f"Using default rival multiplier for {rival_team}: 1.0")
        return 1.0

    def get_time_decay_factor(self, days_to_match: int) -> float:
        """
        Get time decay factor based on days until match.

        Args:
            days_to_match: Number of days until the match

        Returns:
            Time decay multiplier
        """
        factors = self.rules.get("time_decay_factors", [])

        # Iterate through factors to find matching range
        for factor in factors:
            min_days = factor.get("min_days", 0)
            max_days = factor.get("max_days", 999)

            if min_days <= days_to_match <= max_days:
                multiplier = float(factor.get("multiplier", 1.0))
                description = factor.get("description", "")
                logger.debug(
                    f"Time decay factor for {days_to_match} days: {multiplier} ({description})"
                )
                return multiplier

        # Default fallback
        logger.warning(
            f"No time decay factor found for {days_to_match} days, using 1.0"
        )
        return 1.0

    def get_inventory_pressure_factor(self, occupancy_percent: float) -> float:
        """
        Get inventory pressure factor based on zone occupancy.

        Args:
            occupancy_percent: Occupancy percentage (0.0 to 1.0)

        Returns:
            Inventory pressure multiplier
        """
        factors = self.rules.get("inventory_pressure_factors", [])

        # Ensure occupancy is in valid range
        occupancy_percent = max(0.0, min(1.0, occupancy_percent))

        # Find matching occupancy range
        for factor in factors:
            min_occ = factor.get("min_occupancy", 0.0)
            max_occ = factor.get("max_occupancy", 1.0)

            if min_occ <= occupancy_percent <= max_occ:
                multiplier = float(factor.get("multiplier", 1.0))
                description = factor.get("description", "")
                logger.debug(
                    f"Inventory pressure factor for {occupancy_percent:.1%} occupancy: "
                    f"{multiplier} ({description})"
                )
                return multiplier

        # Default fallback
        logger.warning(
            f"No inventory pressure factor found for {occupancy_percent:.1%} occupancy, using 1.0"
        )
        return 1.0

    def get_special_multipliers(
        self, match: Match, current_datetime: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Get all applicable special condition multipliers for a match.

        Args:
            match: Match object
            current_datetime: Current datetime (defaults to now)

        Returns:
            Dictionary of special multiplier names and values
        """
        if current_datetime is None:
            current_datetime = datetime.now()

        special_conditions = self.rules.get("special_conditions", {})
        multipliers = {}

        # Holiday multiplier
        if match.is_holiday:
            holiday_multiplier = float(
                special_conditions.get("holiday", {}).get("national_holiday", 1.20)
            )
            multipliers["holiday"] = holiday_multiplier
            logger.debug(f"Holiday multiplier applied: {holiday_multiplier}")

        # Weekend multiplier
        weekday_name = match.date.strftime("%A").lower()
        weekday_multipliers = special_conditions.get("weekday", {})

        if weekday_name in weekday_multipliers:
            weekday_multiplier = float(weekday_multipliers[weekday_name])
            multipliers["weekday"] = weekday_multiplier
            logger.debug(
                f"Weekday multiplier for {weekday_name}: {weekday_multiplier}"
            )

        # Derby multiplier
        if match.is_derby:
            derby_multiplier = float(special_conditions.get("derby", 2.0))
            multipliers["derby"] = derby_multiplier
            logger.debug(f"Derby multiplier applied: {derby_multiplier}")

        # Match time multiplier
        match_hour = match.date.hour
        match_time_multipliers = special_conditions.get("match_time", {})

        if match_hour < 14:
            time_multiplier = float(match_time_multipliers.get("morning", 0.90))
            multipliers["match_time"] = time_multiplier
        elif match_hour < 18:
            time_multiplier = float(match_time_multipliers.get("afternoon", 1.05))
            multipliers["match_time"] = time_multiplier
        elif match_hour < 21:
            time_multiplier = float(match_time_multipliers.get("evening", 1.15))
            multipliers["match_time"] = time_multiplier
        else:
            time_multiplier = float(match_time_multipliers.get("night", 1.10))
            multipliers["match_time"] = time_multiplier

        # Team performance multiplier (based on recent form)
        team_performance = self._get_team_performance_multiplier(match.home_team)
        if team_performance != 1.0:
            multipliers["team_performance"] = team_performance

        logger.debug(
            f"Special multipliers for match {match.id}: {multipliers}"
        )
        return multipliers

    def get_weather_factor(
        self, weather_condition: str = "good", context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Get weather factor multiplier.

        Args:
            weather_condition: Weather condition (excellent, good, fair, poor)
            context: Additional weather context

        Returns:
            Weather multiplier
        """
        weather_multipliers = self.rules.get("special_conditions", {}).get("weather", {})

        multiplier = float(weather_multipliers.get(weather_condition, 1.0))
        logger.debug(f"Weather factor for '{weather_condition}': {multiplier}")
        return multiplier

    def _get_team_performance_multiplier(self, team_name: str) -> float:
        """
        Calculate team performance multiplier based on recent form.

        Args:
            team_name: Name of the home team

        Returns:
            Performance multiplier based on recent results
        """
        # If no football API available, return neutral multiplier
        if not self.football_api:
            logger.debug("No Football API available, using neutral team performance")
            return 1.0

        try:
            # Try to get team ID from team name (simplified mapping)
            # In production, you'd have a proper mapping table
            team_id = self._get_team_id_from_name(team_name)
            if not team_id:
                logger.debug(f"Team ID not found for {team_name}, using neutral performance")
                return 1.0

            # Get recent form (last 5 matches)
            recent_matches = self.football_api.get_team_recent_form(team_id, matches=5)

            if not recent_matches:
                logger.debug(f"No recent matches found for {team_name}, using neutral performance")
                return 1.0

            # Calculate wins, draws, losses
            wins = 0
            draws = 0
            losses = 0

            for match in recent_matches:
                home_team = match.get("homeTeam", {})
                away_team = match.get("awayTeam", {})
                score = match.get("score", {}).get("fullTime", {})
                home_score = score.get("home")
                away_score = score.get("away")

                if home_score is None or away_score is None:
                    continue

                # Determine if our team was home or away
                is_home = home_team.get("id") == team_id

                if is_home:
                    if home_score > away_score:
                        wins += 1
                    elif home_score == away_score:
                        draws += 1
                    else:
                        losses += 1
                else:
                    if away_score > home_score:
                        wins += 1
                    elif away_score == home_score:
                        draws += 1
                    else:
                        losses += 1

            total_matches = wins + draws + losses
            if total_matches == 0:
                return 1.0

            # Calculate win percentage
            win_percentage = wins / total_matches

            # Get performance category and multiplier
            performance_multipliers = self.rules.get("special_conditions", {}).get("team_performance", {})

            if win_percentage >= 0.8:  # 4-5 wins
                multiplier = float(performance_multipliers.get("excellent", 1.15))
                category = "excellent"
            elif win_percentage >= 0.6:  # 3 wins
                multiplier = float(performance_multipliers.get("very_good", 1.08))
                category = "very_good"
            elif win_percentage >= 0.4:  # 2 wins
                multiplier = float(performance_multipliers.get("good", 1.02))
                category = "good"
            elif win_percentage >= 0.2:  # 1 win
                multiplier = float(performance_multipliers.get("poor", 0.95))
                category = "poor"
            elif wins == 0:  # No wins
                multiplier = float(performance_multipliers.get("very_poor", 0.90))
                category = "very_poor"
            else:
                multiplier = float(performance_multipliers.get("average", 1.0))
                category = "average"

            logger.info(
                f"Team performance for {team_name}: {category} "
                f"({wins}W-{draws}D-{losses}L, {win_percentage:.1%}) = {multiplier}"
            )

            return multiplier

        except Exception as e:
            logger.warning(
                f"Failed to calculate team performance for {team_name}: {e}. Using neutral multiplier."
            )
            return 1.0

    def _get_team_position(
        self,
        team_name: str,
        competition: str = "LaLiga",
        season: Optional[str] = None
    ) -> Optional[int]:
        """
        Get team's current position in the standings.

        Args:
            team_name: Name of the team
            competition: Competition name (e.g., "LaLiga")
            season: Season year. If None, uses current year.

        Returns:
            Team position (1-20 for LaLiga) or None if not found
        """
        if not self.football_api:
            logger.debug("No Football API available for position lookup")
            return None

        try:
            # Map competition name to API league code
            competition_mapping = {
                "LaLiga": "PD",  # Primera División
                "Copa_del_Rey": "CLI",
                "UEFA_Champions_League": "CL",
                "UEFA_Europa_League": "EL",
            }

            league_code = competition_mapping.get(competition)
            if not league_code:
                logger.debug(f"No league code mapping for competition: {competition}")
                return None

            # Use current year if season not specified
            if not season:
                from datetime import datetime
                season = str(datetime.now().year)

            # Get standings from API
            standings_data = self.football_api.get_team_standings(league_code, season)

            # Extract standings table
            standings = standings_data.get("standings", [])
            if not standings:
                logger.warning(f"No standings data found for {competition} {season}")
                return None

            # The API returns standings in a nested structure
            # standings[0] is usually the main table
            main_table = standings[0] if isinstance(standings, list) else standings
            table = main_table.get("table", [])

            # Find team in the table
            for entry in table:
                team = entry.get("team", {})
                if team.get("name") == team_name:
                    position = entry.get("position")
                    logger.info(
                        f"Found {team_name} at position {position} in {competition} {season}"
                    )
                    return position

            logger.warning(f"Team {team_name} not found in {competition} standings")
            return None

        except Exception as e:
            logger.warning(
                f"Failed to get team position for {team_name} in {competition}: {e}"
            )
            return None

    def _get_team_id_from_name(self, team_name: str) -> Optional[str]:
        """
        Get team ID from team name using database.

        Args:
            team_name: Team name

        Returns:
            Team ID if found, None otherwise
        """
        # Try to get team ID from database
        if self.db_session:
            try:
                from src.domain.models.db_models import TeamDB

                team = self.db_session.query(TeamDB).filter(
                    TeamDB.name == team_name
                ).first()

                if team and team.football_data_api_id:
                    return team.football_data_api_id

            except Exception as e:
                logger.warning(f"Failed to query team from database: {e}")

        # Fallback to hardcoded mapping if database query fails
        team_mapping = {
            "RCD Mallorca": "1084",
            "Real Madrid": "86",
            "FC Barcelona": "81",
            "Atlético Madrid": "78",
            "Sevilla FC": "559",
            "Real Betis": "90",
            "Valencia CF": "94",
            "Real Sociedad": "92",
            "Athletic Club": "77",
            "Villarreal CF": "94",
            "Celta de Vigo": "558",
            "Girona FC": "1049",
            "CA Osasuna": "79",
            "Getafe CF": "82",
            "UD Las Palmas": "275",
            "Deportivo Alavés": "263",
            "RCD Espanyol": "80",
            "Rayo Vallecano": "87",
            "Almería": "1090",
        }

        return team_mapping.get(team_name)

    def is_price_change_allowed(
        self,
        current_price: float,
        new_price: float,
        changes_today: int,
        hours_since_last_change: Optional[float] = None,
        hours_to_match: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Validate if a price change is allowed based on constraints.

        Args:
            current_price: Current price
            new_price: Proposed new price
            changes_today: Number of price changes already made today
            hours_since_last_change: Hours since last price change
            hours_to_match: Hours until the match

        Returns:
            Tuple of (is_allowed, reason)
        """
        constraints = self.rules.get("constraints", {})

        # Check daily change limit
        max_changes_per_day = constraints.get("max_changes_per_day", 5)
        if changes_today >= max_changes_per_day:
            return False, f"Daily change limit reached ({max_changes_per_day})"

        # Check minimum time between changes
        if hours_since_last_change is not None:
            min_hours = constraints.get("min_hours_between_changes", 2)
            if hours_since_last_change < min_hours:
                return False, f"Minimum {min_hours}h required between changes"

        # Check blackout period before match
        if hours_to_match is not None:
            blackout_periods = constraints.get("blackout_periods", [])
            for period in blackout_periods:
                blackout_hours = period.get("hours_before_match", 24)
                if hours_to_match <= blackout_hours:
                    reason = period.get("reason", "Blackout period")
                    return False, f"In blackout period: {reason}"

        # Check price change percentage limits
        if current_price > 0:
            price_change_percent = ((new_price - current_price) / current_price) * 100

            if price_change_percent > 0:
                max_increase = constraints.get("max_price_increase_percent", 20)
                if price_change_percent > max_increase:
                    return False, f"Increase exceeds {max_increase}% limit"
            else:
                max_decrease = constraints.get("max_price_decrease_percent", 25)
                if abs(price_change_percent) > max_decrease:
                    return False, f"Decrease exceeds {max_decrease}% limit"

        # Check minimum change threshold (avoid trivial changes)
        min_change_euros = constraints.get("absolute_limits", {}).get(
            "min_price_change_euros", 0.50
        )
        if abs(new_price - current_price) < min_change_euros:
            return False, f"Change less than minimum €{min_change_euros:.2f}"

        # Check absolute multiplier limits
        absolute_limits = constraints.get("absolute_limits", {})
        min_multiplier = absolute_limits.get("min_price_multiplier", 0.50)
        max_multiplier = absolute_limits.get("max_price_multiplier", 3.0)

        # We need a base price to check this - skip if not available
        # This will be checked at a higher level with actual zone base prices

        logger.debug(
            f"Price change validation passed: €{current_price:.2f} -> €{new_price:.2f}"
        )
        return True, "Change allowed"

    def get_constraints(self) -> Dict[str, Any]:
        """
        Get all pricing constraints.

        Returns:
            Dictionary of constraints
        """
        return self.rules.get("constraints", {})

    def get_dynamic_strategy(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a dynamic pricing strategy.

        Args:
            strategy_name: Name of the strategy (velocity_based, last_minute, etc.)

        Returns:
            Strategy configuration or None if not found
        """
        strategies = self.rules.get("dynamic_strategies", {})
        return strategies.get(strategy_name)

    def get_velocity_multiplier(self, tickets_per_hour: float) -> float:
        """
        Get multiplier based on sales velocity.

        Args:
            tickets_per_hour: Current tickets sold per hour

        Returns:
            Velocity-based multiplier
        """
        strategy = self.get_dynamic_strategy("velocity_based")

        if not strategy or not strategy.get("enabled", False):
            return 1.0

        thresholds = strategy.get("thresholds", {})
        multipliers = strategy.get("multipliers", {})

        # Determine velocity category
        if tickets_per_hour >= thresholds.get("very_high", 50):
            multiplier = float(multipliers.get("very_high", 1.20))
        elif tickets_per_hour >= thresholds.get("high", 20):
            multiplier = float(multipliers.get("high", 1.10))
        elif tickets_per_hour >= thresholds.get("medium", 10):
            multiplier = float(multipliers.get("medium", 1.0))
        elif tickets_per_hour >= thresholds.get("low", 5):
            multiplier = float(multipliers.get("low", 0.95))
        else:
            multiplier = float(multipliers.get("very_low", 0.85))

        logger.debug(
            f"Velocity multiplier for {tickets_per_hour:.1f} tickets/h: {multiplier}"
        )
        return multiplier
