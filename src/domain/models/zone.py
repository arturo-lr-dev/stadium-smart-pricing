"""
Zone domain models.

Pydantic models for stadium zones and related enumerations.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class ZoneCategory(str, Enum):
    """Zone category enumeration."""

    VIP = "vip"
    PREMIUM = "premium"
    STANDARD = "standard"
    REDUCED = "reduced"
    FAMILY = "family"
    STUDENT = "student"


class Zone(BaseModel):
    """
    Zone domain model.

    Represents a stadium zone/section with pricing configuration.
    """

    model_config = ConfigDict(from_attributes=True, use_enum_values=False)

    id: str = Field(..., description="Unique zone identifier")
    name: str = Field(..., description="Zone name", min_length=1, max_length=100)
    category: str = Field(..., description="Zone category")
    capacity: int = Field(..., description="Zone capacity", gt=0)
    base_price: float = Field(..., description="Base price for this zone", gt=0)
    min_price: float = Field(..., description="Minimum allowed price", gt=0)
    max_price: float = Field(..., description="Maximum allowed price", gt=0)
    price_multiplier: float = Field(
        default=1.0, description="Zone-specific price multiplier", gt=0
    )
    is_active: bool = Field(default=True, description="Whether zone is active")
    description: Optional[str] = Field(None, description="Zone description")
    amenities: Optional[List[str]] = Field(None, description="List of zone amenities")

    @field_validator("min_price", "max_price")
    @classmethod
    def validate_prices(cls, v: float, info) -> float:
        """
        Validate price constraints.

        Args:
            v: Price value
            info: Validation info

        Returns:
            Validated price

        Raises:
            ValueError: If price constraints are violated
        """
        if v <= 0:
            raise ValueError("Prices must be positive")

        field_name = info.field_name

        # Validate min_price <= base_price
        if field_name == "min_price" and "base_price" in info.data:
            if v > info.data["base_price"]:
                raise ValueError("min_price must be less than or equal to base_price")

        # Validate base_price <= max_price
        if field_name == "max_price" and "base_price" in info.data:
            if v < info.data["base_price"]:
                raise ValueError("max_price must be greater than or equal to base_price")

        return v

    def validate_price(self, price: float) -> float:
        """
        Validate and clamp a price to allowed range.

        Args:
            price: Proposed price

        Returns:
            Clamped price within min_price and max_price

        Example:
            >>> zone = Zone(id="z1", name="North Stand", category="standard",
            ...             capacity=5000, base_price=30, min_price=20, max_price=50)
            >>> zone.validate_price(15)
            20.0
            >>> zone.validate_price(60)
            50.0
            >>> zone.validate_price(35)
            35.0
        """
        return max(self.min_price, min(price, self.max_price))

    def price_range_width(self) -> float:
        """
        Calculate the width of the allowed price range.

        Returns:
            Difference between max and min price
        """
        return self.max_price - self.min_price

    def price_flexibility(self) -> float:
        """
        Calculate price flexibility as percentage of base price.

        Returns:
            Price flexibility ratio (range width / base price)
        """
        return self.price_range_width() / self.base_price


class ZoneCreate(BaseModel):
    """Schema for creating a new zone."""

    id: str = Field(..., description="Unique zone identifier")
    name: str = Field(..., min_length=1, max_length=100)
    category: str
    capacity: int = Field(..., gt=0)
    base_price: float = Field(..., gt=0)
    min_price: float = Field(..., gt=0)
    max_price: float = Field(..., gt=0)
    price_multiplier: float = Field(default=1.0, gt=0)
    is_active: bool = Field(default=True)
    description: Optional[str] = None
    amenities: Optional[List[str]] = None


class ZoneUpdate(BaseModel):
    """Schema for updating an existing zone."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = None
    capacity: Optional[int] = Field(None, gt=0)
    base_price: Optional[float] = Field(None, gt=0)
    min_price: Optional[float] = Field(None, gt=0)
    max_price: Optional[float] = Field(None, gt=0)
    price_multiplier: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None
    description: Optional[str] = None
    amenities: Optional[List[str]] = None


class ZoneResponse(BaseModel):
    """Schema for zone API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    capacity: int
    base_price: float
    min_price: float
    max_price: float
    price_multiplier: float
    is_active: bool
    description: Optional[str] = None
    amenities: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
