"""
Pricing domain models.

Pydantic models for pricing calculations and related data.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class PricingFactors(BaseModel):
    """
    Pricing factors model.

    Contains all the factors that influence price calculation.
    """

    model_config = ConfigDict(from_attributes=True)

    demand_score: float = Field(
        ..., description="Predicted demand score from ML model", ge=0.0, le=1.0
    )
    time_factor: float = Field(
        ..., description="Time-based multiplier (urgency)", ge=0.5, le=2.0
    )
    inventory_factor: float = Field(
        ..., description="Inventory pressure multiplier", ge=0.7, le=1.5
    )
    competition_factor: float = Field(
        ..., description="Competition importance multiplier", ge=1.0, le=3.0
    )
    rival_factor: float = Field(
        default=1.0, description="Rival team multiplier", ge=0.8, le=2.0
    )
    weather_factor: float = Field(
        default=1.0, description="Weather impact multiplier", ge=0.9, le=1.1
    )
    special_conditions: Dict[str, float] = Field(
        default_factory=dict, description="Special condition multipliers (derby, holiday, etc.)"
    )

    def calculate_combined_multiplier(self) -> float:
        """
        Calculate the combined multiplier from all factors.

        Returns:
            Combined multiplier to apply to base price
        """
        # Base multiplier from main factors
        base = self.time_factor * self.inventory_factor * self.competition_factor * self.rival_factor

        # Apply special conditions
        for condition, multiplier in self.special_conditions.items():
            base *= multiplier

        # Weather is typically a small adjustment
        base *= self.weather_factor

        # Demand score influences but doesn't multiply directly
        # It can boost or reduce the final multiplier slightly
        demand_adjustment = 0.8 + (self.demand_score * 0.4)  # Range: 0.8 to 1.2
        base *= demand_adjustment

        return base


class ZonePricing(BaseModel):
    """
    Zone pricing model.

    Contains current pricing information for a specific zone in a match.
    """

    model_config = ConfigDict(from_attributes=True)

    zone_id: str = Field(..., description="Zone identifier")
    zone_name: str = Field(..., description="Zone name")
    current_price: float = Field(..., description="Current calculated price", gt=0)
    base_price: float = Field(..., description="Base price for this zone", gt=0)
    factors: PricingFactors = Field(..., description="Pricing factors used")
    last_updated: datetime = Field(..., description="Last price update timestamp")

    # Inventory information
    sold_tickets: int = Field(..., description="Number of tickets sold", ge=0)
    available_tickets: int = Field(..., description="Number of available tickets", ge=0)
    capacity: int = Field(..., description="Total zone capacity", gt=0)
    occupancy_percent: float = Field(..., description="Occupancy percentage", ge=0.0, le=100.0)

    def calculate_occupancy(self) -> float:
        """
        Calculate occupancy percentage.

        Returns:
            Occupancy as percentage (0-100)
        """
        if self.capacity == 0:
            return 0.0
        return (self.sold_tickets / self.capacity) * 100

    def price_change_from_base(self) -> float:
        """
        Calculate price change from base price.

        Returns:
            Percentage change from base price
        """
        return ((self.current_price - self.base_price) / self.base_price) * 100

    def is_selling_well(self) -> bool:
        """
        Determine if this zone is selling well.

        Returns:
            True if occupancy is above 70%
        """
        return self.occupancy_percent >= 70.0

    def is_underperforming(self) -> bool:
        """
        Determine if this zone is underperforming.

        Returns:
            True if occupancy is below 30%
        """
        return self.occupancy_percent <= 30.0


class MatchPricing(BaseModel):
    """
    Match pricing model.

    Contains pricing information for all zones in a match.
    """

    model_config = ConfigDict(from_attributes=True)

    match_id: str = Field(..., description="Match identifier")
    zones: List[ZonePricing] = Field(..., description="Pricing for each zone")
    total_revenue: float = Field(
        default=0.0, description="Total revenue from sales", ge=0.0
    )
    total_sold: int = Field(default=0, description="Total tickets sold", ge=0)
    total_capacity: int = Field(..., description="Total stadium capacity", gt=0)
    avg_price: float = Field(default=0.0, description="Average ticket price", ge=0.0)
    last_calculation: datetime = Field(..., description="Last calculation timestamp")

    def get_zone_pricing(self, zone_id: str) -> Optional[ZonePricing]:
        """
        Get pricing for a specific zone.

        Args:
            zone_id: Zone identifier

        Returns:
            ZonePricing if found, None otherwise
        """
        for zone_pricing in self.zones:
            if zone_pricing.zone_id == zone_id:
                return zone_pricing
        return None

    def calculate_total_occupancy(self) -> float:
        """
        Calculate overall stadium occupancy.

        Returns:
            Overall occupancy percentage (0-100)
        """
        if self.total_capacity == 0:
            return 0.0
        return (self.total_sold / self.total_capacity) * 100

    def calculate_avg_price(self) -> float:
        """
        Calculate average price across all zones (weighted by capacity).

        Returns:
            Weighted average price
        """
        if not self.zones:
            return 0.0

        total_weighted_price = sum(z.current_price * z.capacity for z in self.zones)
        total_capacity = sum(z.capacity for z in self.zones)

        if total_capacity == 0:
            return 0.0

        return total_weighted_price / total_capacity

    def get_best_selling_zones(self, limit: int = 5) -> List[ZonePricing]:
        """
        Get zones with highest occupancy.

        Args:
            limit: Maximum number of zones to return

        Returns:
            List of top selling zones
        """
        return sorted(self.zones, key=lambda z: z.occupancy_percent, reverse=True)[:limit]

    def get_underperforming_zones(self, threshold: float = 30.0) -> List[ZonePricing]:
        """
        Get zones with low occupancy.

        Args:
            threshold: Occupancy threshold percentage

        Returns:
            List of underperforming zones
        """
        return [z for z in self.zones if z.occupancy_percent <= threshold]



class PriceChangeRequest(BaseModel):
    """Schema for manual price change requests."""

    match_id: str = Field(..., description="Match identifier")
    zone_id: str = Field(..., description="Zone identifier")
    new_price: float = Field(..., description="New price to set", gt=0)
    reason: Optional[str] = Field(None, description="Reason for manual price change")


class PriceChangeResponse(BaseModel):
    """Schema for price change API responses."""

    success: bool = Field(..., description="Whether price change was successful")
    message: str = Field(..., description="Result message")
    old_price: Optional[float] = Field(None, description="Previous price")
    new_price: Optional[float] = Field(None, description="New price")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")
