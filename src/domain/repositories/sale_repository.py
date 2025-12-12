"""Sale repository for database operations.

This module provides repository operations specific to Sale entities
with analytics and aggregation capabilities.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.core.exceptions import DatabaseError
from src.core.logging import get_logger
from src.domain.models.db_models import SaleDB, CustomerType as DBCustomerType, PaymentStatus as DBPaymentStatus
from src.domain.models.sale import Sale, CustomerType, PaymentStatus
from src.domain.repositories.base_repository import BaseRepository

logger = get_logger(__name__)


class SaleRepository(BaseRepository[SaleDB, Sale]):
    """Repository for Sale entities.

    Provides database operations and analytics for ticket sales.
    """

    def __init__(self, session: Session):
        """Initialize sale repository.

        Args:
            session: Database session
        """
        super().__init__(SaleDB, session)

    def _to_domain(self, db_entity: SaleDB) -> Sale:
        """Convert database model to domain model.

        Args:
            db_entity: Database sale entity

        Returns:
            Domain Sale model
        """
        return Sale(
            id=db_entity.id,
            match_id=db_entity.match_id,
            zone_id=db_entity.zone_id,
            quantity=db_entity.quantity,
            price_per_ticket=db_entity.price_per_ticket,
            total_amount=db_entity.total_amount,
            customer_type=CustomerType(db_entity.customer_type.value),
            customer_id=db_entity.customer_id,
            purchase_datetime=db_entity.purchase_datetime,
            payment_status=PaymentStatus(db_entity.payment_status.value),
            payment_method=db_entity.payment_method,
        )

    def _to_db(self, domain_entity: Sale) -> SaleDB:
        """Convert domain model to database model.

        Args:
            domain_entity: Domain Sale model

        Returns:
            Database sale entity
        """
        return SaleDB(
            id=domain_entity.id,
            match_id=domain_entity.match_id,
            zone_id=domain_entity.zone_id,
            quantity=domain_entity.quantity,
            price_per_ticket=domain_entity.price_per_ticket,
            total_amount=domain_entity.total_amount,
            customer_type=DBCustomerType(domain_entity.customer_type.value),
            customer_id=domain_entity.customer_id,
            purchase_datetime=domain_entity.purchase_datetime,
            payment_status=DBPaymentStatus(domain_entity.payment_status.value),
            payment_method=domain_entity.payment_method,
        )

    def get_by_match(self, match_id: str, completed_only: bool = False) -> List[Sale]:
        """Get all sales for a match.

        Args:
            match_id: Match identifier
            completed_only: Only return completed sales (default False)

        Returns:
            List of sales for the match

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(SaleDB).filter(SaleDB.match_id == match_id)

            if completed_only:
                query = query.filter(SaleDB.payment_status == DBPaymentStatus.COMPLETED)

            sales = query.order_by(SaleDB.purchase_datetime.desc()).all()

            logger.debug(f"Retrieved {len(sales)} sales for match {match_id}")
            return [self._to_domain(sale) for sale in sales]

        except SQLAlchemyError as e:
            logger.error(f"Error getting sales by match: {e}")
            raise DatabaseError(f"Failed to get sales by match: {e}")

    def get_by_zone(self, zone_id: str, completed_only: bool = False) -> List[Sale]:
        """Get all sales for a zone.

        Args:
            zone_id: Zone identifier
            completed_only: Only return completed sales (default False)

        Returns:
            List of sales for the zone

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(SaleDB).filter(SaleDB.zone_id == zone_id)

            if completed_only:
                query = query.filter(SaleDB.payment_status == DBPaymentStatus.COMPLETED)

            sales = query.order_by(SaleDB.purchase_datetime.desc()).all()

            logger.debug(f"Retrieved {len(sales)} sales for zone {zone_id}")
            return [self._to_domain(sale) for sale in sales]

        except SQLAlchemyError as e:
            logger.error(f"Error getting sales by zone: {e}")
            raise DatabaseError(f"Failed to get sales by zone: {e}")

    def get_by_match_and_zone(
        self, match_id: str, zone_id: str, completed_only: bool = False
    ) -> List[Sale]:
        """Get sales for a specific match and zone combination.

        Args:
            match_id: Match identifier
            zone_id: Zone identifier
            completed_only: Only return completed sales (default False)

        Returns:
            List of sales

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(SaleDB).filter(
                and_(SaleDB.match_id == match_id, SaleDB.zone_id == zone_id)
            )

            if completed_only:
                query = query.filter(SaleDB.payment_status == DBPaymentStatus.COMPLETED)

            sales = query.order_by(SaleDB.purchase_datetime.desc()).all()

            logger.debug(
                f"Retrieved {len(sales)} sales for match {match_id} and zone {zone_id}"
            )
            return [self._to_domain(sale) for sale in sales]

        except SQLAlchemyError as e:
            logger.error(f"Error getting sales by match and zone: {e}")
            raise DatabaseError(f"Failed to get sales by match and zone: {e}")

    def get_sales_velocity(
        self, match_id: str, zone_id: Optional[str] = None, hours: int = 24
    ) -> Tuple[int, float]:
        """Calculate sales velocity for recent period.

        Args:
            match_id: Match identifier
            zone_id: Optional zone identifier
            hours: Number of hours to look back (default 24)

        Returns:
            Tuple of (tickets_sold, velocity_per_hour)

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            query = self.session.query(func.sum(SaleDB.quantity)).filter(
                and_(
                    SaleDB.match_id == match_id,
                    SaleDB.purchase_datetime >= cutoff_time,
                    SaleDB.payment_status == DBPaymentStatus.COMPLETED,
                )
            )

            if zone_id:
                query = query.filter(SaleDB.zone_id == zone_id)

            tickets_sold = query.scalar() or 0
            velocity = tickets_sold / hours if hours > 0 else 0

            logger.debug(
                f"Sales velocity for match {match_id}: {tickets_sold} tickets "
                f"in last {hours}h = {velocity:.2f} tickets/hour"
            )
            return tickets_sold, velocity

        except SQLAlchemyError as e:
            logger.error(f"Error calculating sales velocity: {e}")
            raise DatabaseError(f"Failed to calculate sales velocity: {e}")

    def get_total_sold(self, match_id: str, zone_id: Optional[str] = None) -> int:
        """Get total tickets sold for a match or zone.

        Args:
            match_id: Match identifier
            zone_id: Optional zone identifier

        Returns:
            Total number of tickets sold (completed sales only)

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(func.sum(SaleDB.quantity)).filter(
                and_(
                    SaleDB.match_id == match_id,
                    SaleDB.payment_status == DBPaymentStatus.COMPLETED,
                )
            )

            if zone_id:
                query = query.filter(SaleDB.zone_id == zone_id)

            total = query.scalar() or 0

            logger.debug(f"Total sold for match {match_id}: {total} tickets")
            return total

        except SQLAlchemyError as e:
            logger.error(f"Error getting total sold: {e}")
            raise DatabaseError(f"Failed to get total sold: {e}")

    def get_revenue(
        self, match_id: Optional[str] = None, zone_id: Optional[str] = None
    ) -> float:
        """Get total revenue.

        Args:
            match_id: Optional match identifier
            zone_id: Optional zone identifier

        Returns:
            Total revenue (completed sales only)

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(func.sum(SaleDB.total_amount)).filter(
                SaleDB.payment_status == DBPaymentStatus.COMPLETED
            )

            if match_id:
                query = query.filter(SaleDB.match_id == match_id)

            if zone_id:
                query = query.filter(SaleDB.zone_id == zone_id)

            revenue = query.scalar() or 0.0

            logger.debug(f"Revenue: {revenue:.2f}")
            return revenue

        except SQLAlchemyError as e:
            logger.error(f"Error getting revenue: {e}")
            raise DatabaseError(f"Failed to get revenue: {e}")

    def get_average_price(
        self, match_id: Optional[str] = None, zone_id: Optional[str] = None
    ) -> float:
        """Get average ticket price.

        Args:
            match_id: Optional match identifier
            zone_id: Optional zone identifier

        Returns:
            Average price per ticket (completed sales only)

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(func.avg(SaleDB.price_per_ticket)).filter(
                SaleDB.payment_status == DBPaymentStatus.COMPLETED
            )

            if match_id:
                query = query.filter(SaleDB.match_id == match_id)

            if zone_id:
                query = query.filter(SaleDB.zone_id == zone_id)

            avg_price = query.scalar() or 0.0

            logger.debug(f"Average price: {avg_price:.2f}")
            return avg_price

        except SQLAlchemyError as e:
            logger.error(f"Error getting average price: {e}")
            raise DatabaseError(f"Failed to get average price: {e}")

    def get_sales_by_customer_type(self, match_id: str) -> Dict[str, int]:
        """Get sales count by customer type for a match.

        Args:
            match_id: Match identifier

        Returns:
            Dictionary mapping customer type to sales count

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            results = (
                self.session.query(
                    SaleDB.customer_type, func.count(SaleDB.id)
                )
                .filter(
                    and_(
                        SaleDB.match_id == match_id,
                        SaleDB.payment_status == DBPaymentStatus.COMPLETED,
                    )
                )
                .group_by(SaleDB.customer_type)
                .all()
            )

            sales_by_type = {ct.value: count for ct, count in results}

            logger.debug(f"Sales by customer type for match {match_id}: {sales_by_type}")
            return sales_by_type

        except SQLAlchemyError as e:
            logger.error(f"Error getting sales by customer type: {e}")
            raise DatabaseError(f"Failed to get sales by customer type: {e}")

    def get_sales_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[Sale]:
        """Get sales within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of sales in date range

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            sales = (
                self.session.query(SaleDB)
                .filter(
                    and_(
                        SaleDB.purchase_datetime >= start_date,
                        SaleDB.purchase_datetime <= end_date,
                    )
                )
                .order_by(SaleDB.purchase_datetime.desc())
                .all()
            )

            logger.debug(
                f"Retrieved {len(sales)} sales between {start_date} and {end_date}"
            )
            return [self._to_domain(sale) for sale in sales]

        except SQLAlchemyError as e:
            logger.error(f"Error getting sales by date range: {e}")
            raise DatabaseError(f"Failed to get sales by date range: {e}")

    def get_recent_sales(self, hours: int = 24, limit: int = 100) -> List[Sale]:
        """Get recent sales.

        Args:
            hours: Number of hours to look back (default 24)
            limit: Maximum number of sales to return (default 100)

        Returns:
            List of recent sales

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            sales = (
                self.session.query(SaleDB)
                .filter(SaleDB.purchase_datetime >= cutoff_time)
                .order_by(SaleDB.purchase_datetime.desc())
                .limit(limit)
                .all()
            )

            logger.debug(f"Retrieved {len(sales)} recent sales (last {hours}h)")
            return [self._to_domain(sale) for sale in sales]

        except SQLAlchemyError as e:
            logger.error(f"Error getting recent sales: {e}")
            raise DatabaseError(f"Failed to get recent sales: {e}")

    def update_payment_status(
        self, sale_id: str, status: PaymentStatus
    ) -> Optional[Sale]:
        """Update payment status for a sale.

        Args:
            sale_id: Sale identifier
            status: New payment status

        Returns:
            Updated sale or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            sale = self.session.query(SaleDB).filter(SaleDB.id == sale_id).first()

            if sale is None:
                logger.warning(f"Sale {sale_id} not found for status update")
                return None

            old_status = sale.payment_status
            sale.payment_status = DBPaymentStatus(status.value)
            self.session.commit()
            self.session.refresh(sale)

            logger.info(
                f"Updated sale {sale_id} payment status from {old_status} to {status.value}"
            )
            return self._to_domain(sale)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error updating payment status: {e}")
            raise DatabaseError(f"Failed to update payment status: {e}")
