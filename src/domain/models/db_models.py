"""
SQLAlchemy database models.

This module defines the database schema for the Smart Pricing system.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base


class MatchStatus(str, PyEnum):
    """Match status enumeration."""

    SCHEDULED = "scheduled"
    ON_SALE = "on_sale"
    SOLD_OUT = "sold_out"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CustomerType(str, PyEnum):
    """Customer type enumeration."""

    MEMBER = "member"
    GENERAL = "general"
    VIP = "vip"
    STUDENT = "student"


class PaymentStatus(str, PyEnum):
    """Payment status enumeration."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class MatchDB(Base):
    """
    Match database model.

    Represents a football match with all relevant information for pricing.
    """

    __tablename__ = "matches"

    # Primary key
    id = Column(String(50), primary_key=True, index=True)

    # Match information
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    competition = Column(String(100), nullable=False, index=True)
    match_date = Column(DateTime, nullable=False, index=True)
    status = Column(Enum(MatchStatus), default=MatchStatus.SCHEDULED, nullable=False, index=True)

    # Venue information
    venue = Column(String(100), nullable=False, default="Son Moix")
    capacity = Column(Integer, nullable=False, default=23142)

    # Match attributes for pricing
    is_derby = Column(Boolean, default=False, nullable=False)
    is_holiday = Column(Boolean, default=False, nullable=False)
    home_position = Column(Integer, nullable=True)  # League position
    away_position = Column(Integer, nullable=True)  # League position

    # Additional metadata
    metadata_json = Column(JSON, nullable=True)  # For flexible additional data

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    sales = relationship("SaleDB", back_populates="match", cascade="all, delete-orphan")
    pricing_history = relationship(
        "PricingHistoryDB", back_populates="match", cascade="all, delete-orphan"
    )
    demand_metrics = relationship(
        "DemandMetricsDB", back_populates="match", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Match {self.id}: {self.home_team} vs {self.away_team} on {self.match_date}>"


class ZoneDB(Base):
    """
    Zone database model.

    Represents a stadium zone/section with pricing configuration.
    """

    __tablename__ = "zones"

    # Primary key
    id = Column(String(50), primary_key=True, index=True)

    # Zone information
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, index=True)  # VIP, Premium, Standard, Reduced

    # Capacity
    capacity = Column(Integer, nullable=False)

    # Pricing configuration
    base_price = Column(Float, nullable=False)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    price_multiplier = Column(Float, default=1.0, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Additional metadata
    description = Column(Text, nullable=True)
    amenities = Column(JSON, nullable=True)  # List of amenities

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    sales = relationship("SaleDB", back_populates="zone")
    pricing_history = relationship("PricingHistoryDB", back_populates="zone")
    demand_metrics = relationship("DemandMetricsDB", back_populates="zone")

    def __repr__(self) -> str:
        return f"<Zone {self.id}: {self.name} ({self.category})>"


class SaleDB(Base):
    """
    Sale database model.

    Represents a ticket sale transaction.
    """

    __tablename__ = "sales"

    # Primary key
    id = Column(String(50), primary_key=True, index=True)

    # Foreign keys
    match_id = Column(String(50), ForeignKey("matches.id"), nullable=False, index=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False, index=True)

    # Sale information
    quantity = Column(Integer, nullable=False)
    price_per_ticket = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)

    # Customer information
    customer_type = Column(Enum(CustomerType), default=CustomerType.GENERAL, nullable=False)
    customer_id = Column(String(50), nullable=True, index=True)

    # Payment information
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_method = Column(String(50), nullable=True)

    # Timestamps
    purchase_datetime = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Additional metadata
    metadata_json = Column(JSON, nullable=True)

    # Relationships
    match = relationship("MatchDB", back_populates="sales")
    zone = relationship("ZoneDB", back_populates="sales")

    def __repr__(self) -> str:
        return (
            f"<Sale {self.id}: {self.quantity} tickets for match {self.match_id} "
            f"in zone {self.zone_id}>"
        )


class PricingHistoryDB(Base):
    """
    Pricing history database model.

    Stores historical pricing calculations and factors.
    """

    __tablename__ = "pricing_history"

    # Primary key
    id = Column(String(50), primary_key=True, index=True)

    # Foreign keys
    match_id = Column(String(50), ForeignKey("matches.id"), nullable=False, index=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False, index=True)

    # Pricing information
    price = Column(Float, nullable=False)

    # Pricing factors
    demand_score = Column(Float, nullable=True)
    time_factor = Column(Float, nullable=True)
    inventory_factor = Column(Float, nullable=True)
    competition_factor = Column(Float, nullable=True)
    rival_factor = Column(Float, nullable=True)
    weather_factor = Column(Float, nullable=True)
    special_conditions = Column(JSON, nullable=True)  # Dict of special multipliers

    # Inventory at time of pricing
    sold_tickets = Column(Integer, nullable=True)
    available_tickets = Column(Integer, nullable=True)
    occupancy_percent = Column(Float, nullable=True)

    # Timestamp
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    match = relationship("MatchDB", back_populates="pricing_history")
    zone = relationship("ZoneDB", back_populates="pricing_history")

    def __repr__(self) -> str:
        return (
            f"<PricingHistory {self.id}: €{self.price} for match {self.match_id} "
            f"zone {self.zone_id} at {self.timestamp}>"
        )


class DemandMetricsDB(Base):
    """
    Demand metrics database model.

    Stores metrics about user behavior and demand signals.
    """

    __tablename__ = "demand_metrics"

    # Primary key
    id = Column(String(50), primary_key=True, index=True)

    # Foreign keys
    match_id = Column(String(50), ForeignKey("matches.id"), nullable=False, index=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False, index=True)

    # Metrics
    views = Column(Integer, default=0, nullable=False)
    cart_additions = Column(Integer, default=0, nullable=False)
    cart_abandonments = Column(Integer, default=0, nullable=False)
    completed_purchases = Column(Integer, default=0, nullable=False)

    # Calculated metrics
    conversion_rate = Column(Float, nullable=True)
    abandonment_rate = Column(Float, nullable=True)

    # Timestamp (hourly aggregation)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Additional metrics
    metadata_json = Column(JSON, nullable=True)

    # Relationships
    match = relationship("MatchDB", back_populates="demand_metrics")
    zone = relationship("ZoneDB", back_populates="demand_metrics")

    def __repr__(self) -> str:
        return (
            f"<DemandMetrics {self.id}: {self.views} views, {self.cart_additions} cart adds "
            f"for match {self.match_id} zone {self.zone_id}>"
        )


class ExternalDataDB(Base):
    """
    External data cache database model.

    Caches data from external APIs (weather, football stats, etc.).
    """

    __tablename__ = "external_data"

    # Primary key
    id = Column(String(50), primary_key=True, index=True)

    # Data identification
    source = Column(String(50), nullable=False, index=True)  # weather, football_stats, transport
    data_key = Column(String(200), nullable=False, index=True)  # Unique key for the data

    # Data
    data_value = Column(JSON, nullable=False)

    # Cache metadata
    fetched_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    # Status
    is_valid = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<ExternalData {self.id}: {self.source}:{self.data_key}>"


class ConfigurationDB(Base):
    """
    Configuration database model.

    Stores system configuration that can be updated at runtime.
    """

    __tablename__ = "configurations"

    # Primary key
    id = Column(String(50), primary_key=True, index=True)

    # Configuration
    category = Column(String(50), nullable=False, index=True)  # pricing, ml, system
    key = Column(String(100), nullable=False, index=True)
    value = Column(JSON, nullable=False)

    # Metadata
    description = Column(Text, nullable=True)
    updated_by = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Configuration {self.category}.{self.key}>"
