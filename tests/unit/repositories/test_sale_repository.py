"""Unit tests for SaleRepository."""

import pytest
from datetime import datetime, timedelta

from src.domain.repositories.sale_repository import SaleRepository
from src.domain.models.sale import Sale, PaymentStatus


class TestSaleRepository:
    """Test suite for SaleRepository."""

    def test_create_sale(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test creating a sale."""
        repo = SaleRepository(test_db_session)
        sale = Sale(**sample_sale_data)

        created_sale = repo.create(sale)

        assert created_sale.id == sample_sale_data["id"]
        assert created_sale.match_id == sample_sale_data["match_id"]
        assert created_sale.quantity == sample_sale_data["quantity"]

    def test_get_by_id(self, test_db_session, create_sale):
        """Test getting sale by ID."""
        repo = SaleRepository(test_db_session)

        sale = repo.get_by_id(create_sale.id)

        assert sale is not None
        assert sale.id == create_sale.id

    def test_get_by_match(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting sales by match."""
        repo = SaleRepository(test_db_session)

        # Create multiple sales for the match
        for i in range(3):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            sale = Sale(**data)
            repo.create(sale)

        sales = repo.get_by_match(create_match.id)

        assert len(sales) == 3

    def test_get_by_match_completed_only(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting only completed sales."""
        repo = SaleRepository(test_db_session)

        # Create sales with different statuses
        for i, status in enumerate([PaymentStatus.COMPLETED, PaymentStatus.PENDING, PaymentStatus.COMPLETED]):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            data["payment_status"] = status
            sale = Sale(**data)
            repo.create(sale)

        sales = repo.get_by_match(create_match.id, completed_only=True)

        assert len(sales) == 2

    def test_get_by_zone(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting sales by zone."""
        repo = SaleRepository(test_db_session)

        # Create sales
        for i in range(2):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            sale = Sale(**data)
            repo.create(sale)

        sales = repo.get_by_zone(create_zone.id)

        assert len(sales) == 2

    def test_get_by_match_and_zone(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting sales by match and zone."""
        repo = SaleRepository(test_db_session)

        # Create sales
        for i in range(2):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            sale = Sale(**data)
            repo.create(sale)

        sales = repo.get_by_match_and_zone(create_match.id, create_zone.id)

        assert len(sales) == 2

    def test_get_total_sold(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting total tickets sold."""
        repo = SaleRepository(test_db_session)

        # Create sales with different quantities
        for i in range(3):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            data["quantity"] = i + 1  # 1, 2, 3
            data["total_amount"] = data["quantity"] * data["price_per_ticket"]
            sale = Sale(**data)
            repo.create(sale)

        total = repo.get_total_sold(create_match.id)

        assert total == 6  # 1 + 2 + 3

    def test_get_revenue(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting total revenue."""
        repo = SaleRepository(test_db_session)

        # Create sales
        for i in range(3):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            data["quantity"] = 2
            data["price_per_ticket"] = 30.0 + (i * 10)  # 30, 40, 50
            data["total_amount"] = data["quantity"] * data["price_per_ticket"]
            sale = Sale(**data)
            repo.create(sale)

        revenue = repo.get_revenue(match_id=create_match.id)

        assert revenue == 240.0  # (2*30) + (2*40) + (2*50)

    def test_get_average_price(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting average ticket price."""
        repo = SaleRepository(test_db_session)

        # Create sales with different prices
        for i in range(3):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            data["price_per_ticket"] = 30.0 + (i * 10)  # 30, 40, 50
            data["total_amount"] = data["quantity"] * data["price_per_ticket"]
            sale = Sale(**data)
            repo.create(sale)

        avg_price = repo.get_average_price(match_id=create_match.id)

        assert avg_price == 40.0

    def test_get_sales_velocity(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test calculating sales velocity."""
        repo = SaleRepository(test_db_session)

        # Create sales with recent timestamps
        for i in range(3):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            data["quantity"] = 10
            sale = Sale(**data)
            repo.create(sale)

        tickets_sold, velocity = repo.get_sales_velocity(create_match.id, hours=24)

        assert tickets_sold == 30
        assert velocity == 30 / 24

    def test_get_sales_by_customer_type(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting sales count by customer type."""
        repo = SaleRepository(test_db_session)

        # Create sales with different customer types
        from src.domain.models.sale import CustomerType
        for i, ctype in enumerate([CustomerType.MEMBER, CustomerType.GENERAL, CustomerType.MEMBER]):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            data["customer_type"] = ctype
            sale = Sale(**data)
            repo.create(sale)

        sales_by_type = repo.get_sales_by_customer_type(create_match.id)

        assert sales_by_type["member"] == 2
        assert sales_by_type["general"] == 1

    def test_update_payment_status(self, test_db_session, create_sale):
        """Test updating payment status."""
        repo = SaleRepository(test_db_session)

        updated = repo.update_payment_status(create_sale.id, PaymentStatus.REFUNDED)

        assert updated is not None
        assert updated.payment_status == PaymentStatus.REFUNDED

    def test_get_recent_sales(self, test_db_session, create_match, create_zone, sample_sale_data):
        """Test getting recent sales."""
        repo = SaleRepository(test_db_session)

        # Create sales
        for i in range(5):
            data = sample_sale_data.copy()
            data["id"] = f"sale_{i}"
            sale = Sale(**data)
            repo.create(sale)

        recent_sales = repo.get_recent_sales(hours=24, limit=3)

        assert len(recent_sales) <= 3
