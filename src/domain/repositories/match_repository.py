"""Match repository for database operations.

This module provides repository operations specific to Match entities.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.core.exceptions import DatabaseError
from src.core.logging import get_logger
from src.domain.models.db_models import MatchDB, MatchStatus as DBMatchStatus
from src.domain.models.match import Match, MatchStatus
from src.domain.repositories.base_repository import BaseRepository

logger = get_logger(__name__)


class MatchRepository(BaseRepository[MatchDB, Match]):
    """Repository for Match entities.

    Provides database operations specific to football matches.
    """

    def __init__(self, session: Session):
        """Initialize match repository.

        Args:
            session: Database session
        """
        super().__init__(MatchDB, session)

    def _to_domain(self, db_entity: MatchDB) -> Match:
        """Convert database model to domain model.

        Args:
            db_entity: Database match entity

        Returns:
            Domain Match model
        """
        return Match(
            id=db_entity.id,
            home_team=db_entity.home_team,
            away_team=db_entity.away_team,
            competition=db_entity.competition,
            match_date=db_entity.match_date,
            venue=db_entity.venue,
            capacity=db_entity.capacity,
            is_derby=db_entity.is_derby,
            is_holiday=db_entity.is_holiday,
            home_position=db_entity.home_position,
            away_position=db_entity.away_position,
            status=MatchStatus(db_entity.status.value),
        )

    def _to_db(self, domain_entity: Match) -> MatchDB:
        """Convert domain model to database model.

        Args:
            domain_entity: Domain Match model

        Returns:
            Database match entity
        """
        return MatchDB(
            id=domain_entity.id,
            home_team=domain_entity.home_team,
            away_team=domain_entity.away_team,
            competition=domain_entity.competition,
            match_date=domain_entity.date,
            venue=domain_entity.venue,
            capacity=domain_entity.capacity,
            is_derby=domain_entity.is_derby,
            is_holiday=domain_entity.is_holiday,
            home_position=domain_entity.home_position,
            away_position=domain_entity.away_position,
            status=DBMatchStatus(domain_entity.status.value),
        )

    def get_upcoming(self, days: int = 30, from_date: Optional[datetime] = None) -> List[Match]:
        """Get upcoming matches within specified days.

        Args:
            days: Number of days to look ahead (default 30)
            from_date: Start date (defaults to now)

        Returns:
            List of upcoming matches ordered by date

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            if from_date is None:
                from_date = datetime.now()

            end_date = from_date + timedelta(days=days)

            matches = (
                self.session.query(MatchDB)
                .filter(
                    and_(
                        MatchDB.match_date >= from_date,
                        MatchDB.match_date <= end_date,
                        MatchDB.status.in_([DBMatchStatus.SCHEDULED, DBMatchStatus.ON_SALE])
                    )
                )
                .order_by(MatchDB.match_date.asc())
                .all()
            )

            logger.debug(f"Retrieved {len(matches)} upcoming matches within {days} days")
            return [self._to_domain(match) for match in matches]

        except SQLAlchemyError as e:
            logger.error(f"Error getting upcoming matches: {e}")
            raise DatabaseError(f"Failed to get upcoming matches: {e}")

    def get_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[Match]:
        """Get matches within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of matches in date range ordered by date

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            matches = (
                self.session.query(MatchDB)
                .filter(
                    and_(
                        MatchDB.match_date >= start_date,
                        MatchDB.match_date <= end_date
                    )
                )
                .order_by(MatchDB.match_date.asc())
                .all()
            )

            logger.debug(
                f"Retrieved {len(matches)} matches between {start_date} and {end_date}"
            )
            return [self._to_domain(match) for match in matches]

        except SQLAlchemyError as e:
            logger.error(f"Error getting matches by date range: {e}")
            raise DatabaseError(f"Failed to get matches by date range: {e}")

    def get_by_competition(self, competition: str) -> List[Match]:
        """Get matches by competition.

        Args:
            competition: Competition name/type

        Returns:
            List of matches in competition ordered by date

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            matches = (
                self.session.query(MatchDB)
                .filter(MatchDB.competition == competition)
                .order_by(MatchDB.match_date.asc())
                .all()
            )

            logger.debug(f"Retrieved {len(matches)} matches for competition {competition}")
            return [self._to_domain(match) for match in matches]

        except SQLAlchemyError as e:
            logger.error(f"Error getting matches by competition: {e}")
            raise DatabaseError(f"Failed to get matches by competition: {e}")

    def get_by_status(self, status: MatchStatus) -> List[Match]:
        """Get matches by status.

        Args:
            status: Match status

        Returns:
            List of matches with given status ordered by date

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            db_status = DBMatchStatus(status.value)
            matches = (
                self.session.query(MatchDB)
                .filter(MatchDB.status == db_status)
                .order_by(MatchDB.match_date.asc())
                .all()
            )

            logger.debug(f"Retrieved {len(matches)} matches with status {status.value}")
            return [self._to_domain(match) for match in matches]

        except SQLAlchemyError as e:
            logger.error(f"Error getting matches by status: {e}")
            raise DatabaseError(f"Failed to get matches by status: {e}")

    def get_by_team(self, team: str, home_only: bool = False, away_only: bool = False) -> List[Match]:
        """Get matches involving a specific team.

        Args:
            team: Team name
            home_only: Only return matches where team is home (default False)
            away_only: Only return matches where team is away (default False)

        Returns:
            List of matches involving the team ordered by date

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            if home_only:
                filter_condition = MatchDB.home_team == team
            elif away_only:
                filter_condition = MatchDB.away_team == team
            else:
                filter_condition = or_(
                    MatchDB.home_team == team,
                    MatchDB.away_team == team
                )

            matches = (
                self.session.query(MatchDB)
                .filter(filter_condition)
                .order_by(MatchDB.match_date.asc())
                .all()
            )

            logger.debug(f"Retrieved {len(matches)} matches for team {team}")
            return [self._to_domain(match) for match in matches]

        except SQLAlchemyError as e:
            logger.error(f"Error getting matches by team: {e}")
            raise DatabaseError(f"Failed to get matches by team: {e}")

    def get_derby_matches(self, from_date: Optional[datetime] = None) -> List[Match]:
        """Get all derby matches.

        Args:
            from_date: Optional start date (defaults to now)

        Returns:
            List of derby matches ordered by date

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(MatchDB).filter(MatchDB.is_derby == True)

            if from_date:
                query = query.filter(MatchDB.match_date >= from_date)

            matches = query.order_by(MatchDB.match_date.asc()).all()

            logger.debug(f"Retrieved {len(matches)} derby matches")
            return [self._to_domain(match) for match in matches]

        except SQLAlchemyError as e:
            logger.error(f"Error getting derby matches: {e}")
            raise DatabaseError(f"Failed to get derby matches: {e}")

    def update_status(self, match_id: str, status: MatchStatus) -> Optional[Match]:
        """Update match status.

        Args:
            match_id: Match ID
            status: New status

        Returns:
            Updated match or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            match = self.session.query(MatchDB).filter(MatchDB.id == match_id).first()

            if match is None:
                logger.warning(f"Match {match_id} not found for status update")
                return None

            old_status = match.status
            match.status = DBMatchStatus(status.value)
            self.session.commit()
            self.session.refresh(match)

            logger.info(f"Updated match {match_id} status from {old_status} to {status.value}")
            return self._to_domain(match)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error updating match status: {e}")
            raise DatabaseError(f"Failed to update match status: {e}")

    def search(
        self,
        competition: Optional[str] = None,
        status: Optional[MatchStatus] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Match]:
        """Search matches with multiple filters.

        Args:
            competition: Filter by competition
            status: Filter by status
            from_date: Filter by start date
            to_date: Filter by end date
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matches matching filters

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = self.session.query(MatchDB)

            if competition:
                query = query.filter(MatchDB.competition == competition)

            if status:
                db_status = DBMatchStatus(status.value)
                query = query.filter(MatchDB.status == db_status)

            if from_date:
                query = query.filter(MatchDB.match_date >= from_date)

            if to_date:
                query = query.filter(MatchDB.match_date <= to_date)

            matches = (
                query.order_by(MatchDB.match_date.asc())
                .offset(skip)
                .limit(limit)
                .all()
            )

            logger.debug(f"Search returned {len(matches)} matches")
            return [self._to_domain(match) for match in matches]

        except SQLAlchemyError as e:
            logger.error(f"Error searching matches: {e}")
            raise DatabaseError(f"Failed to search matches: {e}")
