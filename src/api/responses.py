"""Response models for API endpoints.

This module defines consistent response formats for the API,
following best practices for API design.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response wrapper.

    Attributes:
        success: Always True for success responses
        data: The actual response data
        message: Optional success message
        timestamp: When the response was generated
    """

    success: bool = Field(True, description="Indicates successful operation")
    data: T = Field(..., description="Response payload")
    message: Optional[str] = Field(None, description="Optional success message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": "123", "name": "Example"},
                "message": "Operation completed successfully",
                "timestamp": "2024-12-13T10:00:00Z"
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response format.

    Attributes:
        success: Always False for error responses
        error: Error details
        timestamp: When the error occurred
    """

    success: bool = Field(False, description="Indicates failed operation")
    error: Dict[str, Any] = Field(..., description="Error details")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Resource not found",
                    "details": {}
                },
                "timestamp": "2024-12-13T10:00:00Z"
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper.

    Attributes:
        success: Always True for successful paginated responses
        data: List of items for current page
        pagination: Pagination metadata
        timestamp: Response timestamp
    """

    success: bool = Field(True, description="Indicates successful operation")
    data: List[T] = Field(..., description="List of items")
    pagination: Dict[str, Any] = Field(..., description="Pagination metadata")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [
                    {"id": "1", "name": "Item 1"},
                    {"id": "2", "name": "Item 2"}
                ],
                "pagination": {
                    "total": 100,
                    "page": 1,
                    "page_size": 20,
                    "total_pages": 5
                },
                "timestamp": "2024-12-13T10:00:00Z"
            }
        }


class HealthStatus(BaseModel):
    """Health check response.

    Attributes:
        status: Overall health status
        version: API version
        timestamp: Current server time
        services: Status of individual services
    """

    status: str = Field(..., description="Overall status: healthy, degraded, unhealthy")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Current server time"
    )
    services: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Status of individual services"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2024-12-13T10:00:00Z",
                "services": {
                    "database": {
                        "status": "healthy",
                        "latency_ms": 5.2
                    },
                    "redis": {
                        "status": "healthy",
                        "latency_ms": 1.1
                    }
                }
            }
        }


class ReadinessStatus(BaseModel):
    """Readiness check response.

    Attributes:
        ready: Whether the application is ready to serve requests
        timestamp: Current server time
        checks: Individual readiness checks
    """

    ready: bool = Field(..., description="Whether the app is ready")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Current server time"
    )
    checks: Dict[str, bool] = Field(
        default_factory=dict,
        description="Individual readiness checks"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "ready": True,
                "timestamp": "2024-12-13T10:00:00Z",
                "checks": {
                    "ml_model_loaded": True,
                    "config_loaded": True,
                    "database_connected": True,
                    "redis_connected": True
                }
            }
        }


def create_success_response(
    data: T,
    message: Optional[str] = None
) -> SuccessResponse[T]:
    """Helper function to create success responses.

    Args:
        data: Response data
        message: Optional success message

    Returns:
        Formatted success response
    """
    return SuccessResponse(data=data, message=message)


def create_error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> ErrorResponse:
    """Helper function to create error responses.

    Args:
        code: Error code
        message: Error message
        details: Optional additional error details

    Returns:
        Formatted error response
    """
    return ErrorResponse(
        error={
            "code": code,
            "message": message,
            "details": details or {}
        }
    )


def create_paginated_response(
    data: List[T],
    total: int,
    page: int,
    page_size: int
) -> PaginatedResponse[T]:
    """Helper function to create paginated responses.

    Args:
        data: List of items for current page
        total: Total number of items
        page: Current page number (1-indexed)
        page_size: Number of items per page

    Returns:
        Formatted paginated response
    """
    total_pages = (total + page_size - 1) // page_size  # Ceiling division

    return PaginatedResponse(
        data=data,
        pagination={
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    )
