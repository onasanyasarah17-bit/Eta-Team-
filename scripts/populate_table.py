#!/usr/bin/env python
"""
Populate the DynamoDB employee table with sample data.

This script uses boto3's default credential provider chain. On EC2, credentials
should come from the attached IAM Role. Do not run aws configure or add access
keys to environment variables for this project.
"""

import os
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv


SAMPLE_EMPLOYEES: List[Dict[str, Any]] = [
    {
        "employeeId": "EMP001",
        "name": "John Kamau",
        "department": "Finance",
        "role": "Manager",
        "email": "john@company.com",
        "office": "Nairobi",
    },
    {
        "employeeId": "EMP002",
        "name": "Amina Otieno",
        "department": "Engineering",
        "role": "Backend Developer",
        "email": "amina@company.com",
        "office": "Mombasa",
    },
    {
        "employeeId": "EMP003",
        "name": "Brian Mwangi",
        "department": "Security",
        "role": "Cloud Security Engineer",
        "email": "brian@company.com",
        "office": "Nairobi",
    },
]


def main() -> None:
    load_dotenv()

    table_name = os.getenv("DYNAMODB_TABLE_NAME", "secure-employees")
    region = os.getenv("AWS_REGION", "us-east-1")

    print(f"Using DynamoDB table: {table_name}")
    print(f"Using AWS region: {region}")
    print("Credentials source: boto3 default provider chain")

    try:
        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)
        table.table_status

        with table.batch_writer() as batch:
            for employee in SAMPLE_EMPLOYEES:
                batch.put_item(Item=employee)
                print(f"Queued employee: {employee['employeeId']}")

        print("Sample employees inserted successfully.")

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
