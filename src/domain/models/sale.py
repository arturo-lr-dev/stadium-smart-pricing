"""
Sale domain models.

Pydantic models for ticket sales and related enumerations.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class CustomerType(str, Enum):
    """Customer type enumeration."""

    MEMBER = "member"
    GENERAL = "general"
    VIP = "vip"
    STUDENT = "student"


class PaymentStatus(str, Enum):
    """Payment status enumeration."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Sale(BaseModel):
    """
    Sale domain model.

    Represents a ticket sale transaction.
    """

    model_config = ConfigDict(from_attributes=True, use_enum_values=False)

    id: str = Field(..., description="Unique sale identifier")
    match_id: str = Field(..., description="Match identifier")
    zone_id: str = Field(..., description="Zone identifier")
    quantity: int = Field(..., description="Number of tickets sold", gt=0, le=10)
    price_per_ticket: float = Field(..., description="Price per ticket", gt=0)
    total_amount: float = Field(..., description="Total transaction amount", gt=0)
    customer_type: CustomerType = Field(
        default=CustomerType.GENERAL, description="Type of customer"
    )
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    purchase_datetime: datetime = Field(..., description="Purchase timestamp")
    payment_status: PaymentStatus = Field(
        default=PaymentStatus.PENDING, description="Payment status"
    )
    payment_method: Optional[str] = Field(None, description="Payment method used")

    @field_validator("total_amount")
    @classmethod
    def validate_total_amount(cls, v: float, info) -> float:
        """
        Validate that total amount matches quantity * price_per_ticket.

        Args:
            v: Total amount
            info: Validation info

        Returns:
            Validated total amount

        Raises:
            ValueError: If total doesn't match calculation
        """
        if "quantity" in info.data and "price_per_ticket" in info.data:
            expected_total = info.data["quantity"] * info.data["price_per_ticket"]
            # Allow small floating point differences
            if abs(v - expected_total) > 0.01:
                raise ValueError(
                    f"total_amount ({v}) must equal quantity * price_per_ticket ({expected_total})"
                )
        return v

    def is_completed(self) -> bool:
        """
        Check if sale is completed.

        Returns:
            True if payment is completed
        """
        return self.payment_status == PaymentStatus.COMPLETED

    def is_refunded(self) -> bool:
        """
        Check if sale was refunded.

        Returns:
            True if payment was refunded
        """
        return self.payment_status == PaymentStatus.REFUNDED



class SaleCreate(BaseModel):
    """Schema for creating a new sale."""

    id: str = Field(..., description="Unique sale identifier")
    match_id: str
    zone_id: str
    quantity: int = Field(..., gt=0, le=10)
    price_per_ticket: float = Field(..., gt=0)
    customer_type: CustomerType = Field(default=CustomerType.GENERAL)
    customer_id: Optional[str] = None
    payment_method: Optional[str] = None

    @property
    def total_amount(self) -> float:
        """Calculate total amount."""
        return self.quantity * self.price_per_ticket


class SaleUpdate(BaseModel):
    """Schema for updating a sale."""

    payment_status: Optional[PaymentStatus] = None
    payment_method: Optional[str] = None


class SaleResponse(BaseModel):
    """Schema for sale API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    match_id: str
    zone_id: str
    quantity: int
    price_per_ticket: float
    total_amount: float
    customer_type: CustomerType
    customer_id: Optional[str] = None
    purchase_datetime: datetime
    payment_status: PaymentStatus
    payment_method: Optional[str] = None


class SalesSummary(BaseModel):
    """Summary of sales for a match or zone."""

    match_id: Optional[str] = Field(None, description="Match identifier")
    zone_id: Optional[str] = Field(None, description="Zone identifier")
    total_sales: int = Field(..., description="Total number of sales", ge=0)
    total_tickets: int = Field(..., description="Total tickets sold", ge=0)
    total_revenue: float = Field(..., description="Total revenue", ge=0)
    avg_price: float = Field(..., description="Average price per ticket", ge=0)
    sales_by_customer_type: Dict[str, int] = Field(
        default_factory=dict, description="Sales breakdown by customer type"
    )
    sales_by_payment_status: Dict[str, int] = Field(
        default_factory=dict, description="Sales breakdown by payment status"
    )


class SalesVelocity(BaseModel):
    """Sales velocity metrics."""

    match_id: str = Field(..., description="Match identifier")
    zone_id: Optional[str] = Field(None, description="Zone identifier (if specific)")
    time_period_hours: int = Field(..., description="Time period in hours", gt=0)
    tickets_sold: int = Field(..., description="Tickets sold in period", ge=0)
    velocity_per_hour: float = Field(..., description="Average tickets per hour", ge=0)
    velocity_per_day: float = Field(..., description="Projected tickets per day", ge=0)
    projected_sellout_date: Optional[datetime] = Field(
        None, description="Projected sellout date"
    )

