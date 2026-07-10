# EC2 + IAM Role (CloudFormation)

This stack finishes the Secure Employee Directory demo:

- EC2 instance (Amazon Linux 2023)
- Security group (SSH + app port 5000)
- IAM role + instance profile with **least-privilege DynamoDB access**
- Bootstrap that clones the app, starts Gunicorn, and seeds sample data

The Flask app on EC2 uses the **instance profile**. No AWS access keys are placed on the instance or in Git.

## Template

```text
infrastructure/ec2-iam.yaml
```

## Prerequisites

1. DynamoDB table already exists in `eu-north-1` (console or `infrastructure/dynamodb.yaml`)
2. An EC2 key pair in `eu-north-1`
3. AWS CLI / CloudShell credentials for the **shared team account** (local profile only — never commit keys)
4. Permission to create EC2, IAM roles/policies/instance profiles, and security groups

## Get the table ARN

```bash
aws dynamodb describe-table \
  --table-name secure-employees \
  --region eu-north-1 \
  --query "Table.TableArn" \
  --output text
```

Or from the DynamoDB CloudFormation stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory \
  --region eu-north-1 \
  --query "Stacks[0].Outputs" \
  --output table
```

## Deploy

Replace `YOUR_KEY_PAIR` and `TABLE_ARN` before running.

```bash
aws cloudformation deploy \
  --template-file infrastructure/ec2-iam.yaml \
  --stack-name secure-employee-ec2 \
  --parameter-overrides \
    KeyName=YOUR_KEY_PAIR \
    TableName=secure-employees \
    TableArn=TABLE_ARN \
    Environment=production \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1
```

`CAPABILITY_NAMED_IAM` is required because the template creates a named IAM role/instance profile.

## After deploy

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-ec2 \
  --region eu-north-1 \
  --query "Stacks[0].Outputs" \
  --output table
```

Open:

- `AppUrl` → employee directory
- `HealthUrl` → should show `"authentication": "IAM Role"` and `"database": "connected"`

Allow 3–5 minutes after `CREATE_COMPLETE` for UserData (git clone, pip install, service start).

## What the IAM role allows (least privilege)

Scoped to the **single table ARN** you pass in:

| Action | Why |
|--------|-----|
| `dynamodb:GetItem` | Employee detail pages/API |
| `dynamodb:Scan` | List employees |
| `dynamodb:DescribeTable` | `/health` connectivity check |
| `dynamodb:PutItem` | Seed script |
| `dynamodb:BatchWriteItem` | Seed script |

No `Resource: "*"`.

## Demo talking points

1. DynamoDB table holds employees
2. EC2 has an **IAM instance profile**, not access keys
3. boto3 uses the default credential provider chain → instance role
4. Policy is scoped to one table ARN (least privilege)
5. `/health` reports authentication method as IAM Role

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `NoCredentialsError` | Instance profile attached? Role trust `ec2.amazonaws.com`? |
| `AccessDeniedException` | `TableArn` parameter correct? Policy attached to role? |
| `ResourceNotFoundException` | Table name/region (`eu-north-1`) match? |
| App URL not loading | Security group port 5000? UserData finished? `journalctl -u secure-employee-directory` |
| Bootstrap log | SSH in → `sudo cat /var/log/secure-employee-directory-bootstrap.log` |

## Security notes for the shared account

- Keep AWS access keys in a **local CLI profile** or CloudShell only
- Do not commit `.env`, keys, or account IDs into the repo
- After the demo, restrict `SSHLocation` to your IP or delete the stack
