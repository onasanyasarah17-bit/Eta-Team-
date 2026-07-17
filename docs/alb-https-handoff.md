# HTTPS via Application Load Balancer — Secure Employee Directory

HTTPS for this project is configured using an Application Load Balancer (ALB)
with an ACM SSL/TLS certificate, provisioned via CloudFormation using
`infrastructure/alb-https.yaml`.

The ALB terminates TLS on port 443 and forwards plain HTTP to the EC2 instance
on port 5000. Port 80 on the ALB immediately redirects to HTTPS with a 301 —
the EC2 instance never handles TLS directly.

The Flask app was already built for this setup. `ProxyFix` is enabled when
`TRUST_PROXY=true`, which restores the real client IP and correct scheme from
the `X-Forwarded-For` and `X-Forwarded-Proto` headers the ALB injects.
`/health/ready` is the health check endpoint the ALB polls.

---

## Template Location

```
infrastructure/alb-https.yaml
```

---

## What Gets Created

| Resource | Type | Purpose |
|----------|------|---------|
| `AppCertificate` | `AWS::CertificateManager::Certificate` | ACM SSL/TLS cert for the domain — auto-validated via Route 53 |
| `AlbSecurityGroup` | `AWS::EC2::SecurityGroup` | Accepts port 80 and 443 from anywhere |
| `Ec2IngressFromAlb` | `AWS::EC2::SecurityGroupIngress` | Locks EC2 port 5000 to ALB traffic only |
| `AppLoadBalancer` | `AWS::ElasticLoadBalancingV2::LoadBalancer` | Internet-facing ALB across two AZs |
| `AppTargetGroup` | `AWS::ElasticLoadBalancingV2::TargetGroup` | Routes traffic to EC2 on port 5000 |
| `HttpsListener` | `AWS::ElasticLoadBalancingV2::Listener` | HTTPS on 443, TLS terminated with ACM cert |
| `HttpListener` | `AWS::ElasticLoadBalancingV2::Listener` | HTTP on 80, 301 redirect to HTTPS |
| `AppAliasRecord` | `AWS::Route53::RecordSet` | (Optional) A record alias pointing domain to ALB |

---

## Parameters

| Parameter | Default | Required | Description |
|-----------|---------|----------|-------------|
| `Environment` | `production` | No | Tags all resources |
| `VpcId` | — | **Yes** | VPC — must match the EC2/IAM stack |
| `PublicSubnet1Id` | — | **Yes** | First public subnet — ALB needs two AZs |
| `PublicSubnet2Id` | — | **Yes** | Second public subnet in a different AZ |
| `Ec2InstanceId` | — | **Yes** | EC2 instance ID from the EC2/IAM stack outputs |
| `Ec2SecurityGroupId` | — | **Yes** | EC2 security group ID — ALB SG added as inbound source |
| `DomainName` | — | **Yes** | FQDN for the app (e.g. `employees.yourdomain.com`) |
| `HostedZoneId` | — | **Yes** | Route 53 hosted zone ID for automated DNS validation |
| `AppPort` | `5000` | No | Flask listen port — must match EC2/IAM stack |
| `CreateAliasRecord` | `"true"` | No | Whether to create a Route 53 alias record for the domain |

---

## How It Works

1. Deploy stack - ACM creates certificate with DomainValidationOptions referencing HostedZoneId

2. CloudFormation waits for DNS validation (automatic via Route 53)

3. ACM creates validation CNAME in Route 53

4. ACM validates certificate

5. Stack continues - ALB created with valid certificate

6. Route 53 alias record created pointing to ALB

**Key Benefits:**
- **Zero manual steps** — no need to add CNAME records manually
- **Automatic renewal** — ACM auto-renews certificates
- **Seamless deployment** — stack pauses and resumes automatically
- **Clean rollback** — validation records are cleaned up on deletion
- **Faster deployment** — DNS validation typically completes in 2-5 minutes

---

## Security Design

- **EC2 is not directly reachable on port 5000 from the internet** after this
  stack deploys. The `Ec2IngressFromAlb` resource adds the ALB security group
  as the only allowed source on the EC2 security group — replacing the open
  `0.0.0.0/0` rule that was there before.
- **TLS policy** is set to `ELBSecurityPolicy-TLS13-1-2-2021-06` — enforces
  TLS 1.2 minimum and prefers TLS 1.3. SSLv3, TLS 1.0, and TLS 1.1 are blocked.
- **HTTP to HTTPS redirect** uses a 301 — browsers cache it and will not retry HTTP.
- **ACM certificates are free** and auto-renew before expiry. No manual cert rotation.
- ACM certificates are free and auto-renew before expiry. No manual cert rotation.
- Route 53 integration ensures DNS validation is secure and automated.

---

## Stack Deployment Order (full infrastructure)

```
1. infrastructure/dynamodb.yaml   -  stack: secure-employee-directory
2. infrastructure/ec2-iam.yaml    -  stack: secure-employee-directory-app
3. infrastructure/alb-https.yaml  -  stack: secure-employee-directory-alb
```

Each stack depends on outputs from the one before it.

---

## Deployment

### Prerequisites

Before deploying this stack:

1. **The EC2/IAM stack must already be deployed** — you need the instance ID
   and security group ID from its outputs.
2. **You must have a domain in Route 53** — the hosted zone ID is required for
   automated certificate validation. The domain's NS records must point to
   Route 53's name servers.
3. **The VPC must have two public subnets in different AZs** — the ALB requires
   multi-AZ placement. If you only have one public subnet, create a second one
   in a different AZ inside the same VPC before proceeding.
4. **AWS CLI / CloudShell open in `eu-north-1`** with `alb-https.yaml` available.

---

### Step 1 — Get EC2/IAM stack outputs

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-app \
  --query "Stacks[0].Outputs[?OutputKey=='InstanceId' || OutputKey=='SecurityGroupId'].[OutputKey,OutputValue]" \
  --output table \
  --region eu-north-1
```

Note down the values for `InstanceId` and `SecurityGroupId`.

---

### Step 2 — Get your VPC and public subnet IDs

```bash
# Default VPC ID
aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region eu-north-1

# All subnets in that VPC — pick two from different AZs
aws ec2 describe-subnets \
  --filters Name=vpc-id,Values=<VpcId> \
  --query "Subnets[*].[SubnetId,AvailabilityZone,MapPublicIpOnLaunch]" \
  --output table \
  --region eu-north-1
```

Pick two subnets where `MapPublicIpOnLaunch` is `True` and the AZ values differ
(e.g. `eu-north-1a` and `eu-north-1b`).

---

### Step 3 — Get your Route 53 Hosted Zone ID

```bash
# List all hosted zones
aws route53 list-hosted-zones \
  --query "HostedZones[*].[Name,Id]" \
  --output table \
  --region eu-north-1

# Or get specific zone ID (replace with your domain)
aws route53 list-hosted-zones \
  --query "HostedZones[?Name=='yourdomain.com.'].Id" \
  --output text \
  --region eu-north-1
```

The hosted zone ID will look like: /hostedzone/ZXXXXXXXXXXXXX

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
      DomainName=employees.yourdomain.com \
      HostedZoneId=<HostedZoneId> \
      CreateAliasRecord=true \
  --region eu-north-1
```
What happens next:

- The stack creates the ACM certificate
- CloudFormation automatically adds validation CNAME records to Route 53
- ACM validates the certificate (typically 2-5 minutes)
- The stack continues and creates all remaining resources
- An alias record is created pointing your domain to the ALB
- The stack will pause at CREATE_IN_PROGRESS on the AppCertificate resource (this is expected and automatic. No manual intervention is needed)

---


### Step 5 - Monitor deployment progress (optional)

You can watch the progress in the AWS Console or via CLI:

```bash
# Monitor stack events
aws cloudformation describe-stack-events \
  --stack-name secure-employee-directory-alb \
  --region eu-north-1 \
  --query "StackEvents[*].[ResourceStatus,ResourceType,LogicalResourceId,ResourceStatusReason]" \
  --output table

# Check certificate validation status (if you have the ARN)
aws acm describe-certificate \
  --certificate-arn <certificate-arn-from-stack> \
  --region eu-north-1 \
  --query "Certificate.DomainValidationOptions[0].ValidationStatus"
```
---

### Step 6 — Verify the deployment

After the stack reaches `CREATE_COMPLETE`:

```bash
# Get the ALB DNS name
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-alb \
  --query "Stacks[0].Outputs[?OutputKey=='AlbDnsName' || OutputKey=='HttpsUrl'].[OutputKey,OutputValue]" \
  --output table \
  --region eu-north-1

# Test HTTPS — should return 200 and the health payload
curl https://employees.yourdomain.com/health/ready

# Test HTTP — should return 301 redirect to HTTPS
curl -I http://employees.yourdomain.com
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

Expected HTTP redirect response headers:
```text
HTTP/1.1 301 Moved Permanently
Location: https://employees.yourdomain.com/
```

---

## Advanced Configuration
### Disable Alias Record Creation
If you want to manage DNS records yourself (e.g., for split DNS or multi-region):

```bash
aws cloudformation deploy \
  --template-file infrastructure/alb-https.yaml \
  --stack-name secure-employee-directory-alb \
  --parameter-overrides \
      ...other parameters... \
      CreateAliasRecord=false \
  --region eu-north-1
```

Then manually create a CNAME or alias record pointing to the ALB DNS name.

## Use with External DNS Providers (Non-Route 53)
If you're using Cloudflare, Namecheap, GoDaddy, etc.:

- You must manually handle DNS validation — ACM won't auto-validate
- Deploy with CreateAliasRecord=false
- The stack will pause at certificate creation
- Go to ACM Console and get the CNAME name and value
- Add the CNAME record in your DNS provider
- Wait for validation (up to 30 minutes)
- Stack will continue
- Create a CNAME record pointing your domain to the ALB DNS name

**Note:** This approach requires manual steps and hence we would prefer Route 53 which is recommended.

## Multi-Region Deployment
For multi-region deployments:

- Deploy the ALB stack in each region with CreateAliasRecord=false
- Use Route 53 routing policies (weighted, latency-based, or geolocation)
- Create health checks for each ALB
- Configure Route 53 records with failover or weighted routing

Example for two regions:

```bash
# Region 1 (Primary)
aws cloudformation deploy ... --region eu-north-1 \
  --parameter-overrides CreateAliasRecord=false ...

# Region 2 (Secondary)
aws cloudformation deploy ... --region eu-west-1 \
  --parameter-overrides CreateAliasRecord=false ...

# Configure Route 53 with weighted records
aws route53 change-resource-record-sets ... --region eu-north-1
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
| `DomainValidationStatus` |	Status of certificate domain validation |

---

## Troubleshooting

| Symptom | What to check |
|---------|---------------|
| Stack stuck at `CREATE_IN_PROGRESS` on `AppCertificate` | DNS validation CNAME not added yet — check ACM Console |
| `Target.FailedHealthChecks` in the target group | EC2 bootstrap still running — wait 3–5 min after `CREATE_COMPLETE` |
| Browser shows `ERR_SSL_PROTOCOL_ERROR` | Certificate not yet validated — check ACM Console status |
| `curl https://...` returns connection refused | DNS not propagated yet — test directly: `curl https://<AlbDnsName>` |
| App returns `502 Bad Gateway` | Flask not running on EC2 — SSH in and run `systemctl status secure-employee-directory` |
| Direct EC2 IP on port 5000 still reachable | The old `0.0.0.0/0` inbound rule on the EC2 SG still exists which is to be removed manually |
| Alias record not created	| Check if CreateAliasRecord=true was passed in parameters |
| Domain not resolving to ALB	| Verify the alias record exists in Route 53; check NS records for the domain |
| Target.FailedHealthChecks in target group |	EC2 bootstrap still running — wait 3-5 min after `CREATE_COMPLETE` |
| ERR_SSL_PROTOCOL_ERROR in browser |	Certificate not yet validated — check ACM Console status |
| Route 53 validation records missing |	CloudFormation might not have permissions to create records — check IAM permissions |
| Hosted zone ID format error	|| Must be just the ID (e.g., ZXXXXXXXXXXXXX) without /hostedzone/ prefix |

---

## Cleanup
Delete the stack to remove all resources including Route 53 records:

```bash
aws cloudformation delete-stack \
  --stack-name secure-employee-directory-alb \
  --region eu-north-1
```

Note: The ACM certificate will be automatically deleted when the stack is deleted,
and the DNS validation records will be cleaned up. The Route 53 alias record will
also be removed if it was created by the stack.