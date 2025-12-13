"""Sales simulator endpoints for realistic sales progression.

This module provides endpoints for simulating realistic ticket sales
over time with automatic timeline progression.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.responses import SuccessResponse, create_success_response
from src.core.dependencies import (
    get_db,
    get_pricing_engine,
    get_zone_repository,
)
from src.domain.models.match import CompetitionType, Match, MatchStatus
from src.domain.models.zone import Zone
from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

router = APIRouter()


class SalesSimulationStep(BaseModel):
    """Single step in sales simulation."""

    days_remaining: int
    current_datetime: datetime
    zones: List[Dict]
    total_sold: int
    total_revenue: float
    avg_price: float
    overall_occupancy: float


class SalesSimulationRequest(BaseModel):
    """Request parameters for sales simulation."""

    match_id: str = Field(default="simulation", description="Match identifier")
    competition: CompetitionType = Field(default=CompetitionType.LA_LIGA)
    opponent: str = Field(default="FC Barcelona")
    is_derby: bool = Field(default=False)
    days_until_match: int = Field(default=30, ge=1, le=90)
    base_demand: float = Field(default=0.7, ge=0.1, le=1.0, description="Base demand level")


@router.post(
    "/simulator/sales-timeline",
    response_model=SuccessResponse[List[SalesSimulationStep]],
    summary="Simulate sales timeline",
    description="Generate complete sales timeline from sale start to match day",
    tags=["Simulator"]
)
async def simulate_sales_timeline(
    request: SalesSimulationRequest,
    db: Session = Depends(get_db),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
    pricing_engine: PricingEngine = Depends(get_pricing_engine),
) -> SuccessResponse[List[SalesSimulationStep]]:
    """Simulate realistic sales progression over time.

    Generates a timeline showing how sales progress from announcement
    to match day, with dynamic pricing adjustments.
    """
    logger.info(f"Simulating sales timeline for {request.days_until_match} days")

    # Get all zones
    zones = zone_repo.get_active_zones()
    if not zones:
        zones = []  # Fallback to empty

    # Create synthetic match
    match_date = datetime.utcnow() + timedelta(days=request.days_until_match)
    match = Match(
        id=request.match_id,
        home_team="RCD Mallorca",
        away_team=request.opponent,
        competition=request.competition,
        match_date=match_date,
        venue="Son Moix",
        capacity=23142,
        is_derby=request.is_derby,
        is_holiday=False,
        home_position=10,
        away_position=5,
        status=MatchStatus.ON_SALE,
    )

    # Initialize zone states
    zone_states = {}
    for zone in zones:
        zone_states[zone.id] = {
            "zone": zone,
            "sold": 0,
            "capacity": zone.capacity,
            "sales_history": []
        }

    # Generate timeline (sample key days)
    timeline = []
    days_samples = generate_timeline_samples(request.days_until_match)

    for days_remaining in days_samples:
        current_datetime = match_date - timedelta(days=days_remaining)

        # Simulate sales for this time period
        step_zones = []
        total_sold = 0
        total_revenue = 0.0

        # Simulate sales for this period first
        for zone_id, state in zone_states.items():
            zone = state["zone"]

            # Calculate expected sales for this period
            sales_rate = calculate_sales_rate(
                days_remaining=days_remaining,
                total_days=request.days_until_match,
                base_demand=request.base_demand,
                is_derby=request.is_derby,
                competition=request.competition
            )

            # Apply zone-specific multiplier
            zone_multiplier = get_zone_demand_multiplier(zone.category)
            expected_sales = int(zone.capacity * sales_rate * zone_multiplier)

            # Add randomness
            actual_sales = max(0, int(expected_sales * random.uniform(0.8, 1.2)))

            # Update sold tickets (cumulative)
            state["sold"] = min(state["sold"] + actual_sales, zone.capacity)

        # Now calculate prices using pricing_engine with simulated occupancy
        for zone_id, state in zone_states.items():
            zone = state["zone"]
            
            # Use PricingEngine to calculate price with simulated occupancy
            # This ensures we use the complete ML model pipeline
            zone_pricing = pricing_engine._calculate_zone_price(
                match=match,
                zone=zone,
                current_datetime=current_datetime,
                override_occupancy=(state["sold"], zone.capacity - state["sold"])
            )
            
            # Extract calculated values
            current_price = zone_pricing.current_price
            base_price = zone_pricing.base_price
            factors = zone_pricing.factors
            current_occupancy = zone_pricing.occupancy_percent
            
            # Calculate new sales this period
            previous_sold = state.get("previous_sold", 0)
            new_sales_this_period = state["sold"] - previous_sold
            
            # Record this period's sales in history with its price
            if new_sales_this_period > 0:
                state["sales_history"].append({
                    "days_remaining": days_remaining,
                    "new_sales": new_sales_this_period,
                    "price": current_price,
                    "revenue": new_sales_this_period * current_price
                })
            
            # Update tracking for next period
            state["previous_sold"] = state["sold"]
            
            # Calculate TOTAL revenue from complete sales history
            zone_total_revenue = sum(s["revenue"] for s in state["sales_history"])
            
            # Accumulate totals for this step
            total_revenue += zone_total_revenue
            total_sold += state["sold"]

            step_zones.append({
                "zone_id": zone.id,
                "zone_name": zone.name,
                "category": zone.category,
                "base_price": round(base_price, 2),
                "current_price": round(current_price, 2),
                "sold_tickets": state["sold"],
                "new_sales": new_sales_this_period,
                "capacity": zone.capacity,
                "occupancy_percent": round(current_occupancy, 4),
                "revenue": round(zone_total_revenue, 2),
                "price_change_percent": round(((current_price - base_price) / base_price) * 100, 1),
                "factors": {
                    "demand_score": round(factors.demand_score, 2),
                    "time_factor": round(factors.time_factor, 2),
                    "inventory_factor": round(factors.inventory_factor, 2),
                    "competition_factor": round(factors.competition_factor, 2),
                    "rival_factor": round(factors.rival_factor, 2),
                    "weather_factor": round(factors.weather_factor, 2),
                    "special_conditions": {
                        "weekday": round(factors.special_conditions.get("weekday", 1.0), 2),
                        "derby": round(factors.special_conditions.get("derby", 1.0), 2),
                        "holiday": round(factors.special_conditions.get("holiday", 1.0), 2),
                        "match_time": round(factors.special_conditions.get("match_time", 1.0), 2),
                        "team_performance": round(factors.special_conditions.get("team_performance", 1.0), 2),
                    }
                }
            })

        # Calculate overall stats
        total_capacity = sum(z["capacity"] for z in step_zones)
        overall_occupancy = total_sold / total_capacity if total_capacity > 0 else 0
        avg_price = total_revenue / total_sold if total_sold > 0 else 0

        timeline.append(SalesSimulationStep(
            days_remaining=days_remaining,
            current_datetime=current_datetime,
            zones=step_zones,
            total_sold=total_sold,
            total_revenue=round(total_revenue, 2),
            avg_price=round(avg_price, 2),
            overall_occupancy=round(overall_occupancy, 4)
        ))

    logger.info(f"Generated timeline with {len(timeline)} steps")

    return create_success_response(
        data=timeline,
        message=f"Sales timeline generated for {request.days_until_match} days"
    )


def generate_timeline_samples(total_days: int) -> List[int]:
    """Generate sample points in timeline (more samples closer to match day)."""
    if total_days <= 7:
        # Daily samples for short periods
        return list(range(total_days, -1, -1))

    samples = []

    # Sample more frequently as we get closer to match
    # First phase: early days (sparse sampling)
    if total_days > 30:
        samples.extend(range(total_days, 30, -5))
    elif total_days > 14:
        samples.extend(range(total_days, 14, -3))

    # Second phase: medium days (moderate sampling)
    if total_days > 14:
        samples.extend(range(14, 7, -2))
    elif total_days > 7:
        samples.extend(range(total_days, 7, -2))

    # Third phase: final week (daily sampling)
    samples.extend(range(min(7, total_days), -1, -1))

    # Remove duplicates and sort
    return sorted(list(set(samples)), reverse=True)


def calculate_sales_rate(
    days_remaining: int,
    total_days: int,
    base_demand: float,
    is_derby: bool,
    competition: CompetitionType
) -> float:
    """Calculate sales rate for a given time period.

    Returns the incremental sales rate (not cumulative).
    Sales follow a realistic pattern:
    - Slow start when tickets go on sale
    - Gradual increase
    - Spike in final week
    - Last minute rush
    """
    progress = (total_days - days_remaining) / total_days

    # Base curve (S-curve for realistic sales progression)
    # More sales at beginning and end, slower in middle
    if progress < 0.1:
        # Initial announcement spike
        rate = 0.15 * base_demand
    elif progress < 0.3:
        # Early steady sales
        rate = 0.05 * base_demand
    elif progress < 0.7:
        # Mid-period slow down
        rate = 0.03 * base_demand
    elif progress < 0.85:
        # Pre-final week pickup
        rate = 0.08 * base_demand
    elif progress < 0.95:
        # Final week spike
        rate = 0.15 * base_demand
    else:
        # Last-minute rush
        rate = 0.25 * base_demand

    # Competition multiplier
    comp_multipliers = {
        CompetitionType.CHAMPIONS_LEAGUE: 1.5,
        CompetitionType.LA_LIGA: 1.2,
        CompetitionType.COPA_DEL_REY: 1.0,
        CompetitionType.EUROPA_LEAGUE: 1.1,
        CompetitionType.FRIENDLY: 0.6,
    }
    rate *= comp_multipliers.get(competition, 1.0)

    # Derby boost
    if is_derby:
        rate *= 1.8

    # Weekend effect (assume 30% of days are weekends)
    if random.random() < 0.3:
        rate *= 1.3

    return min(rate, 0.5)  # Cap at 50% per period


def get_zone_demand_multiplier(category: str) -> float:
    """Get demand multiplier based on zone category."""
    multipliers = {
        "vip": 0.6,  # VIP sells slower but at higher price
        "premium": 0.8,
        "standard": 1.0,
        "reduced": 1.2,  # Reduced price zones sell faster
    }
    return multipliers.get(category.lower() if category else "standard", 1.0)
