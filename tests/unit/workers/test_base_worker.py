"""Unit tests for BaseWorker class."""

import signal
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.workers.base_worker import BaseWorker


class DummyWorker(BaseWorker):
    """Dummy worker for testing BaseWorker functionality."""

    def __init__(self, **kwargs):
        super().__init__(name="DummyWorker", **kwargs)
        self.run_called = False
        self.iterations = 0
        self.max_iterations = 3

    def run(self):
        """Simple run implementation that iterates a few times."""
        self.run_called = True
        while self.running and self.iterations < self.max_iterations:
            self.heartbeat()
            self.iterations += 1
            time.sleep(0.1)


def test_worker_initialization():
    """Test worker initialization."""
    worker = DummyWorker()

    assert worker.name == "DummyWorker"
    assert worker.running is False
    assert worker.last_heartbeat is None
    assert worker.error_count == 0
    assert worker.max_consecutive_errors == 5


def test_worker_initialization_with_custom_max_errors():
    """Test worker initialization with custom max errors."""
    worker = DummyWorker(max_consecutive_errors=10)

    assert worker.max_consecutive_errors == 10


def test_worker_start():
    """Test worker start method."""
    worker = DummyWorker()

    worker.start()

    assert worker.run_called is True
    assert worker.running is False  # Should be False after run() completes
    assert worker.iterations == 3


def test_worker_stop():
    """Test worker stop method."""
    worker = DummyWorker(max_consecutive_errors=10)
    worker.running = True

    worker.stop()

    assert worker.running is False


def test_worker_heartbeat():
    """Test worker heartbeat."""
    worker = DummyWorker()

    # Initial state
    assert worker.last_heartbeat is None

    # First heartbeat
    worker.heartbeat()
    first_heartbeat = worker.last_heartbeat
    assert first_heartbeat is not None
    assert isinstance(first_heartbeat, datetime)

    # Second heartbeat
    time.sleep(0.1)
    worker.heartbeat()
    second_heartbeat = worker.last_heartbeat
    assert second_heartbeat > first_heartbeat


def test_worker_is_healthy_not_running():
    """Test health check when worker is not running."""
    worker = DummyWorker()

    assert worker.is_healthy() is False


def test_worker_is_healthy_no_heartbeat():
    """Test health check when no heartbeat."""
    worker = DummyWorker()
    worker.running = True

    assert worker.is_healthy() is False


def test_worker_is_healthy_recent_heartbeat():
    """Test health check with recent heartbeat."""
    worker = DummyWorker()
    worker.running = True
    worker.heartbeat()

    assert worker.is_healthy() is True


def test_worker_is_healthy_old_heartbeat():
    """Test health check with old heartbeat."""
    worker = DummyWorker()
    worker.running = True
    worker.last_heartbeat = datetime.fromtimestamp(0)  # Very old

    assert worker.is_healthy() is False


def test_worker_handle_error():
    """Test error handling."""
    worker = DummyWorker(max_consecutive_errors=3)
    worker.running = True

    error = Exception("Test error")

    # First error
    worker.handle_error(error)
    assert worker.error_count == 1

    # Second error
    worker.handle_error(error)
    assert worker.error_count == 2

    # Third error should raise
    with pytest.raises(Exception, match="Test error"):
        worker.handle_error(error)

    assert worker.error_count == 3
    assert worker.running is False  # Should stop after max errors


def test_worker_handle_error_raises_on_max():
    """Test error handling raises after max errors."""
    worker = DummyWorker(max_consecutive_errors=2)
    worker.running = True

    error = Exception("Test error")

    # First error
    worker.handle_error(error)
    assert worker.error_count == 1

    # Second error should raise
    with pytest.raises(Exception, match="Test error"):
        worker.handle_error(error)

    assert worker.error_count == 2
    assert worker.running is False


def test_worker_reset_error_count():
    """Test resetting error count."""
    worker = DummyWorker()
    worker.error_count = 3

    worker.reset_error_count()

    assert worker.error_count == 0


def test_worker_sleep():
    """Test sleep method."""
    worker = DummyWorker()
    worker.running = True

    start_time = time.time()
    worker.sleep(1)
    elapsed = time.time() - start_time

    assert elapsed >= 1.0
    assert elapsed < 1.5  # Should not be much longer


def test_worker_sleep_interrupted():
    """Test sleep can be interrupted."""
    worker = DummyWorker()
    worker.running = True

    # Stop worker after 0.5 seconds
    def stop_worker():
        time.sleep(0.5)
        worker.stop()

    import threading
    stop_thread = threading.Thread(target=stop_worker)
    stop_thread.start()

    start_time = time.time()
    worker.sleep(5)  # Try to sleep 5 seconds
    elapsed = time.time() - start_time

    stop_thread.join()

    # Should be interrupted and not sleep full 5 seconds
    assert elapsed < 2.0
    assert worker.running is False


def test_worker_signal_handler_sigterm():
    """Test SIGTERM signal handler."""
    worker = DummyWorker()
    worker.running = True

    # Simulate SIGTERM
    worker._handle_signal(signal.SIGTERM, None)

    assert worker.running is False


def test_worker_signal_handler_sigint():
    """Test SIGINT signal handler."""
    worker = DummyWorker()
    worker.running = True

    # Simulate SIGINT
    worker._handle_signal(signal.SIGINT, None)

    assert worker.running is False


def test_worker_run_is_abstract():
    """Test that run() must be implemented."""
    with pytest.raises(TypeError):
        # Should not be able to instantiate BaseWorker directly
        BaseWorker(name="Test")
