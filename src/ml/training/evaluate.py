"""
Evaluation script for demand prediction model.

Evaluates a trained model on test data and generates visualizations.
"""

import logging
import argparse
import sys
from pathlib import Path
from typing import Dict, Any
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.logging import setup_logging
from src.ml.models.demand_model import DemandModel
from src.ml.training.train_demand import load_training_data, prepare_features_and_target
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

# Set plotting style
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)


def load_model(path: str) -> DemandModel:
    """
    Load a trained model from disk.

    Args:
        path: Path to model file

    Returns:
        Loaded DemandModel
    """
    logger.info(f"Loading model from {path}")
    model = DemandModel()  # Create empty model
    model.load(path)
    logger.info(f"Model loaded: {model.model_name}")
    return model


def evaluate_model(
    model: DemandModel,
    X_test: pd.DataFrame,
    y_test: pd.Series
) -> Dict[str, Any]:
    """
    Evaluate model on test data.

    Args:
        model: Trained model
        X_test: Test features
        y_test: Test labels

    Returns:
        Dictionary with evaluation results
    """
    logger.info("Evaluating model on test data...")

    # Get predictions
    predictions = model.predict(X_test)

    # Calculate metrics
    metrics = model.evaluate(X_test, y_test)

    # Calculate additional metrics
    residuals = y_test - predictions
    metrics['mean_residual'] = np.mean(residuals)
    metrics['std_residual'] = np.std(residuals)
    metrics['max_error'] = np.max(np.abs(residuals))

    # Prediction ranges
    metrics['mean_prediction'] = np.mean(predictions)
    metrics['std_prediction'] = np.std(predictions)
    metrics['min_prediction'] = np.min(predictions)
    metrics['max_prediction'] = np.max(predictions)

    logger.info(f"Test MAE: {metrics['mae']:.4f}")
    logger.info(f"Test RMSE: {metrics['rmse']:.4f}")
    logger.info(f"Test R²: {metrics['r2']:.4f}")

    return {
        'metrics': metrics,
        'predictions': predictions,
        'residuals': residuals
    }


def plot_predictions_vs_actual(
    y_test: pd.Series,
    predictions: np.ndarray,
    output_dir: Path
) -> None:
    """
    Plot predictions vs actual values.

    Args:
        y_test: True values
        predictions: Predicted values
        output_dir: Directory to save plots
    """
    logger.info("Generating predictions vs actual plot...")

    plt.figure(figsize=(10, 10))
    plt.scatter(y_test, predictions, alpha=0.5, s=20)
    plt.plot([0, 1], [0, 1], 'r--', lw=2, label='Perfect prediction')
    plt.xlabel('Actual Occupancy Rate', fontsize=12)
    plt.ylabel('Predicted Occupancy Rate', fontsize=12)
    plt.title('Predictions vs Actual Values', fontsize=14, fontweight='bold')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xlim(0, 1)
    plt.ylim(0, 1)

    output_path = output_dir / 'predictions_vs_actual.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Plot saved to {output_path}")


def plot_residuals(
    residuals: np.ndarray,
    output_dir: Path
) -> None:
    """
    Plot residual distribution.

    Args:
        residuals: Prediction residuals
        output_dir: Directory to save plots
    """
    logger.info("Generating residuals plot...")

    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    # Histogram
    axes[0].hist(residuals, bins=50, alpha=0.7, edgecolor='black')
    axes[0].axvline(x=0, color='r', linestyle='--', linewidth=2)
    axes[0].set_xlabel('Residual', fontsize=12)
    axes[0].set_ylabel('Frequency', fontsize=12)
    axes[0].set_title('Residual Distribution', fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.3)

    # Q-Q plot
    from scipy import stats
    stats.probplot(residuals, dist="norm", plot=axes[1])
    axes[1].set_title('Q-Q Plot', fontsize=14, fontweight='bold')
    axes[1].grid(True, alpha=0.3)

    output_path = output_dir / 'residuals.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Plot saved to {output_path}")


def plot_feature_importance(
    model: DemandModel,
    output_dir: Path,
    top_n: int = 20
) -> None:
    """
    Plot feature importance.

    Args:
        model: Trained model
        output_dir: Directory to save plots
        top_n: Number of top features to plot
    """
    logger.info("Generating feature importance plot...")

    feature_importance = model.get_feature_importance(top_n=top_n)

    if not feature_importance:
        logger.warning("No feature importance available for this model")
        return

    # Create plot
    features = list(feature_importance.keys())
    importances = list(feature_importance.values())

    plt.figure(figsize=(12, 8))
    plt.barh(range(len(features)), importances, alpha=0.8)
    plt.yticks(range(len(features)), features)
    plt.xlabel('Importance', fontsize=12)
    plt.ylabel('Feature', fontsize=12)
    plt.title(f'Top {top_n} Most Important Features', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='x')

    output_path = output_dir / 'feature_importance.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Plot saved to {output_path}")


def save_metrics_json(
    metrics: Dict[str, float],
    model_info: Dict[str, Any],
    output_dir: Path
) -> None:
    """
    Save metrics to JSON file.

    Args:
        metrics: Evaluation metrics
        model_info: Model information
        output_dir: Directory to save JSON
    """
    logger.info("Saving metrics to JSON...")

    output = {
        'model_info': model_info,
        'test_metrics': metrics,
        'evaluation_timestamp': pd.Timestamp.now().isoformat()
    }

    output_path = output_dir / 'evaluation_metrics.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    logger.info(f"Metrics saved to {output_path}")


def main():
    """Main evaluation function."""
    parser = argparse.ArgumentParser(description='Evaluate demand prediction model')
    parser.add_argument(
        '--model-path',
        type=str,
        default='models/demand_model.pkl',
        help='Path to trained model file'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='evaluation_results',
        help='Directory to save evaluation results'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()
    logging.getLogger().setLevel(args.log_level)

    logger.info("=" * 80)
    logger.info("Starting Model Evaluation")
    logger.info("=" * 80)

    try:
        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load model
        model = load_model(args.model_path)
        model_info = model.get_model_info()

        # Load data
        logger.info("Loading data...")
        matches, zones, sales_df = load_training_data()
        X, y = prepare_features_and_target(matches, zones, sales_df)

        # Split into train/test (use same split as training)
        _, X_test, _, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Evaluate
        results = evaluate_model(model, X_test, y_test)

        # Generate plots
        plot_predictions_vs_actual(y_test, results['predictions'], output_dir)
        plot_residuals(results['residuals'], output_dir)
        plot_feature_importance(model, output_dir, top_n=20)

        # Save metrics
        save_metrics_json(results['metrics'], model_info, output_dir)

        logger.info("=" * 80)
        logger.info("Evaluation completed successfully!")
        logger.info(f"Results saved to {output_dir}")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.exception(f"Evaluation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
