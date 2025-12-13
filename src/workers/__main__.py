"""Worker orchestration module for the Smart Pricing System.

This module provides a CLI to start different background workers.

Usage:
    python -m src.workers price_updater
    python -m src.workers data_collector
    python -m src.workers model_retrainer
"""

import argparse
import logging
import sys
from typing import Optional

from src.core.config import get_settings
from src.core.logging import setup_logging
from src.workers.base_worker import BaseWorker
from src.workers.data_collector import DataCollectorWorker
from src.workers.model_retrainer import ModelRetrainerWorker
from src.workers.price_updater import PriceUpdaterWorker

logger = logging.getLogger(__name__)


def create_worker(worker_name: str, **kwargs) -> Optional[BaseWorker]:
    """Create a worker instance by name.

    Args:
        worker_name: Name of the worker to create
        **kwargs: Additional arguments to pass to worker constructor

    Returns:
        Worker instance or None if worker name is invalid
    """
    workers = {
        "price_updater": PriceUpdaterWorker,
        "data_collector": DataCollectorWorker,
        "model_retrainer": ModelRetrainerWorker,
    }

    worker_class = workers.get(worker_name)
    if not worker_class:
        logger.error(f"Unknown worker: {worker_name}")
        logger.info(f"Available workers: {', '.join(workers.keys())}")
        return None

    try:
        worker = worker_class(**kwargs)
        logger.info(f"Created worker: {worker_name}")
        return worker
    except Exception as e:
        logger.error(f"Failed to create worker {worker_name}: {e}", exc_info=True)
        return None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Smart Pricing System - Background Workers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start price updater worker (updates prices every 5 minutes)
  python -m src.workers price_updater

  # Start price updater with custom interval (10 minutes)
  python -m src.workers price_updater --interval 600

  # Start data collector worker (collects external data every hour)
  python -m src.workers data_collector

  # Start model retrainer worker (retrains model weekly)
  python -m src.workers model_retrainer

  # Start with custom log level
  python -m src.workers price_updater --log-level DEBUG

Available Workers:
  price_updater    - Periodically updates prices for upcoming matches
  data_collector   - Collects data from external APIs (football, weather, analytics)
  model_retrainer  - Periodically retrains ML demand prediction model
        """
    )

    parser.add_argument(
        "worker",
        type=str,
        choices=["price_updater", "data_collector", "model_retrainer"],
        help="Worker to run"
    )

    parser.add_argument(
        "--interval",
        type=int,
        help="Interval in seconds between worker cycles (worker-specific default if not provided)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)"
    )

    parser.add_argument(
        "--max-errors",
        type=int,
        default=5,
        help="Maximum consecutive errors before shutdown (default: 5)"
    )

    # Worker-specific arguments
    parser.add_argument(
        "--lookback-days",
        type=int,
        help="[price_updater] Days to look ahead for matches (default: 30)"
    )

    parser.add_argument(
        "--min-samples",
        type=int,
        help="[model_retrainer] Minimum training samples required (default: 100)"
    )

    parser.add_argument(
        "--improvement-threshold",
        type=float,
        help="[model_retrainer] Minimum improvement to deploy new model (default: 0.05)"
    )

    parser.add_argument(
        "--model-dir",
        type=str,
        help="[model_retrainer] Directory to store models (default: models)"
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point for worker orchestration.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse arguments
    args = parse_args()

    # Setup logging
    setup_logging(level=args.log_level)

    # Log startup
    settings = get_settings()
    logger.info("=" * 80)
    logger.info("Smart Pricing System - Background Workers")
    logger.info(f"Environment: {settings.app.environment}")
    logger.info(f"Worker: {args.worker}")
    logger.info("=" * 80)

    # Prepare worker-specific kwargs
    worker_kwargs = {
        "max_consecutive_errors": args.max_errors,
    }

    # Add interval if provided
    if args.interval:
        if args.worker == "price_updater":
            worker_kwargs["update_interval"] = args.interval
        elif args.worker == "data_collector":
            worker_kwargs["collection_interval"] = args.interval
        elif args.worker == "model_retrainer":
            worker_kwargs["retraining_interval"] = args.interval

    # Add worker-specific arguments
    if args.worker == "price_updater":
        if args.lookback_days:
            worker_kwargs["lookback_days"] = args.lookback_days

    elif args.worker == "model_retrainer":
        if args.min_samples:
            worker_kwargs["min_training_samples"] = args.min_samples
        if args.improvement_threshold:
            worker_kwargs["improvement_threshold"] = args.improvement_threshold
        if args.model_dir:
            worker_kwargs["model_dir"] = args.model_dir

    # Create worker
    worker = create_worker(args.worker, **worker_kwargs)
    if not worker:
        logger.error("Failed to create worker. Exiting.")
        return 1

    # Start worker
    try:
        logger.info(f"Starting worker: {args.worker}")
        worker.start()
        logger.info(f"Worker {args.worker} completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Stopping worker...")
        worker.stop()
        logger.info("Worker stopped")
        return 0

    except Exception as e:
        logger.error(f"Worker failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
