"""Unit tests for ModelRetrainerWorker."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.domain.models.match import CompetitionType, Match, MatchStatus
from src.workers.model_retrainer import ModelRetrainerWorker


@pytest.fixture
def temp_model_dir():
    """Create temporary directory for model files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_dependencies():
    """Mock all dependencies for ModelRetrainerWorker."""
    with patch("src.workers.model_retrainer.get_db_session") as mock_db_session, \
         patch("src.workers.model_retrainer.MatchRepository") as mock_match_repo, \
         patch("src.workers.model_retrainer.SaleRepository") as mock_sale_repo, \
         patch("src.workers.model_retrainer.DemandModel") as mock_model, \
         patch("src.workers.model_retrainer.prepare_features_and_target") as mock_prepare:

        # Mock database session
        db_mock = MagicMock()
        mock_db_session.return_value = iter([db_mock])

        # Mock repositories
        match_repo_mock = MagicMock()
        sale_repo_mock = MagicMock()

        mock_match_repo.return_value = match_repo_mock
        mock_sale_repo.return_value = sale_repo_mock

        # Mock model
        model_mock = MagicMock()
        mock_model.return_value = model_mock

        # Mock prepare function
        import pandas as pd
        X_mock = pd.DataFrame({"feature1": [1, 2, 3]})
        y_mock = pd.Series([0.5, 0.6, 0.7])
        mock_prepare.return_value = (X_mock, y_mock)

        yield {
            "db": db_mock,
            "match_repo": match_repo_mock,
            "sale_repo": sale_repo_mock,
            "model": model_mock,
            "prepare": mock_prepare,
            "X": X_mock,
            "y": y_mock,
        }


def create_sample_matches(count=10):
    """Create sample matches for testing."""
    matches = []
    for i in range(count):
        match = Match.model_validate({
            "id": f"match{i}",
            "home_team": "Real Mallorca",
            "away_team": f"Team {i}",
            "competition": "la_liga",
            "match_date": datetime.now() - timedelta(days=i * 7),
            "venue": "Son Moix",
            "capacity": 23142,
            "is_derby": False,
            "is_holiday": False,
            "status": "completed",
        })
        matches.append(match)
    return matches


def test_worker_initialization(temp_model_dir):
    """Test worker initialization."""
    worker = ModelRetrainerWorker(
        retraining_interval=604800,
        min_training_samples=100,
        improvement_threshold=0.05,
        model_dir=temp_model_dir,
        max_consecutive_errors=3
    )

    assert worker.name == "ModelRetrainerWorker"
    assert worker.retraining_interval == 604800
    assert worker.min_training_samples == 100
    assert worker.improvement_threshold == 0.05
    assert worker.max_consecutive_errors == 3
    assert worker.retraining_count == 0
    assert worker.deployments_count == 0


def test_worker_creates_model_directory():
    """Test that worker creates model directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir) / "models"
        assert not model_dir.exists()

        worker = ModelRetrainerWorker(model_dir=str(model_dir))

        assert model_dir.exists()


def test_load_training_data(mock_dependencies):
    """Test loading training data."""
    worker = ModelRetrainerWorker(retraining_interval=1, min_training_samples=5)
    worker.db = mock_dependencies["db"]

    # Mock data
    sample_matches = create_sample_matches(10)
    mock_dependencies["match_repo"].get_by_date_range.return_value = sample_matches
    mock_dependencies["sale_repo"].get_by_match.return_value = []

    with patch("src.workers.model_retrainer.MatchRepository", return_value=mock_dependencies["match_repo"]), \
         patch("src.workers.model_retrainer.SaleRepository", return_value=mock_dependencies["sale_repo"]):
        matches, sales = worker._load_training_data()

    assert len(matches) == 10
    mock_dependencies["match_repo"].get_by_date_range.assert_called_once()


def test_load_training_data_filters_incomplete_matches(mock_dependencies):
    """Test that only completed matches are loaded."""
    worker = ModelRetrainerWorker(retraining_interval=1)
    worker.db = mock_dependencies["db"]

    # Mix of completed and scheduled matches
    matches = create_sample_matches(5)
    scheduled_match = Match.model_validate({
        "id": "match_scheduled",
        "home_team": "Real Mallorca",
        "away_team": "Team X",
        "competition": "la_liga",
        "match_date": datetime.now() + timedelta(days=7),
        "venue": "Son Moix",
        "capacity": 23142,
        "is_derby": False,
        "is_holiday": False,
        "status": "scheduled",
    })
    all_matches = matches + [scheduled_match]

    mock_dependencies["match_repo"].get_by_date_range.return_value = all_matches
    mock_dependencies["sale_repo"].get_by_match.return_value = []

    with patch("src.workers.model_retrainer.MatchRepository", return_value=mock_dependencies["match_repo"]), \
         patch("src.workers.model_retrainer.SaleRepository", return_value=mock_dependencies["sale_repo"]):
        matches, sales = worker._load_training_data()

    # Should only include completed matches
    assert len(matches) == 5


def test_prepare_training_data(mock_dependencies):
    """Test preparing training data."""
    worker = ModelRetrainerWorker(retraining_interval=1)

    matches = create_sample_matches(5)
    sales = []

    X, y = worker._prepare_training_data(matches, sales)

    assert len(X) == 3
    assert len(y) == 3
    mock_dependencies["prepare"].assert_called_once()


def test_train_new_model(mock_dependencies):
    """Test training new model."""
    worker = ModelRetrainerWorker(retraining_interval=1)

    X = mock_dependencies["X"]
    y = mock_dependencies["y"]

    with patch("src.workers.model_retrainer.DemandModel", return_value=mock_dependencies["model"]):
        model = worker._train_new_model(X, y)

    mock_dependencies["model"].train.assert_called_once_with(X, y)


def test_evaluate_and_compare_no_current_model(mock_dependencies, temp_model_dir):
    """Test evaluation when no current model exists."""
    worker = ModelRetrainerWorker(
        retraining_interval=1,
        improvement_threshold=0.05,
        model_dir=temp_model_dir
    )

    new_model = mock_dependencies["model"]
    new_model.evaluate.return_value = {"mae": 0.1, "rmse": 0.15, "r2": 0.85}

    X = mock_dependencies["X"]
    y = mock_dependencies["y"]

    should_deploy, metrics = worker._evaluate_and_compare(new_model, X, y)

    assert should_deploy is True
    assert "mae" in metrics


def test_evaluate_and_compare_new_model_better(mock_dependencies, temp_model_dir):
    """Test evaluation when new model is better."""
    worker = ModelRetrainerWorker(
        retraining_interval=1,
        improvement_threshold=0.05,
        model_dir=temp_model_dir
    )

    # Create a current model file
    current_model_path = Path(temp_model_dir) / "demand_model_current.pkl"
    current_model_path.touch()

    # Mock current and new model evaluations
    current_model_mock = MagicMock()
    current_model_mock.evaluate.return_value = {"mae": 0.2, "rmse": 0.25, "r2": 0.75}

    new_model = mock_dependencies["model"]
    new_model.evaluate.return_value = {"mae": 0.15, "rmse": 0.18, "r2": 0.85}

    X = mock_dependencies["X"]
    y = mock_dependencies["y"]

    with patch("src.workers.model_retrainer.DemandModel", return_value=current_model_mock):
        should_deploy, metrics = worker._evaluate_and_compare(new_model, X, y)

    # New model has 25% improvement in MAE (0.2 -> 0.15)
    assert should_deploy is True


def test_evaluate_and_compare_new_model_not_better(mock_dependencies, temp_model_dir):
    """Test evaluation when new model is not significantly better."""
    worker = ModelRetrainerWorker(
        retraining_interval=1,
        improvement_threshold=0.10,  # 10% improvement required
        model_dir=temp_model_dir
    )

    # Create a current model file
    current_model_path = Path(temp_model_dir) / "demand_model_current.pkl"
    current_model_path.touch()

    # Mock current and new model evaluations
    current_model_mock = MagicMock()
    current_model_mock.evaluate.return_value = {"mae": 0.2, "rmse": 0.25, "r2": 0.75}

    new_model = mock_dependencies["model"]
    new_model.evaluate.return_value = {"mae": 0.19, "rmse": 0.24, "r2": 0.76}

    X = mock_dependencies["X"]
    y = mock_dependencies["y"]

    with patch("src.workers.model_retrainer.DemandModel", return_value=current_model_mock):
        should_deploy, metrics = worker._evaluate_and_compare(new_model, X, y)

    # New model has only 5% improvement, but threshold is 10%
    assert should_deploy is False


def test_deploy_model(mock_dependencies, temp_model_dir):
    """Test deploying a model."""
    worker = ModelRetrainerWorker(
        retraining_interval=1,
        model_dir=temp_model_dir
    )

    model = mock_dependencies["model"]
    metrics = {"mae": 0.1, "rmse": 0.15, "r2": 0.85}

    worker._deploy_model(model, metrics)

    # Verify model was saved
    model.save.assert_called_once()

    # Verify metrics file was created
    metrics_path = Path(temp_model_dir) / "current_model_metrics.json"
    assert metrics_path.exists()


def test_deploy_model_backs_up_current(mock_dependencies, temp_model_dir):
    """Test that current model is backed up when deploying new model."""
    worker = ModelRetrainerWorker(
        retraining_interval=1,
        model_dir=temp_model_dir
    )

    # Create a current model file
    current_model_path = Path(temp_model_dir) / "demand_model_current.pkl"
    current_model_path.write_text("old model")

    model = mock_dependencies["model"]
    metrics = {"mae": 0.1, "rmse": 0.15, "r2": 0.85}

    worker._deploy_model(model, metrics)

    # Verify backup was created
    backup_dir = Path(temp_model_dir) / "backups"
    assert backup_dir.exists()
    backups = list(backup_dir.glob("demand_model_*.pkl"))
    assert len(backups) == 1


def test_get_metrics():
    """Test getting worker metrics."""
    worker = ModelRetrainerWorker(retraining_interval=604800)
    worker.retraining_count = 5
    worker.deployments_count = 3
    worker.total_execution_time = 450.5
    worker.error_count = 1

    metrics = worker.get_metrics()

    assert metrics["worker_name"] == "ModelRetrainerWorker"
    assert metrics["running"] is False
    assert metrics["retraining_count"] == 5
    assert metrics["deployments_count"] == 3
    assert metrics["deployment_rate"] == 0.6  # 3/5
    assert metrics["total_execution_time"] == 450.5
    assert metrics["error_count"] == 1
    assert "is_healthy" in metrics


def test_execute_retraining_cycle_insufficient_data(mock_dependencies):
    """Test retraining cycle with insufficient data."""
    worker = ModelRetrainerWorker(
        retraining_interval=1,
        min_training_samples=100
    )
    worker.db = mock_dependencies["db"]

    # Mock insufficient data
    sample_matches = create_sample_matches(5)  # Only 5 matches
    mock_dependencies["match_repo"].get_by_date_range.return_value = sample_matches
    mock_dependencies["sale_repo"].get_by_match.return_value = []

    with patch("src.workers.model_retrainer.MatchRepository", return_value=mock_dependencies["match_repo"]), \
         patch("src.workers.model_retrainer.SaleRepository", return_value=mock_dependencies["sale_repo"]):
        worker._execute_retraining_cycle()

    # Should skip retraining
    assert worker.retraining_count == 0
