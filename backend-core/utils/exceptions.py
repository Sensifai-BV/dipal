"""
Custom exception classes for PhotoGear Backend.
"""


class PhotoGearException(Exception):
    """Base exception for all PhotoGear errors."""
    
    def __init__(self, message: str = "An error occurred", status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(PhotoGearException):
    """Raised when data validation fails."""
    
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=400)


class AuthenticationError(PhotoGearException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class PermissionError(PhotoGearException):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)


class NotFoundError(PhotoGearException):
    """Raised when a requested resource is not found."""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ConflictError(PhotoGearException):
    """Raised when there's a conflict with existing data."""
    
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, status_code=409)


class DatabaseError(PhotoGearException):
    """Raised when database operations fail."""
    
    def __init__(self, message: str = "Database error occurred"):
        super().__init__(message, status_code=500)


class ExternalServiceError(PhotoGearException):
    """Raised when an external service call fails."""
    
    def __init__(self, message: str = "External service error"):
        super().__init__(message, status_code=502)
