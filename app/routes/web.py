"""
Web routes (HTML views).

Handles:
- GET / - Home page with all employees
- GET /employee/<employee_id> - Individual employee details

Uses DynamoDB service for data retrieval.
Gracefully handles errors (missing table, access denied, etc.)
"""

from flask import Blueprint, render_template, current_app, abort
from werkzeug.exceptions import HTTPException
from botocore.exceptions import ClientError, NoCredentialsError
from app.utils.logger import get_logger


web_bp = Blueprint("web", __name__, url_prefix="/")
logger = get_logger(__name__)

AWS_CREDENTIALS_ERROR = (
    "AWS credentials error: IAM Role not found. Check EC2 instance configuration."
)


def _employee_list_error_message(error_code: str) -> str:
    if error_code == "ResourceNotFoundException":
        table_name = current_app.config["DYNAMODB_TABLE_NAME"]
        return f"DynamoDB table not found: {table_name}"
    if error_code == "AccessDeniedException":
        return "Access denied to DynamoDB. Check IAM Role permissions."
    return f"Database error: {error_code}"


def _employee_detail_error_message(error_code: str) -> str:
    if error_code == "ResourceNotFoundException":
        return "DynamoDB table not found"
    if error_code == "AccessDeniedException":
        return "Access denied to DynamoDB"
    return f"Database error: {error_code}"


@web_bp.route("/")
def index():
    """
    Home page - list all employees in an HTML table.

    Returns:
        Rendered HTML template with employee list
    """
    try:
        dynamodb_service = current_app.dynamodb_service

        # Scan all employees from DynamoDB
        result = dynamodb_service.scan_all()
        employees = result["items"]

        logger.info(f"Displaying {len(employees)} employees on home page")
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
            500,
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"DynamoDB error while fetching employees: {error_code}")

        error_msg = _employee_list_error_message(error_code)

        return (
            render_template(
                "index.html",
                employees=[],
                error=error_msg,
            ),
            500,
        )

    except Exception as e:
        logger.error(f"Unexpected error fetching employees: {e}")
        return (
            render_template(
                "index.html",
                employees=[],
                error=f"An unexpected error occurred: {str(e)}",
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
        if not employee_id or not employee_id.strip():
            logger.warning("Empty employee_id provided")
            abort(400)

        dynamodb_service = current_app.dynamodb_service

        # Get employee by ID
        employee = dynamodb_service.get_employee(employee_id)

        if not employee:
            logger.info(f"Employee not found: {employee_id}")
            abort(404)

        logger.info(f"Displaying employee details: {employee_id}")
        return render_template(
            "employee.html",
            employee=employee,
            error=None,
        )

    except NoCredentialsError:
        logger.error("IAM Role credentials not found")
        return (
            render_template(
                "employee.html",
                employee=None,
                error=AWS_CREDENTIALS_ERROR,
            ),
            500,
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"DynamoDB error while fetching employee: {error_code}")

        error_msg = _employee_detail_error_message(error_code)

        return (
            render_template(
                "employee.html",
                employee=None,
                error=error_msg,
            ),
            500,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error fetching employee: {e}")
        return (
            render_template(
                "employee.html",
                employee=None,
                error=f"An unexpected error occurred: {str(e)}",
            ),
            500,
        )
