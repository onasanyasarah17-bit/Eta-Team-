"""
Web routes (HTML views).

Handles:
- GET / - Home page with all employees
- GET /employee/<employee_id> - Individual employee details

Uses DynamoDB service for data retrieval.
Gracefully handles errors (missing table, access denied, etc.)
"""

from flask import Blueprint, abort, current_app, render_template
from werkzeug.exceptions import HTTPException
from botocore.exceptions import ClientError, NoCredentialsError

from app.utils.errors import AWS_CREDENTIALS_ERROR, DYNAMODB_ERROR_MESSAGES
from app.utils.logger import get_logger
from app.utils.validators import ValidationError, validate_employee_id


web_bp = Blueprint("web", __name__, url_prefix="/")
logger = get_logger(__name__)


def _employee_list_error_message(error_code: str) -> str:
    if error_code == "ResourceNotFoundException":
        table_name = current_app.config["DYNAMODB_TABLE_NAME"]
        return f"DynamoDB table not found: {table_name}"
    return DYNAMODB_ERROR_MESSAGES.get(error_code, f"Database error: {error_code}")


def _employee_detail_error_message(error_code: str) -> str:
    return DYNAMODB_ERROR_MESSAGES.get(error_code, f"Database error: {error_code}")


@web_bp.route("/")
def index():
    """
    Home page - list all employees in an HTML table.

    Returns:
        Rendered HTML template with employee list
    """
    try:
        dynamodb_service = current_app.dynamodb_service
        result = dynamodb_service.scan_all()
        employees = result["items"]

        logger.info("Displaying %s employees on home page", len(employees))
        return render_template(
            "index.html",
            employees=employees,
            error=None,
        )

    except NoCredentialsError:
        logger.error("IAM Role credentials not found")
        return (
            render_template(
                "index.html",
                employees=[],
                error=AWS_CREDENTIALS_ERROR,
            ),
            503,
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("DynamoDB error while fetching employees: %s", error_code)
        return (
            render_template(
                "index.html",
                employees=[],
                error=_employee_list_error_message(error_code),
            ),
            503 if error_code in {"ProvisionedThroughputExceededException", "ThrottlingException"} else 500,
        )

    except Exception:
        logger.exception("Unexpected error fetching employees")
        return (
            render_template(
                "index.html",
                employees=[],
                error="An unexpected error occurred",
            ),
            500,
        )


@web_bp.route("/employee/<employee_id>")
def employee_detail(employee_id: str):
    """
    Employee detail page.

    Args:
        employee_id: Employee ID (from URL)

    Returns:
        Rendered HTML template with employee details
    """
    try:
        normalized_id = validate_employee_id(employee_id)

        dynamodb_service = current_app.dynamodb_service
        employee = dynamodb_service.get_employee(normalized_id)

        if not employee:
            logger.info("Employee not found: %s", normalized_id)
            abort(404)

        logger.info("Displaying employee details: %s", normalized_id)
        return render_template(
            "employee.html",
            employee=employee,
            error=None,
        )

    except ValidationError:
        logger.warning("Invalid employee_id provided")
        abort(400)

    except NoCredentialsError:
        logger.error("IAM Role credentials not found")
        return (
            render_template(
                "employee.html",
                employee=None,
                error=AWS_CREDENTIALS_ERROR,
            ),
            503,
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("DynamoDB error while fetching employee: %s", error_code)
        return (
            render_template(
                "employee.html",
                employee=None,
                error=_employee_detail_error_message(error_code),
            ),
            503 if error_code in {"ProvisionedThroughputExceededException", "ThrottlingException"} else 500,
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception("Unexpected error fetching employee")
        return (
            render_template(
                "employee.html",
                employee=None,
                error="An unexpected error occurred",
            ),
            500,
        )
