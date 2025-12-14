"""Sales simulator endpoints for realistic sales progression.

This module provides endpoints for simulating realistic ticket sales
over time with automatic timeline progression.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
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
from src.domain.repositories.match_repository import MatchRepository
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

    match_id: Optional[str] = Field(default=None, description="Real match ID from database (optional)")
    competition: Optional[CompetitionType] = Field(default=CompetitionType.LA_LIGA)
    opponent: Optional[str] = Field(default="FC Barcelona")
    is_derby: Optional[bool] = Field(default=False)
    days_until_match: Optional[int] = Field(default=None, ge=1, le=90, description="Override days until match (optional)")
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
    
    # Determine if using real match or synthetic match
    if request.match_id:
        # Use real match from database
        match_repo = MatchRepository(db)
        match = match_repo.get_by_id(request.match_id)

        if not match:
            raise HTTPException(
                status_code=404,
                detail=f"Match with ID {request.match_id} not found"
            )

        # Calculate days until match
        now = datetime.utcnow()
        if match.date <= now:
            raise HTTPException(
                status_code=400,
                detail="Cannot simulate past matches. Match date must be in the future."
            )

        days_until_match = request.days_until_match or (match.date - now).days
        match_date = match.date

        logger.info(
            f"Simulating sales timeline for real match {match.id}: "
            f"{match.home_team} vs {match.away_team} ({days_until_match} days)"
        )
    else:
        # Create synthetic match (original behavior)
        days_until_match = request.days_until_match or 30
        match_date = datetime.utcnow() + timedelta(days=days_until_match)

        match = Match(
            id="simulation",
            home_team="RCD Mallorca",
            away_team=request.opponent or "FC Barcelona",
            competition=request.competition or CompetitionType.LA_LIGA,
            match_date=match_date,
            venue="Son Moix",
            capacity=23142,
            is_derby=request.is_derby or False,
            is_holiday=False,
            home_position=10,
            away_position=5,
            status=MatchStatus.ON_SALE,
        )

        logger.info(
            f"Simulating sales timeline for synthetic match: "
            f"{match.home_team} vs {match.away_team} ({days_until_match} days)"
        )

    logger.info(f"Simulating sales timeline for {days_until_match} days")

    # Get all zones
    zones = zone_repo.get_active_zones()
    if not zones:
        zones = []  # Fallback to empty

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
    days_samples = generate_timeline_samples(days_until_match)

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
                total_days=days_until_match,
                base_demand=request.base_demand,
                is_derby=match.is_derby,
                competition=match.competition
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
                    "demand_score": round(factors.demand_score, 2) if hasattr(factors, "demand_score") and factors.demand_score is not None else "NA",
                    "time_factor": round(factors.time_factor, 2) if hasattr(factors, "time_factor") and factors.time_factor is not None else "NA",
                    "inventory_factor": round(factors.inventory_factor, 2) if hasattr(factors, "inventory_factor") and factors.inventory_factor is not None else "NA",
                    "competition_factor": round(factors.competition_factor, 2) if hasattr(factors, "competition_factor") and factors.competition_factor is not None else "NA",
                    "rival_factor": round(factors.rival_factor, 2) if hasattr(factors, "rival_factor") and factors.rival_factor is not None else "NA",
                    "weather_factor": round(factors.weather_factor, 2) if hasattr(factors, "weather_factor") and factors.weather_factor is not None else "NA",
                    "special_conditions": {
                        "weekday": round(factors.special_conditions["weekday"], 2) if "weekday" in factors.special_conditions else "NA",
                        "derby": round(factors.special_conditions["derby"], 2) if "derby" in factors.special_conditions else "NA",
                        "holiday": round(factors.special_conditions["holiday"], 2) if "holiday" in factors.special_conditions else "NA",
                        "match_time": round(factors.special_conditions["match_time"], 2) if "match_time" in factors.special_conditions else "NA",
                        "team_performance": round(factors.special_conditions["team_performance"], 2) if "team_performance" in factors.special_conditions else "NA",
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
        message=f"Sales timeline generated for {days_until_match} days"
    )


class AvailableMatch(BaseModel):
    """Available match for simulation."""
    
    id: str
    home_team: str
    away_team: str
    competition: str
    date: datetime
    venue: str
    is_derby: bool
    days_until_match: int


@router.get(
    "/simulator/available-matches",
    response_model=SuccessResponse[List[AvailableMatch]],
    summary="Get available matches",
    description="List future matches available for sales simulation",
    tags=["Simulator"]
)
async def get_available_matches(
    db: Session = Depends(get_db),
    days_ahead: int = 90,
) -> SuccessResponse[List[AvailableMatch]]:
    """Get list of future matches available for simulation.
    
    Args:
        days_ahead: Number of days to look ahead (default 90)
        
    Returns:
        List of available matches with ON_SALE status
    """
    match_repo = MatchRepository(db)
    
    # Get upcoming matches with ON_SALE status
    upcoming_matches = match_repo.get_upcoming(days=days_ahead)
    
    # Filter by ON_SALE status and convert to response model
    now = datetime.utcnow()
    available_matches = []
    
    for match in upcoming_matches:
        if match.status == MatchStatus.ON_SALE:
            days_until = (match.date - now).days
            available_matches.append(AvailableMatch(
                id=match.id,
                home_team=match.home_team,
                away_team=match.away_team,
                competition=match.competition.value if hasattr(match.competition, 'value') else str(match.competition),
                date=match.date,
                venue=match.venue,
                is_derby=match.is_derby,
                days_until_match=days_until
            ))
    
    logger.info(f"Found {len(available_matches)} available matches for simulation")
    
    return create_success_response(
        data=available_matches,
        message=f"Found {len(available_matches)} available matches"
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
