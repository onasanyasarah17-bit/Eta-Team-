"""
DynamoDB service layer.

Handles all DynamoDB operations.
Abstracts boto3 complexity from routes.
Demonstrates IAM Role authentication (no hardcoded credentials).

AWS Credentials Flow:
1. boto3.resource() initializes without explicit credentials
2. boto3 uses default credential provider chain
3. On EC2, detects and uses attached IAM Role automatically
4. IAM Role has policies allowing DynamoDB access
5. No aws configure needed, no credentials in code
"""

from typing import Any, Dict, Optional
import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
)

from app.utils.logger import get_logger
from app.models.employee import Employee


logger = get_logger(__name__)


class DynamoDBService:
    """
    Service layer for DynamoDB operations.

    Uses boto3 resource API (higher-level) instead of low-level client.
    boto3 automatically handles IAM Role credential chain on EC2.

    Example:
        >>> service = DynamoDBService(table_name="secure-employees")
        >>> result = service.scan_all()
        >>> emp = service.get_employee("EMP001")
    """

    def __init__(self, table_name: str, region: str = "us-east-1"):
        """
        Initialize DynamoDB service.

        Credentials come from boto3's default provider chain:
        1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        2. ~/.aws/credentials file
        3. IAM Role attached to EC2 instance (recommended in production)
        4. Container metadata (ECS task roles)

        Args:
            table_name: DynamoDB table name
            region: AWS region

        Raises:
            ValueError: If table_name is empty
        """
        if not table_name:
            raise ValueError("table_name cannot be empty")

        self.table_name = table_name
        self.region = region
        self._table = None

        logger.info(
            f"Initializing DynamoDB service for table '{table_name}' "
            f"in region '{region}'. Using IAM Role credential chain."
        )

    @property
    def table(self):
        """
        Lazy-load DynamoDB table resource.

        Credentials are obtained from boto3 default provider chain.
        On EC2, IAM Role is automatically detected and used.

        Returns:
            boto3 DynamoDB table resource

        Raises:
            NoCredentialsError: If IAM Role not attached to EC2
            ClientError: If table doesn't exist or region is invalid
        """
        if self._table is None:
            try:
                dynamodb = boto3.resource("dynamodb", region_name=self.region)
                self._table = dynamodb.Table(self.table_name)
                # Verify table exists and we have access
                self._table.table_status
                logger.info(
                    f"Successfully connected to DynamoDB table '{self.table_name}'"
                )
            except NoCredentialsError:
                logger.error(
                    "No AWS credentials found. Ensure IAM Role is attached. "
                    "Do not use aws configure or hardcoded credentials."
                )
                raise
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    logger.error(f"DynamoDB table '{self.table_name}' not found")
                else:
                    logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
                raise
        return self._table

    def scan_all(
        self,
        limit: Optional[int] = None,
        start_key: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Scan employee items in the table with pagination support.

        Args:
            limit: Maximum items to return (None = all pages)
            start_key: LastEvaluatedKey for pagination

        Returns:
            {
                "items": [Employee objects],
                "count": number of items returned,
                "last_evaluated_key": for pagination or None
            }

        Raises:
            ClientError: If scan operation fails
        """
        try:
            scan_kwargs: Dict[str, Any] = {}
            if limit:
                scan_kwargs["Limit"] = limit
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key

            items = []
            last_evaluated_key = None

            while True:
                response = self.table.scan(**scan_kwargs)
                items.extend(
                    Employee.from_dynamodb_item(item)
                    for item in response.get("Items", [])
                )

                last_evaluated_key = response.get("LastEvaluatedKey")
                if limit or not last_evaluated_key:
                    break

                scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

            logger.info(
                f"Scanned {len(items)} employees from DynamoDB. "
                f"Has more: {bool(last_evaluated_key)}"
            )

            return {
                "items": items,
                "count": len(items),
                "last_evaluated_key": last_evaluated_key,
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"DynamoDB scan failed: {error_code} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during scan: {e}")
            raise

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        """
        Get a single employee by ID.

        Args:
            employee_id: Employee ID (partition key)

        Returns:
            Employee object or None if not found

        Raises:
            ClientError: If operation fails
        """
        if not employee_id:
            raise ValueError("employee_id cannot be empty")

        try:
            response = self.table.get_item(Key={"employeeId": employee_id})

            if "Item" not in response:
                logger.info(f"Employee '{employee_id}' not found")
                return None

            employee = Employee.from_dynamodb_item(response["Item"])
            logger.info(f"Retrieved employee '{employee_id}'")
            return employee

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "AccessDeniedException":
                logger.error(
                    "Access denied to DynamoDB. "
                    "Verify IAM Role has DynamoDB read permissions."
                )
            else:
                logger.error(f"DynamoDB get_item failed: {error_code} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving employee: {e}")
            raise

    def put_employee(self, employee: Employee) -> bool:
        """
        Put an employee item into DynamoDB.

        Args:
            employee: Employee object

        Returns:
            True if successful

        Raises:
            ClientError: If operation fails
            ValueError: If employee data is invalid
        """
        employee.validate()

        try:
            self.table.put_item(Item=employee.to_dynamodb_item())
            logger.info(f"Inserted employee '{employee.employee_id}'")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "AccessDeniedException":
                logger.error(
                    "Access denied to DynamoDB. "
                    "Verify IAM Role has DynamoDB write permissions."
                )
            else:
                logger.error(f"DynamoDB put_item failed: {error_code} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error inserting employee: {e}")
            raise

    def delete_employee(self, employee_id: str) -> bool:
        """
        Delete an employee from DynamoDB.

        Args:
            employee_id: Employee ID

        Returns:
            True if successful

        Raises:
            ClientError: If operation fails
        """
        if not employee_id:
            raise ValueError("employee_id cannot be empty")

        try:
            self.table.delete_item(Key={"employeeId": employee_id})
            logger.info(f"Deleted employee '{employee_id}'")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"DynamoDB delete_item failed: {error_code} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting employee: {e}")
            raise

    def check_connectivity(self) -> Dict[str, Any]:
        """
        Check if DynamoDB is accessible.

        Returns:
            {
                "connected": bool,
                "table": table name,
                "region": AWS region,
                "error": error message if not connected
            }
        """
        try:
            # Try to get table status
            self.table.table_status
            logger.info("DynamoDB connectivity check passed")
            return {
                "connected": True,
                "table": self.table_name,
                "region": self.region,
            }
        except NoCredentialsError:
            logger.error(
                "DynamoDB check failed: No AWS credentials (IAM Role not attached?)"
            )
            return {
                "connected": False,
                "table": self.table_name,
                "region": self.region,
                "error": "No AWS credentials. Ensure IAM Role is attached to EC2.",
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"DynamoDB check failed: {error_code}")
            return {
                "connected": False,
                "table": self.table_name,
                "region": self.region,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"DynamoDB check failed: {e}")
            return {
                "connected": False,
                "table": self.table_name,
                "region": self.region,
                "error": str(e),
            }
