# AWS Secrets Manager deployment

Production configuration:
- ENVIRONMENT=production
- SECRET_PROVIDER=aws_secrets_manager

Do not configure TENANT_DB_URL_<REF> variables in production.

Use one AWS Secrets Manager secret per tenant, for example:
minitally/tenants/SPW/database

The secret may contain either the raw PostgreSQL URL or JSON:
{"database_url": "postgresql+psycopg://..."}

Store only the secret name/ARN in tenant_companies.database_secret_ref.

Attach iam/tenant-secret-reader-policy.json to the AWS workload role used by
the API. Replace <REGION> and <ACCOUNT_ID> before deployment.

The policy grants only secretsmanager:GetSecretValue for minitally/tenants/*.
Do not commit AWS access keys or database credentials.
