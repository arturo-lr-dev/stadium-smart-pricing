"""Base worker class for background jobs in the Smart Pricing System.

This module provides the abstract base class for all background workers,
including signal handling, logging, and health check functionality.
"""

import logging
import signal
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.utils.metrics import (
    worker_errors_total,
    worker_last_run_timestamp,
    worker_task_duration_seconds,
    worker_tasks_total,
)

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Abstract base class for background workers.

    Provides common functionality for all workers including:
    - Signal handling (SIGTERM, SIGINT)
    - Health check mechanism
    - Structured logging
    - Graceful shutdown

    Attributes:
        name: Worker name for identification
        running: Flag indicating if worker is currently running
        last_heartbeat: Timestamp of last successful execution
        error_count: Count of consecutive errors
    """

    def __init__(self, name: str, max_consecutive_errors: int = 5):
        """Initialize the base worker.

        Args:
            name: Worker name for identification and logging
            max_consecutive_errors: Maximum consecutive errors before shutdown
        """
        self.name = name
        self.running = False
        self.last_heartbeat: Optional[datetime] = None
        self.error_count = 0
        self.max_consecutive_errors = max_consecutive_errors

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info(f"Initialized worker: {self.name}")

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = signal.Signals(signum).name
        logger.info(f"Received signal {signal_name}, initiating graceful shutdown...")
        self.stop()

    def start(self) -> None:
        """Start the worker.

        This method sets up the worker and calls the run() method.
        Handles errors and implements retry logic.
        """
        logger.info(f"Starting worker: {self.name}")
        self.running = True
        self.last_heartbeat = datetime.now()

        # Record worker start
        worker_tasks_total.labels(worker_name=self.name, status="started").inc()

        start_time = time.time()
        try:
            self.run()

            # Record successful completion
            duration = time.time() - start_time
            worker_task_duration_seconds.labels(worker_name=self.name).observe(duration)
            worker_tasks_total.labels(worker_name=self.name, status="completed").inc()

        except Exception as e:
            # Record failure
            duration = time.time() - start_time
            worker_task_duration_seconds.labels(worker_name=self.name).observe(duration)
            worker_tasks_total.labels(worker_name=self.name, status="failed").inc()

            logger.error(f"Worker {self.name} failed with error: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"Worker {self.name} stopped")
            self.running = False

    def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info(f"Stopping worker: {self.name}")
        self.running = False

    def heartbeat(self) -> None:
        """Update the last heartbeat timestamp.

        Should be called periodically by the worker to indicate it's alive.
        """
        self.last_heartbeat = datetime.now()

        # Update last run timestamp metric
        worker_last_run_timestamp.labels(worker_name=self.name).set(self.last_heartbeat.timestamp())

        logger.debug(f"Worker {self.name} heartbeat at {self.last_heartbeat}")

    def is_healthy(self) -> bool:
        """Check if the worker is healthy.

        Returns:
            True if worker is running and has recent heartbeat, False otherwise
        """
        if not self.running:
            return False

        if self.last_heartbeat is None:
            return False

        # Check if last heartbeat was within last 5 minutes
        time_since_heartbeat = (datetime.now() - self.last_heartbeat).total_seconds()
        is_healthy = time_since_heartbeat < 300  # 5 minutes

        if not is_healthy:
            logger.warning(
                f"Worker {self.name} health check failed. "
                f"Last heartbeat: {time_since_heartbeat}s ago"
            )

        return is_healthy

    def handle_error(self, error: Exception) -> None:
        """Handle errors during worker execution.

        Args:
            error: Exception that occurred

        Raises:
            Exception: If max consecutive errors exceeded
        """
        self.error_count += 1

        # Record worker error metric
        worker_errors_total.labels(
            worker_name=self.name,
            error_type=type(error).__name__
        ).inc()

        logger.error(
            f"Error in worker {self.name} (count: {self.error_count}/{self.max_consecutive_errors}): {error}",
            exc_info=True
        )

        if self.error_count >= self.max_consecutive_errors:
            logger.critical(
                f"Worker {self.name} exceeded max consecutive errors ({self.max_consecutive_errors}). "
                "Shutting down..."
            )
            self.stop()
            raise error

    def reset_error_count(self) -> None:
        """Reset the error counter after successful execution."""
        if self.error_count > 0:
            logger.info(f"Resetting error count for worker {self.name}")
            self.error_count = 0

    @abstractmethod
    def run(self) -> None:
        """Main worker logic.

        This method must be implemented by subclasses.
        Should contain the main loop or job execution logic.
        """
        pass

    def sleep(self, seconds: int) -> None:
        """Sleep for specified seconds while allowing for interruption.

        Args:
            seconds: Number of seconds to sleep
        """
        logger.debug(f"Worker {self.name} sleeping for {seconds} seconds")
        for _ in range(seconds):
            if not self.running:
                logger.info(f"Worker {self.name} interrupted during sleep")
                break
            time.sleep(1)
