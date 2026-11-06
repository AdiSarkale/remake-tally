# MiniTally production roadmap

**Reviewed:** 2026-11-06  
**Branch:** `production`  
**Purpose:** Single release roadmap covering application readiness, multi-company operations, deployment controls, and manufacturing MVP delivery.

> Status is assessed against files and implementation visible on this branch. A roadmap or implementation on the divergent `main` branch is not automatically present in `production`. **Documented elsewhere** is not the same as implemented here.

## Status definitions

- **DONE** — implementation is present on this branch and has relevant passing test evidence.
- **PARTIAL** — some implementation exists, but release-critical controls or workflows are missing.
- **NOT DONE** — no complete implementation is present on this branch.
- **NOT VERIFIED** — documentation or code exists in another branch, or production operation has not been tested against a live environment.
- **BLOCKED** — a release dependency prevents the capability from being treated as ready.

## 1. Executive release assessment

<badge>NOT PRODUCTION-READY</badge>

The current `production` branch is a backend-focused snapshot. It contains a manufacturing foundation and a read-only material-plan endpoint, but it does not contain the frontend tree. It also does not contain the multi-company deployment/backup implementation documented on the divergent `main` branch. The branch must be reconciled with the intended full-stack release source before it can be called a deployable ERP MVP.

| Release area | Status | Reason |
|---|---|---|
| Manufacturing backend foundation | **PARTIAL** | BOM, routing, workcenters, production orders, batch execution, quality result and summary report endpoints exist |
| Manufacturing material planning | **DONE** | Read-only BOM requirement/consumption/stock/shortage endpoint and focused tests exist |
| Full-stack application on this branch | **BLOCKED** | No `frontend/` directory exists in this branch snapshot |
| Multi-company control plane and tenant lifecycle | **NOT VERIFIED** | A detailed design/operations document exists on `main`; its implementation is not present in this branch snapshot |
| Tenant backup/restore and audit | **NOT VERIFIED** | `main` contains a backup/restore and migration-audit guide; production-branch implementation and live restore evidence are absent |
| Live deployment | **NOT VERIFIED** | No deployed frontend/API smoke-test evidence is recorded here |
| CI | **PARTIAL** | Production-branch backend CI has passed in recorded runs; this does not validate frontend, production database, tenant isolation or live operations |

## 2. Branch and release-source reconciliation — P0

At the last comparison, `production` was **5 commits ahead and 370 commits behind `main`**, with diverged histories. The `main` branch contains the current full-stack repository layout and additional tenant operations documentation; the `production` branch does not contain those files.

- [ ] Identify the intended canonical release source and freeze the scope for the MVP.
- [ ] Review the 370 commits on `main` since the merge base; classify backend, frontend, schema, migration, security and documentation changes.
- [ ] Reconcile histories using a reviewed integration branch or selective cherry-picks. Do not blindly force-merge either branch.
- [ ] Resolve migration lineage and duplicate/conflicting model changes before deploying.
- [ ] Restore the intended `frontend/` application into the release candidate.
- [ ] Run backend tests, frontend typecheck/build, migration tests and tenant-isolation tests on the integrated candidate.
- [ ] Fast-forward or otherwise promote the verified release candidate to `production`.

**Acceptance:** one release commit contains the intended frontend and backend, migration history is linear/understood, all required CI jobs pass, and a rollback target is recorded.

## 3. Multi-company architecture and operations — P0

### 3.1 Architecture described by the `main` branch document

The document `docs/multi-company-production.md` on `main` describes a database-per-company model:

- **Control database:** tenant registry, migration audit records and routing metadata.
- **Tenant database:** ERP schema for one company.
- `CONTROL_DATABASE_URL` points to the dedicated control database.
- Tenant sessions are resolved from trusted JWT `company_id` context and control-plane metadata, not a request-supplied database URL or company selector.
- Control-plane and tenant migrations use separate Alembic environments.
- PostgreSQL advisory locks coordinate fleet-wide and per-company schema operations.
- Tenant DB credentials are stored as secret references and resolved through a SecretProvider.
- Provisioning, migration and retry operations record migration audit events.

**Production-branch status: BLOCKED — implementation absent.** The branch still uses one process-wide `DATABASE_URL` engine and its JWTs do not carry a company context. The production tree does not contain the control-plane models/database, tenant engine/session resolver, tenant credential provider, company-token resolver, or tenant-isolation tests. The implementation exists on `main`, but `production` and `main` have diverged substantially; selectively copying a few files would leave incompatible auth, settings, user-schema and migration assumptions. Port the complete tenant boundary through a reviewed integration branch before promoting it.

### 3.2 Required tenant controls

- [ ] Dedicated control database and isolated tenant databases.
- [ ] Trusted JWT-to-tenant resolution on every tenant-scoped request.
- [ ] No request-supplied tenant ID or database URL can override authenticated context.
- [ ] Per-tenant credentials resolved through a managed secret provider.
- [ ] Control-plane and tenant migrations independently versioned and tested.
- [ ] Global and per-tenant migration concurrency locks.
- [ ] Tenant provisioning, migration, retry and decommissioning audit events.
- [ ] Automated tenant-isolation tests covering read and write paths.
- [ ] Tenant lifecycle states and safe disable/decommission transitions.
- [ ] Production fleet migration preflight verifies every active/ready tenant revision.

### 3.3 Secret management

- [ ] No production database credentials or JWT secrets committed to the repository.
- [ ] Use managed secret storage for production tenant credentials.
- [ ] Restrict secret read permissions to the runtime/worker identities that require them.
- [ ] Rotate credentials and signing secrets using a documented procedure.
- [ ] Verify secret resolution and failure behaviour in deployment tests.

The multi-company guide describes AWS Secrets Manager for production and environment-backed secrets for local/demo use. Confirm the actual provider implementation and deployment configuration on this branch before marking this done.

## 4. Tenant backup, restore and decommissioning — P0

The multi-company guide describes a tenant backup utility using PostgreSQL custom-format dumps, JSON manifests and SHA-256 checksums; a restore utility; per-tenant migration revision audits; and a decommission workflow that disables the tenant and requires a final backup before marking it decommissioned.

**Production-branch status: BLOCKED — implementation absent.** The production tree has no control-plane migration environment, tenant backup/restore utility, tenant lifecycle scripts, secret-reference resolver, or PostgreSQL backup/restore integration tests. The guide describes the intended controls but is not executable evidence. These capabilities depend on phase 7's tenant architecture and must be ported and tested together.

### Required controls

- [ ] Independently back up every tenant database.
- [ ] Include company code, source migration revision, timestamp and SHA-256 checksum in a manifest.
- [ ] Verify checksum and company identity before restore.
- [ ] Restore only to an explicitly supplied target database.
- [ ] Test a real backup/restore round trip against PostgreSQL in CI.
- [ ] Run periodic restore drills and retain evidence.
- [ ] Upload dump and manifest together to private, encrypted object storage.
- [ ] Require TLS, public-access blocking, least-privilege access, versioning and audit logging.
- [ ] Set retention (90 days as the baseline in the `main` branch guide, or longer where policy requires).
- [ ] Use immutable retention/Object Lock for backup classes requiring it.
- [ ] Use storage lifecycle policies for archival/expiry; do not let ordinary app credentials delete historical backups.
- [ ] Require a verified final backup before tenant database destruction.
- [ ] Keep physical database deletion a separate operator-controlled action.

**Acceptance:** successful restore of a tenant backup into an empty replacement database, with company identity and checksum validated, plus documented recovery time and operator steps.

## 5. Deployment and runtime readiness — P0

- [ ] Confirm production hosting for frontend, API and databases.
- [ ] Configure HTTPS and trusted origins.
- [ ] Set exact frontend origins in CORS; do not use wildcard origins with authenticated credentials.
- [ ] Configure production database URLs, secret provider, JWT signing secret and token expiry.
- [ ] Verify health/liveness/readiness endpoints.
- [ ] Apply control-plane and tenant migrations through a controlled release job.
- [ ] Ensure startup does not reset or reseed production data.
- [ ] Confirm process restart, deploy rollback and database migration rollback strategy.
- [ ] Configure structured logs, error monitoring, metrics and alerting.
- [ ] Confirm resource limits, connection pooling and database capacity.
- [ ] Run login, role authorization, tenant isolation and critical business-flow smoke tests against the deployed URLs.
- [ ] Record release version, migration revisions and smoke-test evidence.

## 6. Manufacturing MVP roadmap

### 6.1 Capability status

| Capability | Status | Implemented on `production` | Remaining work |
|---|---|---|---|
| Bill of Materials | **PARTIAL** | Versioned BOMs, active version, component quantities and expected scrap | Multi-level explosion, sub-assemblies, alternates and operation costing |
| Workcenters | **PARTIAL** | Master data, capacity-per-hour, status, location and supported materials | Shift calendars, downtime and finite-capacity scheduling |
| Routing | **PARTIAL** | Versioned routing and ordered operations with workcenter, skill and setup/run time | Operation scheduling, actual time capture and revision controls |
| Production orders | **DONE — core lifecycle** | Planned, Released, In Progress, Completed and Cancelled states; validated transitions, reservation gate, operation assignment, completion checks, cancellation restrictions and audit events | Hold/resume/stop states and demand-driven creation remain outside this phase's accepted scope |
| Material planning | **DONE** | Read-only endpoint calculates BOM requirements, recorded consumption, available stock and shortage | Reservation, warehouse allocation and concurrency protection |
| Material reservation/release | **DONE — backend scope** | Atomic BOM-based reservation preflight, row locking, idempotent reserve, consumed-quantity tracking, release, warehouse association, WIP transfer and audit | PostgreSQL concurrency stress testing and multi-tenant authorization validation remain release gates |
| Production execution | **PARTIAL** | Production entries, BOM consumption, finished-goods receipt and scrap at batch level | Dedicated operation execution, WIP transfer, controlled issue/return and traceability |
| Job cards | **DONE — core execution** | One card per order operation, employee assignment, start/stop lifecycle, time logs, overlap prevention, completion guards and production-output progress updates | Multi-employee parallel assignment, detailed operation quality routing and efficiency analytics remain future enhancements |
| Quality | **DONE — core inspection gate** | Per-batch inspection record, measured check lines, accepted/rejected quantities, finalization guard, audit trail and release of accepted quantity only; rejected output remains on hold | Reusable inspection templates, non-conformance disposition and corrective-action workflow remain future enhancements |
| Manufacturing inventory | **DONE — core warehouse flow** | Warehouse balances, source-to-WIP transfers, WIP consumption, target-warehouse finished-goods receipt, transfer idempotency and quality-hold balances | Bin-level picking, serial/batch traceability and advanced returns remain future enhancements |
| Manufacturing reports | **PARTIAL** | Production totals, scrap, material variance and workcenter aggregation | Operation efficiency, capacity utilization, labor reporting and production costing |
| Multi-level production planning | **DONE — BOM planning preview** | Recursive BOM explosion, cycle/depth and missing-BOM detection, aggregated subassembly demand, existing subassembly stock netting, make quantities and raw-material shortages | Finite-capacity scheduling, lead-time calendars and actual subassembly stock issue/consumption remain future work |

### 6.2 Existing manufacturing API/test evidence

- **DONE:** manufacturing router is registered in FastAPI.
- **DONE:** `GET /api/v1/manufacturing/production-orders/{order_id}/material-plan` returns a point-in-time material availability snapshot.
- **DONE:** focused tests cover router registration, shortages, prior consumption and missing active BOM.
- **DONE:** production-execution regression tests cover default BOM consumption, insufficient-stock rejection without posting inventory movements, and successful raw-material/finished-goods ledger updates.
- **DONE — phase 1 backend scope:** production reservation regression coverage verifies shortage atomicity, idempotency, release, protection of reserved stock and company-wide reservations during warehouse issues.
- **DONE — phase 2 core lifecycle:** explicit transition regression coverage verifies invalid transition rejection, release/start ordering, reservation prerequisite, premature completion rejection, cancellation restrictions, reservation release and successful completion. Commit `5f01ae3` passed both GitHub Actions workflows on 2026-11-06; 37 tests passed, 2 warnings.
- **DONE — phase 3 core job-card execution:** release-generated job cards, start/stop time capture, employee overlap prevention and premature-completion rejection are covered. Commit `9e0b258` passed both GitHub Actions workflows on 2026-11-06; 38 tests passed, 2 warnings.
- **DONE — phase 4 core warehouse/WIP flow:** source warehouse to WIP transfer, WIP material consumption, target-warehouse output receipt, quality-hold integration and repeated-transfer idempotency are covered. Commit `cad5cae` passed both GitHub Actions workflows on 2026-11-06; 39 tests passed, 2 warnings.
- **DONE — phase 5 core quality gate:** inspection records and measured checks, accepted/rejected quantity reconciliation, finalization protection, accepted-stock release and rejected-stock hold are covered. Commit `0b8f170` passed both GitHub Actions workflows on 2026-11-06; 40 tests passed, 2 warnings. Reusable templates and corrective-action workflows are not included in this core scope.
- **DONE — phase 6 BOM planning preview:** recursive BOM planning now nets existing subassembly stock before exploding lower-level raw-material requirements; it also reports make quantities and avoids requiring a BOM when existing stock fully covers demand. Commit `6ee2bf2` passed both GitHub Actions workflows on 2026-11-06; 40 tests passed, 2 warnings. Finite-capacity scheduling, lead-time calendars and subassembly stock consumption during production execution remain outside this phase's verified scope. The branch remains backend-only and CI is not a production deployment sign-off.

The material-plan endpoint does **not** reserve stock, lock inventory, allocate a warehouse or guarantee availability at a later time. A positive result must not be treated as authorization to start production.

### 6.3 Manufacturing delivery sequence

**P1 — controlled execution**
- [x] Transactional material reservation and release (backend scope; see CI evidence above).
- [x] Explicit production-order lifecycle and transition validation (core lifecycle; see phase 2 CI evidence above).
- [x] Dedicated job cards and employee time logs (core execution scope; see phase 3 CI evidence above).
- [x] Warehouse-aware material issue, WIP transfer and finished-goods receipt (core flow; returns and traceability extensions remain open).
- [x] Quality inspection records and accepted/rejected stock-release gate (core scope; reusable templates and corrective actions remain open).

**P2 — planning and operational depth**
- [x] Recursive multi-level BOM explosion and sub-assembly make-quantity planning (core preview; finite capacity scheduling remains open).
- [ ] Capacity calendars, finite scheduling and downtime.
- [ ] Production costing, labor variance and operation efficiency.
- [ ] Serial/batch traceability and advanced manufacturing analytics.

## 7. Application-wide MVP acceptance — P0

A full ERP MVP is not complete just because manufacturing endpoints pass. For every module included in the release:

- [ ] List supported user journeys and explicit exclusions.
- [ ] Verify frontend screens use the real API and handle loading, validation and API errors.
- [ ] Verify backend authorization for every protected operation.
- [ ] Verify tenant isolation for all reads and writes.
- [ ] Verify audit history for sensitive changes.
- [ ] Verify migrations on a clean database and an upgrade from the previous release.
- [ ] Add automated tests for business rules and failure paths.
- [ ] Verify exports/reports against source transactions.
- [ ] Test realistic data volumes and pagination.
- [ ] Document operational ownership, support path and known limitations.

### Release smoke-test minimum

1. Login and token expiry.
2. Tenant switching/isolation (where supported) and cross-tenant denial.
3. Role/area permission enforcement from direct API calls.
4. Core master-data create/update/read flows.
5. Procurement to inventory receipt.
6. BOM, routing, production order, material plan and production entry.
7. Quality result and accepted/rejected quantity handling.
8. Finance posting/report reconciliation for included flows.
9. HR/payroll access restrictions for included flows.
10. Frontend refresh/deep-link behaviour.
11. Backup and restore drill.
12. Error logging and health/readiness checks.

## 8. Delivery gates and definition of done

### Phase 7–8 integration blocker (verified 2026-11-06)

The `production` branch currently has no DB-per-company runtime boundary or tenant backup/restore implementation. A GitHub comparison on 2026-11-06 reports `main` is 372 commits ahead of `production`, while `production` is 54 commits ahead of `main`, with 214 changed files. `main` contains the tenant and backup capabilities, but its runtime replaces the single-database session/authentication path and expects additional settings, JWT claims, user fields, control-plane migrations and deployment configuration. A blind merge or partial file copy is unsafe. Phases 7 and 8 remain BLOCKED until the branch histories and migration lineage are reconciled on a dedicated integration branch, then the complete tenant implementation is ported with PostgreSQL isolation and backup/restore CI.

| Gate | Required evidence | Promotion decision |
|---|---|---|
| G0 — scope and branch | Approved module scope, release source and reviewed branch reconciliation | No implementation promotion until agreed |
| G1 — code complete | Feature implementation, migrations, permissions, audit and documentation | Candidate may enter CI |
| G2 — automated validation | Backend tests, frontend checks/build, migration tests, tenant isolation and PostgreSQL integration tests | Candidate may enter staging |
| G3 — staging acceptance | End-to-end user journeys, security checks, backup/restore drill and smoke tests | Candidate may enter production approval |
| G4 — production release | Reviewed deployment config, secrets, migration plan, rollback target, monitoring and owner sign-off | Deploy |
| G5 — post-release | Health checks, login/business-flow smoke tests, error monitoring and backup confirmation | Release accepted |

A capability is **DONE** only when implementation, migrations, backend authorization, frontend behaviour, automated tests, tenant isolation, audit behaviour and documentation have been reviewed. A green CI run alone is not a production-readiness sign-off.

## 9. Related documents and source-of-truth rules

- [Manufacturing parity and detailed capability comparison](erpnext-production-parity.md)
- [Multi-company production deployment design on `main`](https://github.com/AdiSarkale/remake-tally/blob/main/docs/multi-company-production.md) — source reference only; not evidence of implementation on this branch.

This roadmap is the consolidated release tracker. Update statuses only after verifying code and relevant test/deployment evidence on the release branch. Keep detailed implementation notes in the linked documents, and do not mark a capability complete based solely on a plan or a document existing on another branch.
