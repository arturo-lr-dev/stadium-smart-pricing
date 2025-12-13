"""
Unit tests for demand prediction model.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
import tempfile

from src.ml.models.demand_model import DemandModel
from src.domain.models.match import Match, CompetitionType, MatchStatus
from src.domain.models.zone import Zone, ZoneCategory


@pytest.fixture
def sample_match():
    """Create a sample match for testing."""
    return Match(
        id="match-1",
        home_team="RCD Mallorca",
        away_team="FC Barcelona",
        competition=CompetitionType.LA_LIGA,
        match_date=datetime(2024, 3, 15, 20, 0, 0),
        venue="Son Moix",
        capacity=23000,
        is_derby=False,
        is_holiday=False,
        home_position=10,
        away_position=1,
        status=MatchStatus.SCHEDULED
    )


@pytest.fixture
def sample_zone():
    """Create a sample zone for testing."""
    return Zone(
        id="zone-standard-1",
        name="Standard North",
        category=ZoneCategory.STANDARD,
        capacity=8000,
        base_price=40.0,
        min_price=30.0,
        max_price=80.0,
        price_multiplier=1.0
    )


@pytest.fixture
def training_data():
    """Create synthetic training data."""
    np.random.seed(42)
    n_samples = 100

    # Create random features
    X = pd.DataFrame({
        'match_importance': np.random.uniform(0.3, 1.0, n_samples),
        'rival_position_normalized': np.random.uniform(0, 1, n_samples),
        'days_to_match': np.random.randint(1, 60, n_samples),
        'is_weekend': np.random.choice([0, 1], n_samples),
        'is_derby': np.random.choice([0, 1], n_samples, p=[0.9, 0.1]),
        'zone_capacity': np.random.uniform(3000, 10000, n_samples),
        'temperature': np.random.uniform(10, 30, n_samples),
    })

    # Create target (occupancy rate) based on features
    y = (
        0.3 +
        0.3 * X['match_importance'] +
        0.2 * X['rival_position_normalized'] +
        0.1 * X['is_derby'] +
        0.1 * X['is_weekend'] -
        0.01 * X['days_to_match']
    )
    y = np.clip(y + np.random.normal(0, 0.05, n_samples), 0, 1)
    y = pd.Series(y, name='occupancy')

    return X, y


class TestDemandModel:
    """Tests for DemandModel."""

    def test_initialization_random_forest(self):
        """Test model initialization with Random Forest."""
        model = DemandModel(model_type="random_forest")

        assert model.model_name == "demand_model_random_forest"
        assert model.model is not None
        assert model.is_trained is False

    def test_initialization_gradient_boosting(self):
        """Test model initialization with Gradient Boosting."""
        model = DemandModel(model_type="gradient_boosting")

        assert model.model_name == "demand_model_gradient_boosting"
        assert model.model is not None

    def test_initialization_invalid_type(self):
        """Test that invalid model type raises error."""
        with pytest.raises(ValueError, match="Unknown model_type"):
            DemandModel(model_type="invalid_model")

    def test_extract_features(self, sample_match, sample_zone):
        """Test feature extraction."""
        model = DemandModel()
        features = model.extract_features(sample_match, sample_zone, days_to_match=14)

        assert isinstance(features, dict)
        assert "days_to_match" in features
        assert features["days_to_match"] == 14
        assert "match_importance" in features
        assert "zone_capacity" in features
        assert len(features) > 30  # Should have many features

    def test_train_and_predict(self, training_data):
        """Test training and prediction."""
        X, y = training_data
        model = DemandModel(model_type="random_forest")

        # Train
        metrics = model.train(X, y, validation_split=0.2)

        assert model.is_trained is True
        assert "val_mae" in metrics
        assert "val_r2" in metrics
        assert metrics["val_mae"] >= 0
        assert -1 <= metrics["val_r2"] <= 1

        # Predict
        predictions = model.predict(X.head(10))

        assert len(predictions) == 10
        assert np.all(predictions >= 0)
        assert np.all(predictions <= 1)

    def test_fallback_demand(self, sample_match, sample_zone):
        """Test heuristic fallback method."""
        model = DemandModel()

        # Should use fallback when not trained
        demand = model._fallback_demand(sample_match, sample_zone, days_to_match=7)

        assert 0 <= demand <= 1
        assert isinstance(demand, (float, np.floating))

    def test_predict_demand_untrained(self, sample_match, sample_zone):
        """Test prediction when model is not trained (uses fallback)."""
        model = DemandModel()

        # Should use fallback
        demand = model.predict_demand(sample_match, sample_zone, days_to_match=7)

        assert 0 <= demand <= 1

    def test_predict_demand_trained(self, sample_match, sample_zone, training_data):
        """Test prediction with trained model."""
        X, y = training_data
        model = DemandModel()
        model.train(X, y, validation_split=0.2)

        # Should use ML model
        demand = model.predict_demand(sample_match, sample_zone, days_to_match=7)

        assert 0 <= demand <= 1

    def test_save_and_load(self, training_data):
        """Test saving and loading model."""
        X, y = training_data
        model = DemandModel(model_type="random_forest")
        model.train(X, y, validation_split=0.2)

        # Save
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pkl"
            model.save(str(model_path))

            assert model_path.exists()

            # Load
            loaded_model = DemandModel()
            loaded_model.load(str(model_path))

            assert loaded_model.is_trained is True
            assert loaded_model.model_name == model.model_name
            assert loaded_model.feature_names == model.feature_names

            # Predictions should be the same
            pred_original = model.predict(X.head(5))
            pred_loaded = loaded_model.predict(X.head(5))
            np.testing.assert_array_almost_equal(pred_original, pred_loaded)

    def test_get_feature_importance(self, training_data):
        """Test feature importance extraction."""
        X, y = training_data
        model = DemandModel(model_type="random_forest")
        model.train(X, y, validation_split=0.2)

        importance = model.get_feature_importance(top_n=5)

        assert isinstance(importance, dict)
        assert len(importance) <= 5
        # All importance values should be positive
        assert all(v >= 0 for v in importance.values())

    def test_get_model_info(self, training_data):
        """Test getting model information."""
        X, y = training_data
        model = DemandModel()

        # Before training
        info = model.get_model_info()
        assert info["is_trained"] is False

        # After training
        model.train(X, y, validation_split=0.2)
        info = model.get_model_info()
        assert info["is_trained"] is True
        assert info["num_features"] == len(X.columns)
        assert "metrics" in info

    def test_evaluate(self, training_data):
        """Test model evaluation."""
        X, y = training_data
        model = DemandModel()
        model.train(X, y, validation_split=0.2)

        # Evaluate on training data
        metrics = model.evaluate(X, y)

        assert "mae" in metrics
        assert "rmse" in metrics
        assert "r2" in metrics
        assert metrics["mae"] >= 0
        assert metrics["rmse"] >= 0

    def test_predictions_clipped(self, training_data):
        """Test that predictions are clipped to [0, 1]."""
        X, y = training_data
        model = DemandModel()
        model.train(X, y, validation_split=0.2)

        # Make many predictions
        predictions = model.predict(X)

        # All should be in valid range
        assert np.all(predictions >= 0)
        assert np.all(predictions <= 1)

    def test_feature_scaling(self, training_data):
        """Test model with feature scaling."""
        X, y = training_data
        model = DemandModel(use_scaler=True)
        model.train(X, y, validation_split=0.2)

        assert model.scaler is not None

        # Should still make valid predictions
        predictions = model.predict(X.head(10))
        assert np.all(predictions >= 0)
        assert np.all(predictions <= 1)
