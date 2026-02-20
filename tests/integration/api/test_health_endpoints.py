"""Integration tests for health and status endpoints."""

import pytest
from fastapi import status


def test_root_endpoint(client):
    """Test root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "docs" in data


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "services" in data


def test_readiness_check(client):
    """Test readiness check endpoint."""
    response = client.get("/status/ready")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "ready" in data
    assert "checks" in data


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == status.HTTP_200_OK

    # Metrics endpoint returns Prometheus text format, not JSON
    assert response.headers["content-type"].startswith("text/plain")
    content = response.text
    # Verify it contains some expected metrics
    assert len(content) > 0


def test_docs_endpoint(client):
    """Test that OpenAPI docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == status.HTTP_200_OK


def test_openapi_json(client):
    """Test that OpenAPI JSON is accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert "paths" in data
