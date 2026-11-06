# MiniTally production MVP status

**Reviewed:** 2026-11-06  
**Branch:** `production`  
**Scope:** Repository state on the `production` branch. Statuses below describe code present in this branch; they are not claims that a live deployment has been verified.

## Status legend

- **DONE** — implemented in this branch and covered by the available tests or CI evidence.
- **PARTIAL** — a usable foundation exists, but important workflow or production controls are missing.
- **NOT DONE** — no complete implementation is present in this branch.
- **BLOCKED** — cannot be treated as release-ready until an external dependency or deployment condition is resolved.

## Manufacturing capability checklist

| Capability | Status | What exists | Remaining work |
|---|---|---|---|
| Bill of Materials (BOM) | **PARTIAL** | Versioned BOMs, active-version selection, component quantities, expected scrap percentage | Multi-level BOM explosion, sub-assemblies, alternate materials, operation-level costing |
| Workcenters | **PARTIAL** | Workcenter master, capacity-per-hour field, status, location, supported materials | Shift/calendar capacity, downtime, finite-capacity scheduling and utilization |
| Routing | **PARTIAL** | Versioned product routing, ordered operations, workcenter, required skill, setup/run time | Operation scheduling, actual time capture and routing revision controls |
| Production orders | **PARTIAL** | Create/list orders, planned quantity/date/due date, routing snapshot, operation rows and employee assignment | Controlled draft/release/hold/resume/stop/cancel/close lifecycle; sales-order demand planning |
| Material planning | **DONE** | Read-only material-plan endpoint calculates BOM requirement, recorded consumption, available stock and shortage | Reservation, allocation, warehouse selection and protection from concurrent stock claims |
| Material reservation/release | **NOT DONE** | No transactional reservation workflow | Atomic reservation/release, idempotency, concurrency protection and audit trail |
| Production execution | **PARTIAL** | Production entries, BOM consumption, finished-goods receipt and scrap movement at batch level | Dedicated operation execution, WIP transfers, controlled issue/return and full traceability |
| Job cards | **NOT DONE** | Production-order operation rows provide a basic assignment foundation | Separate job-card records, operation status lifecycle, employee time logs and actual-vs-standard reporting |
| Quality control | **PARTIAL** | Production-level status, accepted/rejected quantities and remarks | Inspection templates, measured parameters, sampling, non-conformance workflow and release gate |
| Inventory for manufacturing | **PARTIAL** | Aggregate raw-material stock and stock movement ledger | Warehouse/bin-level balances, reservations, serial/batch traceability, WIP stock and reconciliation |
| Manufacturing reports | **PARTIAL** | Production totals, scrap, material variance and workcenter aggregation | Operation efficiency, capacity utilization, labor reporting, production costing and drill-down auditability |
| Multi-level production planning | **NOT DONE** | No complete production-plan/BOM-explosion workflow | Demand consolidation, nested BOM explosion, make/buy suggestions and purchase requirements |

## API and test status

| Item | Status | Evidence / notes |
|---|---|---|
| Manufacturing router registration | **DONE** | Router is registered in the FastAPI application on this branch |
| Material-plan API | **DONE** | `GET /api/v1/manufacturing/production-orders/{order_id}/material-plan` |
| Material-plan test coverage | **DONE** | Tests cover router registration, shortages, prior consumption and missing active BOM |
| Production branch CI configuration | **DONE** | Backend dependency installation, compilation and pytest are configured; this branch snapshot has no frontend directory |
| Latest known production CI | **DONE** | The previous implementation commits passed the recorded `MiniTally Production CI` and `Backend Tests` runs; this is not a live deployment check |
| Live API smoke test | **NOT DONE** | No production URL health/login/business-flow verification is recorded here |
| Database migration on production database | **NOT VERIFIED** | CI passing does not prove the live database has been backed up and migrated successfully |

### Material-plan endpoint limitation

The material plan is a point-in-time availability calculation. It does **not** reserve stock, lock inventory, allocate a warehouse, generate a pick list, or guarantee that the displayed quantity will still be available when a later transaction runs. Do not treat a successful material plan as authorization to start production.

## Production deployment readiness

| Release requirement | Status | Required action |
|---|---|---|
| Backend manufacturing API baseline | **PARTIAL** | Core master data, order, execution, quality and report endpoints exist; lifecycle and stock controls remain incomplete |
| Frontend included in `production` | **BLOCKED** | The branch root has no frontend directory. Bring the intended frontend into a release branch and verify API compatibility |
| Branch alignment with `main` | **BLOCKED** | At review, `production` is 5 commits ahead and 370 commits behind `main`; histories are diverged. Reconcile deliberately, not with an unreviewed blind merge |
| Deployment configuration and secrets | **NOT VERIFIED** | Confirm hosting configuration, environment variables, CORS origins, database URL, secret management and HTTPS |
| Database backup/restore procedure | **NOT VERIFIED** | Document and test backup, restore and migration rollback procedures |
| Authentication and authorization smoke tests | **NOT VERIFIED** | Test login, token expiry, tenant isolation and role/area permissions against the deployed environment |
| Observability and recovery | **NOT VERIFIED** | Configure structured logs, error reporting, health checks, backups and operational alerts |
| End-to-end release acceptance | **NOT DONE** | Run critical workflows against the actual deployed frontend and backend using production-like data |

**Release assessment: NOT PRODUCTION-READY as a complete ERP application.** The production branch currently provides a backend manufacturing foundation, not a verified full-stack MVP. Passing CI is necessary but does not establish deployment readiness, tenant safety, data integrity or end-to-end workflow correctness.

## Prioritized work remaining

### P0 — required before calling this a deployable MVP

- [ ] Reconcile `production` with the intended frontend/backend release source; resolve the 370-commit divergence without blindly merging.
- [ ] Publish and verify the frontend and backend deployment configuration.
- [ ] Verify production environment variables, CORS, HTTPS, secrets and database connectivity.
- [ ] Run deployed login, tenant-isolation, role-permission and core CRUD smoke tests.
- [ ] Establish tested database backup, restore and migration procedures.
- [ ] Run end-to-end acceptance tests for the modules included in the MVP.

### P1 — required for controlled manufacturing execution

- [ ] Add transactional material reservation and release with concurrency protection.
- [ ] Add explicit production-order lifecycle transitions and audit history.
- [ ] Add dedicated job cards and employee time logs.
- [ ] Add warehouse-aware material issue, return, WIP transfer and finished-goods receipt.
- [ ] Add quality inspection templates and prevent unapproved/rejected output from being released as accepted stock.

### P2 — post-MVP manufacturing depth

- [ ] Multi-level BOM explosion and sub-assembly planning.
- [ ] Capacity calendars, finite scheduling and downtime management.
- [ ] Production costing, labor variance and operation efficiency.
- [ ] Serial/batch traceability and richer manufacturing analytics.

## Implementation notes

- The manufacturing router and read-only material-plan endpoint were added on `production`.
- The material-plan endpoint has focused backend tests.
- No material-reservation, job-card, employee-time-log or new production lifecycle implementation is included in the reviewed branch snapshot.
- This document intentionally distinguishes implemented code from planned work. Update a row to **DONE** only after the feature exists in the branch and its relevant tests pass.

## ERPNext workflow references

These links are used as workflow references, not as evidence of MiniTally feature parity:

- [ERPNext BOM](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/bom)
- [ERPNext Production Plan](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/production_plan)
- [ERPNext Work Order](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/work_order)
- [ERPNext Job Card](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/job_card)
- [ERPNext Stock Entry](https://github.com/frappe/erpnext/tree/develop/erpnext/stock/doctype/stock_entry)
