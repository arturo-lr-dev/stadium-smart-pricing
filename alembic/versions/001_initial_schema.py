"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-12-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""

    # Create enum types
    op.execute("""
        CREATE TYPE matchstatus AS ENUM ('scheduled', 'on_sale', 'sold_out', 'completed', 'cancelled');
        CREATE TYPE customertype AS ENUM ('member', 'general', 'vip', 'student');
        CREATE TYPE paymentstatus AS ENUM ('pending', 'completed', 'failed', 'refunded');
    """)

    # Create zones table
    op.create_table(
        'zones',
        sa.Column('id', sa.String(50), primary_key=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('base_price', sa.Float(), nullable=False),
        sa.Column('min_price', sa.Float(), nullable=False),
        sa.Column('max_price', sa.Float(), nullable=False),
        sa.Column('price_multiplier', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amenities', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_zones_id', 'zones', ['id'])
    op.create_index('ix_zones_category', 'zones', ['category'])

    # Create matches table
    op.create_table(
        'matches',
        sa.Column('id', sa.String(50), primary_key=True, nullable=False),
        sa.Column('home_team', sa.String(100), nullable=False),
        sa.Column('away_team', sa.String(100), nullable=False),
        sa.Column('competition', sa.String(100), nullable=False),
        sa.Column('match_date', sa.DateTime(), nullable=False),
        sa.Column('status', postgresql.ENUM('scheduled', 'on_sale', 'sold_out', 'completed', 'cancelled', name='matchstatus'), nullable=False, server_default='scheduled'),
        sa.Column('venue', sa.String(100), nullable=False, server_default='Son Moix'),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='23142'),
        sa.Column('is_derby', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_holiday', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('home_position', sa.Integer(), nullable=True),
        sa.Column('away_position', sa.Integer(), nullable=True),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_matches_id', 'matches', ['id'])
    op.create_index('ix_matches_competition', 'matches', ['competition'])
    op.create_index('ix_matches_match_date', 'matches', ['match_date'])
    op.create_index('ix_matches_status', 'matches', ['status'])

    # Create sales table
    op.create_table(
        'sales',
        sa.Column('id', sa.String(50), primary_key=True, nullable=False),
        sa.Column('match_id', sa.String(50), sa.ForeignKey('matches.id'), nullable=False),
        sa.Column('zone_id', sa.String(50), sa.ForeignKey('zones.id'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price_per_ticket', sa.Float(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('customer_type', postgresql.ENUM('member', 'general', 'vip', 'student', name='customertype'), nullable=False, server_default='general'),
        sa.Column('customer_id', sa.String(50), nullable=True),
        sa.Column('payment_status', postgresql.ENUM('pending', 'completed', 'failed', 'refunded', name='paymentstatus'), nullable=False, server_default='pending'),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('purchase_datetime', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    op.create_index('ix_sales_id', 'sales', ['id'])
    op.create_index('ix_sales_match_id', 'sales', ['match_id'])
    op.create_index('ix_sales_zone_id', 'sales', ['zone_id'])
    op.create_index('ix_sales_customer_id', 'sales', ['customer_id'])
    op.create_index('ix_sales_purchase_datetime', 'sales', ['purchase_datetime'])

    # Create pricing_history table
    op.create_table(
        'pricing_history',
        sa.Column('id', sa.String(50), primary_key=True, nullable=False),
        sa.Column('match_id', sa.String(50), sa.ForeignKey('matches.id'), nullable=False),
        sa.Column('zone_id', sa.String(50), sa.ForeignKey('zones.id'), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('demand_score', sa.Float(), nullable=True),
        sa.Column('time_factor', sa.Float(), nullable=True),
        sa.Column('inventory_factor', sa.Float(), nullable=True),
        sa.Column('competition_factor', sa.Float(), nullable=True),
        sa.Column('rival_factor', sa.Float(), nullable=True),
        sa.Column('weather_factor', sa.Float(), nullable=True),
        sa.Column('special_conditions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('sold_tickets', sa.Integer(), nullable=True),
        sa.Column('available_tickets', sa.Integer(), nullable=True),
        sa.Column('occupancy_percent', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_pricing_history_id', 'pricing_history', ['id'])
    op.create_index('ix_pricing_history_match_id', 'pricing_history', ['match_id'])
    op.create_index('ix_pricing_history_zone_id', 'pricing_history', ['zone_id'])
    op.create_index('ix_pricing_history_timestamp', 'pricing_history', ['timestamp'])

    # Create demand_metrics table
    op.create_table(
        'demand_metrics',
        sa.Column('id', sa.String(50), primary_key=True, nullable=False),
        sa.Column('match_id', sa.String(50), sa.ForeignKey('matches.id'), nullable=False),
        sa.Column('zone_id', sa.String(50), sa.ForeignKey('zones.id'), nullable=False),
        sa.Column('views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cart_additions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cart_abandonments', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_purchases', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('conversion_rate', sa.Float(), nullable=True),
        sa.Column('abandonment_rate', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    op.create_index('ix_demand_metrics_id', 'demand_metrics', ['id'])
    op.create_index('ix_demand_metrics_match_id', 'demand_metrics', ['match_id'])
    op.create_index('ix_demand_metrics_zone_id', 'demand_metrics', ['zone_id'])
    op.create_index('ix_demand_metrics_timestamp', 'demand_metrics', ['timestamp'])

    # Create external_data table
    op.create_table(
        'external_data',
        sa.Column('id', sa.String(50), primary_key=True, nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('data_key', sa.String(200), nullable=False),
        sa.Column('data_value', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
    )
    op.create_index('ix_external_data_id', 'external_data', ['id'])
    op.create_index('ix_external_data_source', 'external_data', ['source'])
    op.create_index('ix_external_data_data_key', 'external_data', ['data_key'])
    op.create_index('ix_external_data_expires_at', 'external_data', ['expires_at'])

    # Create configurations table
    op.create_table(
        'configurations',
        sa.Column('id', sa.String(50), primary_key=True, nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_configurations_id', 'configurations', ['id'])
    op.create_index('ix_configurations_category', 'configurations', ['category'])
    op.create_index('ix_configurations_key', 'configurations', ['key'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('configurations')
    op.drop_table('external_data')
    op.drop_table('demand_metrics')
    op.drop_table('pricing_history')
    op.drop_table('sales')
    op.drop_table('matches')
    op.drop_table('zones')

    op.execute("""
        DROP TYPE IF EXISTS matchstatus;
        DROP TYPE IF EXISTS customertype;
        DROP TYPE IF EXISTS paymentstatus;
    """)
