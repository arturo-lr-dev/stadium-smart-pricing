"""Pytest fixtures for API integration tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import create_app
from src.core.config import Settings
from src.core.dependencies import get_db
from src.domain.models.db_models import Base


@pytest.fixture(scope="module")
def test_settings():
    """Create test settings."""
    return Settings(
        environment="testing",
        database={"url": "sqlite:///:memory:"},  # In-memory SQLite for tests
    )


@pytest.fixture(scope="module")
def test_db_engine(test_settings):
    """Create test database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def test_db_session(test_db_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine,
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client(test_settings, test_db_session):
    """Create test client."""
    app = create_app(settings=test_settings)

    # Override database dependency
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client
