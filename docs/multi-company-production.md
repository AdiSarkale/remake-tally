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

## Tenant backup and restore

Back up an active tenant to PostgreSQL custom format:

```bash
cd backend
python scripts/tenant_backup.py backup \
  --company DEMO \
  --output backups/demo-$(date +%Y%m%d%H%M%S).dump
```

The utility resolves the tenant database credential through the configured SecretProvider, creates a `pg_dump -Fc` artifact, and writes a JSON manifest containing the company code, source Alembic revision, creation timestamp, and SHA-256 checksum.

Restore into a replacement PostgreSQL database:

```bash
python scripts/tenant_backup.py restore \
  --company DEMO \
  --backup backups/demo-20261007T094700.dump \
  --target-url postgresql+psycopg://.../demo_restore
```

Restore is intentionally explicit: the target database must be supplied by the operator. The manifest checksum is verified, and a cross-company restore is rejected when the backup company code does not match the requested company.

CI executes a real PostgreSQL backup/restore round trip against the same PostgreSQL service used for migration validation. This proves that a tenant can be reconstructed into an empty replacement database rather than merely generating a dump file.

For production, upload the generated dump and manifest to encrypted, access-controlled object storage with retention and lifecycle policies. The repository utility deliberately does not embed a cloud-specific backup store.

## Production backup storage policy

The repository backup utility is responsible for producing and validating PostgreSQL backup artifacts. It deliberately does not embed a cloud-specific object-storage client. Production deployments must provide durable object storage outside the application runtime.

### Required controls

Production tenant backup artifacts must be stored in a **private object-storage bucket** with the following controls:

- **Encryption at rest:** server-side encryption is mandatory. AWS deployments should use SSE-KMS with a dedicated backup KMS key where organizational policy permits.
- **Encryption in transit:** all backup uploads and downloads must use TLS.
- **Access control:** bucket access must be denied publicly. The application or backup worker should have only the object permissions required to write new artifacts; restore operators receive read access. Historical backup deletion must not be part of ordinary application permissions.
- **Versioning:** object versioning should be enabled so an accidental overwrite does not destroy the previous artifact.
- **Retention:** production backups must have a defined retention period. The default operational baseline is **90 days**, unless contractual, accounting, legal, or customer-specific requirements require longer retention.
- **Immutability:** critical production backups should use object-lock/immutable retention for the applicable retention window where the storage platform supports it.
- **Lifecycle management:** expiration or archival must be implemented through the storage platform's lifecycle policy rather than application code deleting backup objects.
- **Audit logging:** object access and administrative deletion events should be retained according to the organization's security/audit policy.
- **Integrity:** the PostgreSQL dump and its JSON manifest must be stored together. The manifest SHA-256 checksum must be verified before restore.
- **Company isolation:** backup storage permissions and object prefixes should prevent one company's backup artifacts from being casually exposed to another company's operators.

A recommended AWS layout is:

```text
Private S3 bucket
└── tenants/
    └── <COMPANY_CODE>/
        └── <YYYY>/
            └── <MM>/
                ├── <backup-id>.dump
                └── <backup-id>.dump.json
```

The bucket should use a dedicated backup policy, block public access, enable versioning, and apply the organization's approved KMS key and lifecycle/retention rules. Object Lock should be enabled for backup classes that require immutable retention.

### Backup and restore evidence

For every production backup, retain the dump and manifest as one logical backup set. The manifest records the company code, source Alembic revision, creation timestamp, and SHA-256 checksum. Restore operators must verify:

1. the artifact exists and is readable;
2. the manifest checksum matches the downloaded dump;
3. the manifest company code matches the intended restore company;
4. the target PostgreSQL database is explicitly identified;
5. the restore completes successfully.

Restore tests should be performed periodically and the result retained as operational evidence. A successful `pg_dump` alone is not sufficient proof of recoverability.

### Decommissioning retention

A tenant's final decommissioning backup must be uploaded to the production backup store before the tenant database is physically destroyed. The retention policy must outlive the destruction event for the required retention window. Physical database deletion remains a separate, operator-controlled action and must not bypass backup retention or restore-validation requirements.

### Deployment checklist

Before treating production backup storage as ready, verify:

- [ ] private bucket/container with public access blocked;
- [ ] encryption at rest enabled and approved key configured;
- [ ] TLS required for object access;
- [ ] least-privilege writer and restore roles configured;
- [ ] versioning enabled;
- [ ] retention period configured (90 days minimum baseline unless policy requires longer);
- [ ] lifecycle/archive policy configured;
- [ ] immutable retention/Object Lock enabled where required;
- [ ] object access and deletion auditing enabled;
- [ ] dump and manifest stored together;
- [ ] a restore test has been completed and evidence retained.

The application remains cloud-neutral: `tenant_backup.py` creates the dump and manifest, while deployment/operations tooling is responsible for uploading and protecting those artifacts in the approved object store.

## Tenant decommissioning

Decommissioning is a control-plane state transition, not an automatic database drop.

Run:

```bash
cd backend
python scripts/tenant_lifecycle.py decommission \
  --company-id <control-plane-company-id> \
  --backup backups/demo-final.dump \
  --reason "Contract terminated"
```

The workflow:

1. acquires the per-company advisory lock;
2. immediately disables the tenant and moves it to `decommissioning`;
3. creates and checks the final PostgreSQL backup;
4. records the lifecycle event;
5. only then marks the company `decommissioned`.

A failed backup never reactivates the tenant. The database is not physically dropped by the application. That destruction step remains a separate operator action after retention and restore requirements are satisfied.


## Migration lineage preflight

Before a production fleet migration, run the read-only tenant revision audit:

```bash
cd backend
python scripts/audit_tenant_migrations.py
```

The audit enumerates every control-plane tenant that is both `active` and `ready`, resolves its database URL through the configured SecretProvider, reads its `alembic_version`, and verifies that the recorded revision exists on the currently deployed migration head path.

The command performs no schema changes. A non-zero exit means at least one tenant is not safely represented by the deployed migration lineage and the fleet migration must not proceed until that tenant is investigated.

This is the runtime gate for the "every actually deployed tenant revision" requirement. The audit should be run against the production control database immediately before a migration release and retained with the release evidence.
