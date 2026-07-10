# EC2, IAM & VPC - Secure Employee Directory

The EC2 instance and IAM Role for this project are provisioned via
CloudFormation using the template at `infrastructure/ec2-iam.yaml`. This document
covers the template structure, parameters, deployment steps, outputs, and how
everything connects to the DynamoDB table.

---

## Template Location

```
infrastructure/ec2-iam.yaml
```

---

## What Gets Created

The template provisions compute and IAM resources in one deployment, using an **existing VPC**:

| Resource                           | Type                           | Purpose                                           |
|------------------------------------|--------------------------------|---------------------------------------------------|
| `EmployeeDirectoryRole`            | `AWS::IAM::Role`               | Grants EC2 access to the DynamoDB table           |
| `EmployeeDirectoryInstanceProfile` | `AWS::IAM::InstanceProfile`    | Wraps the Role so EC2 can assume it               |
| `AppSecurityGroup`                 | `AWS::EC2::SecurityGroup`      | Allows inbound on port 5000 only, no SSH          |
| `AppInstance`                      | `AWS::EC2::Instance`           | Ubuntu 22.04 t2.micro running the Flask app       |

---

## Parameters

| Parameter          | Default        | Required | Description                                                  |
|--------------------|----------------|----------|--------------------------------------------------------------|
| `Environment`      | `production`   | No       | Tags all resources with the deployment environment           |
| `DynamoDBTableArn` | -              | **Yes**  | ARN of the `secure-employees` table from the DynamoDB stack  |
| `AmiId`            | Auto-resolved  | No       | Ubuntu 22.04 AMI ‚Äî pulled automatically from SSM            |
| `VpcId`            | -              | **Yes**  | Existing VPC ID to deploy the instance into                  |
| `SubnetId`         | -              | **Yes**  | Existing public subnet ID in the VPC                         |
| `KeyPairName`      | -              | **Yes**  | EC2 Key Pair name for SSH access                             |
| `SshCidr`          | `0.0.0.0/0`    | No       | CIDR range allowed to SSH (recommend restricting to an IP) |


Only `DynamoDBTableArn`, `VpcId`, `SubnetId`, and `KeyPairName` are required.

---

## Network Architecture

Existing VPC (provided as parameter)
- Existing Public Subnet (provided as parameter)
- EC2 Instance (Ubuntu 22.04, t2.micro)
- Security Group (port 5000 inbound, port 22 inbound)

The instance is deployed in an existing public subnet with a public IP assigned automatically.
All outbound traffic routes through the existing Internet Gateway (must exist in the VPC).
Required for boto3 to reach the DynamoDB API endpoint and for manual package installations.

---

## IAM Role & Policy

The IAM Role uses least privilege — scoped exclusively to the `secure-employees`
DynamoDB table ARN. The instance cannot access any other AWS resource.

**Runtime permissions (Flask app — used on every request):**

| Action                   | Purpose                                       |
|--------------------------|-----------------------------------------------|
| `dynamodb:Scan`          | Fetch all employees for the directory listing  |
| `dynamodb:GetItem`       | Fetch a single employee by `employeeId`        |
| `dynamodb:DescribeTable` | Health check — confirms table is reachable    |

**Seed permissions (`populate_table.py` — runs once at first boot):**

| Action                    | Purpose                               |
|---------------------------|---------------------------------------|
| `dynamodb:PutItem`        | Write a single employee record        |
| `dynamodb:BatchWriteItem` | Write multiple employee records at once|

The Role is attached via an **Instance Profile** — boto3 retrieves temporary
credentials automatically from the instance metadata endpoint at boot.
No access keys are stored anywhere on the instance.

---

## Security Group

| Rule     | Protocol | Port | Source    | Reason                          |
|----------|----------|------|-----------|---------------------------------|
| Inbound  | TCP      | 5000 | 0.0.0.0/0   | Flask app access                |
| Inbound  | TCP      | 22   | !Ref SshCidr| SSH access (restricted)         |
| Outbound | All      | All  | 0.0.0.0/0   | Package installs, AWS API calls |


---

## Deployment

### Prerequisites
- DynamoDB stack already deployed (`secure-employee-directory` stack)
- Existing VPC with a public subnet and Internet Gateway
- EC2 Key Pair created in the same region
- CloudShell open in the AWS Console (or local AWS CLI configured)
- `ec2-iam.yaml` uploaded to CloudShell via **Actions**

### Step 1 — Retrieve the DynamoDB table ARN

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory \
  --query "Stacks[0].Outputs[?OutputKey=='TableArn'].OutputValue" \
  --output text \
  --region eu-north-1
```

Copy the ARN value for the next step.

### Step 2 — Deploy the stack

```bash
aws cloudformation deploy \
  --template-file ec2-iam.yaml \
  --stack-name secure-employee-directory-app \
  --parameter-overrides \
      Environment=production \
      DynamoDBTableArn=<paste TableArn here> \
      VpcId=<your-vpc-id> \
      SubnetId=<your-public-subnet-id> \
      KeyPairName=<your-keypair-name> \
      SshCidr=<your-ip-address>/32 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1
```

> **Note:** `--capabilities CAPABILITY_NAMED_IAM` is required because the template
> creates a named IAM Role. CloudFormation requires explicit acknowledgement
> before creating IAM resources.

The stack creates only the EC2 instance, IAM role, and security group.
No VPC networking resources are created.

---

## Application Deployment
- Follows the README.md in the repo

## Outputs

After a successful deployment the stack exposes seven outputs:

| Output Key       | Description                                       |
|------------------|---------------------------------------------------|
| `VpcId`          | ID of the created VPC                             |
| `PublicSubnetId` | ID of the public subnet                           |
| `InstanceId`     | EC2 instance ID                                   |
| `InstancePublicIp`       | Public IP address of the instance         |
| `InstancePublicDns`|    Public DNS of the instance (for SSH)        |
| `AppUrl`         | Direct URL to the Flask app                       |
| `SecurityGroupId`| ID of the security group                          |
| `IamRoleArn`     | ARN of the IAM Role attached to the instance      |

### Retrieve outputs after deployment

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-app \
  --query "Stacks[0].Outputs" \
  --output table \
  --region eu-north-1
```

---

## Verifying the Deployment

Once the stack is deployed, verify:

```bash
curl http://<InstancePublicIp>:5000/health
```


Confirm the employee data was seeded:

```bash
curl http://<InstancePublicIp>:5000/api/employees
```

---

## Troubleshooting
### SSH Connection Issues
- Verify the SshCidr parameter includes your IP address

- Confirm the Key Pair exists in the same region

- Check that the security group allows inbound SSH (port 22)

### Application Not Accessible
- Flask app must be running on port 5000

- Check application logs

- Verify the IAM Role has correct permissions to DynamoDB

### DynamoDB Access Issues
- Confirm DynamoDBTableArn is correct

- Check the IAM Role policy in the AWS Console


