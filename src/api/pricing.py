"""Pricing endpoints for the Smart Pricing API.

This module contains all endpoints related to pricing calculations
and price history.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.responses import SuccessResponse, create_success_response
from src.core.dependencies import (
    get_db,
    get_match_repository,
    get_pricing_engine,
    get_pricing_repository,
    get_zone_repository,
)
from src.domain.models.match import Match
from src.domain.models.pricing import MatchPricing, ZonePricing
from src.domain.repositories.match_repository import MatchRepository
from src.domain.repositories.pricing_repository import PricingHistoryRepository
from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/pricing/match/{match_id}",
    response_model=SuccessResponse[MatchPricing],
    summary="Get match pricing",
    description="Calculate and return the current pricing for all zones of a specific match",
    responses={
        200: {
            "description": "Pricing calculated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "match_id": "match_123",
                            "zones": [
                                {
                                    "zone_id": "tribuna",
                                    "current_price": 45.50,
                                    "base_price": 40.00,
                                    "factors": {
                                        "demand_score": 0.75,
                                        "time_factor": 1.2,
                                        "inventory_factor": 1.1,
                                        "competition_factor": 1.5,
                                        "weather_factor": 1.0
                                    },
                                    "sold_tickets": 1200,
                                    "available_tickets": 800,
                                    "occupancy_percent": 60.0
                                }
                            ],
                            "total_revenue": 125000.0,
                            "total_sold": 5000,
                            "total_capacity": 23142,
                            "avg_price": 42.50
                        }
                    }
                }
            }
        },
        404: {"description": "Match not found"},
        500: {"description": "Error calculating pricing"}
    }
)
async def get_match_pricing(
    match_id: str,
    db: Session = Depends(get_db),
    match_repo: MatchRepository = Depends(get_match_repository),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
    pricing_engine: PricingEngine = Depends(get_pricing_engine),
) -> SuccessResponse[MatchPricing]:
    """Get current pricing for a specific match.

    Args:
        match_id: ID of the match
        db: Database session
        match_repo: Match repository instance
        zone_repo: Zone repository instance
        pricing_engine: Pricing engine instance

    Returns:
        Success response with match pricing data

    Raises:
        HTTPException: If match not found or pricing calculation fails
    """
    logger.info(f"Calculating pricing for match {match_id}")

    # Get match
    match = match_repo.get_by_id(match_id)
    if not match:
        logger.warning(f"Match {match_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found"
        )

    # Get all active zones
    zones = zone_repo.get_active_zones()
    if not zones:
        logger.error("No active zones found")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No active zones configured"
        )

    # Calculate pricing
    try:
        pricing = pricing_engine.calculate_match_pricing(
            match=match,
            zones=zones,
            current_datetime=datetime.utcnow()
        )
        logger.info(f"Pricing calculated for match {match_id}: avg_price={pricing.avg_price:.2f}")
        return create_success_response(
            data=pricing,
            message="Pricing calculated successfully"
        )
    except Exception as e:
        logger.error(f"Error calculating pricing for match {match_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating pricing: {str(e)}"
        )


@router.get(
    "/pricing/match/{match_id}/zone/{zone_id}",
    response_model=SuccessResponse[ZonePricing],
    summary="Get zone pricing",
    description="Get the current pricing for a specific zone in a match",
    responses={
        404: {"description": "Match or zone not found"},
        500: {"description": "Error calculating pricing"}
    }
)
async def get_zone_pricing(
    match_id: str,
    zone_id: str,
    db: Session = Depends(get_db),
    match_repo: MatchRepository = Depends(get_match_repository),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
    pricing_engine: PricingEngine = Depends(get_pricing_engine),
) -> SuccessResponse[ZonePricing]:
    """Get current pricing for a specific zone in a match.

    Args:
        match_id: ID of the match
        zone_id: ID of the zone
        db: Database session
        match_repo: Match repository instance
        zone_repo: Zone repository instance
        pricing_engine: Pricing engine instance

    Returns:
        Success response with zone pricing data

    Raises:
        HTTPException: If match or zone not found
    """
    logger.info(f"Calculating pricing for match {match_id}, zone {zone_id}")

    # Get match
    match = match_repo.get_by_id(match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found"
        )

    # Get zone
    zone = zone_repo.get_by_id(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found"
        )

    # Calculate pricing for all zones
    try:
        zones = zone_repo.get_active_zones()
        pricing = pricing_engine.calculate_match_pricing(
            match=match,
            zones=zones,
            current_datetime=datetime.utcnow()
        )

        # Find the specific zone
        zone_pricing = pricing.get_zone_pricing(zone_id)
        if not zone_pricing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Zone {zone_id} not found in pricing calculation"
            )

        logger.info(f"Zone pricing calculated: {zone_id} = {zone_pricing.current_price:.2f}")
        return create_success_response(
            data=zone_pricing,
            message="Zone pricing calculated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating zone pricing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating pricing: {str(e)}"
        )


@router.get(
    "/pricing/upcoming",
    response_model=SuccessResponse[List[MatchPricing]],
    summary="Get upcoming matches pricing",
    description="Calculate pricing for all upcoming matches within a specified time window",
    responses={
        200: {"description": "Pricing calculated for upcoming matches"},
        422: {"description": "Invalid parameters"},
        500: {"description": "Error calculating pricing"}
    }
)
async def get_upcoming_pricing(
    days: int = Query(
        default=30,
        ge=1,
        le=90,
        description="Number of days to look ahead (1-90)"
    ),
    db: Session = Depends(get_db),
    match_repo: MatchRepository = Depends(get_match_repository),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
    pricing_engine: PricingEngine = Depends(get_pricing_engine),
) -> SuccessResponse[List[MatchPricing]]:
    """Get pricing for all upcoming matches.

    Args:
        days: Number of days to look ahead (default 30, max 90)
        db: Database session
        match_repo: Match repository instance
        zone_repo: Zone repository instance
        pricing_engine: Pricing engine instance

    Returns:
        Success response with list of match pricings

    Raises:
        HTTPException: If error occurs during calculation
    """
    logger.info(f"Calculating pricing for upcoming matches (next {days} days)")

    try:
        # Get all active zones (only once)
        zones = zone_repo.get_active_zones()
        if not zones:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No active zones configured"
            )

        # Get upcoming matches
        matches = match_repo.get_upcoming(days=days)
        logger.info(f"Found {len(matches)} upcoming matches")

        # Calculate pricing for each match
        pricings = []
        errors = []

        for match in matches:
            try:
                pricing = pricing_engine.calculate_match_pricing(
                    match=match,
                    zones=zones,
                    current_datetime=datetime.utcnow()
                )
                pricings.append(pricing)
            except Exception as e:
                logger.error(f"Error calculating pricing for match {match.id}: {e}")
                errors.append({"match_id": match.id, "error": str(e)})

        logger.info(f"Successfully calculated pricing for {len(pricings)} matches")

        if errors:
            logger.warning(f"Failed to calculate pricing for {len(errors)} matches: {errors}")

        return create_success_response(
            data=pricings,
            message=f"Pricing calculated for {len(pricings)} matches" +
                    (f" ({len(errors)} errors)" if errors else "")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating upcoming pricing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating pricing: {str(e)}"
        )


@router.post(
    "/pricing/match/{match_id}/recalculate",
    response_model=SuccessResponse[MatchPricing],
    summary="Recalculate match pricing",
    description="Force recalculation of pricing for a match and save to history",
    responses={
        200: {"description": "Pricing recalculated successfully"},
        404: {"description": "Match not found"},
        500: {"description": "Error recalculating pricing"}
    }
)
async def recalculate_match_pricing(
    match_id: str,
    save_to_history: bool = Query(
        default=True,
        description="Whether to save the recalculated pricing to history"
    ),
    db: Session = Depends(get_db),
    match_repo: MatchRepository = Depends(get_match_repository),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
    pricing_engine: PricingEngine = Depends(get_pricing_engine),
) -> SuccessResponse[MatchPricing]:
    """Force recalculation of pricing for a match.

    This endpoint forces a fresh calculation of pricing and optionally
    saves it to the pricing history table.

    Args:
        match_id: ID of the match
        save_to_history: Whether to save to pricing history (default True)
        db: Database session
        match_repo: Match repository instance
        zone_repo: Zone repository instance
        pricing_engine: Pricing engine instance

    Returns:
        Success response with recalculated pricing

    Raises:
        HTTPException: If match not found or calculation fails
    """
    logger.info(f"Forcing recalculation of pricing for match {match_id}")

    # Get match
    match = match_repo.get_by_id(match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found"
        )

    # Get zones
    zones = zone_repo.get_active_zones()
    if not zones:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No active zones configured"
        )

    try:
        # Calculate pricing
        pricing = pricing_engine.calculate_match_pricing(
            match=match,
            zones=zones,
            current_datetime=datetime.utcnow()
        )

        # Save to history if requested
        if save_to_history:
            pricing_engine.save_pricing_to_history(pricing)
            logger.info(f"Pricing saved to history for match {match_id}")

        logger.info(f"Pricing recalculated for match {match_id}: avg_price={pricing.avg_price:.2f}")
        return create_success_response(
            data=pricing,
            message="Pricing recalculated and saved to history" if save_to_history
                    else "Pricing recalculated"
        )
    except Exception as e:
        logger.error(f"Error recalculating pricing for match {match_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recalculating pricing: {str(e)}"
        )


@router.get(
    "/pricing/match/{match_id}/history",
    response_model=SuccessResponse[List[dict]],
    summary="Get pricing history",
    description="Get historical pricing data for a match",
    responses={
        200: {"description": "Pricing history retrieved successfully"},
        404: {"description": "Match not found"},
        500: {"description": "Error retrieving pricing history"}
    }
)
async def get_pricing_history(
    match_id: str,
    zone_id: Optional[str] = Query(
        default=None,
        description="Filter by specific zone (optional)"
    ),
    hours: int = Query(
        default=24,
        ge=1,
        le=720,
        description="Number of hours of history to retrieve (1-720, default 24)"
    ),
    db: Session = Depends(get_db),
    match_repo: MatchRepository = Depends(get_match_repository),
    pricing_repo: PricingHistoryRepository = Depends(get_pricing_repository),
) -> SuccessResponse[List[dict]]:
    """Get pricing history for a match.

    Retrieves historical pricing data points for a match, optionally
    filtered by zone.

    Args:
        match_id: ID of the match
        zone_id: Optional zone ID to filter by
        hours: Number of hours of history to retrieve (default 24)
        db: Database session
        match_repo: Match repository instance
        pricing_repo: Pricing history repository instance

    Returns:
        Success response with pricing history

    Raises:
        HTTPException: If match not found or error occurs
    """
    logger.info(f"Retrieving pricing history for match {match_id} (last {hours}h)")

    # Verify match exists
    match = match_repo.get_by_id(match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found"
        )

    try:
        # Get pricing history
        history = pricing_repo.get_price_history(
            match_id=match_id,
            zone_id=zone_id,
            hours=hours
        )

        logger.info(f"Retrieved {len(history)} pricing history records for match {match_id}")

        # Convert to dict for JSON serialization
        history_data = [
            {
                "timestamp": record.timestamp.isoformat(),
                "zone_id": record.zone_id,
                "price": record.price,
                "demand_score": record.demand_score,
                "time_factor": record.time_factor,
                "inventory_factor": record.inventory_factor,
                "competition_factor": record.competition_factor,
                "weather_factor": record.weather_factor,
            }
            for record in history
        ]

        return create_success_response(
            data=history_data,
            message=f"Retrieved {len(history_data)} pricing history records"
        )
    except Exception as e:
        logger.error(f"Error retrieving pricing history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving pricing history: {str(e)}"
        )
