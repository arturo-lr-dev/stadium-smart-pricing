"""
Inventory Manager for stadium ticket inventory.

This module contains the InventoryManager class that manages inventory tracking,
sales velocity calculations, and inventory alerts.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.core.cache_strategies import InventoryCacheStrategy
from src.domain.models.zone import Zone
from src.domain.repositories.sale_repository import SaleRepository
from src.domain.repositories.zone_repository import ZoneRepository

logger = logging.getLogger(__name__)


class InventoryManager:
    """
    Inventory Manager for ticket inventory operations.

    This class provides methods to query inventory levels, calculate sales velocity,
    predict sellout times, and generate inventory alerts. Uses InventoryCacheStrategy
    for efficient caching with optimized 2-minute TTL.
    """

    def __init__(
        self,
        sale_repository: SaleRepository,
        zone_repository: ZoneRepository,
        cache_strategy: Optional[InventoryCacheStrategy] = None,
    ):
        """
        Initialize the Inventory Manager.

        Args:
            sale_repository: Repository for sale operations
            zone_repository: Repository for zone operations
            cache_strategy: Cache strategy for inventory (uses default if not provided)
        """
        self.sale_repo = sale_repository
        self.zone_repo = zone_repository
        self.cache = cache_strategy or InventoryCacheStrategy()
        logger.info("InventoryManager initialized with InventoryCacheStrategy")

    def get_zone_inventory(
        self, match_id: str, zone_id: str, use_cache: bool = True
    ) -> Tuple[int, int]:
        """
        Get inventory for a specific zone in a match.

        Args:
            match_id: Match identifier
            zone_id: Zone identifier
            use_cache: Whether to use cache (default True)

        Returns:
            Tuple of (sold_tickets, available_tickets)

        Raises:
            ValueError: If zone not found
        """
        # Check cache first
        if use_cache:
            try:
                cached = self.cache.get(match_id, zone_id)
                if cached:
                    # JSON serialization converts tuples to lists, convert back
                    if isinstance(cached, list) and len(cached) == 2:
                        return tuple(cached)
                    elif isinstance(cached, tuple):
                        return cached
                    else:
                        logger.warning(f"Unexpected cached format for {match_id}/{zone_id}: {type(cached)}")
            except Exception as e:
                logger.warning(f"Cache error, falling back to database: {e}")

        # Get zone to determine capacity
        zone = self.zone_repo.get_by_id(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")

        # Get total sold tickets for this zone
        sold_tickets = self.sale_repo.get_total_sold(match_id, zone_id)

        # Calculate available
        available_tickets = max(0, zone.capacity - sold_tickets)

        logger.debug(
            f"Inventory for match {match_id}, zone {zone_id}: "
            f"{sold_tickets} sold, {available_tickets} available"
        )

        # Cache the result
        if use_cache:
            try:
                self.cache.set(match_id, zone_id, (sold_tickets, available_tickets))
            except Exception as e:
                logger.warning(f"Failed to cache inventory data: {e}")

        return sold_tickets, available_tickets

    def get_match_inventory(
        self, match_id: str, use_cache: bool = True
    ) -> Dict[str, Tuple[int, int]]:
        """
        Get inventory for all zones in a match.

        Uses batch cache operations for efficiency.

        Args:
            match_id: Match identifier
            use_cache: Whether to use cache (default True)

        Returns:
            Dictionary mapping zone_id to (sold_tickets, available_tickets)
        """
        # Get all active zones
        zones = self.zone_repo.get_active_zones()
        zone_ids = [zone.id for zone in zones]

        inventory = {}
        zones_to_fetch = []

        # Try to get cached data in batch
        if use_cache:
            try:
                cached_data = self.cache.get_match_inventory(match_id, zone_ids)

                for zone_id in zone_ids:
                    if zone_id in cached_data:
                        data = cached_data[zone_id]
                        # Convert list to tuple if necessary
                        if isinstance(data, list) and len(data) == 2:
                            inventory[zone_id] = tuple(data)
                        elif isinstance(data, tuple):
                            inventory[zone_id] = data
                    else:
                        zones_to_fetch.append(zone_id)
            except Exception as e:
                logger.warning(f"Cache error in get_match_inventory, falling back to database: {e}")
                zones_to_fetch = zone_ids
        else:
            zones_to_fetch = zone_ids

        # Fetch missing zones from database
        for zone_id in zones_to_fetch:
            sold, available = self.get_zone_inventory(
                match_id, zone_id, use_cache=False
            )
            inventory[zone_id] = (sold, available)

            # Cache individual zone result
            if use_cache:
                self.cache.set(match_id, zone_id, (sold, available))

        logger.debug(
            f"Inventory for match {match_id}: {len(inventory)} zones "
            f"({len(zones_to_fetch)} from DB, {len(zone_ids) - len(zones_to_fetch)} from cache)"
        )

        return inventory

    def get_total_occupancy(self, match_id: str) -> float:
        """
        Get total occupancy percentage for a match.

        Args:
            match_id: Match identifier

        Returns:
            Occupancy percentage (0.0 to 1.0)
        """
        inventory = self.get_match_inventory(match_id)

        total_sold = sum(sold for sold, _ in inventory.values())
        total_capacity = sum(sold + available for sold, available in inventory.values())

        if total_capacity == 0:
            logger.warning(f"Match {match_id} has zero capacity")
            return 0.0

        occupancy = total_sold / total_capacity

        logger.debug(
            f"Total occupancy for match {match_id}: {occupancy:.1%} "
            f"({total_sold}/{total_capacity})"
        )

        return occupancy

    def get_zone_occupancy(self, match_id: str, zone_id: str) -> float:
        """
        Get occupancy percentage for a specific zone.

        Args:
            match_id: Match identifier
            zone_id: Zone identifier

        Returns:
            Occupancy percentage (0.0 to 1.0)
        """
        sold, available = self.get_zone_inventory(match_id, zone_id)
        total_capacity = sold + available

        if total_capacity == 0:
            logger.warning(f"Zone {zone_id} has zero capacity")
            return 0.0

        occupancy = sold / total_capacity

        logger.debug(
            f"Occupancy for zone {zone_id}: {occupancy:.1%} ({sold}/{total_capacity})"
        )

        return occupancy

    def get_sales_velocity(
        self, match_id: str, zone_id: Optional[str] = None, hours: int = 24
    ) -> float:
        """
        Calculate sales velocity (tickets per hour).

        Args:
            match_id: Match identifier
            zone_id: Optional zone identifier (all zones if not specified)
            hours: Number of hours to look back (default 24)

        Returns:
            Sales velocity in tickets per hour
        """
        tickets_sold, velocity = self.sale_repo.get_sales_velocity(
            match_id, zone_id, hours
        )

        logger.debug(
            f"Sales velocity for match {match_id}"
            + (f", zone {zone_id}" if zone_id else "")
            + f": {velocity:.2f} tickets/hour ({tickets_sold} tickets in last {hours}h)"
        )

        return velocity

    def predict_sellout_time(
        self, match_id: str, zone_id: str, velocity_hours: int = 24
    ) -> Optional[datetime]:
        """
        Predict when a zone will sell out based on current velocity.

        Args:
            match_id: Match identifier
            zone_id: Zone identifier
            velocity_hours: Hours to use for velocity calculation (default 24)

        Returns:
            Predicted sellout datetime or None if won't sell out or velocity is zero
        """
        # Get current inventory
        sold, available = self.get_zone_inventory(match_id, zone_id)

        if available == 0:
            logger.info(f"Zone {zone_id} is already sold out")
            return datetime.now()

        # Get sales velocity
        velocity = self.get_sales_velocity(match_id, zone_id, velocity_hours)

        if velocity <= 0:
            logger.debug(
                f"Zero or negative velocity for zone {zone_id}, cannot predict sellout"
            )
            return None

        # Calculate hours until sellout
        hours_to_sellout = available / velocity

        # Calculate sellout datetime
        sellout_time = datetime.now() + timedelta(hours=hours_to_sellout)

        logger.info(
            f"Predicted sellout for zone {zone_id}: {sellout_time.strftime('%Y-%m-%d %H:%M')} "
            f"({hours_to_sellout:.1f} hours from now)"
        )

        return sellout_time

    def check_inventory_alerts(self, match_id: str) -> List[Dict]:
        """
        Check for inventory alerts (high/low occupancy, velocity changes).

        Args:
            match_id: Match identifier

        Returns:
            List of alert dictionaries with type, zone_id, message, and severity
        """
        alerts = []

        # Get all zones inventory
        inventory = self.get_match_inventory(match_id)

        for zone_id, (sold, available) in inventory.items():
            total_capacity = sold + available
            if total_capacity == 0:
                continue

            occupancy = sold / total_capacity

            # Alert: High occupancy (>90%)
            if occupancy > 0.90:
                alerts.append({
                    "type": "high_occupancy",
                    "zone_id": zone_id,
                    "occupancy": occupancy,
                    "sold": sold,
                    "available": available,
                    "message": f"Zone {zone_id} is {occupancy:.1%} full ({available} tickets left)",
                    "severity": "high" if occupancy > 0.95 else "medium"
                })
                logger.info(
                    f"High occupancy alert for zone {zone_id}: {occupancy:.1%}"
                )

            # Alert: Low occupancy (<20%) - may need promotion
            elif occupancy < 0.20:
                # Get sales velocity to see if it's picking up
                velocity = self.get_sales_velocity(match_id, zone_id, hours=24)

                alerts.append({
                    "type": "low_occupancy",
                    "zone_id": zone_id,
                    "occupancy": occupancy,
                    "sold": sold,
                    "available": available,
                    "velocity": velocity,
                    "message": f"Zone {zone_id} has low occupancy: {occupancy:.1%} ({sold} sold)",
                    "severity": "low"
                })
                logger.info(
                    f"Low occupancy alert for zone {zone_id}: {occupancy:.1%}"
                )

            # Alert: Rapid sales velocity
            velocity = self.get_sales_velocity(match_id, zone_id, hours=6)
            if velocity > 10:  # More than 10 tickets/hour
                sellout_time = self.predict_sellout_time(match_id, zone_id, velocity_hours=6)

                alerts.append({
                    "type": "high_velocity",
                    "zone_id": zone_id,
                    "velocity": velocity,
                    "occupancy": occupancy,
                    "sellout_prediction": sellout_time.isoformat() if sellout_time else None,
                    "message": f"Zone {zone_id} selling rapidly: {velocity:.1f} tickets/hour",
                    "severity": "high"
                })
                logger.info(
                    f"High velocity alert for zone {zone_id}: {velocity:.1f} tickets/hour"
                )

        logger.debug(f"Generated {len(alerts)} inventory alerts for match {match_id}")

        return alerts

    def invalidate_cache(self, match_id: str, zone_id: Optional[str] = None) -> None:
        """
        Invalidate cache for a match or specific zone.

        Args:
            match_id: Match identifier
            zone_id: Optional zone identifier (invalidates all zones if not specified)
        """
        try:
            if zone_id:
                # Invalidate specific zone
                self.cache.invalidate(match_id, zone_id)
                logger.info(f"Invalidated cache for match {match_id}, zone {zone_id}")
            else:
                # Invalidate all zones for this match
                self.cache.invalidate_match(match_id)
                logger.info(f"Invalidated all cache for match {match_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

    def warm_cache(self, match_ids: List[str]) -> None:
        """
        Pre-populate cache for multiple matches.

        Args:
            match_ids: List of match identifiers
        """
        logger.info(f"Warming cache for {len(match_ids)} matches")

        for match_id in match_ids:
            try:
                # This will populate the cache as a side effect
                self.get_match_inventory(match_id, use_cache=True)
                logger.debug(f"Warmed cache for match {match_id}")
            except Exception as e:
                logger.error(f"Error warming cache for match {match_id}: {e}")

        logger.info(f"Cache warming completed for {len(match_ids)} matches")

    def get_inventory_summary(self, match_id: str) -> Dict:
        """
        Get a comprehensive inventory summary for a match.

        Args:
            match_id: Match identifier

        Returns:
            Dictionary with inventory statistics
        """
        inventory = self.get_match_inventory(match_id)

        total_sold = sum(sold for sold, _ in inventory.values())
        total_available = sum(available for _, available in inventory.values())
        total_capacity = total_sold + total_available

        # Calculate per-zone statistics
        zone_stats = []
        for zone_id, (sold, available) in inventory.items():
            zone = self.zone_repo.get_by_id(zone_id)
            if not zone:
                continue

            capacity = sold + available
            occupancy = sold / capacity if capacity > 0 else 0.0
            velocity = self.get_sales_velocity(match_id, zone_id, hours=24)

            zone_stats.append({
                "zone_id": zone_id,
                "zone_name": zone.name,
                "sold": sold,
                "available": available,
                "capacity": capacity,
                "occupancy": occupancy,
                "velocity_24h": velocity
            })

        # Sort by occupancy descending
        zone_stats.sort(key=lambda x: x["occupancy"], reverse=True)

        summary = {
            "match_id": match_id,
            "total_sold": total_sold,
            "total_available": total_available,
            "total_capacity": total_capacity,
            "overall_occupancy": total_sold / total_capacity if total_capacity > 0 else 0.0,
            "zones": zone_stats,
            "alerts": self.check_inventory_alerts(match_id),
            "timestamp": datetime.now().isoformat()
        }

        logger.debug(
            f"Generated inventory summary for match {match_id}: "
            f"{summary['overall_occupancy']:.1%} occupancy"
        )

        return summary
