"""
Centralized logging configuration.

Supports plain-text logs for local development and JSON logs for CloudWatch.
Never logs AWS credentials, tokens, or request bodies with PII.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
from datetime import datetime, timezone
from typing import Any, Optional


class SensitiveDataFilter(logging.Filter):
    """Redact common secret patterns from log messages."""

    SENSITIVE_PATTERNS = (
        (re.compile(r"(?i)(password|token|secret|credential)\s*[:=]\s*\S+"), r"\1=***REDACTED***"),
        (re.compile(r"(?i)aws_access_key_id\s*[:=]\s*\S+"), "aws_access_key_id=***REDACTED***"),
        (re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*\S+"), "aws_secret_access_key=***REDACTED***"),
        (re.compile(r"AKIA[0-9A-Z]{16}"), "***REDACTED***"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        redacted = message
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            redacted = pattern.sub(replacement, redacted)

        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for CloudWatch Logs Insights."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in (
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "remote_addr",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
    json_logs: bool = False,
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        format_string: Custom format string for plain-text logs
        json_logs: If True, emit JSON lines (CloudWatch-friendly)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("secure_employee_directory")
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers = []
    logger.propagate = False

    if json_logs:
        formatter: logging.Formatter = JsonFormatter()
    else:
        if format_string is None:
            format_string = (
                "%(asctime)s - %(name)s - %(levelname)s - "
                "[%(filename)s:%(lineno)d] - %(message)s"
            )
        formatter = logging.Formatter(format_string)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(f"secure_employee_directory.{name}")
