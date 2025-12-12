"""Pricing history repository for database operations.

This module provides repository operations for pricing history records.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from uuid import uuid4

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.core.exceptions import DatabaseError
from src.core.logging import get_logger
from src.domain.models.db_models import PricingHistoryDB
from src.domain.models.pricing import PricingFactors, ZonePricing, MatchPricing
from src.domain.repositories.base_repository import BaseRepository

logger = get_logger(__name__)


class PricingHistoryRepository(BaseRepository[PricingHistoryDB, Dict]):
    """Repository for PricingHistory entities.

    Provides database operations for pricing history and analytics.
    Note: This repository works with dictionaries rather than a dedicated
    domain model, as pricing history is primarily for analytics.
    """

    def __init__(self, session: Session):
        """Initialize pricing history repository.

        Args:
            session: Database session
        """
        super().__init__(PricingHistoryDB, session)

    def _to_domain(self, db_entity: PricingHistoryDB) -> Dict:
        """Convert database model to dictionary.

        Args:
            db_entity: Database pricing history entity

        Returns:
            Dictionary representation
        """
        return {
            "id": db_entity.id,
            "match_id": db_entity.match_id,
            "zone_id": db_entity.zone_id,
            "price": db_entity.price,
            "demand_score": db_entity.demand_score,
            "time_factor": db_entity.time_factor,
            "inventory_factor": db_entity.inventory_factor,
            "competition_factor": db_entity.competition_factor,
            "rival_factor": db_entity.rival_factor,
            "weather_factor": db_entity.weather_factor,
            "special_conditions": db_entity.special_conditions or {},
            "sold_tickets": db_entity.sold_tickets,
            "available_tickets": db_entity.available_tickets,
            "occupancy_percent": db_entity.occupancy_percent,
            "timestamp": db_entity.timestamp,
        }

    def _to_db(self, domain_entity: Dict) -> PricingHistoryDB:
        """Convert dictionary to database model.

        Args:
            domain_entity: Dictionary representation

        Returns:
            Database pricing history entity
        """
        return PricingHistoryDB(
            id=domain_entity.get("id", str(uuid4())),
            match_id=domain_entity["match_id"],
            zone_id=domain_entity["zone_id"],
            price=domain_entity["price"],
            demand_score=domain_entity.get("demand_score"),
            time_factor=domain_entity.get("time_factor"),
            inventory_factor=domain_entity.get("inventory_factor"),
            competition_factor=domain_entity.get("competition_factor"),
            rival_factor=domain_entity.get("rival_factor"),
            weather_factor=domain_entity.get("weather_factor"),
            special_conditions=domain_entity.get("special_conditions"),
            sold_tickets=domain_entity.get("sold_tickets"),
            available_tickets=domain_entity.get("available_tickets"),
            occupancy_percent=domain_entity.get("occupancy_percent"),
        )

    def get_by_match(self, match_id: str, limit: int = 100) -> List[Dict]:
        """Get pricing history for a match.

        Args:
            match_id: Match identifier
            limit: Maximum number of records (default 100)

        Returns:
            List of pricing history records ordered by timestamp desc

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            records = (
                self.session.query(PricingHistoryDB)
                .filter(PricingHistoryDB.match_id == match_id)
                .order_by(desc(PricingHistoryDB.timestamp))
                .limit(limit)
                .all()
            )

            logger.debug(f"Retrieved {len(records)} pricing history records for match {match_id}")
            return [self._to_domain(record) for record in records]

        except SQLAlchemyError as e:
            logger.error(f"Error getting pricing history by match: {e}")
            raise DatabaseError(f"Failed to get pricing history by match: {e}")

    def get_latest_price(self, match_id: str, zone_id: str) -> Optional[Dict]:
        """Get latest price for a match and zone.

        Args:
            match_id: Match identifier
            zone_id: Zone identifier

        Returns:
            Latest pricing record or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            record = (
                self.session.query(PricingHistoryDB)
                .filter(
                    and_(
                        PricingHistoryDB.match_id == match_id,
                        PricingHistoryDB.zone_id == zone_id,
                    )
                )
                .order_by(desc(PricingHistoryDB.timestamp))
                .first()
            )

            if record:
                logger.debug(f"Retrieved latest price for match {match_id}, zone {zone_id}: €{record.price}")
                return self._to_domain(record)
            else:
                logger.debug(f"No pricing history found for match {match_id}, zone {zone_id}")
                return None

        except SQLAlchemyError as e:
            logger.error(f"Error getting latest price: {e}")
            raise DatabaseError(f"Failed to get latest price: {e}")

    def get_price_history(
        self, match_id: str, zone_id: str, hours: int = 24
    ) -> List[Dict]:
        """Get price history for a match and zone over time period.

        Args:
            match_id: Match identifier
            zone_id: Zone identifier
            hours: Number of hours to look back (default 24)

        Returns:
            List of pricing records ordered by timestamp asc

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            records = (
                self.session.query(PricingHistoryDB)
                .filter(
                    and_(
                        PricingHistoryDB.match_id == match_id,
                        PricingHistoryDB.zone_id == zone_id,
                        PricingHistoryDB.timestamp >= cutoff_time,
                    )
                )
                .order_by(PricingHistoryDB.timestamp.asc())
                .all()
            )

            logger.debug(
                f"Retrieved {len(records)} pricing history records for match {match_id}, "
                f"zone {zone_id} over last {hours}h"
            )
            return [self._to_domain(record) for record in records]

        except SQLAlchemyError as e:
            logger.error(f"Error getting price history: {e}")
            raise DatabaseError(f"Failed to get price history: {e}")

    def save_pricing(self, pricing: MatchPricing) -> List[Dict]:
        """Save pricing history for a match.

        Creates pricing history records for all zones in the match pricing.

        Args:
            pricing: Match pricing with all zones

        Returns:
            List of created pricing history records

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            created_records = []

            for zone_pricing in pricing.zones:
                record = PricingHistoryDB(
                    id=str(uuid4()),
                    match_id=pricing.match_id,
                    zone_id=zone_pricing.zone_id,
                    price=zone_pricing.current_price,
                    demand_score=zone_pricing.factors.demand_score,
                    time_factor=zone_pricing.factors.time_factor,
                    inventory_factor=zone_pricing.factors.inventory_factor,
                    competition_factor=zone_pricing.factors.competition_factor,
                    rival_factor=zone_pricing.factors.rival_factor,
                    weather_factor=zone_pricing.factors.weather_factor,
                    special_conditions=zone_pricing.factors.special_conditions,
                    sold_tickets=zone_pricing.sold_tickets,
                    available_tickets=zone_pricing.available_tickets,
                    occupancy_percent=zone_pricing.occupancy_percent,
                )

                self.session.add(record)
                created_records.append(record)

            self.session.commit()

            logger.info(
                f"Saved {len(created_records)} pricing history records for match {pricing.match_id}"
            )
            return [self._to_domain(record) for record in created_records]

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error saving pricing history: {e}")
            raise DatabaseError(f"Failed to save pricing history: {e}")

    def save_zone_pricing(self, match_id: str, zone_pricing: ZonePricing) -> Dict:
        """Save pricing history for a single zone.

        Args:
            match_id: Match identifier
            zone_pricing: Zone pricing information

        Returns:
            Created pricing history record

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            record = PricingHistoryDB(
                id=str(uuid4()),
                match_id=match_id,
                zone_id=zone_pricing.zone_id,
                price=zone_pricing.current_price,
                demand_score=zone_pricing.factors.demand_score,
                time_factor=zone_pricing.factors.time_factor,
                inventory_factor=zone_pricing.factors.inventory_factor,
                competition_factor=zone_pricing.factors.competition_factor,
                rival_factor=zone_pricing.factors.rival_factor,
                weather_factor=zone_pricing.factors.weather_factor,
                special_conditions=zone_pricing.factors.special_conditions,
                sold_tickets=zone_pricing.sold_tickets,
                available_tickets=zone_pricing.available_tickets,
                occupancy_percent=zone_pricing.occupancy_percent,
            )

            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)

            logger.info(
                f"Saved pricing history for match {match_id}, zone {zone_pricing.zone_id}: €{zone_pricing.current_price}"
            )
            return self._to_domain(record)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error saving zone pricing history: {e}")
            raise DatabaseError(f"Failed to save zone pricing history: {e}")

    def get_price_changes(
        self, match_id: str, zone_id: str, min_change_percent: float = 5.0
    ) -> List[Dict]:
        """Get significant price changes for a match and zone.

        Args:
            match_id: Match identifier
            zone_id: Zone identifier
            min_change_percent: Minimum percentage change to include (default 5.0)

        Returns:
            List of records with significant price changes

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            records = (
                self.session.query(PricingHistoryDB)
                .filter(
                    and_(
                        PricingHistoryDB.match_id == match_id,
                        PricingHistoryDB.zone_id == zone_id,
                    )
                )
                .order_by(PricingHistoryDB.timestamp.asc())
                .all()
            )

            if len(records) < 2:
                return []

            significant_changes = []
            previous_price = records[0].price

            for record in records[1:]:
                change_percent = abs((record.price - previous_price) / previous_price * 100)
                if change_percent >= min_change_percent:
                    record_dict = self._to_domain(record)
                    record_dict["price_change_percent"] = change_percent
                    record_dict["previous_price"] = previous_price
                    significant_changes.append(record_dict)
                previous_price = record.price

            logger.debug(
                f"Found {len(significant_changes)} significant price changes "
                f"(>={min_change_percent}%) for match {match_id}, zone {zone_id}"
            )
            return significant_changes

        except SQLAlchemyError as e:
            logger.error(f"Error getting price changes: {e}")
            raise DatabaseError(f"Failed to get price changes: {e}")

    def get_average_price(
        self, match_id: str, zone_id: Optional[str] = None, hours: int = 24
    ) -> float:
        """Get average price over time period.

        Args:
            match_id: Match identifier
            zone_id: Optional zone identifier
            hours: Number of hours to look back (default 24)

        Returns:
            Average price

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            query = self.session.query(PricingHistoryDB).filter(
                and_(
                    PricingHistoryDB.match_id == match_id,
                    PricingHistoryDB.timestamp >= cutoff_time,
                )
            )

            if zone_id:
                query = query.filter(PricingHistoryDB.zone_id == zone_id)

            records = query.all()

            if not records:
                return 0.0

            avg_price = sum(r.price for r in records) / len(records)

            logger.debug(f"Average price over last {hours}h: €{avg_price:.2f}")
            return avg_price

        except SQLAlchemyError as e:
            logger.error(f"Error getting average price: {e}")
            raise DatabaseError(f"Failed to get average price: {e}")

    def delete_old_records(self, days: int = 90) -> int:
        """Delete pricing history records older than specified days.

        Args:
            days: Number of days to keep (default 90)

        Returns:
            Number of records deleted

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            count = (
                self.session.query(PricingHistoryDB)
                .filter(PricingHistoryDB.timestamp < cutoff_date)
                .delete()
            )

            self.session.commit()

            logger.info(f"Deleted {count} pricing history records older than {days} days")
            return count

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error deleting old pricing records: {e}")
            raise DatabaseError(f"Failed to delete old pricing records: {e}")
