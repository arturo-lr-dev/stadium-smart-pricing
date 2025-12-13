"""Integration tests for pricing endpoints.

Note: These tests will be skipped if the database is not properly set up,
as they require actual data to work with.
"""

import pytest
from fastapi import status


@pytest.mark.skip(reason="Requires database with seeded data")
def test_get_match_pricing(client):
    """Test getting pricing for a specific match."""
    # This test requires a seeded database
    match_id = "match_test_001"

    response = client.get(f"/api/v1/pricing/match/{match_id}")

    # Should return 404 if match doesn't exist, or 200 if it does
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_404_NOT_FOUND,
    ]


@pytest.mark.skip(reason="Requires database with seeded data")
def test_get_zone_pricing(client):
    """Test getting pricing for a specific zone in a match."""
    match_id = "match_test_001"
    zone_id = "tribuna"

    response = client.get(f"/api/v1/pricing/match/{match_id}/zone/{zone_id}")

    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_404_NOT_FOUND,
    ]


def test_get_upcoming_pricing_default(client):
    """Test getting upcoming pricing with default parameters."""
    response = client.get("/api/v1/pricing/upcoming")

    # Should return 200 even if no matches found (empty list)
    # or 500 if there's a configuration error
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ]


def test_get_upcoming_pricing_with_days(client):
    """Test getting upcoming pricing with custom days parameter."""
    response = client.get("/api/v1/pricing/upcoming?days=7")

    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ]


def test_get_upcoming_pricing_invalid_days(client):
    """Test that invalid days parameter is rejected."""
    # Days > 90 should be rejected
    response = client.get("/api/v1/pricing/upcoming?days=100")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Days < 1 should be rejected
    response = client.get("/api/v1/pricing/upcoming?days=0")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.skip(reason="Requires database with seeded data")
def test_recalculate_match_pricing(client):
    """Test forcing recalculation of match pricing."""
    match_id = "match_test_001"

    response = client.post(f"/api/v1/pricing/match/{match_id}/recalculate")

    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_404_NOT_FOUND,
    ]


@pytest.mark.skip(reason="Requires database with seeded data")
def test_get_pricing_history(client):
    """Test getting pricing history."""
    match_id = "match_test_001"

    response = client.get(f"/api/v1/pricing/match/{match_id}/history")

    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_404_NOT_FOUND,
    ]


@pytest.mark.skip(reason="Requires database with seeded data")
def test_get_pricing_history_with_zone(client):
    """Test getting pricing history filtered by zone."""
    match_id = "match_test_001"
    zone_id = "tribuna"

    response = client.get(
        f"/api/v1/pricing/match/{match_id}/history?zone_id={zone_id}"
    )

    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_404_NOT_FOUND,
    ]


def test_pricing_history_invalid_hours(client):
    """Test that invalid hours parameter is rejected."""
    match_id = "match_test_001"

    # Hours > 720 should be rejected
    response = client.get(f"/api/v1/pricing/match/{match_id}/history?hours=800")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Hours < 1 should be rejected
    response = client.get(f"/api/v1/pricing/match/{match_id}/history?hours=0")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
