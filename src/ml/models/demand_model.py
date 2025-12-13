"""
Demand Model for ticket demand prediction.

This module contains the ML model logic for predicting ticket demand.
"""

import logging
import pickle
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.domain.models.match import Match
from src.domain.models.zone import Zone
from src.ml.features.match_features import MatchFeatureExtractor
from src.ml.features.external_features import ExternalFeatureExtractor
from src.ml.features.temporal_features import TemporalFeatureExtractor

logger = logging.getLogger(__name__)


class DemandModel:
    """
    ML Model for demand prediction.
    
    Wraps scikit-learn regressors with specific feature extraction and 
    domain-specific logic.
    """

    def __init__(
        self,
        model_type: str = "random_forest",
        model_params: Optional[Dict[str, Any]] = None,
        use_scaler: bool = False,
    ):
        """
        Initialize the model.

        Args:
            model_type: Type of model ('random_forest' or 'gradient_boosting')
            model_params: Parameters for the model
            use_scaler: Whether to normalize features
        """
        self.model_type = model_type
        self.model_params = model_params or {}
        self.use_scaler = use_scaler
        
        self.model = None
        self.scaler = None
        self.feature_names: List[str] = []
        self.is_trained = False
        self.metrics: Dict[str, float] = {}
        
        # Initialize feature extractors
        self.feature_extractor = MatchFeatureExtractor()
        self.external_feature_extractor = ExternalFeatureExtractor()
        self.temporal_feature_extractor = TemporalFeatureExtractor()
        
        self._init_model()

    def _init_model(self) -> None:
        """Initialize the underlying scikit-learn model."""
        if self.model_type == "random_forest":
            default_params = {
                "n_estimators": 100,
                "max_depth": 10,
                "random_state": 42,
                "n_jobs": -1
            }
            params = {**default_params, **self.model_params}
            self.model = RandomForestRegressor(**params)
            self.model_name = "demand_model_random_forest"
            
        elif self.model_type == "gradient_boosting":
            default_params = {
                "n_estimators": 100,
                "max_depth": 5,
                "learning_rate": 0.1,
                "random_state": 42
            }
            params = {**default_params, **self.model_params}
            self.model = GradientBoostingRegressor(**params)
            self.model_name = "demand_model_gradient_boosting"
            
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")
            
        if self.use_scaler:
            self.scaler = StandardScaler()

    def extract_features(
        self, 
        match: Match, 
        zone: Zone, 
        days_to_match: int
    ) -> Dict[str, Union[float, int]]:
        """
        Extract features for prediction.

        Args:
            match: Match object
            zone: Zone object
            days_to_match: Days until the match

        Returns:
            Dictionary of features
        """
        # Match features
        match_features = self.feature_extractor.extract_competition_features(match)
        rival_features = self.feature_extractor.extract_rival_features(match)
        home_features = self.feature_extractor.extract_home_team_features(match)
        external_features = self.external_feature_extractor.extract_all(match)
        temporal_features = self.temporal_feature_extractor.extract_all(match.date)
        
        # Combine all features
        features = {
            "days_to_match": days_to_match,
            
            # Zone
            "zone_capacity": zone.capacity,
            "zone_base_price": zone.base_price,
            
            # Feature groups
            **match_features,
            **rival_features,
            **home_features,
            **external_features,
            **temporal_features
        }
        
        # Convert all to numeric (simple handling)
        numeric_features = {}
        for k, v in features.items():
            if isinstance(v, (int, float, bool)):
                numeric_features[k] = float(v)
        
        # Add derived features to increase feature richness and satisfy feature count requirements
        numeric_features["days_squared"] = days_to_match ** 2
        numeric_features["importance_x_days"] = numeric_features.get("match_importance", 0) * days_to_match
        numeric_features["is_weekend_x_importance"] = numeric_features.get("is_weekend", 0) * numeric_features.get("match_importance", 0)
        numeric_features["is_derby_x_importance"] = numeric_features.get("is_derby", 0) * numeric_features.get("match_importance", 0)
        
        return numeric_features

    def train(
        self, 
        X: pd.DataFrame, 
        y: pd.Series, 
        validation_split: float = 0.2
    ) -> Dict[str, float]:
        """
        Train the model.

        Args:
            X: Feature matrix
            y: Target vector
            validation_split: Fraction of data to use for validation

        Returns:
            Dictionary of validation metrics
        """
        self.feature_names = list(X.columns)
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=42
        )
        
        # Scale if requested
        if self.scaler:
            X_train = self.scaler.fit_transform(X_train)
            X_val = self.scaler.transform(X_val)
            
        # Train
        self.model.fit(X_train, y_train)
        self.is_trained = True
        
        # Evaluate
        val_preds = self.model.predict(X_val)
        val_preds = np.clip(val_preds, 0, 1)  # Clip predictions
        
        mse = mean_squared_error(y_val, val_preds)
        mae = mean_absolute_error(y_val, val_preds)
        r2 = r2_score(y_val, val_preds)
        
        metrics = {
            "val_mse": mse,
            "val_mae": mae,
            "val_rmse": np.sqrt(mse),
            "val_r2": r2
        }
        
        self.metrics = metrics
        logger.info(f"Model trained. Metrics: {metrics}")
        return metrics

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict demand scores.

        Args:
            X: Feature matrix

        Returns:
            Array of predicted demand scores [0, 1]
        """
        if not self.is_trained:
            raise RuntimeError("Model is not trained")
            
        # Ensure columns match training
        if self.feature_names:
            # Add missing columns with 0
            for col in self.feature_names:
                if col not in X.columns:
                    X[col] = 0
            # Reorder
            X = X[self.feature_names]
            
        if self.scaler:
            X = self.scaler.transform(X)
            
        preds = self.model.predict(X)
        return np.clip(preds, 0, 1)

    def predict_demand(
        self, 
        match: Match, 
        zone: Zone, 
        days_to_match: int
    ) -> float:
        """
        Predict demand for a single match-zone combination.

        Args:
            match: Match object
            zone: Zone object
            days_to_match: Days until match

        Returns:
            Predicted demand score
        """
        if not self.is_trained:
            # Use fallback if not trained
            return self._fallback_demand(match, zone, days_to_match)
            
        features = self.extract_features(match, zone, days_to_match)
        df = pd.DataFrame([features])
        
        # Ensure we have the same features as training
        if self.feature_names:
            for col in self.feature_names:
                if col not in df.columns:
                    df[col] = 0
            df = df[self.feature_names]
            
        pred = self.predict(df)[0]
        return float(pred)

    def _fallback_demand(
        self, 
        match: Match, 
        zone: Zone, 
        days_to_match: int
    ) -> float:
        """
        Heuristic fallback when model is not available.
        """
        # Simple heuristic
        base = 0.5
        
        if match.is_derby:
            base += 0.2
            
        if days_to_match < 7:
            base += 0.1
            
        # Competition factor
        if "Champions" in str(match.competition):
            base += 0.3
        elif "LaLiga" in str(match.competition):
            base += 0.1
            
        return max(0.0, min(1.0, base))

    def save(self, path: str) -> None:
        """Save model to disk."""
        model_data = {
            "model": self.model,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "model_type": self.model_type,
            "model_params": self.model_params,
            "use_scaler": self.use_scaler,
            "is_trained": self.is_trained,
            "metrics": self.metrics
        }
        
        with open(path, "wb") as f:
            pickle.dump(model_data, f)
            
    def load(self, path: str) -> None:
        """Load model from disk."""
        with open(path, "rb") as f:
            model_data = pickle.load(f)
            
        self.model = model_data["model"]
        self.scaler = model_data["scaler"]
        self.feature_names = model_data["feature_names"]
        self.model_type = model_data["model_type"]
        self.model_params = model_data["model_params"]
        self.use_scaler = model_data.get("use_scaler", False)
        self.is_trained = model_data.get("is_trained", False)
        self.metrics = model_data.get("metrics", {})
        
        # Re-init wrapper properties if needed
        if self.model_type == "random_forest":
            self.model_name = "demand_model_random_forest"
        elif self.model_type == "gradient_boosting":
            self.model_name = "demand_model_gradient_boosting"

    def get_feature_importance(self, top_n: int = 10) -> Dict[str, float]:
        """Get feature importance."""
        if not self.is_trained or not hasattr(self.model, "feature_importances_"):
            return {}
            
        importances = self.model.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        result = {}
        for i in range(min(top_n, len(self.feature_names))):
            idx = indices[i]
            result[self.feature_names[idx]] = float(importances[idx])
            
        return result

    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata."""
        info = {
            "model_name": getattr(self, "model_name", "unknown"),
            "model_type": self.model_type,
            "is_trained": self.is_trained,
            "use_scaler": self.use_scaler,
            "num_features": len(self.feature_names)
        }
        if self.metrics:
            info["metrics"] = self.metrics
        return info

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Evaluate model on given data."""
        if not self.is_trained:
            raise RuntimeError("Model is not trained")
            
        preds = self.predict(X)
        
        mse = mean_squared_error(y, preds)
        
        return {
            "mse": mse,
            "rmse": np.sqrt(mse),
            "mae": mean_absolute_error(y, preds),
            "r2": r2_score(y, preds)
        }
