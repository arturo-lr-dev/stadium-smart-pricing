"""
Ticketing System Integration (Mock).

This module provides integration with an external ticketing system for
inventory management, reservations, and purchase confirmations.

Note: This is a mock implementation for MVP. In production, this would
integrate with the actual ticketing platform API (e.g., Ticketmaster, Eventbrite).
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum

from src.core.config import get_settings
from src.core.exceptions import ExternalAPIError


logger = logging.getLogger(__name__)


class ReservationStatus(str, Enum):
    """Reservation status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TicketingSystemAPI:
    """
    Client for Ticketing System integration.

    Provides methods to manage inventory, create reservations, and
    handle ticket purchases.

    This is a MOCK implementation for development and testing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.ticketing-system.example.com/v1",
        reservation_ttl: int = 900,  # 15 minutes
    ):
        """
        Initialize Ticketing System API client.

        Args:
            api_key: API key for authentication. If None, reads from settings.
            base_url: Base URL for the API.
            reservation_ttl: Time in seconds before reservations expire.
        """
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "TICKETING_API_KEY", "mock")
        self.base_url = base_url.rstrip("/")
        self.reservation_ttl = reservation_ttl

        # Mock mode flag
        self.mock_mode = self.api_key == "mock"

        # In-memory storage for mock reservations
        self._reservations: Dict[str, Dict] = {}

        # In-memory storage for mock inventory
        # Key: f"{match_id}:{zone_id}", Value: available count
        self._mock_inventory: Dict[str, int] = {}

        if self.mock_mode:
            logger.warning(
                "Ticketing System running in MOCK mode. "
                "Set TICKETING_API_KEY in environment to enable real integration."
            )
        else:
            logger.info(
                "TicketingSystemAPI initialized",
                extra={
                    "base_url": self.base_url,
                    "reservation_ttl": self.reservation_ttl,
                },
            )

    def get_available_inventory(self, match_id: str) -> Dict[str, int]:
        """
        Get available inventory for all zones in a match.

        Args:
            match_id: Unique match identifier.

        Returns:
            Dictionary mapping zone_id to available ticket count:
            {
                "zone_1": 150,
                "zone_2": 320,
                ...
            }

        Raises:
            ExternalAPIError: If the API request fails.
        """
        logger.info(f"Fetching available inventory for match {match_id}")

        if self.mock_mode:
            # Return mock inventory
            return self._get_mock_inventory(match_id)

        try:
            # In production, make API request
            # response = requests.get(
            #     f"{self.base_url}/matches/{match_id}/inventory",
            #     headers={"Authorization": f"Bearer {self.api_key}"},
            # )
            # return response.json()

            # For now, return mock data
            return self._get_mock_inventory(match_id)

        except Exception as e:
            logger.error(
                f"Failed to fetch inventory: {e}",
                extra={"match_id": match_id},
            )
            raise ExternalAPIError(
                f"Ticketing System error: {e}",
                source="ticketing_system",
            )

    def reserve_tickets(
        self,
        match_id: str,
        zone_id: str,
        quantity: int,
        customer_email: Optional[str] = None,
    ) -> str:
        """
        Reserve tickets for a customer.

        Creates a temporary hold on tickets. The reservation will expire
        after the configured TTL if not confirmed.

        Args:
            match_id: Unique match identifier.
            zone_id: Zone identifier.
            quantity: Number of tickets to reserve.
            customer_email: Optional customer email for notification.

        Returns:
            Reservation ID (unique identifier for this reservation).

        Raises:
            ExternalAPIError: If reservation fails (insufficient inventory, etc.).
        """
        logger.info(
            f"Reserving {quantity} tickets for match {match_id}, zone {zone_id}"
        )

        if self.mock_mode:
            return self._create_mock_reservation(
                match_id, zone_id, quantity, customer_email
            )

        try:
            # In production, make API request
            # response = requests.post(
            #     f"{self.base_url}/reservations",
            #     headers={"Authorization": f"Bearer {self.api_key}"},
            #     json={
            #         "match_id": match_id,
            #         "zone_id": zone_id,
            #         "quantity": quantity,
            #         "customer_email": customer_email,
            #     },
            # )
            # return response.json()["reservation_id"]

            # For now, use mock
            return self._create_mock_reservation(
                match_id, zone_id, quantity, customer_email
            )

        except Exception as e:
            logger.error(
                f"Failed to reserve tickets: {e}",
                extra={
                    "match_id": match_id,
                    "zone_id": zone_id,
                    "quantity": quantity,
                },
            )
            raise ExternalAPIError(
                f"Ticketing System error: {e}",
                source="ticketing_system",
            )

    def confirm_purchase(self, reservation_id: str, payment_id: str) -> bool:
        """
        Confirm a reservation and complete the purchase.

        Args:
            reservation_id: Reservation ID from reserve_tickets().
            payment_id: Payment transaction ID.

        Returns:
            True if purchase was confirmed successfully.

        Raises:
            ExternalAPIError: If confirmation fails.
        """
        logger.info(
            f"Confirming purchase for reservation {reservation_id}"
        )

        if self.mock_mode:
            return self._confirm_mock_reservation(reservation_id, payment_id)

        try:
            # In production, make API request
            # response = requests.post(
            #     f"{self.base_url}/reservations/{reservation_id}/confirm",
            #     headers={"Authorization": f"Bearer {self.api_key}"},
            #     json={"payment_id": payment_id},
            # )
            # return response.status_code == 200

            # For now, use mock
            return self._confirm_mock_reservation(reservation_id, payment_id)

        except Exception as e:
            logger.error(
                f"Failed to confirm purchase: {e}",
                extra={"reservation_id": reservation_id},
            )
            raise ExternalAPIError(
                f"Ticketing System error: {e}",
                source="ticketing_system",
            )

    def cancel_reservation(self, reservation_id: str) -> bool:
        """
        Cancel a reservation and release the tickets.

        Args:
            reservation_id: Reservation ID to cancel.

        Returns:
            True if cancellation was successful.

        Raises:
            ExternalAPIError: If cancellation fails.
        """
        logger.info(f"Cancelling reservation {reservation_id}")

        if self.mock_mode:
            return self._cancel_mock_reservation(reservation_id)

        try:
            # In production, make API request
            # response = requests.delete(
            #     f"{self.base_url}/reservations/{reservation_id}",
            #     headers={"Authorization": f"Bearer {self.api_key}"},
            # )
            # return response.status_code == 200

            # For now, use mock
            return self._cancel_mock_reservation(reservation_id)

        except Exception as e:
            logger.error(
                f"Failed to cancel reservation: {e}",
                extra={"reservation_id": reservation_id},
            )
            raise ExternalAPIError(
                f"Ticketing System error: {e}",
                source="ticketing_system",
            )

    def get_reservation_status(self, reservation_id: str) -> Dict:
        """
        Get the current status of a reservation.

        Args:
            reservation_id: Reservation ID to check.

        Returns:
            Dictionary containing reservation details:
            {
                "reservation_id": str,
                "status": str,
                "match_id": str,
                "zone_id": str,
                "quantity": int,
                "expires_at": str (ISO format),
                ...
            }

        Raises:
            ExternalAPIError: If reservation not found or API fails.
        """
        logger.info(f"Checking status of reservation {reservation_id}")

        if self.mock_mode:
            return self._get_mock_reservation_status(reservation_id)

        try:
            # In production, make API request
            # response = requests.get(
            #     f"{self.base_url}/reservations/{reservation_id}",
            #     headers={"Authorization": f"Bearer {self.api_key}"},
            # )
            # return response.json()

            # For now, use mock
            return self._get_mock_reservation_status(reservation_id)

        except Exception as e:
            logger.error(
                f"Failed to get reservation status: {e}",
                extra={"reservation_id": reservation_id},
            )
            raise ExternalAPIError(
                f"Ticketing System error: {e}",
                source="ticketing_system",
            )

    # Mock implementation methods

    def _get_mock_inventory(self, match_id: str) -> Dict[str, int]:
        """Get mock inventory for a match."""
        # Generate consistent mock inventory based on match_id
        zones = ["zone_vip_1", "zone_premium_1", "zone_standard_1", "zone_standard_2"]
        inventory = {}

        for zone_id in zones:
            key = f"{match_id}:{zone_id}"
            if key not in self._mock_inventory:
                # Initialize with random-ish but consistent values
                base = hash(key) % 500 + 100
                self._mock_inventory[key] = base
            inventory[zone_id] = self._mock_inventory[key]

        logger.debug(f"Mock inventory for match {match_id}: {inventory}")
        return inventory

    def _create_mock_reservation(
        self,
        match_id: str,
        zone_id: str,
        quantity: int,
        customer_email: Optional[str] = None,
    ) -> str:
        """Create a mock reservation."""
        # Check if enough inventory available
        key = f"{match_id}:{zone_id}"
        available = self._mock_inventory.get(key, 0)

        if available < quantity:
            raise ExternalAPIError(
                f"Insufficient inventory. Available: {available}, Requested: {quantity}",
                source="ticketing_system",
            )

        # Create reservation
        reservation_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(seconds=self.reservation_ttl)

        self._reservations[reservation_id] = {
            "reservation_id": reservation_id,
            "status": ReservationStatus.PENDING,
            "match_id": match_id,
            "zone_id": zone_id,
            "quantity": quantity,
            "customer_email": customer_email,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
        }

        # Decrease available inventory
        self._mock_inventory[key] -= quantity

        logger.info(
            f"Created mock reservation {reservation_id}",
            extra={
                "match_id": match_id,
                "zone_id": zone_id,
                "quantity": quantity,
                "expires_at": expires_at.isoformat(),
            },
        )

        return reservation_id

    def _confirm_mock_reservation(
        self,
        reservation_id: str,
        payment_id: str,
    ) -> bool:
        """Confirm a mock reservation."""
        if reservation_id not in self._reservations:
            raise ExternalAPIError(
                f"Reservation {reservation_id} not found",
                source="ticketing_system",
            )

        reservation = self._reservations[reservation_id]

        # Check if expired
        if datetime.utcnow() > reservation["expires_at"]:
            reservation["status"] = ReservationStatus.EXPIRED
            # Release inventory
            key = f"{reservation['match_id']}:{reservation['zone_id']}"
            self._mock_inventory[key] = self._mock_inventory.get(key, 0) + reservation["quantity"]
            raise ExternalAPIError(
                f"Reservation {reservation_id} has expired",
                source="ticketing_system",
            )

        # Confirm reservation
        reservation["status"] = ReservationStatus.CONFIRMED
        reservation["payment_id"] = payment_id
        reservation["confirmed_at"] = datetime.utcnow()

        logger.info(f"Confirmed mock reservation {reservation_id}")
        return True

    def _cancel_mock_reservation(self, reservation_id: str) -> bool:
        """Cancel a mock reservation."""
        if reservation_id not in self._reservations:
            raise ExternalAPIError(
                f"Reservation {reservation_id} not found",
                source="ticketing_system",
            )

        reservation = self._reservations[reservation_id]

        # Only cancel if not already confirmed
        if reservation["status"] == ReservationStatus.CONFIRMED:
            raise ExternalAPIError(
                f"Cannot cancel confirmed reservation {reservation_id}",
                source="ticketing_system",
            )

        # Release inventory
        key = f"{reservation['match_id']}:{reservation['zone_id']}"
        self._mock_inventory[key] = self._mock_inventory.get(key, 0) + reservation["quantity"]

        # Mark as cancelled
        reservation["status"] = ReservationStatus.CANCELLED
        reservation["cancelled_at"] = datetime.utcnow()

        logger.info(f"Cancelled mock reservation {reservation_id}")
        return True

    def _get_mock_reservation_status(self, reservation_id: str) -> Dict:
        """Get status of a mock reservation."""
        if reservation_id not in self._reservations:
            raise ExternalAPIError(
                f"Reservation {reservation_id} not found",
                source="ticketing_system",
            )

        reservation = self._reservations[reservation_id].copy()

        # Check if expired
        if (
            reservation["status"] == ReservationStatus.PENDING
            and datetime.utcnow() > reservation["expires_at"]
        ):
            reservation["status"] = ReservationStatus.EXPIRED
            # Release inventory
            key = f"{reservation['match_id']}:{reservation['zone_id']}"
            self._mock_inventory[key] = self._mock_inventory.get(key, 0) + reservation["quantity"]

        # Convert datetime objects to ISO strings
        for key in ["created_at", "expires_at"]:
            if key in reservation and isinstance(reservation[key], datetime):
                reservation[key] = reservation[key].isoformat()

        logger.debug(f"Mock reservation status: {reservation}")
        return reservation

    def clear_expired_reservations(self) -> int:
        """
        Clear all expired reservations and release their inventory.

        Returns:
            Number of reservations cleared.
        """
        now = datetime.utcnow()
        cleared = 0

        for reservation_id, reservation in list(self._reservations.items()):
            if (
                reservation["status"] == ReservationStatus.PENDING
                and now > reservation["expires_at"]
            ):
                # Release inventory
                key = f"{reservation['match_id']}:{reservation['zone_id']}"
                self._mock_inventory[key] = (
                    self._mock_inventory.get(key, 0) + reservation["quantity"]
                )

                # Mark as expired
                reservation["status"] = ReservationStatus.EXPIRED
                cleared += 1

        if cleared > 0:
            logger.info(f"Cleared {cleared} expired reservations")

        return cleared
