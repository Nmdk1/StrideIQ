"""
Custom exception classes and error handling.

Provides consistent error responses across the API.
"""
from fastapi import HTTPException, status
from typing import Optional, Dict, Any


class APIException(HTTPException):
    """Base API exception with consistent structure."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


class NotFoundError(APIException):
    """Resource not found."""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND"
        )


class ValidationError(APIException):
    """Validation error."""
    
    def __init__(self, detail: str, field: Optional[str] = None):
        error_code = f"VALIDATION_ERROR_{field.upper()}" if field else "VALIDATION_ERROR"
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code
        )


class UnauthorizedError(APIException):
    """Authentication required."""
    
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="UNAUTHORIZED",
            headers={"WWW-Authenticate": "Bearer"}
        )


class ForbiddenError(APIException):
    """Access denied."""
    
    def __init__(self, detail: str = "Access denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="FORBIDDEN"
        )


class ConflictError(APIException):
    """Resource conflict (e.g., duplicate entry)."""
    
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="CONFLICT"
        )


