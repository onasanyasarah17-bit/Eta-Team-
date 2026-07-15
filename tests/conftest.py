import pytest

from app import create_app
from app.models.employee import Employee


class FakeDynamoDBService:
    def __init__(self):
        self.employee = Employee(
            employee_id="EMP001",
            name="John Kamau",
            department="Finance",
            role="Manager",
            email="john@company.com",
            office="Nairobi",
        )
        self.connected = True

    def scan_all(self, limit=None, start_key=None):
        self.last_scan_kwargs = {"limit": limit, "start_key": start_key}
        items = [self.employee]
        last_key = None
        if limit == 1:
            last_key = {"employeeId": self.employee.employee_id}
        return {
            "items": items[:limit] if limit else items,
            "count": len(items[:limit]) if limit else len(items),
            "last_evaluated_key": last_key,
        }

    def get_employee(self, employee_id):
        if employee_id == self.employee.employee_id:
            return self.employee
        return None

    def check_connectivity(self):
        result = {
            "connected": self.connected,
            "table": "test-secure-employees",
            "region": "eu-north-1",
        }
        if not self.connected:
            result["error"] = "Simulated DynamoDB disconnect"
        return result


@pytest.fixture()
def fake_service():
    return FakeDynamoDBService()


@pytest.fixture()
def app(fake_service):
    flask_app = create_app("testing")
    flask_app.dynamodb_service = fake_service
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
