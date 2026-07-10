from app.models.employee import Employee
from app.services.dynamodb_service import DynamoDBService


class FakeTable:
    def __init__(self, scan_responses=None):
        self.scan_responses = scan_responses or []
        self.scan_calls = []
        self.put_items = []
        self.get_keys = []
        self.delete_keys = []
        self.table_status = "ACTIVE"

    def scan(self, **kwargs):
        self.scan_calls.append(kwargs)
        return self.scan_responses.pop(0)

    def put_item(self, Item):
        self.put_items.append(Item)
        return {}

    def get_item(self, Key):
        self.get_keys.append(Key)
        if Key["employeeId"] == "EMP001":
            return {
                "Item": {
                    "employeeId": "EMP001",
                    "name": "John Kamau",
                    "department": "Finance",
                    "role": "Manager",
                    "email": "john@company.com",
                    "office": "Nairobi",
                }
            }
        return {}

    def delete_item(self, Key):
        self.delete_keys.append(Key)
        return {}


def make_service_with_table(table):
    service = DynamoDBService(table_name="secure-employees", region="eu-north-1")
    service._table = table
    return service


def test_employee_accepts_dynamodb_employee_id_and_serializes_back():
    employee = Employee.from_dict(
        {
            "employeeId": "EMP001",
            "name": "John Kamau",
            "department": "Finance",
            "role": "Manager",
            "email": "john@company.com",
            "office": "Nairobi",
        }
    )

    assert employee.employee_id == "EMP001"
    assert employee.to_dict()["employeeId"] == "EMP001"


def test_scan_all_reads_all_pages_when_no_limit():
    table = FakeTable(
        scan_responses=[
            {
                "Items": [
                    {
                        "employeeId": "EMP001",
                        "name": "John Kamau",
                        "department": "Finance",
                        "role": "Manager",
                        "email": "john@company.com",
                        "office": "Nairobi",
                    }
                ],
                "LastEvaluatedKey": {"employeeId": "EMP001"},
            },
            {
                "Items": [
                    {
                        "employeeId": "EMP002",
                        "name": "Amina Otieno",
                        "department": "Engineering",
                        "role": "Developer",
                        "email": "amina@company.com",
                        "office": "Mombasa",
                    }
                ]
            },
        ]
    )
    service = make_service_with_table(table)

    result = service.scan_all()

    assert result["count"] == 2
    assert [employee.employee_id for employee in result["items"]] == [
        "EMP001",
        "EMP002",
    ]
    assert table.scan_calls[1]["ExclusiveStartKey"] == {"employeeId": "EMP001"}


def test_get_employee_uses_employee_id_partition_key():
    table = FakeTable()
    service = make_service_with_table(table)

    employee = service.get_employee("EMP001")

    assert employee.employee_id == "EMP001"
    assert table.get_keys == [{"employeeId": "EMP001"}]


def test_put_employee_writes_dynamodb_schema():
    table = FakeTable()
    service = make_service_with_table(table)
    employee = Employee(
        employee_id="EMP001",
        name="John Kamau",
        department="Finance",
        role="Manager",
        email="john@company.com",
        office="Nairobi",
    )

    service.put_employee(employee)

    assert table.put_items == [
        {
            "employeeId": "EMP001",
            "name": "John Kamau",
            "department": "Finance",
            "role": "Manager",
            "email": "john@company.com",
            "office": "Nairobi",
        }
    ]


def test_delete_employee_uses_employee_id_partition_key():
    table = FakeTable()
    service = make_service_with_table(table)

    service.delete_employee("EMP001")

    assert table.delete_keys == [{"employeeId": "EMP001"}]
