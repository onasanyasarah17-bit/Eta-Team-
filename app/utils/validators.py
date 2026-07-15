"""
Shared request validation helpers for API and web routes.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

# Employee IDs like EMP001 — letters, digits, underscore, hyphen
EMPLOYEE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_EMPLOYEE_ID_LENGTH = 64
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100


class ValidationError(ValueError):
    """Raised when request input fails validation."""


def validate_employee_id(employee_id: str | None) -> str:
    """
    Normalize and validate an employee ID from a path or query parameter.

    Returns:
        Stripped employee ID

    Raises:
        ValidationError: If the ID is empty, too long, or has invalid characters
    """
    if employee_id is None:
        raise ValidationError("employee_id cannot be empty")

    normalized = employee_id.strip()
    if not normalized:
        raise ValidationError("employee_id cannot be empty")

    if len(normalized) > MAX_EMPLOYEE_ID_LENGTH:
        raise ValidationError(
            f"employee_id must be at most {MAX_EMPLOYEE_ID_LENGTH} characters"
        )

    if not EMPLOYEE_ID_PATTERN.fullmatch(normalized):
        raise ValidationError(
            "employee_id may only contain letters, numbers, underscores, and hyphens"
        )

    return normalized


def parse_page_limit(raw_limit: str | None) -> int | None:
    """
    Parse optional `limit` query param.

    Returns:
        None when omitted (scan all pages — existing default behavior)
        Positive int when provided

    Raises:
        ValidationError: If limit is not a valid integer in range
    """
    if raw_limit is None or raw_limit == "":
        return None

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ValidationError("limit must be an integer") from exc

    if limit < 1 or limit > MAX_PAGE_LIMIT:
        raise ValidationError(f"limit must be between 1 and {MAX_PAGE_LIMIT}")

    return limit


def encode_start_key(last_evaluated_key: dict[str, Any] | None) -> str | None:
    """Encode a DynamoDB LastEvaluatedKey as an opaque pagination token."""
    if not last_evaluated_key:
        return None
    payload = json.dumps(last_evaluated_key, separators=(",", ":"), sort_keys=True)
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_start_key(token: str | None) -> dict[str, Any] | None:
    """
    Decode an opaque pagination token into a DynamoDB ExclusiveStartKey.

    Raises:
        ValidationError: If the token is malformed
    """
    if token is None or token == "":
        return None

    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError("start_key is not a valid pagination token") from exc

    if not isinstance(data, dict) or not data:
        raise ValidationError("start_key is not a valid pagination token")

    return data
