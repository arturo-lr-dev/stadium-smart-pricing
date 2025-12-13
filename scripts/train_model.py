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

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def train_model():
    """Train the demand prediction model."""
    logger.info("=" * 60)
    logger.info("Starting ML Model Training")
    logger.info("=" * 60)

    try:
        # Initialize model
        logger.info("Initializing DemandModel...")
        model = DemandModel()

        # Train model (uses synthetic/historical data)
        logger.info("Training model...")
        model.train()

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
