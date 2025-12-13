"""
Training script for demand prediction model.

Trains the demand model on historical sales and match data.
"""

import logging
import argparse
import sys
from pathlib import Path
from typing import Tuple, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings
from src.core.database import get_db_session
from src.core.logging import setup_logging
from src.domain.models.match import Match
from src.domain.models.zone import Zone
from src.domain.models.db_models import MatchDB, ZoneDB, SaleDB
from src.ml.models.demand_model import DemandModel

logger = logging.getLogger(__name__)


def load_training_data() -> Tuple[List[Match], List[Zone], pd.DataFrame]:
    """
    Load historical matches, zones, and sales data from the database.

    Returns:
        Tuple of (matches, zones, sales_df)
    """
    logger.info("Loading training data from database...")

    with get_db_session() as db:
        # Load matches
        matches_db = db.query(MatchDB).all()
        matches = [Match(
            id=m.id,
            home_team=m.home_team,
            away_team=m.away_team,
            competition=m.competition,
            match_date=m.match_date,
            venue=m.venue,
            capacity=m.capacity,
            is_derby=m.is_derby,
            is_holiday=m.is_holiday,
            home_position=m.home_position,
            away_position=m.away_position,
            status=m.status
        ) for m in matches_db]

        # Load zones
        zones_db = db.query(ZoneDB).filter(ZoneDB.is_active == True).all()
        zones = [Zone(
            id=z.id,
            name=z.name,
            category=z.category,
            capacity=z.capacity,
            base_price=z.base_price,
            min_price=z.min_price,
            max_price=z.max_price,
            price_multiplier=z.price_multiplier
        ) for z in zones_db]

        # Load sales data
        sales_query = """
            SELECT
                s.match_id,
                s.zone_id,
                DATE(s.purchase_datetime) as purchase_datetime,
                COUNT(*) as num_sales,
                SUM(s.quantity) as total_quantity
            FROM sales s
            INNER JOIN matches m ON s.match_id = m.id
            WHERE s.payment_status = 'COMPLETED'::paymentstatus
            GROUP BY s.match_id, s.zone_id, DATE(s.purchase_datetime)
            ORDER BY purchase_datetime
        """
        sales_df = pd.read_sql(sales_query, db.bind)

    logger.info(
        f"Loaded {len(matches)} matches, {len(zones)} zones, "
        f"{len(sales_df)} sales records"
    )

    return matches, zones, sales_df


def prepare_features_and_target(
    matches: List[Match],
    zones: List[Zone],
    sales_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Prepare feature matrix and target variable for training.

    The target is the occupancy rate (% of zone filled) at different
    points in time before the match.

    Args:
        matches: List of Match objects
        zones: List of Zone objects
        sales_df: DataFrame with sales data

    Returns:
        Tuple of (X_features, y_target)
    """
    logger.info("Preparing features and target...")

    # Create lookup dictionaries
    match_dict = {m.id: m for m in matches}
    zone_dict = {z.id: z for z in zones}

    # Initialize model to use feature extractors
    model = DemandModel()

    samples = []

    # For each match and zone, create training samples
    for match in matches:
        # Skip future matches (no sales data yet)
        if match.date > datetime.now():
            continue


        for zone in zones:
            # Get sales for this match-zone combination
            zone_sales = sales_df[
                (sales_df['match_id'] == match.id) &
                (sales_df['zone_id'] == zone.id)
            ]

            if zone_sales.empty:
                continue

            # Convert purchase_datetime to datetime if it's string
            zone_sales = zone_sales.copy()
            zone_sales['purchase_datetime'] = pd.to_datetime(zone_sales['purchase_datetime'])

            # Calculate cumulative sales over time
            zone_sales = zone_sales.sort_values('purchase_datetime')
            zone_sales['cumulative_quantity'] = zone_sales['total_quantity'].cumsum()

            # Create samples at different time points (7, 14, 30 days before match)
            sample_days = [1, 3, 7, 14, 21, 30]

            for days_before in sample_days:
                cutoff_date = match.date - timedelta(days=days_before)

                # Get sales up to this point
                sales_up_to_cutoff = zone_sales[
                    zone_sales['purchase_datetime'] <= cutoff_date
                ]

                if sales_up_to_cutoff.empty:
                    sold_quantity = 0
                else:
                    sold_quantity = sales_up_to_cutoff['cumulative_quantity'].iloc[-1]

                # Calculate occupancy rate (target)
                occupancy_rate = min(1.0, sold_quantity / zone.capacity)

                # Extract features
                features = model.extract_features(match, zone, days_before)
                features['target_occupancy'] = occupancy_rate

                samples.append(features)

    # Convert to DataFrame
    df = pd.DataFrame(samples)

    # Separate features and target
    y = df['target_occupancy']
    X = df.drop('target_occupancy', axis=1)

    # Convert boolean columns to int
    bool_columns = X.select_dtypes(include=['bool']).columns
    X[bool_columns] = X[bool_columns].astype(int)

    # Drop non-numeric columns (like season string)
    X = X.select_dtypes(include=[np.number])

    logger.info(f"Prepared {len(X)} training samples with {len(X.columns)} features")
    logger.info(f"Target statistics: mean={y.mean():.3f}, std={y.std():.3f}")

    return X, y


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    config: dict
) -> DemandModel:
    """
    Train the demand model.

    Args:
        X: Feature matrix
        y: Target variable
        config: Configuration dictionary

    Returns:
        Trained DemandModel
    """
    logger.info("Training demand model...")

    model_type = config.get('model_type', 'random_forest')
    model_params = config.get('model_params')
    use_scaler = config.get('use_scaler', False)

    model = DemandModel(
        model_type=model_type,
        model_params=model_params,
        use_scaler=use_scaler
    )

    # Train
    metrics = model.train(X, y, validation_split=0.2)

    logger.info("Training completed!")
    logger.info(f"Training metrics: {metrics}")

    # Show feature importance
    feature_importance = model.get_feature_importance(top_n=10)
    logger.info("Top 10 most important features:")
    for feature, importance in feature_importance.items():
        logger.info(f"  {feature}: {importance:.4f}")

    return model


def main():
    """Main training function."""
    parser = argparse.ArgumentParser(description='Train demand prediction model')
    parser.add_argument(
        '--model-type',
        type=str,
        default='random_forest',
        choices=['random_forest', 'gradient_boosting'],
        help='Type of model to train'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='models/demand_model.pkl',
        help='Path to save the trained model'
    )
    parser.add_argument(
        '--use-scaler',
        action='store_true',
        help='Use StandardScaler for feature normalization'
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
    logger.info("Starting Demand Model Training")
    logger.info("=" * 80)

    try:
        # Load data
        matches, zones, sales_df = load_training_data()

        if len(matches) == 0 or len(sales_df) == 0:
            logger.error("No training data available. Please seed the database first.")
            return 1

        # Prepare features and target
        X, y = prepare_features_and_target(matches, zones, sales_df)

        if len(X) < 10:
            logger.error(f"Insufficient training samples ({len(X)}). Need at least 10.")
            return 1

        # Train model
        config = {
            'model_type': args.model_type,
            'use_scaler': args.use_scaler,
        }
        model = train_model(X, y, config)

        # Save model
        output_path = Path(args.output)
        model.save(str(output_path))
        logger.info(f"Model saved to {output_path}")

        # Save feature list for reference
        feature_list_path = output_path.parent / f"{output_path.stem}_features.txt"
        with open(feature_list_path, 'w') as f:
            f.write("\n".join(model.feature_names))
        logger.info(f"Feature list saved to {feature_list_path}")

        logger.info("=" * 80)
        logger.info("Training completed successfully!")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.exception(f"Training failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
