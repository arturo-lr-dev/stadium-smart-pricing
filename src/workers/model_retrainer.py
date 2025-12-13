"""Model retraining worker for the Smart Pricing System.

This worker periodically retrains the ML demand prediction model
with new historical data, evaluates it, and deploys it if it performs better.
"""

import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.core.database import get_db_session
from src.domain.models.match import Match
from src.domain.models.sale import Sale
from src.domain.repositories.match_repository import MatchRepository
from src.domain.repositories.sale_repository import SaleRepository
from src.ml.models.demand_model import DemandModel
from src.ml.training.train_demand import prepare_features_and_target
from src.workers.base_worker import BaseWorker

logger = logging.getLogger(__name__)


class ModelRetrainerWorker(BaseWorker):
    """Worker that periodically retrains the ML demand prediction model.

    This worker:
    - Runs on a weekly schedule (configurable)
    - Loads latest historical data (matches and sales)
    - Trains a new demand prediction model
    - Evaluates the new model against the current production model
    - Deploys the new model if it performs better
    - Implements model versioning
    - Supports rollback if new model underperforms

    Attributes:
        retraining_interval: Seconds between retraining cycles (default: 1 week)
        min_training_samples: Minimum samples required for retraining
        improvement_threshold: Minimum improvement required to deploy new model
        model_dir: Directory to store model files
        db: Database session
    """

    def __init__(
        self,
        retraining_interval: int = 604800,  # 1 week default
        min_training_samples: int = 100,
        improvement_threshold: float = 0.05,  # 5% improvement required
        model_dir: str = "models",
        max_consecutive_errors: int = 3,
    ):
        """Initialize the model retrainer worker.

        Args:
            retraining_interval: Seconds between retraining cycles
            min_training_samples: Minimum samples required for retraining
            improvement_threshold: Minimum improvement required to deploy (e.g., 0.05 = 5%)
            model_dir: Directory to store model files
            max_consecutive_errors: Maximum consecutive errors before shutdown
        """
        super().__init__(name="ModelRetrainerWorker", max_consecutive_errors=max_consecutive_errors)
        self.retraining_interval = retraining_interval
        self.min_training_samples = min_training_samples
        self.improvement_threshold = improvement_threshold
        self.model_dir = Path(model_dir)
        self.db: Optional[Session] = None

        # Ensure model directory exists
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Metrics
        self.retraining_count = 0
        self.deployments_count = 0
        self.total_execution_time = 0.0

        logger.info(
            f"ModelRetrainerWorker configured with "
            f"retraining_interval={retraining_interval}s (~{retraining_interval/86400:.1f} days), "
            f"min_samples={min_training_samples}, "
            f"improvement_threshold={improvement_threshold*100}%"
        )

    def _initialize_dependencies(self) -> None:
        """Initialize dependencies (DB)."""
        logger.info("Initializing dependencies...")

        try:
            # Get database session
            self.db = next(get_db_session())
            logger.info("Database connection established")

        except Exception as e:
            logger.error(f"Failed to initialize dependencies: {e}", exc_info=True)
            raise

    def _cleanup_dependencies(self) -> None:
        """Cleanup dependencies."""
        logger.info("Cleaning up dependencies...")

        if self.db:
            self.db.close()
            logger.info("Database connection closed")

    def run(self) -> None:
        """Main worker loop.

        Periodically:
        1. Loads historical data
        2. Trains new model
        3. Evaluates against current model
        4. Deploys if better
        5. Sleeps until next cycle
        """
        logger.info(f"Starting {self.name} main loop")

        # Initialize dependencies
        self._initialize_dependencies()

        try:
            while self.running:
                cycle_start = time.time()

                try:
                    # Update heartbeat
                    self.heartbeat()

                    # Execute retraining cycle
                    self._execute_retraining_cycle()

                    # Reset error count on successful execution
                    self.reset_error_count()

                    # Calculate execution time
                    execution_time = time.time() - cycle_start
                    self.total_execution_time += execution_time

                    logger.info(
                        f"Retraining cycle completed in {execution_time:.2f}s. "
                        f"Total retrainings: {self.retraining_count}, "
                        f"Deployments: {self.deployments_count}"
                    )

                    # Sleep until next cycle
                    if self.running:
                        logger.info(
                            f"Sleeping for {self.retraining_interval} seconds "
                            f"(~{self.retraining_interval/86400:.1f} days)..."
                        )
                        self.sleep(self.retraining_interval)

                except Exception as e:
                    self.handle_error(e)

                    # Exponential backoff on error
                    backoff_time = min(3600 * (2 ** self.error_count), 86400)  # Max 24h
                    logger.info(f"Backing off for {backoff_time} seconds after error...")
                    self.sleep(backoff_time)

        finally:
            self._cleanup_dependencies()

    def _execute_retraining_cycle(self) -> None:
        """Execute a single model retraining cycle."""
        logger.info("Starting model retraining cycle...")

        # Load training data
        matches, sales = self._load_training_data()

        if len(matches) < self.min_training_samples:
            logger.warning(
                f"Insufficient training data: {len(matches)} matches "
                f"(minimum: {self.min_training_samples}). Skipping retraining."
            )
            return

        logger.info(f"Loaded {len(matches)} matches and {len(sales)} sales for training")

        # Prepare features and target
        X, y = self._prepare_training_data(matches, sales)

        if len(X) < self.min_training_samples:
            logger.warning(
                f"Insufficient prepared samples: {len(X)} "
                f"(minimum: {self.min_training_samples}). Skipping retraining."
            )
            return

        # Train new model
        new_model = self._train_new_model(X, y)

        # Evaluate new model vs current model
        should_deploy, metrics = self._evaluate_and_compare(new_model, X, y)

        # Deploy if better
        if should_deploy:
            self._deploy_model(new_model, metrics)
            self.deployments_count += 1
            logger.info("New model deployed successfully")
        else:
            logger.info("Current model retained (new model did not meet improvement threshold)")

        self.retraining_count += 1

    def _load_training_data(self) -> Tuple[List[Match], List[Sale]]:
        """Load historical data for training.

        Returns:
            Tuple of (matches, sales) lists
        """
        try:
            match_repo = MatchRepository(self.db)
            sale_repo = SaleRepository(self.db)

            # Load completed matches from the last 6 months
            cutoff_date = datetime.now() - timedelta(days=180)

            # Get completed matches
            matches = match_repo.get_by_date_range(
                start=cutoff_date,
                end=datetime.now()
            )

            # Filter only completed matches
            matches = [m for m in matches if m.status.value == "completed"]

            # Get sales for these matches
            all_sales = []
            for match in matches:
                sales = sale_repo.get_by_match(match.id)
                all_sales.extend(sales)

            logger.info(
                f"Loaded {len(matches)} completed matches and {len(all_sales)} sales "
                f"from last 180 days"
            )

            return matches, all_sales

        except Exception as e:
            logger.error(f"Failed to load training data: {e}", exc_info=True)
            return [], []

    def _prepare_training_data(self, matches: List[Match], sales: List[Sale]) -> Tuple:
        """Prepare features and target from raw data.

        Args:
            matches: List of Match objects
            sales: List of Sale objects

        Returns:
            Tuple of (X, y) for training
        """
        try:
            X, y = prepare_features_and_target(matches, sales)
            logger.info(f"Prepared {len(X)} training samples")
            return X, y

        except Exception as e:
            logger.error(f"Failed to prepare training data: {e}", exc_info=True)
            raise

    def _train_new_model(self, X, y) -> DemandModel:
        """Train a new demand prediction model.

        Args:
            X: Features
            y: Target values

        Returns:
            Trained DemandModel
        """
        logger.info("Training new demand model...")

        try:
            model = DemandModel(model_type="xgboost")
            model.train(X, y)

            logger.info("Model training completed successfully")
            return model

        except Exception as e:
            logger.error(f"Failed to train new model: {e}", exc_info=True)
            raise

    def _evaluate_and_compare(
        self,
        new_model: DemandModel,
        X,
        y
    ) -> Tuple[bool, Dict]:
        """Evaluate new model and compare with current production model.

        Args:
            new_model: Newly trained model
            X: Test features
            y: Test target

        Returns:
            Tuple of (should_deploy, metrics_dict)
        """
        logger.info("Evaluating new model...")

        # Evaluate new model
        new_metrics = new_model.evaluate(X, y)
        logger.info(f"New model metrics: {new_metrics}")

        # Try to load current production model
        current_model_path = self.model_dir / "demand_model_current.pkl"
        if not current_model_path.exists():
            logger.info("No current production model found. Will deploy new model.")
            return True, new_metrics

        try:
            current_model = DemandModel()
            current_model.load(str(current_model_path))

            # Evaluate current model
            current_metrics = current_model.evaluate(X, y)
            logger.info(f"Current model metrics: {current_metrics}")

            # Compare metrics (lower MAE/RMSE is better, higher R² is better)
            # Using MAE as primary metric
            current_mae = current_metrics.get("mae", float("inf"))
            new_mae = new_metrics.get("mae", float("inf"))

            improvement = (current_mae - new_mae) / current_mae if current_mae > 0 else 0

            logger.info(f"MAE improvement: {improvement*100:.2f}%")

            should_deploy = improvement >= self.improvement_threshold

            if should_deploy:
                logger.info(
                    f"New model shows {improvement*100:.2f}% improvement "
                    f"(threshold: {self.improvement_threshold*100:.2f}%)"
                )
            else:
                logger.info(
                    f"New model improvement ({improvement*100:.2f}%) below threshold "
                    f"({self.improvement_threshold*100:.2f}%)"
                )

            return should_deploy, new_metrics

        except Exception as e:
            logger.error(f"Failed to load/evaluate current model: {e}", exc_info=True)
            # If can't load current model, deploy new one
            return True, new_metrics

    def _deploy_model(self, model: DemandModel, metrics: Dict) -> None:
        """Deploy the new model to production.

        Implements versioning by backing up the current model.

        Args:
            model: Model to deploy
            metrics: Model evaluation metrics
        """
        logger.info("Deploying new model...")

        try:
            current_model_path = self.model_dir / "demand_model_current.pkl"
            backup_dir = self.model_dir / "backups"
            backup_dir.mkdir(exist_ok=True)

            # Backup current model if exists
            if current_model_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"demand_model_{timestamp}.pkl"
                shutil.copy(current_model_path, backup_path)
                logger.info(f"Backed up current model to {backup_path}")

            # Save new model as current
            model.save(str(current_model_path))
            logger.info(f"Deployed new model to {current_model_path}")

            # Save metrics
            metrics_path = self.model_dir / "current_model_metrics.json"
            import json
            with open(metrics_path, "w") as f:
                json.dump({
                    "metrics": metrics,
                    "deployed_at": datetime.now().isoformat(),
                    "version": datetime.now().strftime("%Y%m%d_%H%M%S")
                }, f, indent=2)

            logger.info(f"Saved model metrics to {metrics_path}")

        except Exception as e:
            logger.error(f"Failed to deploy model: {e}", exc_info=True)
            raise

    def rollback_model(self) -> bool:
        """Rollback to the previous model version.

        Returns:
            True if rollback successful, False otherwise
        """
        logger.info("Attempting model rollback...")

        try:
            backup_dir = self.model_dir / "backups"
            if not backup_dir.exists():
                logger.error("No backup directory found. Cannot rollback.")
                return False

            # Find most recent backup
            backups = sorted(backup_dir.glob("demand_model_*.pkl"), reverse=True)
            if not backups:
                logger.error("No backup models found. Cannot rollback.")
                return False

            latest_backup = backups[0]
            current_model_path = self.model_dir / "demand_model_current.pkl"

            # Replace current with backup
            shutil.copy(latest_backup, current_model_path)
            logger.info(f"Rolled back to model: {latest_backup.name}")

            return True

        except Exception as e:
            logger.error(f"Failed to rollback model: {e}", exc_info=True)
            return False

    def get_metrics(self) -> dict:
        """Get worker metrics.

        Returns:
            Dictionary with worker metrics
        """
        return {
            "worker_name": self.name,
            "running": self.running,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "retraining_count": self.retraining_count,
            "deployments_count": self.deployments_count,
            "deployment_rate": (
                self.deployments_count / self.retraining_count
                if self.retraining_count > 0 else 0
            ),
            "total_execution_time": self.total_execution_time,
            "error_count": self.error_count,
            "is_healthy": self.is_healthy(),
        }
