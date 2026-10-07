# Multi-company production deployment

Minitally uses database-per-company isolation.

## Databases
- **Control DB**: contains `tenant_companies`, migration audit records, and routing metadata.
- **Tenant DB**: contains the complete ERP schema for exactly one company.

Set `CONTROL_DATABASE_URL` to the dedicated control PostgreSQL database.

## Migrations
Run the control-plane migration once:

```bash
cd backend
alembic -c control_alembic.ini upgrade head
```

Provision a PostgreSQL database for each company, then run the normal ERP migrations against that tenant URL:

```bash
DATABASE_URL=postgresql+psycopg://.../company_a alembic upgrade head
DATABASE_URL=postgresql+psycopg://.../company_b alembic upgrade head
```

Register each tenant database in `tenant_companies`. Application-driven provisioning uses the same Alembic head, so schema creation and later fleet upgrades share one migration path.

## Concurrency control

Tenant schema changes use PostgreSQL advisory locks in the control database:

- one global fleet lock prevents two fleet migration jobs from running concurrently;
- one per-company lock prevents provisioning, retry, and migration operations for the same tenant from overlapping;
- locks are database-backed and therefore coordinate separate API processes, deployment jobs, and worker processes.

No application-level mutex is relied upon for schema safety.

## Migration audit

Each provisioning, fleet migration, and failed-tenant retry writes a row to `tenant_migration_events` containing:

- company and operation;
- source and resulting Alembic revision;
- started/finished timestamps;
- success/failure state;
- triggering principal;
- failure detail when applicable.

This is operational audit data in the control plane, not tenant ERP data.

## Secrets

Tenant database credentials are represented by secret references only. Runtime resolution uses the configured SecretProvider, with environment-backed resolution for local/demo deployments and AWS Secrets Manager for production.

The control-plane secret-reference migration validates through that provider before removing plaintext `database_url` values.

## Security invariant

Authenticated ERP routes resolve their SQLAlchemy session from the `company_id` in the JWT and the corresponding control-plane record. No request-supplied database URL or company ID is accepted as a database selector.

## Production requirements
- Separate PostgreSQL credentials for control and tenant databases.
- Store tenant DB URLs in a managed secret provider.
- Back up each tenant database independently.
- Test restore procedures per tenant.
- Automate tenant provisioning and schema migration.
- Require CI tenant-isolation and PostgreSQL migration tests before merging backend changes.
