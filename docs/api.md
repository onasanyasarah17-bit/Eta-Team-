# Secure Employee Directory API

Base URL: `http://localhost:5000` (or `https://...` when served behind an ALB)

Every response includes an `X-Request-ID` header. Error JSON bodies also include `request_id` when available.

## Health Checks

### Combined / readiness-style health

`GET /health`

Also available as `GET /health/ready`.

Returns application health, DynamoDB connectivity, and authentication method.

- `200` when DynamoDB is reachable (`status: healthy`)
- `503` when DynamoDB is unreachable (`status: degraded`) — suitable for load balancer target checks

Example response:

```json
{
  "status": "healthy",
  "database": "connected",
  "authentication": "IAM Role",
  "table": "secure-employees",
  "region": "eu-north-1",
  "error": null,
  "request_id": "demo-request-1"
}
```

### Liveness

`GET /health/live`

Process-only check. Always returns `200` if the Flask process is up (does not call DynamoDB).

```json
{
  "status": "alive",
  "request_id": "demo-request-1"
}
```

## List Employees

`GET /api/employees`

Returns employees from DynamoDB.

Optional query parameters:

| Param | Description |
|-------|-------------|
| `limit` | Page size (`1`–`100`). Omit to return all pages. |
| `start_key` | Opaque token from a previous `next_start_key`. |

Example response:

```json
{
  "employees": [
    {
      "employeeId": "EMP001",
      "name": "John Kamau",
      "department": "Finance",
      "role": "Manager",
      "email": "john@company.com",
      "office": "Nairobi"
    }
  ],
  "count": 1,
  "next_start_key": null
}
```

When more pages exist, `next_start_key` is a string token. Pass it back as `start_key` on the next request.

## Get Employee

`GET /api/employees/<employeeId>`

Returns one employee by DynamoDB partition key.

Example response:

```json
{
  "employee": {
    "employeeId": "EMP001",
    "name": "John Kamau",
    "department": "Finance",
    "role": "Manager",
    "email": "john@company.com",
    "office": "Nairobi"
  }
}
```

## Error Responses

Common errors:

```json
{
  "error": "NotFound",
  "message": "Employee with ID 'EMP999' not found",
  "request_id": "demo-request-1"
}
```

```json
{
  "error": "AccessDeniedException",
  "message": "Access denied to DynamoDB. Check IAM Role permissions.",
  "request_id": "demo-request-1"
}
```

| Condition | HTTP status |
|-----------|-------------|
| Invalid / empty `employeeId` | `400` |
| Employee or table not found | `404` |
| IAM AccessDenied | `403` |
| Missing IAM Role credentials / DynamoDB throttle | `503` |
| Unexpected server error | `500` (no internal exception text) |

## Data Contract

DynamoDB table:

- Partition key: `employeeId`
- Attributes: `name`, `department`, `role`, `email`, `office`

The application never requires long-term AWS access keys. In AWS, boto3 should receive credentials from the EC2 instance profile IAM Role.
