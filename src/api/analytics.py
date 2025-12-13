"""Analytics endpoints for the Smart Pricing API.

This module contains endpoints for analytics, reporting, and insights
about pricing, revenue, and sales performance.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.responses import SuccessResponse, create_success_response
from src.core.dependencies import (
    get_db,
    get_inventory_manager,
    get_match_repository,
    get_pricing_repository,
    get_sale_repository,
    get_zone_repository,
)
from src.domain.models.db_models import PricingHistoryDB, SaleDB
from src.domain.repositories.match_repository import MatchRepository
from src.domain.repositories.pricing_repository import PricingHistoryRepository
from src.domain.repositories.sale_repository import SaleRepository
from src.domain.repositories.zone_repository import ZoneRepository
from src.domain.services.inventory_manager import InventoryManager

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class RevenueData(BaseModel):
    """Revenue data point."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    revenue: float = Field(..., description="Total revenue for the date")
    tickets_sold: int = Field(..., description="Total tickets sold")
    avg_price: float = Field(..., description="Average ticket price")


class OccupancyData(BaseModel):
    """Occupancy statistics."""

    zone_id: str = Field(..., description="Zone identifier")
    zone_name: str = Field(..., description="Zone name")
    total_capacity: int = Field(..., description="Total zone capacity")
    avg_occupancy: float = Field(..., description="Average occupancy percentage")
    total_tickets_sold: int = Field(..., description="Total tickets sold")
    total_revenue: float = Field(..., description="Total revenue generated")


class PriceElasticityData(BaseModel):
    """Price elasticity analysis data."""

    zone_id: str = Field(..., description="Zone identifier")
    avg_price: float = Field(..., description="Average price")
    avg_occupancy: float = Field(..., description="Average occupancy")
    price_range_min: float = Field(..., description="Minimum price observed")
    price_range_max: float = Field(..., description="Maximum price observed")
    estimated_elasticity: float = Field(..., description="Estimated price elasticity coefficient")


# ============================================================================
# REVENUE ANALYTICS
# ============================================================================


@router.get(
    "/analytics/revenue",
    response_model=SuccessResponse[List[RevenueData]],
    summary="Revenue analytics",
    description="Get revenue data aggregated by time period",
    tags=["Analytics"]
)
async def get_revenue_analytics(
    date_from: Optional[datetime] = Query(
        default=None,
        description="Start date (defaults to 30 days ago)"
    ),
    date_to: Optional[datetime] = Query(
        default=None,
        description="End date (defaults to now)"
    ),
    db: Session = Depends(get_db),
    sale_repo: SaleRepository = Depends(get_sale_repository),
) -> SuccessResponse[List[RevenueData]]:
    """Get revenue analytics for a date range.

    Aggregates sales data by date to show revenue trends.

    Args:
        date_from: Start date for the analysis
        date_to: End date for the analysis
        db: Database session
        sale_repo: Sale repository instance

    Returns:
        Success response with revenue data by date
    """
    # Set default date range
    if not date_to:
        date_to = datetime.utcnow()
    if not date_from:
        date_from = date_to - timedelta(days=30)

    logger.info(f"Retrieving revenue analytics from {date_from} to {date_to}")

    try:
        # Query sales grouped by date
        results = db.query(
            func.date(SaleDB.purchase_datetime).label("date"),
            func.sum(SaleDB.total_amount).label("revenue"),
            func.sum(SaleDB.quantity).label("tickets_sold"),
            func.avg(SaleDB.price_per_ticket).label("avg_price")
        ).filter(
            SaleDB.purchase_datetime >= date_from,
            SaleDB.purchase_datetime <= date_to
        ).group_by(
            func.date(SaleDB.purchase_datetime)
        ).order_by(
            func.date(SaleDB.purchase_datetime)
        ).all()

        # Format results
        revenue_data = [
            RevenueData(
                date=row.date.strftime("%Y-%m-%d"),
                revenue=round(float(row.revenue or 0), 2),
                tickets_sold=int(row.tickets_sold or 0),
                avg_price=round(float(row.avg_price or 0), 2)
            )
            for row in results
        ]

        logger.info(f"Retrieved revenue data for {len(revenue_data)} days")
        return create_success_response(
            data=revenue_data,
            message=f"Revenue data retrieved for {len(revenue_data)} days"
        )
    except Exception as e:
        logger.error(f"Error retrieving revenue analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving revenue analytics: {str(e)}"
        )


# ============================================================================
# OCCUPANCY ANALYTICS
# ============================================================================


@router.get(
    "/analytics/occupancy",
    response_model=SuccessResponse[List[OccupancyData]],
    summary="Occupancy analytics",
    description="Get occupancy statistics by zone",
    tags=["Analytics"]
)
async def get_occupancy_analytics(
    match_id: Optional[str] = Query(
        default=None,
        description="Filter by specific match (otherwise shows all matches)"
    ),
    db: Session = Depends(get_db),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
    sale_repo: SaleRepository = Depends(get_sale_repository),
    inventory_manager: InventoryManager = Depends(get_inventory_manager),
) -> SuccessResponse[List[OccupancyData]]:
    """Get occupancy statistics by zone.

    Calculates average occupancy, total sales, and revenue per zone.

    Args:
        match_id: Optional match ID filter
        db: Database session
        zone_repo: Zone repository instance
        sale_repo: Sale repository instance
        inventory_manager: Inventory manager instance

    Returns:
        Success response with occupancy data by zone
    """
    logger.info(f"Retrieving occupancy analytics (match_id={match_id})")

    try:
        # Get all zones
        zones = zone_repo.get_active_zones()
        occupancy_data = []

        for zone in zones:
            # Get sales for this zone
            if match_id:
                sales = sale_repo.get_by_match_and_zone(match_id, zone.id)
            else:
                # Get all sales for this zone across all matches
                query = db.query(SaleDB).filter(SaleDB.zone_id == zone.id)
                sales = query.all()

            # Calculate statistics
            total_tickets_sold = sum(sale.quantity for sale in sales)
            total_revenue = sum(sale.total_amount for sale in sales)

            # Calculate average occupancy
            # This is simplified - in production you'd want to aggregate by match
            avg_occupancy = (total_tickets_sold / zone.capacity * 100) if zone.capacity > 0 else 0

            occupancy_data.append(
                OccupancyData(
                    zone_id=zone.id,
                    zone_name=zone.name,
                    total_capacity=zone.capacity,
                    avg_occupancy=round(avg_occupancy, 2),
                    total_tickets_sold=total_tickets_sold,
                    total_revenue=round(total_revenue, 2)
                )
            )

        logger.info(f"Retrieved occupancy data for {len(occupancy_data)} zones")
        return create_success_response(
            data=occupancy_data,
            message=f"Occupancy data retrieved for {len(occupancy_data)} zones"
        )
    except Exception as e:
        logger.error(f"Error retrieving occupancy analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving occupancy analytics: {str(e)}"
        )


# ============================================================================
# PRICE ELASTICITY ANALYTICS
# ============================================================================


@router.get(
    "/analytics/price-elasticity",
    response_model=SuccessResponse[List[PriceElasticityData]],
    summary="Price elasticity analysis",
    description="Analyze price-demand elasticity by zone and competition",
    tags=["Analytics"]
)
async def get_price_elasticity(
    zone_id: Optional[str] = Query(
        default=None,
        description="Filter by specific zone"
    ),
    competition: Optional[str] = Query(
        default=None,
        description="Filter by competition type"
    ),
    db: Session = Depends(get_db),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
) -> SuccessResponse[List[PriceElasticityData]]:
    """Analyze price elasticity.

    This provides insights into how price changes affect demand
    for different zones.

    Note: This is a simplified analysis. A production implementation
    would use more sophisticated econometric models.

    Args:
        zone_id: Optional zone ID filter
        competition: Optional competition filter
        db: Database session
        zone_repo: Zone repository instance

    Returns:
        Success response with elasticity data
    """
    logger.info(f"Analyzing price elasticity (zone_id={zone_id}, competition={competition})")

    try:
        # Get zones to analyze
        if zone_id:
            zone = zone_repo.get_by_id(zone_id)
            zones = [zone] if zone else []
        else:
            zones = zone_repo.get_active_zones()

        elasticity_data = []

        for zone in zones:
            # Query pricing history for this zone
            query = db.query(
                func.avg(PricingHistoryDB.price).label("avg_price"),
                func.min(PricingHistoryDB.price).label("min_price"),
                func.max(PricingHistoryDB.price).label("max_price"),
                func.avg(PricingHistoryDB.demand_score).label("avg_demand")
            ).filter(
                PricingHistoryDB.zone_id == zone.id
            )

            result = query.first()

            if result and result.avg_price:
                # Simple elasticity estimation
                # In production, you'd use more sophisticated methods
                # like regression analysis of price vs. demand
                price_range = float(result.max_price - result.min_price)
                avg_demand = float(result.avg_demand or 0.5)

                # Rough elasticity estimate: how much does a 1% price change affect demand
                # This is very simplified - real elasticity calculation would need
                # matched price-quantity observations
                estimated_elasticity = -1.0 if price_range > 0 else 0.0

                elasticity_data.append(
                    PriceElasticityData(
                        zone_id=zone.id,
                        avg_price=round(float(result.avg_price), 2),
                        avg_occupancy=round(avg_demand * 100, 2),
                        price_range_min=round(float(result.min_price), 2),
                        price_range_max=round(float(result.max_price), 2),
                        estimated_elasticity=round(estimated_elasticity, 3)
                    )
                )

        logger.info(f"Retrieved elasticity data for {len(elasticity_data)} zones")
        return create_success_response(
            data=elasticity_data,
            message=f"Price elasticity data retrieved for {len(elasticity_data)} zones"
        )
    except Exception as e:
        logger.error(f"Error analyzing price elasticity: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing price elasticity: {str(e)}"
        )


# ============================================================================
# PREDICTIONS & FORECASTS
# ============================================================================


@router.get(
    "/analytics/predictions",
    response_model=SuccessResponse[dict],
    summary="Revenue predictions",
    description="Get revenue and demand predictions for upcoming matches",
    tags=["Analytics"]
)
async def get_predictions(
    days_ahead: int = Query(
        default=30,
        ge=1,
        le=90,
        description="Number of days to predict ahead"
    ),
    match_repo: MatchRepository = Depends(get_match_repository),
    inventory_manager: InventoryManager = Depends(get_inventory_manager),
) -> SuccessResponse[dict]:
    """Get revenue and demand predictions.

    Provides projections of revenue and sellout times for upcoming matches.

    Args:
        days_ahead: Number of days to predict ahead
        match_repo: Match repository instance
        inventory_manager: Inventory manager instance

    Returns:
        Success response with prediction data
    """
    logger.info(f"Generating predictions for next {days_ahead} days")

    try:
        # Get upcoming matches
        matches = match_repo.get_upcoming(days=days_ahead)

        predictions = {
            "total_matches": len(matches),
            "matches": []
        }

        for match in matches:
            match_prediction = {
                "match_id": match.id,
                "match_date": match.match_date.isoformat(),
                "home_team": match.home_team,
                "away_team": match.away_team,
                "days_until_match": match.days_until_match(),
                "zones": []
            }

            # Get inventory for each zone
            try:
                inventory = inventory_manager.get_match_inventory(match.id)
                for zone_id, (sold, available) in inventory.items():
                    # Predict sellout time
                    sellout_time = inventory_manager.predict_sellout_time(match.id, zone_id)

                    zone_prediction = {
                        "zone_id": zone_id,
                        "sold_tickets": sold,
                        "available_tickets": available,
                        "occupancy_percent": round((sold / (sold + available) * 100), 2) if (sold + available) > 0 else 0,
                        "predicted_sellout": sellout_time.isoformat() if sellout_time else None
                    }
                    match_prediction["zones"].append(zone_prediction)

            except Exception as e:
                logger.warning(f"Error getting predictions for match {match.id}: {e}")

            predictions["matches"].append(match_prediction)

        logger.info(f"Generated predictions for {len(matches)} matches")
        return create_success_response(
            data=predictions,
            message=f"Predictions generated for {len(matches)} matches"
        )
    except Exception as e:
        logger.error(f"Error generating predictions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating predictions: {str(e)}"
        )


# ============================================================================
# PERFORMANCE METRICS
# ============================================================================


@router.get(
    "/analytics/performance",
    response_model=SuccessResponse[dict],
    summary="Performance metrics",
    description="Get overall system performance metrics",
    tags=["Analytics"]
)
async def get_performance_metrics(
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Number of days to analyze"
    ),
    db: Session = Depends(get_db),
    match_repo: MatchRepository = Depends(get_match_repository),
) -> SuccessResponse[dict]:
    """Get overall performance metrics.

    Provides high-level KPIs for the pricing system.

    Args:
        days: Number of days to analyze
        db: Database session
        match_repo: Match repository instance

    Returns:
        Success response with performance metrics
    """
    logger.info(f"Calculating performance metrics for last {days} days")

    try:
        date_from = datetime.utcnow() - timedelta(days=days)

        # Calculate total revenue
        revenue_result = db.query(
            func.sum(SaleDB.total_amount).label("total_revenue"),
            func.sum(SaleDB.quantity).label("total_tickets"),
            func.avg(SaleDB.price_per_ticket).label("avg_price")
        ).filter(
            SaleDB.purchase_datetime >= date_from
        ).first()

        # Count matches in period
        matches = match_repo.get_upcoming(days=days)
        total_matches = len(matches)

        # Calculate metrics
        metrics = {
            "period_days": days,
            "total_revenue": round(float(revenue_result.total_revenue or 0), 2),
            "total_tickets_sold": int(revenue_result.total_tickets or 0),
            "avg_ticket_price": round(float(revenue_result.avg_price or 0), 2),
            "total_matches": total_matches,
            "avg_revenue_per_match": round(
                float(revenue_result.total_revenue or 0) / total_matches, 2
            ) if total_matches > 0 else 0,
            "avg_tickets_per_match": round(
                float(revenue_result.total_tickets or 0) / total_matches, 2
            ) if total_matches > 0 else 0
        }

        logger.info(f"Performance metrics calculated: revenue={metrics['total_revenue']}")
        return create_success_response(
            data=metrics,
            message="Performance metrics calculated successfully"
        )
    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating performance metrics: {str(e)}"
        )
