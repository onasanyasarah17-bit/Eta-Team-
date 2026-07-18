# Full Deployment Guide — Secure Employee Directory

This guide walks through deploying the complete project from scratch on AWS —
from prerequisites to a live HTTPS endpoint at `https://employees.pcons.me`.

Follow the steps in order. Each stack depends on outputs from the one before it.

```
1. infrastructure/dynamodb.yaml   →  secure-employee-directory
2. infrastructure/ec2-iam.yaml    →  secure-employee-directory-app
3. infrastructure/alb-https.yaml  →  secure-employee-directory-alb
     + ACM validation via Namecheap
     + CNAME record in Namecheap
```

Individual stack reference docs are in `docs/` if you need deeper detail on
any one component.

---

## Prerequisites

### 1. AWS account access

You need an IAM user or role with permissions to create:

- CloudFormation stacks
- DynamoDB tables
- EC2 instances, security groups, key pairs
- IAM roles and instance profiles
- ACM certificates
- Elastic Load Balancers and target groups

The simplest approach for a demo/sprint is to use **AWS CloudShell** — it runs
in the browser inside the AWS Console and already has the AWS CLI configured
with your session credentials. No local setup needed.

Open CloudShell: **AWS Console → top navigation bar → CloudShell icon (>_)**

Make sure you are in region **eu-north-1 (Stockholm)**. Check the region
selector in the top-right of the Console and switch if needed.

---

### 2. EC2 key pair

You need a key pair to SSH into the EC2 instance if you need to debug.

**Create one if you don't have one:**

1. AWS Console → **EC2 → Key Pairs → Create key pair**
2. Name: `secure-employee-directory-key` (or anything you'll remember)
3. Type: RSA, format: `.pem`
4. Download and save the `.pem` file — AWS only gives it to you once

Note the key pair name — you will pass it as a parameter when deploying the
EC2 stack.

---

### 3. VPC and public subnets

The EC2 instance deploys into an existing VPC. Your AWS account has a **default
VPC** in every region — you can use it.

The ALB needs **two public subnets in different Availability Zones**. The
default VPC has one subnet per AZ, all public, so this is already satisfied.

You will collect the IDs in Stack 2 below.

---

### 4. Namecheap access

You will need to log into Namecheap twice during this deployment:

- Once to add an **ACM validation CNAME** (proves you own `pcons.me`)
- Once to add a **CNAME record** pointing `employees.pcons.me` at the ALB

Have your Namecheap credentials ready.

---

## Stack 1 — DynamoDB

**Creates:** the `secure-employees` table.

### Upload the template

In CloudShell, clone the repo or upload `infrastructure/dynamodb.yaml`
directly using the **Actions → Upload file** button in the CloudShell toolbar.

### Deploy

```bash
aws cloudformation deploy \
  --template-file dynamodb.yaml \
  --stack-name secure-employee-directory \
  --parameter-overrides Environment=production \
  --region eu-north-1
```

Wait for `Successfully created/updated stack`. Takes about 30 seconds.

### Get the table ARN

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory \
  --region eu-north-1 \
  --query "Stacks[0].Outputs[?OutputKey=='TableArn'].OutputValue" \
  --output text
```

Copy the ARN — it looks like:

```
arn:aws:dynamodb:eu-north-1:123456789012:table/secure-employees
```

You will paste this into the next stack's parameters.

---

## Stack 2 — EC2 + IAM

**Creates:** the EC2 instance, IAM role, and security group. The instance
bootstraps the Flask app automatically on first boot.

### Collect required values

**Table ARN** — from Stack 1 above.

**VPC ID:**

```bash
aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region eu-north-1
```

**Public subnet ID** — pick any one subnet from the default VPC:

```bash
aws ec2 describe-subnets \
  --filters Name=vpc-id,Values=<VpcId> \
  --query "Subnets[*].[SubnetId,AvailabilityZone,MapPublicIpOnLaunch]" \
  --output table \
  --region eu-north-1
```

Pick any subnet where `MapPublicIpOnLaunch` is `True`. Note the `SubnetId`.

### Deploy

```bash
aws cloudformation deploy \
  --template-file ec2-iam.yaml \
  --stack-name secure-employee-directory-app \
  --parameter-overrides \
    Environment=production \
    DynamoDBTableArn=<TableArn> \
    VpcId=<VpcId> \
    SubnetId=<SubnetId> \
    KeyPairName=<YourKeyPairName> \
    SshCidr=0.0.0.0/0 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1
```

`--capabilities CAPABILITY_NAMED_IAM` is required because this stack creates
named IAM resources.

This takes 3–5 minutes. CloudFormation provisions the instance and UserData
runs in the background after the stack completes.

### What happens automatically after CREATE_COMPLETE

You do not need to manually install anything, start the app, or populate the
table. The EC2 instance runs a bootstrap script (UserData) on first boot that
does all of this for you:

1. Clones the project repo from GitHub
2. Creates a Python virtualenv and installs all dependencies from `requirements.txt`
3. Writes the systemd service file and starts the Flask app via Gunicorn on port 5000
4. Runs `scripts/populate_table.py` to seed the DynamoDB table with sample employee data

This all happens in the background after CloudFormation marks the stack
`CREATE_COMPLETE`. It takes 3–5 minutes. You can monitor progress by SSHing
into the instance and tailing the bootstrap log:

```bash
ssh -i your-key.pem ubuntu@<InstancePublicIp>
sudo tail -f /var/log/secure-employee-directory-bootstrap.log
```

Once you see the app start line in the log, or once `/health/ready` returns
200, the instance is fully ready.

### Wait for the app to start

The stack reaching `CREATE_COMPLETE` does not mean the app is ready —
UserData (git clone → pip install → systemd start → table seed) runs after
CloudFormation finishes. Wait 3–5 minutes, then verify:

```bash
# Get the public IP
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-app \
  --region eu-north-1 \
  --query "Stacks[0].Outputs[?OutputKey=='InstancePublicIp'].OutputValue" \
  --output text
```

```bash
curl http://<InstancePublicIp>:5000/health/ready
```

Expected response:

```json
{
  "status": "healthy",
  "database": "connected",
  "authentication": "IAM Role",
  "table": "secure-employees",
  "region": "eu-north-1"
}
```

If the app is not up yet, SSH in and check the bootstrap log:

```bash
ssh -i your-key.pem ubuntu@<InstancePublicIp>
sudo cat /var/log/secure-employee-directory-bootstrap.log
sudo systemctl status secure-employee-directory
```

### Get the outputs you need for Stack 3

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-app \
  --region eu-north-1 \
  --query "Stacks[0].Outputs" \
  --output table
```

Note `InstanceId` and `SecurityGroupId`.

---

## Stack 3 — ALB + HTTPS

**Creates:** the Application Load Balancer, ACM certificate, HTTPS listener,
and HTTP → HTTPS redirect. This is where `employees.pcons.me` gets its
SSL/TLS certificate.

### Collect required values

**Two public subnets in different AZs** — the ALB requires multi-AZ placement.

```bash
aws ec2 describe-subnets \
  --filters Name=vpc-id,Values=<VpcId> \
  --query "Subnets[*].[SubnetId,AvailabilityZone,MapPublicIpOnLaunch]" \
  --output table \
  --region eu-north-1
```

Pick **two** subnets where `MapPublicIpOnLaunch` is `True` and the AZ values
differ — e.g. one in `eu-north-1a` and one in `eu-north-1b`.

### Deploy

```bash
aws cloudformation deploy \
  --template-file alb-https.yaml \
  --stack-name secure-employee-directory-alb \
  --parameter-overrides \
    Environment=production \
    VpcId=<VpcId> \
    PublicSubnet1Id=<SubnetId-AZ1> \
    PublicSubnet2Id=<SubnetId-AZ2> \
    Ec2InstanceId=<InstanceId> \
    Ec2SecurityGroupId=<SecurityGroupId> \
    DomainName=employees.pcons.me \
  --region eu-north-1
```

The stack will immediately pause at `CREATE_IN_PROGRESS` on `AppCertificate`.
**This is expected** — do not cancel it. Proceed to the ACM validation step
below while it waits.

---

## ACM Certificate Validation (Namecheap)

ACM needs to verify you own `pcons.me` before it issues the certificate. It
does this by checking for a specific CNAME record in your DNS.

### Step 1 — Get the validation CNAME from ACM

1. Open **AWS Console → Certificate Manager**
2. You will see a certificate for `employees.pcons.me` with status **Pending validation**
3. Click it
4. Under **Domains**, expand the `employees.pcons.me` row
5. Copy the **CNAME name** and **CNAME value** — they look like:

```
Name:  _abc123def456.employees.pcons.me
Value: _xyz789.acm-validations.aws
```

### Step 2 — Add the CNAME in Namecheap

1. Log into **Namecheap → Domain List → Manage** next to `pcons.me`
2. Go to **Advanced DNS**
3. Click **Add New Record**
4. Add:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| CNAME | `_abc123def456.employees` | `_xyz789.acm-validations.aws` | Automatic |

> **Important:** Namecheap automatically appends `.pcons.me` to the Host
> field. So if the full CNAME name from ACM is
> `_abc123def456.employees.pcons.me`, enter only
> `_abc123def456.employees` in the Host field.
> Remove any trailing dot from the Value field if present.

5. Save the record

### Step 3 — Wait for validation

ACM polls for the CNAME record. With Namecheap, propagation typically takes
**2–10 minutes**.

You can watch the certificate status in the ACM Console — it changes from
**Pending validation** to **Issued**. Once issued, the CloudFormation stack
automatically continues and completes.

---

## Add the App CNAME in Namecheap

Once the stack is in `CREATE_COMPLETE`, get the ALB DNS name:

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-alb \
  --region eu-north-1 \
  --query "Stacks[0].Outputs[?OutputKey=='AlbDnsName'].OutputValue" \
  --output text
```

It looks like:

```
secure-employee-directory-alb-123456789.eu-north-1.elb.amazonaws.com
```

Back in **Namecheap → Advanced DNS**, add a second record:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| CNAME | `employees` | `<AlbDnsName>` | Automatic |

Wait 1–5 minutes for propagation.

---

## Lock Down EC2 Direct Access

The ALB stack added the ALB security group as an inbound source on port 5000,
but the original `0.0.0.0/0` rule is still there. Remove it:

```bash
aws ec2 revoke-security-group-ingress \
  --group-id <SecurityGroupId> \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0 \
  --region eu-north-1
```

After this, port 5000 is only reachable from the ALB. Direct EC2 IP access
on port 5000 will be refused.

---

## Verify the Full Stack

```bash
# HTTPS — full end-to-end
curl https://employees.pcons.me/health/ready

# HTTP — should 301 redirect to HTTPS
curl -I http://employees.pcons.me

# API
curl https://employees.pcons.me/api/employees
```

Expected `/health/ready` response:

```json
{
  "status": "healthy",
  "database": "connected",
  "authentication": "IAM Role",
  "table": "secure-employees",
  "region": "eu-north-1"
}
```

Open `https://employees.pcons.me` in the browser — you should see the
employee directory with a valid padlock.

---

## Troubleshooting

| Symptom | What to check |
|---------|---------------|
| Stack 1 fails | IAM permissions — need `cloudformation:*` and `dynamodb:CreateTable` |
| Stack 2 fails on IAM resource | `--capabilities CAPABILITY_NAMED_IAM` missing |
| Stack 2 `CREATE_COMPLETE` but app not responding | UserData still running — wait 3–5 min, then SSH and check bootstrap log |
| Stack 3 stuck on `AppCertificate` | ACM CNAME not added in Namecheap yet, or not propagated yet |
| ACM status stuck at **Pending validation** | Check CNAME host field — Namecheap auto-appends `.pcons.me`, don't include it manually |
| `curl https://employees.pcons.me` fails | DNS CNAME not propagated — test directly: `curl https://<AlbDnsName>` |
| `Target.FailedHealthChecks` in target group | Flask not running — SSH in, check `systemctl status secure-employee-directory` |
| `502 Bad Gateway` | Flask crashed — check `sudo cat /var/log/secure-employee-directory-bootstrap.log` |
| `ERR_CERT_AUTHORITY_INVALID` | ACM cert not yet issued — check ACM Console |
| Port 5000 still open after lockdown | Run the `revoke-security-group-ingress` command from the Lock Down section |

---

## Tear Down

Delete stacks in reverse order to avoid dependency errors:

```bash
aws cloudformation delete-stack \
  --stack-name secure-employee-directory-alb \
  --region eu-north-1

# Wait for the above to finish, then:
aws cloudformation delete-stack \
  --stack-name secure-employee-directory-app \
  --region eu-north-1

# Wait, then:
aws cloudformation delete-stack \
  --stack-name secure-employee-directory \
  --region eu-north-1
```

Also remove the two CNAME records from Namecheap (the ACM validation record
and the `employees` app record) — they are not managed by CloudFormation.
