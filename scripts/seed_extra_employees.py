#!/usr/bin/env python
"""
Add extra demo employees (EMP004–EMP006) without replacing EMP001–EMP003.

Safe for live demos: this only writes new IDs. It does not delete existing items.
Uses boto3's default credential provider chain (IAM Role on EC2).
"""

import os
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv


EXTRA_EMPLOYEES: List[Dict[str, Any]] = [
    {
        "employeeId": "EMP004",
        "name": "Grace Wanjiku",
        "department": "Product",
        "role": "Product Manager",
        "email": "grace@company.com",
        "office": "Nairobi",
    },
    {
        "employeeId": "EMP005",
        "name": "David Ochieng",
        "department": "Engineering",
        "role": "Frontend Developer",
        "email": "david@company.com",
        "office": "Kisumu",
    },
    {
        "employeeId": "EMP006",
        "name": "Faith Njeri",
        "department": "People",
        "role": "HR Specialist",
        "email": "faith@company.com",
        "office": "Nairobi",
    },
]


def main() -> None:
    load_dotenv()

    table_name = os.getenv("DYNAMODB_TABLE_NAME", "secure-employees")
    region = os.getenv("AWS_REGION", "eu-north-1")

    print(f"Using DynamoDB table: {table_name}")
    print(f"Using AWS region: {region}")
    print("Credentials source: boto3 default provider chain")
    print("Mode: ADD extra employees (EMP004–EMP006); existing rows are kept")

    try:
        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)
        table.table_status

        with table.batch_writer() as batch:
            for employee in EXTRA_EMPLOYEES:
                batch.put_item(Item=employee)
                print(f"Queued employee: {employee['employeeId']} ({employee['name']})")

        print("Extra employees inserted successfully.")
        print("Refresh / or /api/employees to see EMP001–EMP006.")

    except NoCredentialsError as exc:
        raise SystemExit(
            "No AWS credentials found. On EC2, attach the correct IAM Role. "
            "Do not use aws configure for this project."
        ) from exc
    except ClientError as exc:
        error = exc.response["Error"]
        raise SystemExit(
            f"DynamoDB operation failed: {error['Code']} - {error['Message']}"
        ) from exc


if __name__ == "__main__":
    main()
