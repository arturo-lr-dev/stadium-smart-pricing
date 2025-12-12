"""Zone repository for database operations.

This module provides repository operations specific to Zone entities.
"""

from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.core.exceptions import DatabaseError
from src.core.logging import get_logger
from src.domain.models.db_models import ZoneDB
from src.domain.models.zone import Zone, ZoneCategory
from src.domain.repositories.base_repository import BaseRepository

logger = get_logger(__name__)


class ZoneRepository(BaseRepository[ZoneDB, Zone]):
    """Repository for Zone entities.

    Provides database operations specific to stadium zones.
    """

    def __init__(self, session: Session):
        """Initialize zone repository.

        Args:
            session: Database session
        """
        super().__init__(ZoneDB, session)

    def _to_domain(self, db_entity: ZoneDB) -> Zone:
        """Convert database model to domain model.

        Args:
            db_entity: Database zone entity

        Returns:
            Domain Zone model
        """
        return Zone(
            id=db_entity.id,
            name=db_entity.name,
            category=db_entity.category,
            capacity=db_entity.capacity,
            base_price=db_entity.base_price,
            min_price=db_entity.min_price,
            max_price=db_entity.max_price,
            price_multiplier=db_entity.price_multiplier,
            is_active=db_entity.is_active,
            description=db_entity.description,
            amenities=db_entity.amenities if db_entity.amenities else None,
        )

    def _to_db(self, domain_entity: Zone) -> ZoneDB:
        """Convert domain model to database model.

        Args:
            domain_entity: Domain Zone model

        Returns:
            Database zone entity
        """
        return ZoneDB(
            id=domain_entity.id,
            name=domain_entity.name,
            category=domain_entity.category,
            capacity=domain_entity.capacity,
            base_price=domain_entity.base_price,
            min_price=domain_entity.min_price,
            max_price=domain_entity.max_price,
            price_multiplier=domain_entity.price_multiplier,
            is_active=domain_entity.is_active,
            description=domain_entity.description,
            amenities=domain_entity.amenities,
        )

    def get_by_category(self, category: str) -> List[Zone]:
        """Get zones by category.

        Args:
            category: Zone category (e.g., "vip", "standard")

        Returns:
            List of zones in category ordered by name

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            zones = (
                self.session.query(ZoneDB)
                .filter(ZoneDB.category == category)
                .order_by(ZoneDB.name.asc())
                .all()
            )

            logger.debug(f"Retrieved {len(zones)} zones for category {category}")
            return [self._to_domain(zone) for zone in zones]

        except SQLAlchemyError as e:
            logger.error(f"Error getting zones by category: {e}")
            raise DatabaseError(f"Failed to get zones by category: {e}")

    def get_active_zones(self) -> List[Zone]:
        """Get all active zones.

        Returns:
            List of active zones ordered by category and name

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            zones = (
                self.session.query(ZoneDB)
                .filter(ZoneDB.is_active == True)
                .order_by(ZoneDB.category.asc(), ZoneDB.name.asc())
                .all()
            )

            logger.debug(f"Retrieved {len(zones)} active zones")
            return [self._to_domain(zone) for zone in zones]

        except SQLAlchemyError as e:
            logger.error(f"Error getting active zones: {e}")
            raise DatabaseError(f"Failed to get active zones: {e}")

    def get_inactive_zones(self) -> List[Zone]:
        """Get all inactive zones.

        Returns:
            List of inactive zones ordered by name

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            zones = (
                self.session.query(ZoneDB)
                .filter(ZoneDB.is_active == False)
                .order_by(ZoneDB.name.asc())
                .all()
            )

            logger.debug(f"Retrieved {len(zones)} inactive zones")
            return [self._to_domain(zone) for zone in zones]

        except SQLAlchemyError as e:
            logger.error(f"Error getting inactive zones: {e}")
            raise DatabaseError(f"Failed to get inactive zones: {e}")

    def get_by_price_range(self, min_price: float, max_price: float) -> List[Zone]:
        """Get zones within a base price range.

        Args:
            min_price: Minimum base price
            max_price: Maximum base price

        Returns:
            List of zones within price range ordered by base price

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            zones = (
                self.session.query(ZoneDB)
                .filter(
                    and_(
                        ZoneDB.base_price >= min_price,
                        ZoneDB.base_price <= max_price,
                        ZoneDB.is_active == True
                    )
                )
                .order_by(ZoneDB.base_price.asc())
                .all()
            )

            logger.debug(
                f"Retrieved {len(zones)} zones with base price between {min_price} and {max_price}"
            )
            return [self._to_domain(zone) for zone in zones]

        except SQLAlchemyError as e:
            logger.error(f"Error getting zones by price range: {e}")
            raise DatabaseError(f"Failed to get zones by price range: {e}")

    def get_total_capacity(self, active_only: bool = True) -> int:
        """Get total stadium capacity.

        Args:
            active_only: Only count active zones (default True)

        Returns:
            Total capacity across all zones

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(ZoneDB)

            if active_only:
                query = query.filter(ZoneDB.is_active == True)

            zones = query.all()
            total = sum(zone.capacity for zone in zones)

            logger.debug(f"Total capacity: {total} (active_only={active_only})")
            return total

        except SQLAlchemyError as e:
            logger.error(f"Error getting total capacity: {e}")
            raise DatabaseError(f"Failed to get total capacity: {e}")

    def activate_zone(self, zone_id: str) -> Optional[Zone]:
        """Activate a zone.

        Args:
            zone_id: Zone ID

        Returns:
            Updated zone or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            zone = self.session.query(ZoneDB).filter(ZoneDB.id == zone_id).first()

            if zone is None:
                logger.warning(f"Zone {zone_id} not found for activation")
                return None

            if zone.is_active:
                logger.info(f"Zone {zone_id} is already active")
            else:
                zone.is_active = True
                self.session.commit()
                self.session.refresh(zone)
                logger.info(f"Activated zone {zone_id}")

            return self._to_domain(zone)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error activating zone: {e}")
            raise DatabaseError(f"Failed to activate zone: {e}")

    def deactivate_zone(self, zone_id: str) -> Optional[Zone]:
        """Deactivate a zone.

        Args:
            zone_id: Zone ID

        Returns:
            Updated zone or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            zone = self.session.query(ZoneDB).filter(ZoneDB.id == zone_id).first()

            if zone is None:
                logger.warning(f"Zone {zone_id} not found for deactivation")
                return None

            if not zone.is_active:
                logger.info(f"Zone {zone_id} is already inactive")
            else:
                zone.is_active = False
                self.session.commit()
                self.session.refresh(zone)
                logger.info(f"Deactivated zone {zone_id}")

            return self._to_domain(zone)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error deactivating zone: {e}")
            raise DatabaseError(f"Failed to deactivate zone: {e}")

    def update_prices(
        self,
        zone_id: str,
        base_price: Optional[float] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> Optional[Zone]:
        """Update zone prices.

        Args:
            zone_id: Zone ID
            base_price: New base price (optional)
            min_price: New minimum price (optional)
            max_price: New maximum price (optional)

        Returns:
            Updated zone or None if not found

        Raises:
            DatabaseError: If database operation fails
            ValueError: If price constraints are violated
        """
        try:
            zone = self.session.query(ZoneDB).filter(ZoneDB.id == zone_id).first()

            if zone is None:
                logger.warning(f"Zone {zone_id} not found for price update")
                return None

            # Validate price constraints
            updated_min = min_price if min_price is not None else zone.min_price
            updated_base = base_price if base_price is not None else zone.base_price
            updated_max = max_price if max_price is not None else zone.max_price

            if not (updated_min <= updated_base <= updated_max):
                raise ValueError(
                    f"Price constraints violated: min ({updated_min}) <= "
                    f"base ({updated_base}) <= max ({updated_max})"
                )

            # Update prices
            if min_price is not None:
                zone.min_price = min_price
            if base_price is not None:
                zone.base_price = base_price
            if max_price is not None:
                zone.max_price = max_price

            self.session.commit()
            self.session.refresh(zone)

            logger.info(f"Updated prices for zone {zone_id}")
            return self._to_domain(zone)

        except ValueError as e:
            logger.error(f"Price validation error: {e}")
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error updating zone prices: {e}")
            raise DatabaseError(f"Failed to update zone prices: {e}")
