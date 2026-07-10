def test_home_page_lists_employees(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"John Kamau" in response.data
    assert b"Finance" in response.data


def test_employee_detail_page(client):
    response = client.get("/employee/EMP001")

    assert response.status_code == 200
    assert b"Employee Profile" in response.data
    assert b"john@company.com" in response.data


def test_employee_detail_returns_404_for_missing_employee(client):
    response = client.get("/employee/UNKNOWN")

    assert response.status_code == 404


def test_list_employees_api(client):
    response = client.get("/api/employees")

    assert response.status_code == 200
    assert response.json == {
        "employees": [
            {
                "employeeId": "EMP001",
                "name": "John Kamau",
                "department": "Finance",
                "role": "Manager",
                "email": "john@company.com",
                "office": "Nairobi",
            }
        ],
        "count": 1,
    }


def test_get_employee_api(client):
    response = client.get("/api/employees/EMP001")

    assert response.status_code == 200
    assert response.json["employee"]["employeeId"] == "EMP001"


def test_get_employee_api_returns_404_for_missing_employee(client):
    response = client.get("/api/employees/UNKNOWN")

    assert response.status_code == 404
    assert response.json["error"] == "NotFound"


def test_health_endpoint_reports_iam_role_authentication(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "healthy"
    assert response.json["database"] == "connected"
    assert response.json["authentication"] == "IAM Role"
