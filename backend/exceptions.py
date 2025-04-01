"""
Custom exceptions for the backend application.
"""

from typing import Any, NoReturn, Type, TypeVar

from pydantic import BaseModel  # Need BaseModel for TypeVar constraint
from pydantic import ValidationError

from backend.logger import logger

# Define TypeVar for the model instance
T = TypeVar("T", bound=BaseModel)


class InternalDataValidationError(Exception):
    """
    Raised when data from an internal source (DB, AI, etc.) fails Pydantic validation.

    This helps distinguish internal data integrity issues from client-side
    request validation errors.
    """

    def __init__(self, message: str, original_exception: ValidationError | None = None):
        """
        Initializes the exception.

        Args:
            message: A descriptive error message.
            original_exception: The original Pydantic ValidationError, if available.
        """
        super().__init__(message)
        self.original_exception = original_exception
        self.message = message

    def __str__(self) -> str:
        if self.original_exception:
            # Include details from the original error if available
            return f"{self.message}: {self.original_exception}"
        return self.message


# --- Validation Helper ---


def validate_internal_model(
    model_cls: Type[T],
    data: Any,
    context_message: str = "Internal data validation failed",
) -> T:
    """
    Validates data against a Pydantic model, raising InternalDataValidationError on failure.

    Args:
        model_cls: The Pydantic model class to validate against.
        data: The data to validate.
        context_message: A descriptive message for the context of the validation.

    Returns:
        The validated Pydantic model instance.

    Raises:
        InternalDataValidationError: If Pydantic validation fails.
    """
    try:
        return model_cls.model_validate(data)
    except ValidationError as e:
        raise InternalDataValidationError(
            f"{context_message} for model {model_cls.__name__}", original_exception=e
        ) from e


# Helper functions for logging and raising exceptions
def log_and_propagate(
    new_exception_type: Type[Exception],
    new_exception_message: str,
    original_exception: Exception,  # Make original exception mandatory for chaining
    exc_info: bool = True,
    **log_extras: Any,
) -> NoReturn:
    """
    Logs an error message and then raises a specified exception, ensuring the
    original exception is chained (using 'from original_exception').

    Args:
        log_message: The message to log as an error.
        new_exception_type: The type of exception to raise.
        new_exception_message: The message for the new exception.
        original_exception: The exception that triggered this call, to be chained.
        exc_info: Whether to include exception info (stack trace) in the log.
        **log_extras: Additional key-value pairs to include in the log record.

    Raises:
        new_exception_type: Always raises an exception of this type.
    """
    log_message = f"{new_exception_message}: {original_exception}"
    logger.error(log_message, exc_info=exc_info, **log_extras)
    raise new_exception_type(new_exception_message) from original_exception


def log_and_raise_new(
    exception_type: Type[Exception],
    exception_message: str,
    break_chain: bool = False,  # Control 'from None'
    exc_info: bool = True,
    **log_extras: Any,
) -> NoReturn:
    """
    Logs an error message and then raises a specified exception, optionally
    breaking the exception chain (using 'from None' if break_chain is True).

    Args:
        log_message: The message to log as an error.
        new_exception_type: The type of exception to raise.
        new_exception_message: The message for the new exception.
        break_chain: If True, raise the new exception using 'from None'.
                     If False (default), the original context is preserved implicitly.
        exc_info: Whether to include exception info (stack trace) in the log.
        **log_extras: Additional key-value pairs to include in the log record.

    Raises:
        new_exception_type: Always raises an exception of this type.
    """
    log_message = exception_message
    logger.error(log_message, exc_info=exc_info, **log_extras)

    if break_chain:
        raise exception_type(exception_message) from None

    raise exception_type(exception_message)
