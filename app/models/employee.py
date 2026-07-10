"""
Employee domain model.

Represents an employee in the system.
Validates data and provides conversion to/from DynamoDB format.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Employee:
    """
    Employee domain model.

    Represents an employee with all attributes.
    Immutable by design for data consistency.

    Attributes:
        employee_id: Unique identifier (employeeId partition key in DynamoDB)
        name: Employee full name
        department: Department name
        role: Job role/title
        email: Email address
        office: Office location
    """

    employee_id: str
    name: str
    department: str
    role: str
    email: str
    office: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert employee to dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization

        Example:
            >>> emp = Employee(...)
            >>> data = emp.to_dict()
            >>> print(json.dumps(data))
        """
        return {
            "employeeId": self.employee_id,
            "name": self.name,
            "department": self.department,
            "role": self.role,
            "email": self.email,
            "office": self.office,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Employee":
        """
        Create employee from dictionary (e.g., from DynamoDB).

        Args:
            data: Dictionary with employee attributes

        Returns:
            Employee instance

        Raises:
            KeyError: If required fields are missing
            TypeError: If data types are invalid

        Example:
            >>> data = {"employeeId": "EMP001", ...}
            >>> emp = Employee.from_dict(data)
        """
        employee_id = data.get("employeeId", data.get("employee_id"))
        normalized_data = {**data, "employee_id": employee_id}
        required_fields = {
            "employee_id",
            "name",
            "department",
            "role",
            "email",
            "office",
        }

        missing_fields = required_fields - {
            key for key, value in normalized_data.items() if value is not None
        }
        if missing_fields:
            raise KeyError(f"Missing required fields: {missing_fields}")

        return Employee(
            employee_id=str(normalized_data["employee_id"]),
            name=str(normalized_data["name"]),
            department=str(normalized_data["department"]),
            role=str(normalized_data["role"]),
            email=str(normalized_data["email"]),
            office=str(normalized_data["office"]),
        )

    @staticmethod
    def from_dynamodb_item(item: Dict[str, Any]) -> "Employee":
        """
        Create employee from DynamoDB GetItem response.

        DynamoDB returns items with type descriptors:
        {"name": {"S": "John"}, "id": {"S": "EMP001"}}

        Args:
            item: DynamoDB item (from GetItem or Scan)

        Returns:
            Employee instance

        Example:
            >>> item = {"employeeId": "EMP001", ...}
            >>> emp = Employee.from_dynamodb_item(item)
        """
        # boto3 resource automatically converts DynamoDB types
        # If using low-level client, manual conversion would be needed
        return Employee.from_dict(item)

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """
        Convert employee to DynamoDB item format.

        Returns:
            Dictionary using the table schema, including employeeId partition key.
        """
        return self.to_dict()

    def validate(self) -> bool:
        """
        Validate employee data.

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails

        Example:
            >>> emp = Employee(...)
            >>> emp.validate()  # Raises ValueError if invalid
        """
        if not self.employee_id or not isinstance(self.employee_id, str):
            raise ValueError("employee_id must be a non-empty string")

        if not self.name or len(self.name.strip()) == 0:
            raise ValueError("name must be a non-empty string")

        if not self.email or "@" not in self.email:
            raise ValueError("email must be valid")

        if not self.department or len(self.department.strip()) == 0:
            raise ValueError("department must be a non-empty string")

        if not self.role or len(self.role.strip()) == 0:
            raise ValueError("role must be a non-empty string")

        if not self.office or len(self.office.strip()) == 0:
            raise ValueError("office must be a non-empty string")

        return True

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"Employee(id={self.employee_id}, name={self.name}, "
            f"dept={self.department}, role={self.role})"
        )
