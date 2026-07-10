"""
REST API routes (JSON endpoints).

Handles:
- GET /api/employees - List all employees
- GET /api/employees/<employee_id> - Get single employee

All responses follow REST conventions with proper HTTP status codes.
Uses DynamoDB service for data retrieval.
"""

from flask import Blueprint, jsonify, current_app
from botocore.exceptions import ClientError, NoCredentialsError
from app.utils.logger import get_logger


api_bp = Blueprint("api", __name__, url_prefix="/api")
logger = get_logger(__name__)

AWS_CREDENTIALS_ERROR = (
    "AWS credentials not found. IAM Role may not be attached to EC2 instance."
)

DYNAMODB_ERROR_MESSAGES = {
    "ResourceNotFoundException": "DynamoDB table not found",
    "AccessDeniedException": "Access denied to DynamoDB. Check IAM Role permissions.",
    "ProvisionedThroughputExceededException": "DynamoDB throughput exceeded",
}


def _dynamodb_error_response(error: ClientError):
    error_code = error.response["Error"]["Code"]
    message = DYNAMODB_ERROR_MESSAGES.get(
        error_code,
        f"DynamoDB error: {error_code}",
    )
    return (
        jsonify(
            {
                "error": error_code,
                "message": message,
            }
        ),
        500,
    )


@api_bp.route("/employees", methods=["GET"])
def list_employees():
    """
    Get all employees as JSON.

    Returns:
        200: {"employees": [Employee objects], "count": int}
        500: {"error": str, "message": str}
    """
    try:
        dynamodb_service = current_app.dynamodb_service

        # Scan all employees from DynamoDB
        result = dynamodb_service.scan_all()
        employees = result["items"]

        logger.info(f"API: Retrieved {len(employees)} employees")

        return (
            jsonify(
                {
                    "employees": [emp.to_dict() for emp in employees],
                    "count": len(employees),
                }
            ),
            200,
        )

    except NoCredentialsError:
        logger.error("API: IAM Role credentials not found")
        return (
            jsonify(
                {
                    "error": "CredentialsError",
                    "message": AWS_CREDENTIALS_ERROR,
                }
            ),
            500,
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"API: DynamoDB error while listing employees: {error_code}")
        return _dynamodb_error_response(e)

    except Exception as e:
        logger.error(f"API: Unexpected error listing employees: {e}")
        return (
            jsonify(
                {
                    "error": "InternalServerError",
                    "message": str(e),
                }
            ),
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
        400: {"error": str, "message": str} - Invalid ID
        404: {"error": str, "message": str} - Employee not found
        500: {"error": str, "message": str} - Server error
    """
    try:
        # Validate employee_id
        if not employee_id or not employee_id.strip():
            logger.warning("API: Empty employee_id provided")
            return (
                jsonify(
                    {
                        "error": "BadRequest",
                        "message": "employee_id cannot be empty",
                    }
                ),
                400,
            )

        dynamodb_service = current_app.dynamodb_service

        # Get employee by ID
        employee = dynamodb_service.get_employee(employee_id)

        if not employee:
            logger.info(f"API: Employee not found: {employee_id}")
            return (
                jsonify(
                    {
                        "error": "NotFound",
                        "message": f"Employee with ID '{employee_id}' not found",
                    }
                ),
                404,
            )

        logger.info(f"API: Retrieved employee: {employee_id}")

        return (
            jsonify(
                {
                    "employee": employee.to_dict(),
                }
            ),
            200,
        )

    except NoCredentialsError:
        logger.error("API: IAM Role credentials not found")
        return (
            jsonify(
                {
                    "error": "CredentialsError",
                    "message": AWS_CREDENTIALS_ERROR,
                }
            ),
            500,
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"API: DynamoDB error while getting employee: {error_code}")
        return _dynamodb_error_response(e)

    except Exception as e:
        logger.error(f"API: Unexpected error getting employee: {e}")
        return (
            jsonify(
                {
                    "error": "InternalServerError",
                    "message": str(e),
                }
            ),
            500,
        )
