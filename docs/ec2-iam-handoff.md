# EC2, IAM & VPC - Secure Employee Directory

The EC2 instance and IAM Role for this project are provisioned via
CloudFormation using `infrastructure/ec2-iam.yaml`.

This merged template:

- Deploys into an **existing VPC / public subnet** (team approach)
- Creates a **least-privilege IAM role** scoped to one DynamoDB table ARN
- Bootstraps the Flask app automatically (clone → venv → Gunicorn → seed data)

The app authenticates with the **EC2 instance profile**. No access keys on the instance or in Git.

---

## Template Location

```text
infrastructure/ec2-iam.yaml
```

---

## What Gets Created

| Resource | Type | Purpose |
|----------|------|---------|
| `EmployeeDirectoryRole` | `AWS::IAM::Role` | DynamoDB access for EC2 |
| `EmployeeDirectoryInstanceProfile` | `AWS::IAM::InstanceProfile` | Lets EC2 assume the role |
| `AppSecurityGroup` | `AWS::EC2::SecurityGroup` | Ports 5000 (app) and 22 (SSH) |
| `AppInstance` | `AWS::EC2::Instance` | Ubuntu 22.04 running the Flask app |

---

## Parameters

| Parameter | Default | Required | Description |
|-----------|---------|----------|-------------|
| `Environment` | `production` | No | Environment tag |
| `DynamoDBTableArn` | — | **Yes** | Table ARN from DynamoDB stack / `describe-table` |
| `TableName` | `secure-employees` | No | Table name for app env + seed script |
| `AmiId` | Ubuntu 22.04 via SSM | No | AMI ID |
| `VpcId` | — | **Yes** | Existing VPC |
| `SubnetId` | — | **Yes** | Existing public subnet |
| `KeyPairName` | — | **Yes** | EC2 key pair |
| `SshCidr` | `0.0.0.0/0` | No | SSH allowed CIDR (prefer `YOUR_IP/32`) |
| `InstanceType` | `t3.micro` | No | Instance size (`t2.micro` is not available in `eu-north-1`) |
| `AppPort` | `5000` | No | App port |
| `GitRepoUrl` / `GitBranch` | team repo / `belinda-backend` | No | App source to clone |

---

## IAM Role (least privilege)

Scoped to the single `DynamoDBTableArn`:

| Action | Purpose |
|--------|---------|
| `dynamodb:Scan` | List employees |
| `dynamodb:GetItem` | Employee detail |
| `dynamodb:DescribeTable` | `/health` |
| `dynamodb:PutItem` | Seed script |
| `dynamodb:BatchWriteItem` | Seed script |

No `Resource: "*"`.

---

## Deployment

### Prerequisites

- DynamoDB table exists in `eu-north-1` (`secure-employees`)
- Existing VPC with a **public** subnet + Internet Gateway
- EC2 key pair in the same region
- AWS CLI / CloudShell credentials (local profile only — never commit keys)

### Step 1 — Table ARN

```bash
aws dynamodb describe-table \
  --table-name secure-employees \
  --region eu-north-1 \
  --query "Table.TableArn" \
  --output text
```

Or from the DynamoDB CloudFormation stack:

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory \
  --region eu-north-1 \
  --query "Stacks[0].Outputs[?OutputKey=='TableArn'].OutputValue" \
  --output text
```

### Step 2 — Deploy

```bash
aws cloudformation deploy \
  --template-file infrastructure/ec2-iam.yaml \
  --stack-name secure-employee-directory-app \
  --parameter-overrides \
    Environment=production \
    DynamoDBTableArn=PASTE_TABLE_ARN \
    VpcId=vpc-xxxxxxxx \
    SubnetId=subnet-xxxxxxxx \
    KeyPairName=YOUR_KEY_PAIR \
    SshCidr=0.0.0.0/0 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1
```

`CAPABILITY_NAMED_IAM` is required because the template creates named IAM resources.

### Step 3 — Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-app \
  --region eu-north-1 \
  --query "Stacks[0].Outputs" \
  --output table
```

Open `AppUrl` and `HealthUrl`. Allow 3–5 minutes after `CREATE_COMPLETE` for UserData.

---

## Verify

```bash
curl http://<InstancePublicIp>:5000/health
curl http://<InstancePublicIp>:5000/api/employees
```

`/health` should report `"authentication": "IAM Role"` and `"database": "connected"`.

Bootstrap log on the instance:

```bash
sudo cat /var/log/secure-employee-directory-bootstrap.log
sudo systemctl status secure-employee-directory
```

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| SSH fails | `SshCidr`, key pair region, SG port 22 |
| App URL fails | UserData finished? port 5000 open? `systemctl status` |
| `AccessDeniedException` | `DynamoDBTableArn` correct? |
| `ResourceNotFoundException` | Table name/region (`eu-north-1`) |
| No public IP | Subnet public + IGW route; template sets `AssociatePublicIpAddress` |

---

## Security notes

- Keep AWS access keys in a local CLI profile / CloudShell only
- Do not commit secrets
- After the demo, tighten `SshCidr` or delete the stack
