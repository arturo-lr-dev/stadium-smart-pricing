"""
Domain models package.

This package contains Pydantic models for domain entities and SQLAlchemy models
for database persistence.
"""

# Database models
from src.domain.models.db_models import (
    ConfigurationDB,
    CustomerType as DBCustomerType,
    DemandMetricsDB,
    ExternalDataDB,
    MatchDB,
    MatchStatus as DBMatchStatus,
    PaymentStatus as DBPaymentStatus,
    PricingHistoryDB,
    SaleDB,
    ZoneDB,
)

# Domain models - Match
from src.domain.models.match import (
    CompetitionType,
    Match,
    MatchCreate,
    MatchResponse,
    MatchStatus,
    MatchUpdate,
)

# Domain models - Zone
from src.domain.models.zone import (
    Zone,
    ZoneCategory,
    ZoneCreate,
    ZoneResponse,
    ZoneUpdate,
)

# Domain models - Pricing
from src.domain.models.pricing import (
    MatchPricing,
    PriceChangeRequest,
    PriceChangeResponse,
    PricingFactors,
    ZonePricing,
)

# Domain models - Sale
from src.domain.models.sale import (
    CustomerType,
    PaymentStatus,
    Sale,
    SaleCreate,
    SaleResponse,
    SalesSummary,
    SalesVelocity,
    SaleUpdate,
)

__all__ = [
    # Database models
    "MatchDB",
    "ZoneDB",
    "SaleDB",
    "PricingHistoryDB",
    "DemandMetricsDB",
    "ExternalDataDB",
    "ConfigurationDB",
    "DBMatchStatus",
    "DBCustomerType",
    "DBPaymentStatus",
    # Domain models - Match
    "Match",
    "MatchCreate",
    "MatchUpdate",
    "MatchResponse",
    "MatchStatus",
    "CompetitionType",
    # Domain models - Zone
    "Zone",
    "ZoneCreate",
    "ZoneUpdate",
    "ZoneResponse",
    "ZoneCategory",
    # Domain models - Pricing
    "PricingFactors",
    "ZonePricing",
    "MatchPricing",
    "PriceChangeRequest",
    "PriceChangeResponse",
    # Domain models - Sale
    "Sale",
    "SaleCreate",
    "SaleUpdate",
    "SaleResponse",
    "SalesSummary",
    "SalesVelocity",
    "CustomerType",
    "PaymentStatus",
]
