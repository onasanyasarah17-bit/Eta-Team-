"""
Shared error response helpers for API and health endpoints.

Keeps error payloads consistent and avoids leaking internal exception details.
"""

from typing import Any

from botocore.exceptions import ClientError, NoCredentialsError
from flask import g, jsonify


AWS_CREDENTIALS_ERROR = (
    "AWS credentials not found. IAM Role may not be attached to EC2 instance."
)

DYNAMODB_ERROR_MESSAGES = {
    "ResourceNotFoundException": "DynamoDB table not found",
    "AccessDeniedException": "Access denied to DynamoDB. Check IAM Role permissions.",
    "ProvisionedThroughputExceededException": "DynamoDB throughput exceeded",
    "ThrottlingException": "DynamoDB request was throttled",
}

DYNAMODB_STATUS_CODES = {
    "ResourceNotFoundException": 404,
    "AccessDeniedException": 403,
    "ProvisionedThroughputExceededException": 503,
    "ThrottlingException": 503,
}


def _request_id() -> str | None:
    return getattr(g, "request_id", None)


def error_payload(
    error: str,
    message: str,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard JSON error body."""
    payload: dict[str, Any] = {
        "error": error,
        "message": message,
    }
    request_id = _request_id()
    if request_id:
        payload["request_id"] = request_id
    if extra:
        payload.update(extra)
    return payload


def error_response(
    error: str,
    message: str,
    status_code: int,
    *,
    extra: dict[str, Any] | None = None,
):
    """Return a Flask JSON error response."""
    return jsonify(error_payload(error, message, extra=extra)), status_code


def client_error_response(error: ClientError):
    """Map a boto3 ClientError to an appropriate HTTP response."""
    error_code = error.response["Error"]["Code"]
    message = DYNAMODB_ERROR_MESSAGES.get(
        error_code,
        f"DynamoDB error: {error_code}",
    )
    status_code = DYNAMODB_STATUS_CODES.get(error_code, 500)
    return error_response(error_code, message, status_code)


def credentials_error_response():
    """Return a response for missing IAM Role credentials."""
    return error_response("CredentialsError", AWS_CREDENTIALS_ERROR, 503)


def map_aws_exception(exc: Exception) -> tuple[str, str, int] | None:
    """
    Map known AWS exceptions to (error, message, status_code).

    Returns None when the exception should be treated as a generic 500.
    """
    if isinstance(exc, NoCredentialsError):
        return "CredentialsError", AWS_CREDENTIALS_ERROR, 503
    if isinstance(exc, ClientError):
        error_code = exc.response["Error"]["Code"]
        message = DYNAMODB_ERROR_MESSAGES.get(
            error_code,
            f"DynamoDB error: {error_code}",
        )
        status_code = DYNAMODB_STATUS_CODES.get(error_code, 500)
        return error_code, message, status_code
    return None
