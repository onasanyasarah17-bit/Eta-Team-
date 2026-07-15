"""
REST API routes (JSON endpoints).

Handles:
- GET /api/employees - List employees (optional pagination)
- GET /api/employees/<employee_id> - Get single employee

All responses follow REST conventions with proper HTTP status codes.
Uses DynamoDB service for data retrieval.
"""

from flask import Blueprint, current_app, jsonify, request
from botocore.exceptions import ClientError, NoCredentialsError

from app.utils.errors import (
    client_error_response,
    credentials_error_response,
    error_response,
)
from app.utils.logger import get_logger
from app.utils.validators import (
    ValidationError,
    decode_start_key,
    encode_start_key,
    parse_page_limit,
    validate_employee_id,
)


api_bp = Blueprint("api", __name__, url_prefix="/api")
logger = get_logger(__name__)


@api_bp.route("/employees", methods=["GET"])
def list_employees():
    """
    Get employees as JSON.

    Query params:
        limit: optional page size (1-100). Omit to return all pages.
        start_key: opaque token from a previous response's next_start_key.

    Returns:
        200: {"employees": [...], "count": int, "next_start_key": str|null}
        400/403/404/503/500: {"error": str, "message": str, "request_id": str}
    """
    try:
        limit = parse_page_limit(request.args.get("limit"))
        start_key = decode_start_key(request.args.get("start_key"))

        dynamodb_service = current_app.dynamodb_service
        result = dynamodb_service.scan_all(limit=limit, start_key=start_key)
        employees = result["items"]
        next_start_key = encode_start_key(result.get("last_evaluated_key"))

        logger.info(
            "API: Retrieved %s employees (limit=%s, has_more=%s)",
            len(employees),
            limit,
            bool(next_start_key),
        )

        return (
            jsonify(
                {
                    "employees": [emp.to_dict() for emp in employees],
                    "count": len(employees),
                    "next_start_key": next_start_key,
                }
            ),
            200,
        )

    except ValidationError as e:
        logger.warning("API: Invalid list employees query: %s", e)
        return error_response("BadRequest", str(e), 400)

    except NoCredentialsError:
        logger.error("API: IAM Role credentials not found")
        return credentials_error_response()

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("API: DynamoDB error while listing employees: %s", error_code)
        return client_error_response(e)

    except Exception:
        logger.exception("API: Unexpected error listing employees")
        return error_response(
            "InternalServerError",
            "An unexpected error occurred",
            500,
        )


@api_bp.route("/employees/<employee_id>", methods=["GET"])
def get_employee(employee_id: str):
    """
    Get single employee by ID as JSON.

    Args:
        employee_id: Employee ID (from URL)

    Returns:
        200: {"employee": Employee object}
        400/403/404/503/500: {"error": str, "message": str, "request_id": str}
    """
    try:
        normalized_id = validate_employee_id(employee_id)

        dynamodb_service = current_app.dynamodb_service
        employee = dynamodb_service.get_employee(normalized_id)

        if not employee:
            logger.info("API: Employee not found: %s", normalized_id)
            return error_response(
                "NotFound",
                f"Employee with ID '{normalized_id}' not found",
                404,
            )

        logger.info("API: Retrieved employee: %s", normalized_id)

        return (
            jsonify(
                {
                    "employee": employee.to_dict(),
                }
            ),
            200,
        )

    except ValidationError as e:
        logger.warning("API: Invalid employee_id: %s", e)
        return error_response("BadRequest", str(e), 400)

    except NoCredentialsError:
        logger.error("API: IAM Role credentials not found")
        return credentials_error_response()

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("API: DynamoDB error while getting employee: %s", error_code)
        return client_error_response(e)

    except Exception:
        logger.exception("API: Unexpected error getting employee")
        return error_response(
            "InternalServerError",
            "An unexpected error occurred",
            500,
        )
