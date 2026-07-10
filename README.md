# Secure Employee Directory

Python Flask backend demonstrating the AWS best practice of allowing an EC2 instance to access DynamoDB through an IAM Role instead of long-term AWS access keys.

## Project Goal

The application reads employee records from a DynamoDB table and serves them through HTML pages and JSON API endpoints. In AWS, authentication must come from the IAM Role attached to the EC2 instance. No AWS credentials should be hardcoded, committed, or configured with `aws configure`.

## Architecture

- Flask application factory in `app/__init__.py`
- Routes separated into web and REST API blueprints
- DynamoDB access isolated in `app/services/dynamodb_service.py`
- Employee domain model in `app/models/employee.py`
- Environment-based configuration in `app/config.py`
- Centralized logging in `app/utils/logger.py`
- Tests use fakes/mocks instead of real AWS resources

## Folder Structure

```text
IAM-least-previlege-backend/
├── app/
│   ├── routes/
│   ├── services/
│   ├── models/
│   ├── templates/
│   ├── static/css/style.css
│   ├── utils/
│   ├── __init__.py
│   └── config.py
├── docs/
│   └── api.md
├── scripts/
│   └── populate_table.py
├── tests/
│   ├── conftest.py
│   ├── test_routes.py
│   └── test_services.py
├── Dockerfile
├── requirements.txt
├── run.py
├── .env.example
└── README.md
```

## DynamoDB Contract

Table name defaults to `secure-employees`.

Required schema:

- Partition key: `employeeId`
- Attributes: `name`, `department`, `role`, `email`, `office`

Example item:

```json
{
  "employeeId": "EMP001",
  "name": "John Kamau",
  "department": "Finance",
  "role": "Manager",
  "email": "john@company.com",
  "office": "Nairobi"
}
```

## Environment Variables

Copy `.env.example` to `.env` for local development if needed.

```text
FLASK_ENV=development
SECRET_KEY=your-secret-key-here-change-in-production
PORT=5000
HOST=0.0.0.0
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=secure-employees
LOG_LEVEL=INFO
```

Do not set `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` for the AWS challenge deployment. On EC2, boto3 should use the instance profile credentials from the attached IAM Role.

## Local Development

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it and install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python run.py
```

Open:

- `http://localhost:5000/`
- `http://localhost:5000/health`
- `http://localhost:5000/api/employees`

Local runs still need AWS credentials from boto3's provider chain if they access a real DynamoDB table. For this challenge, production EC2 should use the IAM Role.

## Populate Sample Data

After the infrastructure team creates the DynamoDB table and attaches the correct IAM Role to the EC2 instance:

```bash
python scripts/populate_table.py
```

The script uses boto3's default credential provider chain and does not configure or accept access keys.

## Tests

```bash
pytest
```

The tests do not call AWS. They use fake services and fake DynamoDB table objects to validate routing, health output, pagination behavior, and the `employeeId` data contract.

## Docker

Build:

```bash
docker build -t secure-employee-directory .
```

Run:

```bash
docker run --rm -p 5000:5000 \
  -e FLASK_ENV=production \
  -e SECRET_KEY=change-me \
  -e AWS_REGION=us-east-1 \
  -e DYNAMODB_TABLE_NAME=secure-employees \
  secure-employee-directory
```

In AWS, prefer running on EC2 with an instance profile IAM Role. If this container runs on ECS instead, use an ECS task role.

## IAM Role Requirements

The EC2 instance role should follow least privilege. For this app, read-only runtime access needs:

- `dynamodb:Scan`
- `dynamodb:GetItem`
- `dynamodb:DescribeTable`

If running `scripts/populate_table.py`, the role also needs:

- `dynamodb:BatchWriteItem`
- `dynamodb:PutItem`

Scope permissions to the specific DynamoDB table ARN created by CloudFormation.

## API Documentation

See [docs/api.md](docs/api.md).

## Troubleshooting

`NoCredentialsError`:

- Confirm the app is running on the intended EC2 instance.
- Confirm an IAM Role is attached to the instance.
- Do not use `aws configure` for this challenge.

`AccessDeniedException`:

- Confirm the role policy allows the required DynamoDB actions.
- Confirm the policy resource ARN matches the table.

`ResourceNotFoundException`:

- Confirm `DYNAMODB_TABLE_NAME`.
- Confirm `AWS_REGION`.
- Confirm CloudFormation created the table successfully.

## Future Improvements

- Add structured JSON logging for production.
- Add request IDs and correlation IDs.
- Add CloudFormation outputs documentation once infrastructure is finalized.
- Add CI workflow for linting, tests, and Docker build.
- Add pagination parameters to the public API if the employee table grows.
