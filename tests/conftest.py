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

    def scan_all(self):
        return {
            "items": [self.employee],
            "count": 1,
            "last_evaluated_key": None,
        }

    def get_employee(self, employee_id):
        if employee_id == self.employee.employee_id:
            return self.employee
        return None

    def check_connectivity(self):
        return {
            "connected": self.connected,
            "table": "test-secure-employees",
            "region": "eu-north-1",
        }


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
