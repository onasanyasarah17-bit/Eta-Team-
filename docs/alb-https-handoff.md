# HTTPS via Application Load Balancer — Secure Employee Directory

HTTPS for this project is configured using an Application Load Balancer (ALB)
with an ACM SSL/TLS certificate, provisioned via CloudFormation using
`infrastructure/alb-https.yaml`.

The ALB terminates TLS on port 443 and forwards plain HTTP to the EC2 instance
on port 5000. Port 80 on the ALB permanently redirects to HTTPS (301) — the
EC2 instance never handles TLS.

The app was already built for this. `ProxyFix` is enabled in `app/__init__.py`
when `TRUST_PROXY=true`, restoring the real client IP and correct scheme from
`X-Forwarded-For` and `X-Forwarded-Proto` headers the ALB injects.
`ProductionConfig` sets `TRUST_PROXY=true` by default — do not disable it
when running behind the ALB. `/health/ready` is the health check endpoint the
ALB polls.

---

## Feature Summary

| Feature | Status |
|---------|--------|
| HTTP → HTTPS Redirect | ✅ |
| TLS 1.2 / TLS 1.3 | ✅ |
| ACM Certificate | ✅ |
| Automatic Certificate Renewal | ✅ |
| Application Load Balancer | ✅ |
| Health Checks (`/health/ready`) | ✅ |
| CloudFormation Managed | ✅ |
| Multi-AZ Load Balancer | ✅ |
| Secure EC2 Access via ALB Only | ✅ |
| External DNS via Namecheap CNAME | ✅ |

---

## Template Location

```
infrastructure/alb-https.yaml
```

---

## What Gets Created

| Resource | Type | Purpose |
|----------|------|---------|
| `AppCertificate` | `AWS::CertificateManager::Certificate` | ACM SSL/TLS cert for the domain |
| `AlbSecurityGroup` | `AWS::EC2::SecurityGroup` | Accepts ports 80 and 443 from the internet |
| `Ec2IngressFromAlb` | `AWS::EC2::SecurityGroupIngress` | Locks EC2 port 5000 to ALB traffic only |
| `AppLoadBalancer` | `AWS::ElasticLoadBalancingV2::LoadBalancer` | Internet-facing ALB across two AZs |
| `AppTargetGroup` | `AWS::ElasticLoadBalancingV2::TargetGroup` | Routes traffic to EC2 on port 5000 |
| `HttpsListener` | `AWS::ElasticLoadBalancingV2::Listener` | HTTPS on 443, TLS terminated with ACM cert |
| `HttpListener` | `AWS::ElasticLoadBalancingV2::Listener` | HTTP on 80, 301 redirect to HTTPS |

---

## Parameters

| Parameter | Default | Required | Description |
|-----------|---------|----------|-------------|
| `Environment` | `production` | No | Tags all resources |
| `VpcId` | — | **Yes** | VPC — must match the EC2/IAM stack |
| `PublicSubnet1Id` | — | **Yes** | First public subnet — ALB needs two AZs |
| `PublicSubnet2Id` | — | **Yes** | Second public subnet in a different AZ |
| `Ec2InstanceId` | — | **Yes** | From EC2/IAM stack `Outputs.InstanceId` |
| `Ec2SecurityGroupId` | — | **Yes** | From EC2/IAM stack `Outputs.SecurityGroupId` |
| `DomainName` | — | **Yes** | FQDN for the app (e.g. `employees.pcons.me`) |
| `AppPort` | `5000` | No | Flask listen port — must match EC2/IAM stack |

---

## How It Works

```
Browser
  │
  ├── HTTP :80  ──► ALB ──► 301 redirect to HTTPS
  │
  └── HTTPS :443 ─► ALB (TLS terminated with ACM cert)
                      │
                      ▼
              Target Group
              health check: GET /health/ready → HTTP 200
                      │
                      ▼
              EC2 Instance :5000 (Flask / Gunicorn)
              FLASK_ENV=production  TRUST_PROXY=true
                      │
                      ▼
                  DynamoDB (via IAM Instance Profile — no access keys)
```

After TLS termination the ALB adds these headers before forwarding to EC2:

| Header | Value |
|--------|-------|
| `X-Forwarded-For` | Real client IP |
| `X-Forwarded-Proto` | `https` |
| `X-Forwarded-Host` | Original `Host` header |

`ProxyFix` (configured in `app/__init__.py`) reads these and makes them
available as `request.remote_addr` and `request.scheme`. `ProductionConfig`
enables this automatically — `TRUST_PROXY` is `True` by default in production.

---

## Security Design

- **EC2 is not directly reachable on port 5000 from the internet** after this
  stack deploys. `Ec2IngressFromAlb` adds the ALB security group as the only
  allowed inbound source on the EC2 security group for the app port. The old
  `0.0.0.0/0` rule on port 5000 should be removed manually from the EC2 SG
  once the stack is deployed.
- **TLS policy** `ELBSecurityPolicy-TLS13-1-2-2021-06` — TLS 1.2 minimum,
  TLS 1.3 preferred. SSLv3, TLS 1.0, and TLS 1.1 are not accepted.
- **HTTP → HTTPS redirect** is a 301 — browsers cache it permanently.
- **ACM certificates are free** and auto-renew before expiry. No manual
  certificate rotation required.
- **Name collision prevention** — ALB and target group names use
  `!Sub "${AWS::StackName}-alb"` and `!Sub "${AWS::StackName}-tg"` so
  multiple stacks (e.g. staging and production) can coexist without conflicts.

---

## Stack Deployment Order

```
1. infrastructure/dynamodb.yaml   →  stack: secure-employee-directory
2. infrastructure/ec2-iam.yaml    →  stack: secure-employee-directory-app
3. infrastructure/alb-https.yaml  →  stack: secure-employee-directory-alb
```

DNS is managed directly in Namecheap — no Route 53 stack needed.
See Step 6 below for the CNAME record to add.

Each stack depends on outputs from the one before it. Do not deploy the ALB
stack before the EC2/IAM stack is in `CREATE_COMPLETE`.

---

## Deployment

### Prerequisites

1. **EC2/IAM stack must already be deployed** and in `CREATE_COMPLETE`.
   You need `InstanceId` and `SecurityGroupId` from its outputs.
2. **You must own a domain.** ACM validates via a DNS CNAME — you need access
   to your DNS provider (Route 53, Cloudflare, Namecheap, etc.).
3. **The VPC must have two public subnets in different AZs.** If you only have
   one, create a second in a different AZ inside the same VPC first.
4. **AWS CLI or CloudShell open in `eu-north-1`** with the repo checked out.

---

### Step 1 — Get EC2/IAM stack outputs

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-app \
  --region eu-north-1 \
  --query "Stacks[0].Outputs" \
  --output table
```

Note `InstanceId` and `SecurityGroupId`.

---

### Step 2 — Get VPC and public subnet IDs

```bash
# Default VPC
aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region eu-north-1

# All subnets in that VPC — pick two with different AZs
aws ec2 describe-subnets \
  --filters Name=vpc-id,Values=<VpcId> \
  --query "Subnets[*].[SubnetId,AvailabilityZone,MapPublicIpOnLaunch]" \
  --output table \
  --region eu-north-1
```

Pick two subnets where `MapPublicIpOnLaunch` is `True` and the AZ values differ
(e.g. `eu-north-1a` and `eu-north-1b`).

---

### Step 3 — Deploy the stack

```bash
aws cloudformation deploy \
  --template-file infrastructure/alb-https.yaml \
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

No `--capabilities` flag is needed — this stack creates no IAM resources.

The stack will pause at `CREATE_IN_PROGRESS` on `AppCertificate`. This is
expected. Proceed to Step 4 while it waits.

---

### Step 4 — Complete ACM DNS validation

While the stack is waiting:

1. Open **AWS Console → Certificate Manager → Certificates**
2. Click the certificate for your domain
3. Under **Domains**, expand the domain row — you will see a **CNAME name**
   and a **CNAME value**
4. Add that CNAME to your DNS provider

Propagation times:

- **Route 53** — typically 2–5 minutes
- **Cloudflare** — typically 5–10 minutes
- **Other providers** — up to 30 minutes

Once ACM validates the certificate, the stack continues to completion.

---

### Step 5 — Get the ALB DNS name

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-alb \
  --region eu-north-1 \
  --query "Stacks[0].Outputs" \
  --output table
```

Note `AlbDnsName` — it looks like:

```
secure-employee-directory-alb-123456789.eu-north-1.elb.amazonaws.com
```

---

### Step 6 — Add a CNAME record in Namecheap

1. Log into Namecheap → **Domain List** → click **Manage** next to `pcons.me`
2. Go to **Advanced DNS**
3. Add a new record:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| CNAME | `employees` | `<AlbDnsName>` | Automatic |

Replace `<AlbDnsName>` with the value from Step 5.
Namecheap typically propagates within 1–5 minutes.

---

### Step 7 — Remove the old EC2 port 5000 inbound rule

After the ALB stack deploys, the EC2 security group has two inbound rules for
port 5000: the original `0.0.0.0/0` rule and the new ALB-only rule added by
`Ec2IngressFromAlb`. Remove the old one to fully lock down direct access:

```bash
aws ec2 revoke-security-group-ingress \
  --group-id <SecurityGroupId> \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0 \
  --region eu-north-1
```

---

### Step 8 — Verify

```bash
# HTTPS — should return 200 and the health payload
curl https://employees.pcons.me/health/ready

# HTTP — should return 301 redirect to HTTPS
curl -I http://employees.pcons.me
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

Expected HTTP redirect headers:

```
HTTP/1.1 301 Moved Permanently
Location: https://employees.pcons.me/
```

---

## Outputs

| Output Key | Description |
|------------|-------------|
| `AlbDnsName` | ALB DNS name — point your domain CNAME here |
| `AlbHostedZoneId` | Used for Route 53 alias A records |
| `AlbArn` | ALB ARN |
| `TargetGroupArn` | Target group ARN |
| `CertificateArn` | ACM certificate ARN |
| `HttpsUrl` | Final HTTPS URL for the app |
| `AlbSecurityGroupId` | ALB security group ID |

---

## Troubleshooting

| Symptom | What to check |
|---------|---------------|
| Stack stuck on `AppCertificate` | DNS CNAME not added yet — check ACM Console → Certificates |
| `Target.FailedHealthChecks` | EC2 UserData still running — wait 3–5 min after `CREATE_COMPLETE`, then check `systemctl status secure-employee-directory` |
| `ERR_SSL_PROTOCOL_ERROR` | ACM certificate not yet validated — check ACM Console |
| `curl https://...` connection refused | DNS not propagated — test with the ALB DNS directly: `curl https://<AlbDnsName>` |
| `502 Bad Gateway` | Flask not running on EC2 — SSH in and run `systemctl status secure-employee-directory` and `sudo cat /var/log/secure-employee-directory-bootstrap.log` |
| EC2 port 5000 still reachable directly | Old `0.0.0.0/0` inbound rule not removed yet — see Step 7 |
| `request.scheme` returns `http` over HTTPS | `TRUST_PROXY` is not `true` — check `FLASK_ENV=production` is set in the systemd service |

---

## Notes

- ACM certificates in `eu-north-1` are **regional**. If you add CloudFront
  later, you will need a **second certificate in `us-east-1`** — CloudFront
  only accepts certs from `us-east-1`.
- The ALB health check uses `/health/ready`. This returns `503` when DynamoDB
  is unreachable, which correctly pulls the instance out of rotation. Use
  `/health/live` for a process-only liveness probe.
- `TRUST_PROXY=true` is set by `ProductionConfig` automatically. Do not
  disable it when running behind the ALB.
- ALB and target group names use `!Sub "${AWS::StackName}-alb"` /
  `!Sub "${AWS::StackName}-tg"` — deploying a second stack (e.g.
  `secure-employee-directory-alb-staging`) will not collide with the
  production stack.
- The `Ec2IngressFromAlb` resource **adds** an ingress rule to the existing
  EC2 security group. It does not remove the old `0.0.0.0/0` rule — that must
  be done manually (Step 7).
