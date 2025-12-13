#!/usr/bin/env python3
"""
Train ML model for demand prediction.

This script trains the demand prediction model using historical data
from the database.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.logging import setup_logging
from src.ml.models.demand_model import DemandModel
from src.ml.training.train_demand import load_training_data, prepare_features_and_target

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def train_model():
    """Train the demand prediction model."""
    logger.info("=" * 60)
    logger.info("Starting ML Model Training")
    logger.info("=" * 60)

    try:
        # Load historical data from database
        logger.info("Loading training data from database...")
        matches, zones, sales_df = load_training_data()
        
        if len(matches) == 0 or len(sales_df) == 0:
            logger.error("❌ No training data available. Please seed the database first.")
            logger.info("   Run: python scripts/seed_historical_data.py")
            return False
        
        # Prepare features and target
        logger.info("Preparing features and target...")
        X, y = prepare_features_and_target(matches, zones, sales_df)
        
        if len(X) < 10:
            logger.error(f"❌ Insufficient training samples ({len(X)}). Need at least 10.")
            return False
        
        logger.info(f"   Training samples: {len(X)}")
        logger.info(f"   Features: {len(X.columns)}")
        logger.info(f"   Target mean: {y.mean():.3f}, std: {y.std():.3f}")

        # Initialize and train model
        logger.info("Initializing DemandModel...")
        model = DemandModel()

        # Train model with prepared data
        logger.info("Training model...")
        metrics = model.train(X, y)
        
        logger.info("Training completed!")
        logger.info(f"   Validation MAE: {metrics['val_mae']:.4f}")
        logger.info(f"   Validation RMSE: {metrics['val_rmse']:.4f}")
        logger.info(f"   Validation R²: {metrics['val_r2']:.4f}")

        # Save model
        model_path = project_root / "models" / "demand_model.pkl"
        model_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving model to {model_path}...")
        model.save(str(model_path))

        # Save feature names
        features_path = model_path.parent / "demand_model_features.txt"
        with open(features_path, "w") as f:
            f.write("\n".join(model.feature_names))

        logger.info(f"✅ Model trained and saved successfully")
        logger.info(f"   Model file: {model_path} ({model_path.stat().st_size} bytes)")
        logger.info(f"   Features: {len(model.feature_names)}")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"❌ Error training model: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = train_model()
    sys.exit(0 if success else 1)
