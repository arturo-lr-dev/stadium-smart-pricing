"""Base repository with generic CRUD operations.

This module provides an abstract base repository that implements
common database operations following the Repository pattern.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Any, Type
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.core.exceptions import DatabaseError
from src.core.logging import get_logger

logger = get_logger(__name__)

# Type variables for generic types
DBModelType = TypeVar('DBModelType')
DomainModelType = TypeVar('DomainModelType')


class BaseRepository(ABC, Generic[DBModelType, DomainModelType]):
    """Abstract base repository with common CRUD operations.

    This class provides generic database operations and requires
    subclasses to implement conversions between database models
    and domain models.

    Attributes:
        db_model: SQLAlchemy model class
        session: Database session
    """

    def __init__(self, db_model: Type[DBModelType], session: Session):
        """Initialize repository.

        Args:
            db_model: SQLAlchemy model class
            session: Database session
        """
        self.db_model = db_model
        self.session = session

    @abstractmethod
    def _to_domain(self, db_entity: DBModelType) -> DomainModelType:
        """Convert database model to domain model.

        Args:
            db_entity: Database entity

        Returns:
            Domain model instance
        """
        pass

    @abstractmethod
    def _to_db(self, domain_entity: DomainModelType) -> DBModelType:
        """Convert domain model to database model.

        Args:
            domain_entity: Domain entity

        Returns:
            Database model instance
        """
        pass

    def get_by_id(self, id: str) -> Optional[DomainModelType]:
        """Get entity by ID.

        Args:
            id: Entity ID

        Returns:
            Domain model instance or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            db_entity = self.session.query(self.db_model).filter(
                self.db_model.id == id
            ).first()

            if db_entity is None:
                logger.debug(f"{self.db_model.__name__} with id {id} not found")
                return None

            logger.debug(f"Retrieved {self.db_model.__name__} with id {id}")
            return self._to_domain(db_entity)

        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.db_model.__name__} by id {id}: {e}")
            raise DatabaseError(f"Failed to get entity by id: {e}")

    def get_all(self, skip: int = 0, limit: int = 100) -> List[DomainModelType]:
        """Get all entities with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of domain model instances

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            db_entities = self.session.query(self.db_model).offset(skip).limit(limit).all()

            logger.debug(f"Retrieved {len(db_entities)} {self.db_model.__name__} entities")
            return [self._to_domain(entity) for entity in db_entities]

        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.db_model.__name__}: {e}")
            raise DatabaseError(f"Failed to get all entities: {e}")

    def create(self, entity: DomainModelType) -> DomainModelType:
        """Create new entity.

        Args:
            entity: Domain model instance

        Returns:
            Created domain model instance

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            db_entity = self._to_db(entity)
            self.session.add(db_entity)
            self.session.commit()
            self.session.refresh(db_entity)

            logger.info(f"Created {self.db_model.__name__} with id {db_entity.id}")
            return self._to_domain(db_entity)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error creating {self.db_model.__name__}: {e}")
            raise DatabaseError(f"Failed to create entity: {e}")

    def update(self, id: str, entity: DomainModelType) -> Optional[DomainModelType]:
        """Update existing entity.

        Args:
            id: Entity ID
            entity: Updated domain model instance

        Returns:
            Updated domain model instance or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            db_entity = self.session.query(self.db_model).filter(
                self.db_model.id == id
            ).first()

            if db_entity is None:
                logger.warning(f"{self.db_model.__name__} with id {id} not found for update")
                return None

            # Update fields from domain entity
            updated_db_entity = self._to_db(entity)
            for key, value in updated_db_entity.__dict__.items():
                if not key.startswith('_'):
                    setattr(db_entity, key, value)

            self.session.commit()
            self.session.refresh(db_entity)

            logger.info(f"Updated {self.db_model.__name__} with id {id}")
            return self._to_domain(db_entity)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error updating {self.db_model.__name__} with id {id}: {e}")
            raise DatabaseError(f"Failed to update entity: {e}")

    def delete(self, id: str) -> bool:
        """Delete entity by ID.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            db_entity = self.session.query(self.db_model).filter(
                self.db_model.id == id
            ).first()

            if db_entity is None:
                logger.warning(f"{self.db_model.__name__} with id {id} not found for deletion")
                return False

            self.session.delete(db_entity)
            self.session.commit()

            logger.info(f"Deleted {self.db_model.__name__} with id {id}")
            return True

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error deleting {self.db_model.__name__} with id {id}: {e}")
            raise DatabaseError(f"Failed to delete entity: {e}")

    def exists(self, id: str) -> bool:
        """Check if entity exists.

        Args:
            id: Entity ID

        Returns:
            True if exists, False otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            count = self.session.query(self.db_model).filter(
                self.db_model.id == id
            ).count()

            return count > 0

        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.db_model.__name__} with id {id}: {e}")
            raise DatabaseError(f"Failed to check entity existence: {e}")

    def count(self) -> int:
        """Count total number of entities.

        Returns:
            Total count of entities

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            return self.session.query(self.db_model).count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.db_model.__name__}: {e}")
            raise DatabaseError(f"Failed to count entities: {e}")
