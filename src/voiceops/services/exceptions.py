class ServiceError(Exception):
    """Base exception for service-layer errors."""


class NotFoundError(ServiceError):
    """Raised when a requested resource does not exist."""


class BusinessRuleError(ServiceError):
    """Raised when an operation violates a business rule."""


class InsufficientStockError(BusinessRuleError):
    """Raised when available inventory is insufficient."""
