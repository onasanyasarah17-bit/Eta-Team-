# DynamoDB - Secure Employee Directory

![create_database_table](images/dynamodb-cloudformaation.png)

The DynamoDB table for this project is provisioned via CloudFormation using the
template located at `infrastructure/dynamodb.yaml`. This document covers the
template structure, deployment steps, outputs, and how to retrieve the table ARN
for the IAM team.

---

## Template Location

```
infrastructure/dynamodb.yaml
```

---

## Parameters

The template accepts two parameters at deploy time:

| Parameter   | Default            | Allowed Values              | Description                        |
|-------------|--------------------|-----------------------------|------------------------------------|
| `TableName` | `secure-employees` | Any string                  | Name of the DynamoDB table         |
| `Environment` | `production`     | `development`, `production` | Tags the table with the environment |

Both parameters have defaults and hence you can deploy without overriding either unless
you need a different table name or environment tag.

---

## Deployment

### Prerequisites
- AWS CLI installed and configured with sufficient permissions (Used cloudshell though by uploading the yaml file directly)
- CloudFormation `CreateStack` and DynamoDB `CreateTable` permissions among other necessary permissions on the IAM user

### Deploy the stack

Via Cloudshell:
- First, upload the dynamodb.yaml
- Then:

```bash
aws cloudformation deploy \
  --template-file dynamodb.yaml \
  --stack-name secure-employee-directory \
  --parameter-overrides Environment=production \
  --region eu-north-1
```

From the project root:

```bash
aws cloudformation deploy \
  --template-file infrastructure/dynamodb.yaml \
  --stack-name secure-employee-directory \
  --parameter-overrides Environment=production \
  --region eu-north-1
```

To deploy a development instance with a different table name:

```bash
aws cloudformation deploy \
  --template-file infrastructure/dynamodb.yaml \
  --stack-name secure-employee-directory-dev \
  --parameter-overrides TableName=secure-employees-dev Environment=development \
  --region eu-north-1
```

### What gets created

| Resource         | Type                  | Details                              |
|------------------|-----------------------|--------------------------------------|
| `EmployeeTable`  | `AWS::DynamoDB::Table`| Partition key: `employeeId` (String) |
| Billing mode     | PAY_PER_REQUEST       | On-demand, no capacity planning needed |
| Encryption       | SSE enabled           | AWS-managed key                      |
| Point-in-time recovery | Enabled         | Protects against accidental deletion |


---

## Outputs

After a successful deployment the stack exposes two outputs:

| Output Key  | Description                                              |
|-------------|----------------------------------------------------------|
| `TableName` | The name of the created DynamoDB table                   |
| `TableArn`  | The full ARN of the table — needed by the IAM team       |

---

## Retrieving the Table ARN

Run the following command to retrieve the stack outputs after deployment:

```bash
aws cloudformation describe-stacks \
  --stack-name secure-employee-directory \
  --query "Stacks[0].Outputs" \
  --output table \
  --region eu-north-1
```

Output:

```
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
|                                                                                           DescribeStacks                                                                                            |
+-----------------------------------------------------------------------------+--------------------------------------+------------+-------------------------------------------------------------------+
|                                 Description                                 |             ExportName               | OutputKey  |                            OutputValue                            |
+-----------------------------------------------------------------------------+--------------------------------------+------------+-------------------------------------------------------------------+
|  DynamoDB table name                                                        |  secure-employee-directory-TableName |  TableName |  secure-employees                                                 |
|  DynamoDB table ARN ? provide this to the IAM team to scope the role policy |  secure-employee-directory-TableArn  |  TableArn  |  arn:aws:dynamodb:eu-north-1:ACCOUNT_ID:table/secure-employees  |
+-----------------------------------------------------------------------------+--------------------------------------+------------+-------------------------------------------------------------------+

```

> **Note:** The real ARN has been shared with the IAM team directly.
> `ACCOUNT_ID` is omitted from this public document intentionally.


## For the IAM..

The EC2 instance role policy must be scoped to the table ARN (shared directly).
Without the ARN, the policy defaults to `"Resource": "*"` which means the role can perform those DynamoDB actions
on any table in the account. It'll work functionally but it violates least privilege; which 
is literally thhe point of this project.

Once the IAM Role is attached to the EC2 instance, the populate script can be ran
from the project root to seed the table with sample employees:

```bash
python scripts/populate_table.py
```

The app authenticates exclusively via the attached IAM Role.

