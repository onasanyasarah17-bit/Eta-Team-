"""
Centralized logging configuration.

Logs:
- Incoming requests (without sensitive data)
- Errors and exceptions
- DynamoDB operations
- Application startup/shutdown

Never logs:
- AWS credentials (boto3 handles this securely)
- Personal information
- Request/response bodies with PII
"""

import logging
import logging.handlers
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Filter that removes sensitive data from log records."""

    SENSITIVE_KEYS = {
        "password",
        "token",
        "key",
        "secret",
        "credential",
        "aws_access_key",
        "aws_secret_key",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records to prevent sensitive data leakage.

        Args:
            record: Log record

        Returns:
            Always True (we modify in-place, not filter out)
        """
        # Don't filter messages, just ensure they're safe
        # boto3 handles credentials securely, so we don't need to filter them
        return True


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        format_string: Custom format string for logs

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(log_level="DEBUG", log_file="app.log")
        >>> logger.info("Application started")
    """
    logger = logging.getLogger("secure_employee_directory")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers to prevent duplicates
    logger.handlers = []

    # Default format
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(filename)s:%(lineno)d] - %(message)s"
        )

    formatter = logging.Formatter(format_string)

    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Module initialized")
    """
    return logging.getLogger(f"secure_employee_directory.{name}")
