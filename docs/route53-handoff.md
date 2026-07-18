# Route 53 DNS — Secure Employee Directory

DNS for this project is managed via CloudFormation using
`infrastructure/route53.yaml`. The stack creates a Route 53 public hosted
zone for your root domain and an alias A record pointing the app subdomain
at the Application Load Balancer.

It imports `AlbDnsName` and `AlbHostedZoneId` directly from the ALB stack
outputs — no manual copy-pasting of ALB DNS names.

---

## Template Location

```
infrastructure/route53.yaml
```

---

## What Gets Created

| Resource | Type | Purpose |
|----------|------|---------|
| `AppHostedZone` | `AWS::Route53::HostedZone` | Public hosted zone for your root domain (optional — skip if one already exists) |
| `AppAliasRecord` | `AWS::Route53::RecordSet` | Alias A record: `employees.pcons.me` → ALB |

The alias A record is preferred over a CNAME because:
- It resolves at the zone apex (root domain) if needed later
- It has no TTL-based billing cost
- It supports `EvaluateTargetHealth: true` — Route 53 will stop returning the record if the ALB is unhealthy

---

## Parameters

| Parameter | Default | Required | Description |
|-----------|---------|----------|-------------|
| `Environment` | `production` | No | Tags all resources |
| `RootDomain` | — | **Yes** | Root domain you own (e.g. `pcons.me`) |
| `AppSubdomain` | `employees` | No | Subdomain prefix — final record is `<AppSubdomain>.<RootDomain>` |
| `AlbStackName` | `secure-employee-directory-alb` | No | ALB stack name — used to import ALB DNS name and hosted zone ID |
| `CreateHostedZone` | `true` | No | `true` creates a new hosted zone; `false` uses an existing one |
| `ExistingHostedZoneId` | *(empty)* | Conditional | Required when `CreateHostedZone=false` — the ID of your existing zone |

---

## How It Works

```
Route 53 Public Hosted Zone (pcons.me)
  │
  └── Alias A record: employees.pcons.me
        │
        └── ALB DNS name (imported from alb-https stack)
              │
              └── EC2 :5000 (Flask / Gunicorn)
```

The alias A record uses `EvaluateTargetHealth: true` — if the ALB target
group reports unhealthy, Route 53 stops resolving the record and returns
`SERVFAIL` instead of routing traffic to a broken instance.

---

## Stack Deployment Order (full infrastructure)

```
1. infrastructure/dynamodb.yaml   →  stack: secure-employee-directory
2. infrastructure/ec2-iam.yaml    →  stack: secure-employee-directory-app
3. infrastructure/alb-https.yaml  →  stack: secure-employee-directory-alb
4. infrastructure/route53.yaml    →  stack: secure-employee-directory-dns
```

The Route 53 stack **must** be deployed after the ALB stack — it imports
`AlbDnsName` and `AlbHostedZoneId` from it.

---

## Deployment

### Two scenarios

**Scenario A — You don't yet have a hosted zone in Route 53 (most common)**
Use `CreateHostedZone=true` (the default). The stack creates the hosted zone
and the alias record. After deployment, copy the NS records from the
`NameServers` output to your domain registrar.

**Scenario B — A hosted zone for this domain already exists in the account**
Use `CreateHostedZone=false` and provide the zone ID in `ExistingHostedZoneId`.
The stack creates only the alias record inside the existing zone.

---

### Prerequisites

- ALB stack (`secure-employee-directory-alb`) is in `CREATE_COMPLETE`
- You own the domain and can update NS records at your registrar
  (GoDaddy, Namecheap, Google Domains, etc.)

---

### Step 1 — Confirm the ALB stack exports are available

```bash
aws cloudformation list-exports \
  --region eu-north-1 \
  --query "Exports[?starts_with(Name,'secure-employee-directory-alb')].[Name,Value]" \
  --output table
```

You should see `secure-employee-directory-alb-AlbDnsName` and
`secure-employee-directory-alb-AlbHostedZoneId` in the output.

---

### Step 2A — Deploy (new hosted zone)

```bash
aws cloudformation deploy \
  --template-file infrastructure/route53.yaml \
  --stack-name secure-employee-directory-dns \
  --parameter-overrides \
    Environment=production \
    RootDomain=pcons.me \
    AppSubdomain=employees \
    CreateHostedZone=true \
  --region eu-north-1
```

### Step 2B — Deploy (existing hosted zone)

```bash
aws cloudformation deploy \
  --template-file infrastructure/route53.yaml \
  --stack-name secure-employee-directory-dns \
  --parameter-overrides \
    Environment=production \
    RootDomain=pcons.me \
    AppSubdomain=employees \
    CreateHostedZone=false \
    ExistingHostedZoneId=Z1D633PJN98FT9 \
  --region eu-north-1
```

---

### Step 3 — Get the NS records (Scenario A only)

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory-dns \
  --region eu-north-1 \
  --query "Stacks[0].Outputs" \
  --output table
```

Note the `NameServers` output — four NS hostnames that look like:

```
ns-123.awsdns-45.com
ns-678.awsdns-90.net
ns-111.awsdns-22.org
ns-333.awsdns-44.co.uk
```

---

### Step 4 — Update your registrar NS records (Scenario A only)

Log into your domain registrar and replace the existing NS records with the
four values from the `NameServers` output.

Propagation time varies by registrar:
- Most registrars: 15 minutes to a few hours
- Worst case: 48 hours (rare)

You can monitor propagation with:

```bash
# Check from a public DNS resolver
dig employees.pcons.me @8.8.8.8
dig employees.pcons.me @1.1.1.1
```

---

### Step 5 — Verify

```bash
# Should resolve to the ALB IP(s) and return 200
curl https://employees.pcons.me/health/ready
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

---

## Outputs

| Output Key | Description |
|------------|-------------|
| `HostedZoneId` | Route 53 hosted zone ID |
| `NameServers` | NS records to add at your registrar (Scenario A only) |
| `AppRecordName` | Fully qualified DNS name of the alias record |
| `AppUrl` | HTTPS URL — live once NS propagation completes |

---

## Troubleshooting

| Symptom | What to check |
|---------|---------------|
| Stack fails with `No export named secure-employee-directory-alb-AlbDnsName` | ALB stack not yet deployed or named differently — check `AlbStackName` parameter |
| Stack fails with `No export named ...AlbHostedZoneId` | Same as above |
| `dig` returns `NXDOMAIN` | NS records not updated at registrar yet — wait for propagation |
| `dig` returns the ALB IP but HTTPS fails | ACM certificate not yet validated — check ACM console |
| `CreateHostedZone=false` but stack fails on `AppHostedZone` | Condition logic — verify `CreateHostedZone` is exactly `"false"` (string, not boolean) |
| `EvaluateTargetHealth` causes SERVFAIL | ALB target group health check is failing — check `/health/ready` on the EC2 instance directly |

---

## Notes

- **NS delegation is a one-time step** per domain per registrar. Once done,
  all future DNS changes (adding records, etc.) happen inside Route 53 — no
  registrar login needed.
- **`EvaluateTargetHealth: true`** means Route 53 checks ALB health before
  returning the record. If the ALB target group reports the instance as
  unhealthy (e.g. DynamoDB is down), Route 53 returns `SERVFAIL` rather than
  routing traffic to the broken instance.
- **ACM DNS validation** also happens inside the hosted zone. If you used
  `CreateHostedZone=true`, ACM can automatically insert its validation CNAME
  into the Route 53 zone — but only if you add the CNAME manually via the
  ACM console or CLI first (as described in `docs/alb-https-handoff.md`
  Step 4). The ACM certificate must be validated before the ALB stack
  completes, so the hosted zone needs to exist (or an external DNS CNAME
  needs to be added) before the ALB stack is deployed.
- **Alias records have no TTL cost.** Route 53 does not charge for alias
  queries to AWS resources in the same region.
- **Tear-down order** — delete the Route 53 stack before the ALB stack.
  The alias record imports from the ALB stack exports; deleting the ALB
  stack first will leave the Route 53 stack with a dangling reference.
