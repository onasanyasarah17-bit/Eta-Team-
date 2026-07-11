# Demo Commands

Use these checks during the presentation to prove the app accesses DynamoDB securely via an IAM Role.

## 1. Health check

http://13.49.75.169:5000/health

Expected: `"authentication": "IAM Role"`, `"database": "connected"`, `"status": "healthy"`.

Talking point: the app reports IAM Role auth — no access keys configured.

## 2. App can read DynamoDB

- Browser: http://13.49.75.169:5000/
- API: http://13.49.75.169:5000/api/employees
- One employee: http://13.49.75.169:5000/api/employees/EMP001

Talking point: data comes from DynamoDB through the instance role.

## 3. No keys on the instance

From your laptop:

```powershell
ssh -i $env:USERPROFILE\.aws\secure-employee-directory-eu-north-1.pem ubuntu@13.49.75.169
```

On the EC2 instance:

```bash
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY
ls ~/.aws 2>/dev/null || echo "No ~/.aws credentials on instance"
```

Expected:

- Role name: `secure-employee-directory-ec2-role-secure-employee-directory-app`
- Empty access key env vars
- No `~/.aws` credentials directory

Talking point: credentials come from instance profile metadata, not env vars or `aws configure`.

## 4. Least privilege in IAM

AWS Console → IAM → Roles →  
`secure-employee-directory-ec2-role-secure-employee-directory-app`

Policy is scoped to:

`arn:aws:dynamodb:eu-north-1:806162193320:table/secure-employees`

Allowed actions only: `Scan`, `GetItem`, `DescribeTable`, `PutItem`, `BatchWriteItem` — not `*`.
