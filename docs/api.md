# Secure Employee Directory API

Base URL: `http://localhost:5000`

## Health Check

`GET /health`

Returns application health, DynamoDB connectivity, and authentication method.

Example response:

```json
{
  "status": "healthy",
  "database": "connected",
  "authentication": "IAM Role",
  "table": "secure-employees",
  "region": "eu-north-1",
  "error": null
}
```

## List Employees

`GET /api/employees`

Returns all employees from DynamoDB.

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
  "count": 1
}
```

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
  "message": "Employee with ID 'EMP999' not found"
}
```

```json
{
  "error": "AccessDeniedException",
  "message": "Access denied to DynamoDB. Check IAM Role permissions."
}
```

## Data Contract

DynamoDB table:

- Partition key: `employeeId`
- Attributes: `name`, `department`, `role`, `email`, `office`

The application never requires long-term AWS access keys. In AWS, boto3 should receive credentials from the EC2 instance profile IAM Role.
