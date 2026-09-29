# Multi-company production deployment

Minitally uses database-per-company isolation.

## Databases
- **Control DB**: contains only `tenant_companies` and routing metadata.
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
Register each tenant database in `tenant_companies`.

## Security invariant
Authenticated ERP routes resolve their SQLAlchemy session from the `company_id` in the JWT and the corresponding control-plane record. No request-supplied database URL or company ID is accepted as a database selector.

## Production requirements
- Separate PostgreSQL credentials for control and tenant databases.
- Store tenant DB URLs in a secret manager or encrypted configuration.
- Back up each tenant database independently.
- Test restore procedures per tenant.
- Automate tenant provisioning and schema migration.
- Require CI tenant-isolation tests before merging backend changes.