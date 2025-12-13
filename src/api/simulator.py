"""Simulator endpoints for testing pricing scenarios.

This module provides endpoints for simulating pricing with custom parameters.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.responses import SuccessResponse, create_success_response
from src.core.dependencies import (
    get_db,
    get_pricing_engine,
    get_zone_repository,
)
from src.domain.models.match import CompetitionType, Match, MatchStatus
from src.domain.models.pricing import MatchPricing
from src.domain.models.zone import Zone
from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

router = APIRouter()


class SimulationParams(BaseModel):
    """Parameters for pricing simulation."""

    # Match details
    competition: CompetitionType = Field(default=CompetitionType.LA_LIGA)
    rival_strength: float = Field(default=0.5, ge=0.0, le=1.0, description="Rival strength (0=weak, 1=strong)")
    is_derby: bool = Field(default=False)

    # Temporal factors
    days_to_match: int = Field(default=7, ge=0, le=365, description="Days until match")
    weekday: int = Field(default=5, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    hour: int = Field(default=21, ge=0, le=23, description="Match hour (0-23)")

    # Demand and inventory
    demand_multiplier: float = Field(default=1.0, ge=0.1, le=3.0, description="Demand multiplier")
    base_occupancy: float = Field(default=0.3, ge=0.0, le=1.0, description="Current occupancy percentage")

    # Weather
    weather_condition: str = Field(default="clear", description="Weather: clear, cloudy, rain, storm")
    temperature: float = Field(default=20.0, ge=-10.0, le=45.0, description="Temperature in Celsius")

    # Special conditions
    is_holiday: bool = Field(default=False)
    home_team_position: int = Field(default=10, ge=1, le=20, description="Home team league position")
    away_team_position: int = Field(default=10, ge=1, le=20, description="Away team league position")


@router.post(
    "/simulator/calculate",
    response_model=SuccessResponse[MatchPricing],
    summary="Simulate pricing with custom parameters",
    description="Calculate pricing for all zones based on custom simulation parameters",
    tags=["Simulator"]
)
async def simulate_pricing(
    params: SimulationParams,
    db: Session = Depends(get_db),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
    pricing_engine: PricingEngine = Depends(get_pricing_engine),
) -> SuccessResponse[MatchPricing]:
    """Simulate pricing with custom parameters.

    Args:
        params: Simulation parameters
        db: Database session
        zone_repo: Zone repository instance
        pricing_engine: Pricing engine instance

    Returns:
        Success response with simulated match pricing
    """
    logger.info(f"Simulating pricing with custom parameters")

    try:
        # Create a synthetic match for simulation
        match_date = datetime.utcnow() + timedelta(days=params.days_to_match)
        match_date = match_date.replace(hour=params.hour, minute=0, second=0, microsecond=0)

        # Adjust date to specified weekday
        days_diff = params.weekday - match_date.weekday()
        match_date = match_date + timedelta(days=days_diff)

        synthetic_match = Match(
            id="simulation",
            home_team="RCD Mallorca",
            away_team="Simulated Opponent",
            competition=params.competition,
            match_date=match_date,
            venue="Son Moix",
            capacity=23142,
            is_derby=params.is_derby,
            is_holiday=params.is_holiday,
            home_position=params.home_team_position,
            away_position=params.away_team_position,
            status=MatchStatus.ON_SALE,
        )

        # Get all active zones
        zones = zone_repo.get_active_zones()

        if not zones:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active zones found"
            )

        # Override demand predictor for simulation
        original_predict = pricing_engine.demand_predictor.predict_demand

        def simulated_predict_demand(match, zone, days_to_match, current_occupancy=0.0):
            # Use base heuristic but apply custom multiplier
            base_demand = original_predict(match, zone, days_to_match, current_occupancy)
            return min(base_demand * params.demand_multiplier, 1.0)

        pricing_engine.demand_predictor.predict_demand = simulated_predict_demand

        # Override inventory for simulation
        def get_simulated_inventory(zone_id: str):
            zone = next((z for z in zones if z.id == zone_id), None)
            if not zone:
                return 0, zone.capacity, 0.0

            sold = int(zone.capacity * params.base_occupancy)
            available = zone.capacity - sold
            occupancy = params.base_occupancy

            return sold, available, occupancy

        # Calculate pricing with simulation parameters
        zone_pricings = []

        for zone in zones:
            sold_tickets, available_tickets, occupancy = get_simulated_inventory(zone.id)

            # Calculate demand score
            demand_score = simulated_predict_demand(
                synthetic_match,
                zone,
                params.days_to_match,
                occupancy
            )

            # Get base price
            base_price = zone.base_price

            # Calculate factors using rules engine
            competition_factor = pricing_engine.rules_engine.get_competition_multiplier(
                params.competition
            )

            rival_factor = 0.8 + (params.rival_strength * 0.4)  # 0.8 to 1.2

            time_factor = pricing_engine.rules_engine.get_time_decay_factor(params.days_to_match)

            inventory_factor = pricing_engine.rules_engine.get_inventory_pressure_factor(occupancy)

            # Weather factor
            weather_multipliers = {
                "clear": 1.0,
                "cloudy": 0.98,
                "rain": 0.9,
                "storm": 0.85
            }
            weather_factor = weather_multipliers.get(params.weather_condition.lower(), 1.0)

            # Temperature adjustment (optimal 15-25°C)
            if params.temperature < 10:
                weather_factor *= 0.95
            elif params.temperature > 30:
                weather_factor *= 0.95

            # Special conditions
            special_conditions = {
                "weekday": 1.0 if params.weekday in [5, 6] else 0.95,  # Weekend boost
                "derby": 2.0 if params.is_derby else 1.0,
                "holiday": 1.15 if params.is_holiday else 1.0,
                "match_time": 1.1 if params.hour >= 20 else 0.95,  # Prime time
                "team_performance": 1.0 + (0.05 * (20 - params.home_team_position) / 20)  # Better position = higher price
            }

            # Calculate final price
            multiplier = (
                demand_score *
                time_factor *
                inventory_factor *
                competition_factor *
                rival_factor *
                weather_factor *
                special_conditions["weekday"] *
                special_conditions["derby"] *
                special_conditions["holiday"] *
                special_conditions["match_time"] *
                special_conditions["team_performance"]
            )

            current_price = round(base_price * multiplier, 2)

            # Ensure price is within bounds
            min_price = base_price * 0.5
            max_price = base_price * 3.0
            current_price = max(min_price, min(current_price, max_price))

            zone_pricings.append({
                "zone_id": zone.id,
                "zone_name": zone.name,
                "category": zone.category if zone.category else "STANDARD",
                "current_price": current_price,
                "base_price": base_price,
                "factors": {
                    "demand_score": round(demand_score, 2),
                    "time_factor": round(time_factor, 2),
                    "inventory_factor": round(inventory_factor, 2),
                    "competition_factor": round(competition_factor, 2),
                    "rival_factor": round(rival_factor, 2),
                    "weather_factor": round(weather_factor, 2),
                    "special_conditions": {
                        k: round(v, 2) for k, v in special_conditions.items()
                    }
                },
                "sold_tickets": sold_tickets,
                "available_tickets": available_tickets,
                "capacity": zone.capacity,
                "occupancy_percent": occupancy,
                "last_updated": datetime.utcnow().isoformat()
            })

        # Calculate totals
        total_revenue = sum(zp["current_price"] * zp["sold_tickets"] for zp in zone_pricings)
        total_sold = sum(zp["sold_tickets"] for zp in zone_pricings)
        total_capacity = sum(zp["capacity"] for zp in zone_pricings)
        avg_price = total_revenue / total_sold if total_sold > 0 else 0

        result = {
            "match_id": "simulation",
            "zones": zone_pricings,
            "total_revenue": round(total_revenue, 2),
            "total_sold": total_sold,
            "total_capacity": total_capacity,
            "avg_price": round(avg_price, 2),
            "last_calculation": datetime.utcnow(),
            "simulation_params": params.model_dump()
        }

        # Restore original predictor
        pricing_engine.demand_predictor.predict_demand = original_predict

        return create_success_response(
            data=result,
            message="Pricing simulation completed successfully"
        )

    except Exception as e:
        logger.error(f"Error in pricing simulation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}"
        )
