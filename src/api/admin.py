"""Admin endpoints for the Smart Pricing API.

This module contains all administrative endpoints for managing
matches, zones, rules, and system configuration.

Note: In production, these endpoints should be protected with
authentication and authorization.
"""

import logging
from datetime import datetime
from typing import List, Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.responses import SuccessResponse, create_success_response
from src.core.config import get_settings
from src.core.dependencies import (
    get_db,
    get_inventory_manager,
    get_match_repository,
    get_rules_engine,
    get_sale_repository,
    get_zone_repository,
)
from src.domain.models.match import CompetitionType, Match, MatchStatus
from src.domain.models.zone import Zone, ZoneCategory
from src.domain.repositories.match_repository import MatchRepository
from src.domain.repositories.sale_repository import SaleRepository
from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.services.inventory_manager import InventoryManager
from src.domain.services.rules_engine import RulesEngine

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class MatchCreate(BaseModel):
    """Request model for creating a new match."""

    id: str = Field(..., description="Unique match identifier")
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    competition: CompetitionType = Field(..., description="Competition type")
    match_date: datetime = Field(..., description="Match date and time")
    venue: str = Field(default="Son Moix", description="Venue name")
    capacity: int = Field(default=23142, description="Total stadium capacity")
    is_derby: bool = Field(default=False, description="Whether it's a derby match")
    is_holiday: bool = Field(default=False, description="Whether it's on a holiday")
    home_position: Optional[int] = Field(default=None, description="Home team league position")
    away_position: Optional[int] = Field(default=None, description="Away team league position")
    status: MatchStatus = Field(default=MatchStatus.SCHEDULED, description="Match status")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "match_2024_001",
                "home_team": "RCD Mallorca",
                "away_team": "FC Barcelona",
                "competition": "la_liga",
                "match_date": "2024-12-20T21:00:00Z",
                "venue": "Son Moix",
                "capacity": 23142,
                "is_derby": False,
                "is_holiday": False,
                "home_position": 10,
                "away_position": 1,
                "status": "scheduled"
            }
        }


class MatchUpdate(BaseModel):
    """Request model for updating a match."""

    home_team: Optional[str] = None
    away_team: Optional[str] = None
    competition: Optional[CompetitionType] = None
    match_date: Optional[datetime] = None
    venue: Optional[str] = None
    capacity: Optional[int] = None
    is_derby: Optional[bool] = None
    is_holiday: Optional[bool] = None
    home_position: Optional[int] = None
    away_position: Optional[int] = None
    status: Optional[MatchStatus] = None


class ZoneUpdate(BaseModel):
    """Request model for updating a zone."""

    name: Optional[str] = None
    category: Optional[ZoneCategory] = None
    capacity: Optional[int] = None
    base_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    price_multiplier: Optional[float] = None
    is_active: Optional[bool] = None


# ============================================================================
# RULES MANAGEMENT ENDPOINTS
# ============================================================================


@router.post(
    "/admin/rules/reload",
    response_model=SuccessResponse[dict],
    summary="Reload pricing rules",
    description="Reload pricing rules configuration from YAML file",
    tags=["Admin - Rules"]
)
async def reload_rules(
    rules_engine: RulesEngine = Depends(get_rules_engine),
) -> SuccessResponse[dict]:
    """Reload pricing rules from configuration file.

    This endpoint triggers a hot-reload of the pricing rules,
    allowing configuration changes without restarting the service.

    Args:
        rules_engine: Rules engine instance

    Returns:
        Success response confirming reload
    """
    logger.info("Reloading pricing rules")

    try:
        rules_engine.reload_rules()
        logger.info("Pricing rules reloaded successfully")
        return create_success_response(
            data={"reloaded_at": datetime.utcnow().isoformat()},
            message="Pricing rules reloaded successfully"
        )
    except Exception as e:
        logger.error(f"Error reloading rules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reloading rules: {str(e)}"
        )


@router.get(
    "/admin/rules",
    response_model=SuccessResponse[dict],
    summary="Get pricing rules",
    description="Get current pricing rules configuration",
    tags=["Admin - Rules"]
)
async def get_rules(
    rules_engine: RulesEngine = Depends(get_rules_engine),
) -> SuccessResponse[dict]:
    """Get current pricing rules configuration.

    Returns the complete pricing rules configuration currently in use.

    Args:
        rules_engine: Rules engine instance

    Returns:
        Success response with rules configuration
    """
    logger.info("Retrieving pricing rules")

    try:
        rules = rules_engine.rules
        return create_success_response(
            data=rules,
            message="Pricing rules retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error retrieving rules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving rules: {str(e)}"
        )


# ============================================================================
# ZONE MANAGEMENT ENDPOINTS
# ============================================================================


@router.get(
    "/admin/zones",
    response_model=SuccessResponse[List[Zone]],
    summary="List all zones",
    description="Get a list of all stadium zones with their configuration",
    tags=["Admin - Zones"]
)
async def list_zones(
    active_only: bool = Query(
        default=False,
        description="Filter to show only active zones"
    ),
    category: Optional[ZoneCategory] = Query(
        default=None,
        description="Filter by zone category"
    ),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
) -> SuccessResponse[List[Zone]]:
    """List all stadium zones.

    Args:
        active_only: If True, only return active zones
        category: Optional category filter
        zone_repo: Zone repository instance

    Returns:
        Success response with list of zones
    """
    logger.info(f"Listing zones (active_only={active_only}, category={category})")

    try:
        if active_only:
            zones = zone_repo.get_active_zones()
        elif category:
            zones = zone_repo.get_by_category(category)
        else:
            zones = zone_repo.get_all()

        logger.info(f"Retrieved {len(zones)} zones")
        return create_success_response(
            data=zones,
            message=f"Retrieved {len(zones)} zones"
        )
    except Exception as e:
        logger.error(f"Error listing zones: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing zones: {str(e)}"
        )


@router.get(
    "/admin/zones/{zone_id}",
    response_model=SuccessResponse[Zone],
    summary="Get zone details",
    description="Get details of a specific zone",
    tags=["Admin - Zones"]
)
async def get_zone(
    zone_id: str,
    zone_repo: ZoneRepository = Depends(get_zone_repository),
) -> SuccessResponse[Zone]:
    """Get details of a specific zone.

    Args:
        zone_id: ID of the zone
        zone_repo: Zone repository instance

    Returns:
        Success response with zone details

    Raises:
        HTTPException: If zone not found
    """
    logger.info(f"Retrieving zone {zone_id}")

    zone = zone_repo.get_by_id(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found"
        )

    return create_success_response(
        data=zone,
        message="Zone retrieved successfully"
    )


@router.put(
    "/admin/zones/{zone_id}",
    response_model=SuccessResponse[Zone],
    summary="Update zone configuration",
    description="Update configuration of a specific zone",
    tags=["Admin - Zones"]
)
async def update_zone(
    zone_id: str,
    zone_update: ZoneUpdate,
    db: Session = Depends(get_db),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
) -> SuccessResponse[Zone]:
    """Update zone configuration.

    Args:
        zone_id: ID of the zone to update
        zone_update: Updated zone data
        db: Database session
        zone_repo: Zone repository instance

    Returns:
        Success response with updated zone

    Raises:
        HTTPException: If zone not found or validation fails
    """
    logger.info(f"Updating zone {zone_id}")

    # Get existing zone
    zone = zone_repo.get_by_id(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found"
        )

    # Update fields
    update_data = zone_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)

    # Validate price constraints
    if zone.min_price > zone.base_price or zone.base_price > zone.max_price:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid price configuration: min_price <= base_price <= max_price required"
        )

    try:
        updated_zone = zone_repo.update(zone_id, zone)
        db.commit()
        logger.info(f"Zone {zone_id} updated successfully")
        return create_success_response(
            data=updated_zone,
            message="Zone updated successfully"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating zone {zone_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating zone: {str(e)}"
        )


# ============================================================================
# MATCH MANAGEMENT ENDPOINTS
# ============================================================================


@router.get(
    "/admin/matches",
    response_model=SuccessResponse[List[Match]],
    summary="List matches",
    description="Get a list of matches with optional filters",
    tags=["Admin - Matches"]
)
async def list_matches(
    competition: Optional[CompetitionType] = Query(default=None, description="Filter by competition"),
    status_filter: Optional[MatchStatus] = Query(default=None, description="Filter by status", alias="status"),
    days_ahead: Optional[int] = Query(default=None, ge=1, le=365, description="Filter upcoming matches"),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of records to return"),
    match_repo: MatchRepository = Depends(get_match_repository),
) -> SuccessResponse[List[Match]]:
    """List matches with optional filters.

    Args:
        competition: Optional competition filter
        status_filter: Optional status filter
        days_ahead: If specified, only return matches in next N days
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        match_repo: Match repository instance

    Returns:
        Success response with list of matches
    """
    logger.info(f"Listing matches (competition={competition}, status={status_filter}, days_ahead={days_ahead})")

    try:
        if days_ahead:
            matches = match_repo.get_upcoming(days=days_ahead)
        elif competition:
            matches = match_repo.get_by_competition(competition)
        elif status_filter:
            matches = match_repo.get_by_status(status_filter)
        else:
            matches = match_repo.get_all(skip=skip, limit=limit)

        logger.info(f"Retrieved {len(matches)} matches")
        return create_success_response(
            data=matches,
            message=f"Retrieved {len(matches)} matches"
        )
    except Exception as e:
        logger.error(f"Error listing matches: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing matches: {str(e)}"
        )


@router.post(
    "/admin/matches",
    response_model=SuccessResponse[Match],
    summary="Create new match",
    description="Create a new match in the system",
    tags=["Admin - Matches"],
    status_code=status.HTTP_201_CREATED
)
async def create_match(
    match_data: MatchCreate,
    db: Session = Depends(get_db),
    match_repo: MatchRepository = Depends(get_match_repository),
) -> SuccessResponse[Match]:
    """Create a new match.

    Args:
        match_data: Match data
        db: Database session
        match_repo: Match repository instance

    Returns:
        Success response with created match

    Raises:
        HTTPException: If match already exists or validation fails
    """
    logger.info(f"Creating new match: {match_data.id}")

    # Check if match already exists
    existing = match_repo.get_by_id(match_data.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Match {match_data.id} already exists"
        )

    try:
        # Create match domain model
        match = Match(**match_data.model_dump())

        # Save to database
        created_match = match_repo.create(match)
        db.commit()

        logger.info(f"Match {match_data.id} created successfully")
        return create_success_response(
            data=created_match,
            message="Match created successfully"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating match: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating match: {str(e)}"
        )


@router.put(
    "/admin/matches/{match_id}",
    response_model=SuccessResponse[Match],
    summary="Update match",
    description="Update an existing match",
    tags=["Admin - Matches"]
)
async def update_match(
    match_id: str,
    match_update: MatchUpdate,
    db: Session = Depends(get_db),
    match_repo: MatchRepository = Depends(get_match_repository),
) -> SuccessResponse[Match]:
    """Update an existing match.

    Args:
        match_id: ID of the match to update
        match_update: Updated match data
        db: Database session
        match_repo: Match repository instance

    Returns:
        Success response with updated match

    Raises:
        HTTPException: If match not found
    """
    logger.info(f"Updating match {match_id}")

    # Get existing match
    match = match_repo.get_by_id(match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found"
        )

    # Update fields
    update_data = match_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(match, field, value)

    try:
        updated_match = match_repo.update(match_id, match)
        db.commit()
        logger.info(f"Match {match_id} updated successfully")
        return create_success_response(
            data=updated_match,
            message="Match updated successfully"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating match {match_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating match: {str(e)}"
        )


# ============================================================================
# SALES & INVENTORY ENDPOINTS
# ============================================================================


@router.get(
    "/admin/sales/summary",
    response_model=SuccessResponse[dict],
    summary="Get sales summary",
    description="Get aggregated sales summary for matches",
    tags=["Admin - Sales"]
)
async def get_sales_summary(
    match_id: Optional[str] = Query(default=None, description="Filter by specific match"),
    sale_repo: SaleRepository = Depends(get_sale_repository),
) -> SuccessResponse[dict]:
    """Get sales summary.

    Args:
        match_id: Optional match ID to filter by
        sale_repo: Sale repository instance

    Returns:
        Success response with sales summary
    """
    logger.info(f"Retrieving sales summary (match_id={match_id})")

    try:
        if match_id:
            sales = sale_repo.get_by_match(match_id)
        else:
            sales = sale_repo.get_all(limit=1000)

        # Calculate summary
        total_sales = len(sales)
        total_tickets = sum(sale.quantity for sale in sales)
        total_revenue = sum(sale.total_amount for sale in sales)
        avg_ticket_price = total_revenue / total_tickets if total_tickets > 0 else 0

        summary = {
            "total_sales": total_sales,
            "total_tickets": total_tickets,
            "total_revenue": round(total_revenue, 2),
            "avg_ticket_price": round(avg_ticket_price, 2),
        }

        logger.info(f"Sales summary: {summary}")
        return create_success_response(
            data=summary,
            message="Sales summary retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error retrieving sales summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving sales summary: {str(e)}"
        )


@router.get(
    "/admin/pricing/alerts",
    response_model=SuccessResponse[List[dict]],
    summary="Get pricing alerts",
    description="Get inventory and pricing alerts for matches",
    tags=["Admin - Pricing"]
)
async def get_pricing_alerts(
    match_id: Optional[str] = Query(default=None, description="Filter by specific match"),
    db: Session = Depends(get_db),
    inventory_manager: InventoryManager = Depends(get_inventory_manager),
    match_repo: MatchRepository = Depends(get_match_repository),
) -> SuccessResponse[List[dict]]:
    """Get pricing and inventory alerts.

    Returns alerts for high/low occupancy, slow sales, etc.

    Args:
        match_id: Optional match ID to filter by
        db: Database session
        inventory_manager: Inventory manager instance
        match_repo: Match repository instance

    Returns:
        Success response with list of alerts
    """
    logger.info(f"Retrieving pricing alerts (match_id={match_id})")

    try:
        if match_id:
            matches = [match_repo.get_by_id(match_id)]
            if not matches[0]:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Match {match_id} not found"
                )
        else:
            # Get upcoming matches
            matches = match_repo.get_upcoming(days=30)

        # Collect alerts for all matches
        all_alerts = []
        for match in matches:
            if match:
                alerts = inventory_manager.check_inventory_alerts(match.id)
                all_alerts.extend(alerts)

        logger.info(f"Found {len(all_alerts)} alerts")
        return create_success_response(
            data=all_alerts,
            message=f"Retrieved {len(all_alerts)} alerts"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving alerts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving alerts: {str(e)}"
        )
