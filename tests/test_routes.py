from botocore.exceptions import ClientError, NoCredentialsError


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
        "next_start_key": None,
    }


def test_list_employees_api_supports_pagination(client, fake_service):
    response = client.get("/api/employees?limit=1")

    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["next_start_key"]
    assert fake_service.last_scan_kwargs == {
        "limit": 1,
        "start_key": None,
    }


def test_list_employees_api_rejects_invalid_limit(client):
    response = client.get("/api/employees?limit=0")

    assert response.status_code == 400
    assert response.json["error"] == "BadRequest"


def test_get_employee_api_rejects_invalid_employee_id(client):
    response = client.get("/api/employees/bad id!")

    assert response.status_code == 400
    assert response.json["error"] == "BadRequest"


def test_get_employee_api(client):
    response = client.get("/api/employees/EMP001")

    assert response.status_code == 200
    assert response.json["employee"]["employeeId"] == "EMP001"


def test_get_employee_api_returns_404_for_missing_employee(client):
    response = client.get("/api/employees/UNKNOWN")

    assert response.status_code == 404
    assert response.json["error"] == "NotFound"
    assert "request_id" in response.json


def test_health_endpoint_reports_iam_role_authentication(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "healthy"
    assert response.json["database"] == "connected"
    assert response.json["authentication"] == "IAM Role"


def test_health_returns_503_when_database_disconnected(client, fake_service):
    fake_service.connected = False

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json["status"] == "degraded"
    assert response.json["database"] == "disconnected"


def test_liveness_endpoint_is_always_ok(client, fake_service):
    fake_service.connected = False

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json["status"] == "alive"


def test_readiness_endpoint_matches_database_state(client, fake_service):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json["status"] == "healthy"

    fake_service.connected = False
    degraded = client.get("/health/ready")
    assert degraded.status_code == 503
    assert degraded.json["status"] == "degraded"


def test_request_id_header_is_returned(client):
    response = client.get("/health/live", headers={"X-Request-ID": "demo-request-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "demo-request-1"
    assert response.json["request_id"] == "demo-request-1"


def test_api_does_not_leak_internal_exception_details(client, fake_service):
    def boom(**_kwargs):
        raise RuntimeError("secret internal failure detail")

    fake_service.scan_all = boom

    response = client.get("/api/employees")

    assert response.status_code == 500
    assert response.json["error"] == "InternalServerError"
    assert response.json["message"] == "An unexpected error occurred"
    assert "secret internal failure detail" not in response.get_data(as_text=True)


def test_api_maps_access_denied_to_403(client, fake_service):
    def denied(**_kwargs):
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "User is not authorized",
                }
            },
            "Scan",
        )

    fake_service.scan_all = denied

    response = client.get("/api/employees")

    assert response.status_code == 403
    assert response.json["error"] == "AccessDeniedException"
    assert "IAM Role" in response.json["message"]


def test_api_maps_missing_credentials_to_503(client, fake_service):
    def no_creds(_employee_id):
        raise NoCredentialsError()

    fake_service.get_employee = no_creds

    response = client.get("/api/employees/EMP001")

    assert response.status_code == 503
    assert response.json["error"] == "CredentialsError"
