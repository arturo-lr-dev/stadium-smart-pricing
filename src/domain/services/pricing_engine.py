"""
Pricing Engine for dynamic ticket pricing.

This module contains the PricingEngine class that orchestrates all pricing calculations
by combining rules, demand predictions, and inventory data.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.core.cache_strategies import PricingCacheStrategy
from src.domain.models.db_models import PricingHistoryDB
from src.domain.models.match import Match
from src.domain.models.pricing import MatchPricing, PricingFactors, ZonePricing
from src.domain.models.zone import Zone
from src.domain.repositories.match_repository import MatchRepository
from src.domain.repositories.pricing_repository import PricingHistoryRepository
from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.services.demand_predictor import DemandPredictor
from src.domain.services.inventory_manager import InventoryManager
from src.domain.services.rules_engine import RulesEngine
from src.integrations.weather_api import WeatherAPI

logger = logging.getLogger(__name__)


class PricingEngine:
    """
    Pricing Engine for calculating dynamic ticket prices.

    This class orchestrates all pricing calculations by combining:
    - Business rules from RulesEngine
    - Demand predictions from DemandPredictor
    - Inventory data from InventoryManager
    - Match and zone information from repositories

    The pricing engine implements the core dynamic pricing algorithm.
    """

    def __init__(
        self,
        rules_engine: RulesEngine,
        demand_predictor: DemandPredictor,
        inventory_manager: InventoryManager,
        match_repository: MatchRepository,
        zone_repository: ZoneRepository,
        pricing_repository: PricingHistoryRepository,
        weather_api: WeatherAPI,
        db_session: Session,
        cache_strategy: Optional[PricingCacheStrategy] = None,
    ):
        """
        Initialize the Pricing Engine.

        Args:
            rules_engine: Rules engine for pricing multipliers
            demand_predictor: Demand predictor for ML-based predictions
            inventory_manager: Inventory manager for sales data
            match_repository: Repository for match operations
            zone_repository: Repository for zone operations
            pricing_repository: Repository for pricing history operations
            weather_api: Weather API for fetching weather forecasts
            db_session: Database session for transactions
            cache_strategy: Optional PricingCacheStrategy for caching (default creates new instance)
        """
        self.rules_engine = rules_engine
        self.demand_predictor = demand_predictor
        self.inventory_manager = inventory_manager
        self.match_repo = match_repository
        self.zone_repo = zone_repository
        self.pricing_repo = pricing_repository
        self.weather_api = weather_api
        self.db_session = db_session
        self.cache = cache_strategy or PricingCacheStrategy()

        logger.info("PricingEngine initialized successfully")

    def calculate_match_pricing(
        self,
        match: Match,
        zones: List[Zone],
        current_datetime: Optional[datetime] = None,
        use_cache: bool = True,
    ) -> MatchPricing:
        """
        Calculate pricing for all zones in a match.

        This is the main pricing calculation method that orchestrates
        the entire pricing algorithm.

        Args:
            match: Match object
            zones: List of zones to calculate pricing for
            current_datetime: Current datetime (defaults to now)
            use_cache: Whether to use cache (default True)

        Returns:
            MatchPricing object with pricing for all zones

        Raises:
            ValueError: If match or zones are invalid
        """
        if not zones:
            raise ValueError("Cannot calculate pricing without zones")

        if current_datetime is None:
            current_datetime = datetime.now()

        # Check cache first
        if use_cache:
            try:
                cached_pricing = self.cache.get(match.id)
                if cached_pricing:
                    logger.debug(f"Cache hit for match pricing: {match.id}")
                    return MatchPricing(**cached_pricing)
            except Exception as e:
                logger.warning(f"Cache error in calculate_match_pricing, proceeding with calculation: {e}")

        logger.info(
            f"Calculating pricing for match {match.id} ({match.home_team} vs {match.away_team}) "
            f"with {len(zones)} zones"
        )

        # Calculate pricing for each zone
        zone_pricings: List[ZonePricing] = []

        for zone in zones:
            try:
                zone_pricing = self._calculate_zone_price(match, zone, current_datetime)
                zone_pricings.append(zone_pricing)
                logger.debug(
                    f"Zone {zone.id}: price={zone_pricing.current_price:.2f}, "
                    f"occupancy={zone_pricing.occupancy_percent:.1f}%"
                )
            except Exception as e:
                logger.error(f"Error calculating pricing for zone {zone.id}: {e}")
                # Continue with other zones instead of failing completely
                continue

        if not zone_pricings:
            raise ValueError("Failed to calculate pricing for any zone")

        # Calculate aggregate metrics
        total_sold = sum(zp.sold_tickets for zp in zone_pricings)
        total_capacity = sum(zp.capacity for zp in zone_pricings)
        total_revenue = sum(zp.sold_tickets * zp.current_price for zp in zone_pricings)
        avg_price = sum(zp.current_price * zp.capacity for zp in zone_pricings) / total_capacity

        match_pricing = MatchPricing(
            match_id=match.id,
            zones=zone_pricings,
            total_revenue=total_revenue,
            total_sold=total_sold,
            total_capacity=total_capacity,
            avg_price=avg_price,
            last_calculation=current_datetime,
        )

        logger.info(
            f"Match pricing calculated: {len(zone_pricings)} zones, "
            f"avg_price={avg_price:.2f}, "
            f"occupancy={total_sold}/{total_capacity} ({(total_sold/total_capacity*100):.1f}%)"
        )

        # Cache the result
        if use_cache:
            try:
                self.cache.set(match.id, match_pricing.model_dump())
            except Exception as e:
                logger.warning(f"Failed to cache pricing data: {e}")

        return match_pricing

    def _calculate_zone_price(
        self,
        match: Match,
        zone: Zone,
        current_datetime: datetime,
        override_occupancy: Optional[Tuple[int, int]] = None,
    ) -> ZonePricing:
        """
        Calculate pricing for a specific zone.

        Args:
            match: Match object
            zone: Zone object
            current_datetime: Current datetime
            override_occupancy: Optional tuple of (sold_tickets, available_tickets)
                               for simulation scenarios. If None, uses actual inventory.

        Returns:
            ZonePricing object with calculated price and factors
        """
        # Get inventory data
        if override_occupancy is not None:
            sold_tickets, available_tickets = override_occupancy
        else:
            sold_tickets, available_tickets = self.inventory_manager.get_zone_inventory(
                match.id, zone.id
            )
        occupancy_percent = (sold_tickets / zone.capacity) if zone.capacity > 0 else 0.0

        # Calculate all pricing factors
        factors = self._calculate_pricing_factors(
            match, zone, current_datetime, occupancy_percent
        )

        # Calculate base price with zone multiplier
        base_price_with_zone = zone.base_price * zone.price_multiplier

        # Apply all factors to get final price
        combined_multiplier = factors.calculate_combined_multiplier()
        calculated_price = base_price_with_zone * combined_multiplier

        # Validate and clamp price to zone's min/max constraints
        final_price = zone.validate_price(calculated_price)

        if final_price != calculated_price:
            logger.debug(
                f"Price clamped for zone {zone.id}: "
                f"calculated={calculated_price:.2f}, "
                f"clamped={final_price:.2f} "
                f"(min={zone.min_price:.2f}, max={zone.max_price:.2f})"
            )

        # Create ZonePricing object
        zone_pricing = ZonePricing(
            zone_id=zone.id,
            zone_name=zone.name,
            current_price=final_price,
            base_price=zone.base_price,
            factors=factors,
            last_updated=current_datetime,
            sold_tickets=sold_tickets,
            available_tickets=available_tickets,
            capacity=zone.capacity,
            occupancy_percent=occupancy_percent,
        )

        return zone_pricing

    def _calculate_pricing_factors(
        self,
        match: Match,
        zone: Zone,
        current_datetime: datetime,
        occupancy_percent: float,
    ) -> PricingFactors:
        """
        Calculate all pricing factors for a match and zone.

        Args:
            match: Match object
            zone: Zone object
            current_datetime: Current datetime
            occupancy_percent: Current occupancy percentage

        Returns:
            PricingFactors object with all calculated factors
        """
        # Calculate days until match
        days_to_match = match.days_until_match(current_datetime)

        logger.debug(
            f"Calculating factors for match {match.id}, zone {zone.id}, "
            f"days_to_match={days_to_match}"
        )

        # Get demand score from ML predictor
        demand_score = self.demand_predictor.predict_demand(
            match=match,
            zone=zone,
            days_to_match=days_to_match,
            current_occupancy=occupancy_percent,
        )

        # Get time decay factor from rules engine
        time_factor = self.rules_engine.get_time_decay_factor(days_to_match)

        # Get inventory pressure factor from rules engine
        inventory_factor = self.rules_engine.get_inventory_pressure_factor(occupancy_percent)

        # Get competition factor from rules engine
        competition_factor = self.rules_engine.get_competition_multiplier(match.competition)

        # Get rival multiplier from rules engine (with competition context for API lookup)
        rival_factor = self.rules_engine.get_rival_multiplier(
            match.away_team,
            competition=match.competition
        )

        # Get special conditions (derby, holiday, etc.)
        special_conditions = self.rules_engine.get_special_multipliers(match)

        # Get weather factor from weather API and rules engine
        weather_factor = self._get_weather_factor(match)

        factors = PricingFactors(
            demand_score=demand_score,
            time_factor=time_factor,
            inventory_factor=inventory_factor,
            competition_factor=competition_factor,
            rival_factor=rival_factor,
            weather_factor=weather_factor,
            special_conditions=special_conditions,
        )

        logger.debug(
            f"Pricing factors: demand={demand_score:.3f}, time={time_factor:.2f}, "
            f"inventory={inventory_factor:.2f}, competition={competition_factor:.2f}, "
            f"rival={rival_factor:.2f}, special={special_conditions}"
        )

        return factors

    def _get_weather_factor(self, match: Match) -> float:
        """
        Get weather factor for a match based on weather forecast.

        Args:
            match: Match object

        Returns:
            Weather factor multiplier (from pricing rules)
        """
        try:
            # Get weather forecast for the match
            # Coordinates for Palma de Mallorca (Son Moix stadium)
            lat, lon = 39.5925, 2.7301

            weather_data = self.weather_api.get_forecast(lat=lat, lon=lon, date=match.date)

            # Convert weather data to condition category
            weather_condition = self._categorize_weather(weather_data)

            # Get multiplier from rules engine based on condition
            factor = self.rules_engine.get_weather_factor(weather_condition)

            logger.debug(
                f"Weather factor for match {match.id}: {factor} (condition: {weather_condition})"
            )

            return factor

        except Exception as e:
            # If weather API fails, use default "good" weather
            logger.warning(
                f"Failed to get weather data for match {match.id}: {e}. Using default weather factor."
            )
            return self.rules_engine.get_weather_factor("good")

    def _categorize_weather(self, weather_data: Dict) -> str:
        """
        Categorize weather data into condition levels for pricing rules.

        Args:
            weather_data: Weather data from WeatherAPI

        Returns:
            Weather condition: "excellent", "good", "fair", or "poor"
        """
        temp = weather_data.get("temperature", 20.0)
        rain_prob = weather_data.get("precipitation_probability", 0.0)
        wind_speed = weather_data.get("wind_speed", 0.0)

        # Excellent weather: ideal temperature, no rain, light wind
        if 18 <= temp <= 25 and rain_prob < 0.1 and wind_speed < 5:
            return "excellent"

        # Poor weather: extreme conditions
        if (
            temp < 10 or temp > 30  # Very cold or very hot
            or rain_prob > 0.7  # Very likely rain
            or wind_speed > 15  # Very windy
        ):
            return "poor"

        # Fair weather: some adverse conditions
        if (
            temp < 15 or temp > 28  # Cold or hot
            or rain_prob > 0.4  # Likely rain
            or wind_speed > 10  # Windy
        ):
            return "fair"

        # Good weather: everything else
        return "good"

    def should_update_price(
        self,
        match_id: str,
        zone_id: str,
        current_price: float,
        new_price: float,
        changes_today: int = 0,
    ) -> Tuple[bool, str]:
        """
        Determine if a price should be updated.

        This method checks business rules to decide if a price change
        should be applied. It considers:
        - Maximum daily price changes
        - Minimum price change threshold (avoid trivial changes)
        - Price change constraints from rules engine

        Args:
            match_id: Match identifier
            zone_id: Zone identifier
            current_price: Current price
            new_price: Proposed new price
            changes_today: Number of price changes already made today

        Returns:
            Tuple of (should_update: bool, reason: str)
        """
        # Calculate price difference
        price_diff = abs(new_price - current_price)
        price_diff_percent = (price_diff / current_price * 100) if current_price > 0 else 0

        # Check minimum change threshold (avoid trivial changes like 0.01€)
        min_change_threshold = 0.50  # Minimum 0.50€ change
        min_change_percent = 1.0  # Or 1% change

        if price_diff < min_change_threshold and price_diff_percent < min_change_percent:
            return False, (
                f"Price change too small (diff={price_diff:.2f}€, {price_diff_percent:.1f}%), "
                f"below threshold (min={min_change_threshold}€ or {min_change_percent}%)"
            )

        # Check rules engine constraints
        is_allowed, reason = self.rules_engine.is_price_change_allowed(
            current_price, new_price, changes_today
        )

        if not is_allowed:
            return False, f"Price change not allowed: {reason}"

        # Price change is allowed
        change_direction = "increase" if new_price > current_price else "decrease"
        return True, (
            f"Price {change_direction} approved: "
            f"{current_price:.2f}€ → {new_price:.2f}€ "
            f"(diff={price_diff:.2f}€, {price_diff_percent:.1f}%)"
        )

    def calculate_all_upcoming_matches(
        self,
        days: int = 30,
    ) -> List[MatchPricing]:
        """
        Calculate pricing for all upcoming matches.

        This method is useful for batch pricing updates and
        price forecasting.

        Args:
            days: Number of days ahead to include (default: 30)

        Returns:
            List of MatchPricing objects for upcoming matches
        """
        logger.info(f"Calculating pricing for all matches in next {days} days")

        # Get upcoming matches from repository
        upcoming_matches = self.match_repo.get_upcoming(days=days)

        if not upcoming_matches:
            logger.info("No upcoming matches found")
            return []

        logger.info(f"Found {len(upcoming_matches)} upcoming matches")

        # Get all active zones (assumes zones are same for all matches)
        zones = self.zone_repo.get_active_zones()

        if not zones:
            logger.warning("No active zones found")
            return []

        # Calculate pricing for each match
        match_pricings: List[MatchPricing] = []
        current_datetime = datetime.now()

        for match in upcoming_matches:
            try:
                match_pricing = self.calculate_match_pricing(
                    match=match,
                    zones=zones,
                    current_datetime=current_datetime,
                )
                match_pricings.append(match_pricing)
                logger.debug(
                    f"Calculated pricing for match {match.id}: "
                    f"avg_price={match_pricing.avg_price:.2f}€"
                )
            except Exception as e:
                # Log error but continue with other matches
                logger.error(
                    f"Error calculating pricing for match {match.id} "
                    f"({match.home_team} vs {match.away_team}): {e}",
                    exc_info=True,
                )
                continue

        logger.info(
            f"Successfully calculated pricing for {len(match_pricings)}/{len(upcoming_matches)} matches"
        )

        return match_pricings

    def save_pricing_to_history(self, pricing: MatchPricing) -> None:
        """
        Save pricing calculation to historical database.

        This creates a snapshot of the pricing decision for
        later analysis and auditing.

        Args:
            pricing: MatchPricing object to save

        Raises:
            Exception: If database save fails
        """
        logger.info(f"Saving pricing history for match {pricing.match_id}")

        try:
            # Save each zone's pricing to history
            for zone_pricing in pricing.zones:
                history_entry = PricingHistoryDB(
                    match_id=pricing.match_id,
                    zone_id=zone_pricing.zone_id,
                    price=zone_pricing.current_price,
                    demand_score=zone_pricing.factors.demand_score,
                    time_factor=zone_pricing.factors.time_factor,
                    inventory_factor=zone_pricing.factors.inventory_factor,
                    competition_factor=zone_pricing.factors.competition_factor,
                    weather_factor=zone_pricing.factors.weather_factor,
                    timestamp=pricing.last_calculation,
                )

                self.db_session.add(history_entry)

            # Commit transaction
            self.db_session.commit()

            logger.info(
                f"Successfully saved pricing history for match {pricing.match_id}, "
                f"{len(pricing.zones)} zones"
            )

        except Exception as e:
            logger.error(
                f"Error saving pricing history for match {pricing.match_id}: {e}",
                exc_info=True,
            )
            self.db_session.rollback()
            raise

    def get_price_change_count_today(self, match_id: str, zone_id: str) -> int:
        """
        Get the number of price changes made today for a match/zone.

        This is used by should_update_price to enforce daily limits.

        Args:
            match_id: Match identifier
            zone_id: Zone identifier

        Returns:
            Number of price changes made today
        """
        # This method queries the pricing history to count changes
        # For now, we'll delegate to the rules engine's tracking
        # which uses Redis for real-time counting
        try:
            # Query Redis for today's changes (managed by rules engine)
            # The rules engine tracks this in record_price_change()
            return 0  # Placeholder - actual implementation would query Redis
        except Exception as e:
            logger.error(f"Error getting price change count: {e}")
            return 0

    def invalidate_cache(self, match_id: str) -> None:
        """
        Invalidate cached pricing for a match.

        Should be called when match data changes that would affect pricing
        (e.g., new sales, updated match details, weather changes).

        Args:
            match_id: Match identifier
        """
        try:
            self.cache.invalidate(match_id)
            logger.info(f"Invalidated pricing cache for match {match_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate pricing cache: {e}")
