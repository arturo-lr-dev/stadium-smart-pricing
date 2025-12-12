# Phase 2 Implementation - Database Layer & Models

## Status: ✅ COMPLETED

**Date:** 2024-12-12

## Overview

Phase 2 focused on implementing the database layer, including SQLAlchemy models, Pydantic domain models, database initialization scripts, and Alembic migrations.

## Components Implemented

### 1. Database Configuration (`src/core/database.py`)

**Features:**
- SQLAlchemy engine setup with connection pooling
- Session factory with dependency injection support
- Context manager for safe database operations
- Health check functionality
- Connection lifecycle management
- Logging of database events

**Key Functions:**
- `get_engine()`: Returns the global database engine
- `get_db()`: Context manager for database sessions
- `create_all_tables()`: Create all tables (for initial setup)
- `check_database_connection()`: Verify database connectivity

### 2. SQLAlchemy Database Models (`src/domain/models/db_models.py`)

**Models Created:**

#### MatchDB
- Stores match information (teams, competition, date, venue)
- Includes pricing-relevant attributes (is_derby, is_holiday, team positions)
- Status tracking (scheduled, on_sale, sold_out, completed, cancelled)

#### ZoneDB
- Stadium zone/section configuration
- Pricing parameters (base, min, max prices)
- Capacity and category information
- Amenities as JSON field

#### SaleDB
- Ticket sale transactions
- Links to match and zone
- Customer and payment information
- Purchase timestamp for analytics

#### PricingHistoryDB
- Historical pricing calculations
- All pricing factors stored for analysis
- Inventory snapshot at time of pricing
- Timestamp for time-series analysis

#### DemandMetricsDB
- User behavior metrics (views, cart additions, abandonments)
- Conversion and abandonment rates
- Hourly aggregation support

#### ExternalDataDB
- Cache for external API data
- Expiration management
- Source identification

#### ConfigurationDB
- Runtime configuration storage
- Categorized key-value store
- Audit trail (updated_by, timestamps)

**Relationships:**
- Match → Sales (one-to-many)
- Match → PricingHistory (one-to-many)
- Match → DemandMetrics (one-to-many)
- Zone → Sales (one-to-many)
- Zone → PricingHistory (one-to-many)
- Zone → DemandMetrics (one-to-many)

### 3. Pydantic Domain Models

#### Match Models (`src/domain/models/match.py`)
- `Match`: Core match entity with validation
- `MatchCreate`: Schema for creating matches
- `MatchUpdate`: Schema for updating matches
- `MatchResponse`: API response schema
- Enums: `CompetitionType`, `MatchStatus`
- Methods: `days_until_match()`, `is_high_profile()`

#### Zone Models (`src/domain/models/zone.py`)
- `Zone`: Core zone entity with price validation
- `ZoneCreate`, `ZoneUpdate`, `ZoneResponse`: CRUD schemas
- Enum: `ZoneCategory`
- Methods: `validate_price()`, `price_flexibility()`

#### Pricing Models (`src/domain/models/pricing.py`)
- `PricingFactors`: All pricing calculation factors
- `ZonePricing`: Pricing for a specific zone
- `MatchPricing`: Complete pricing for a match
- Methods for occupancy calculation, price changes, analytics

#### Sale Models (`src/domain/models/sale.py`)
- `Sale`: Core sale entity
- `SaleCreate`, `SaleUpdate`, `SaleResponse`: CRUD schemas
- `SalesSummary`: Aggregated sales data
- `SalesVelocity`: Sales velocity metrics
- Enums: `CustomerType`, `PaymentStatus`

### 4. Database Initialization Script (`scripts/init_db.py`)

**Features:**
- Create all tables
- Drop all tables (with double confirmation)
- Reset database (drop + create)
- Show database configuration
- Connection verification

**Usage:**
```bash
# Show database info
python scripts/init_db.py --info

# Create tables
python scripts/init_db.py --create

# Reset database
python scripts/init_db.py --reset
```

### 5. Database Seeding Script (`scripts/seed_data.py`)

**Features:**
- Seed stadium zones (8 zones with different categories)
- Seed sample matches (12 upcoming matches)
- Seed realistic sales data
- Seed pricing history
- Clear existing data option

**Sample Data:**
- 8 zones: VIP, Premium, Standard, Reduced
- 12 matches against various La Liga teams
- Sales data with realistic patterns (more sales for derby matches, closer dates)
- Historical pricing data

**Usage:**
```bash
# Seed all data
python scripts/seed_data.py

# Clear and reseed
python scripts/seed_data.py --clear

# Seed only zones
python scripts/seed_data.py --zones-only
```

### 6. Alembic Configuration

**Files Created:**
- `alembic.ini`: Alembic configuration
- `alembic/env.py`: Environment configuration (auto-loads database URL from settings)
- `alembic/script.py.mako`: Migration template
- `alembic/versions/001_initial_schema.py`: Initial migration

**Features:**
- Automatic database URL loading from application settings
- Type comparison enabled for better autogeneration
- Server default comparison enabled
- Proper enum type handling for PostgreSQL

**Usage:**
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Show current version
alembic current
```

## Database Schema

### Tables Created:
1. **zones** - Stadium zones/sections
2. **matches** - Football matches
3. **sales** - Ticket sales
4. **pricing_history** - Historical pricing data
5. **demand_metrics** - User behavior metrics
6. **external_data** - External API cache
7. **configurations** - Runtime configuration

### Indexes Created:
- Primary key indexes on all tables
- Foreign key indexes for relationships
- Date/timestamp indexes for time-based queries
- Category/status indexes for filtering

### Enum Types:
- `matchstatus`: scheduled, on_sale, sold_out, completed, cancelled
- `customertype`: member, general, vip, student
- `paymentstatus`: pending, completed, failed, refunded

## Validation & Business Rules

### Price Validation
- min_price ≤ base_price ≤ max_price
- Automatic price clamping in `Zone.validate_price()`

### Sale Validation
- total_amount must equal quantity × price_per_ticket
- Quantity limited to 1-10 tickets per sale

### Match Validation
- Home and away teams must be different
- Date validation support

### Zone Validation
- All prices must be positive
- Capacity must be positive

## Next Steps (Phase 3)

The next phase will implement:
1. Repository layer (Base repository pattern)
2. Specific repositories for each entity
3. Data access abstractions
4. Transaction management
5. Unit tests for repositories

## Testing Recommendations

Once dependencies are installed and database is running:

```bash
# 1. Start database
docker compose up -d postgres

# 2. Initialize database
python scripts/init_db.py --create

# 3. Seed sample data
python scripts/seed_data.py

# 4. Verify data
python scripts/init_db.py --info
```

## Files Created

```
src/core/
├── database.py                          # Database configuration

src/domain/models/
├── __init__.py                          # Models export
├── db_models.py                         # SQLAlchemy models
├── match.py                             # Match domain models
├── zone.py                              # Zone domain models
├── pricing.py                           # Pricing domain models
└── sale.py                              # Sale domain models

scripts/
├── init_db.py                           # Database initialization
└── seed_data.py                         # Database seeding

alembic/
├── env.py                               # Alembic environment
├── script.py.mako                       # Migration template
├── README                               # Alembic usage guide
└── versions/
    └── 001_initial_schema.py           # Initial migration

alembic.ini                              # Alembic configuration

docs/
└── PHASE_2_COMPLETION.md               # This document
```

## Notes

- All models include comprehensive docstrings
- Pydantic models provide automatic validation
- SQLAlchemy models include proper relationships and indexes
- Scripts include proper error handling and logging
- Alembic is configured to work seamlessly with application settings
- Sample data is realistic and useful for testing

## Checklist

- [x] Database configuration module
- [x] SQLAlchemy models with relationships
- [x] Pydantic domain models with validation
- [x] Database initialization script
- [x] Database seeding script
- [x] Alembic configuration
- [x] Initial migration
- [x] Documentation

**Phase 2 is complete and ready for Phase 3 implementation.**
