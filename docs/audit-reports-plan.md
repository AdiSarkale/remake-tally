# Audit Reports — Plan and Coverage Requirements

**Status:** Planned; documentation baseline only  
**Purpose:** Define audit-report scope and the work required to turn current activity/tenant-operation records into reliable, access-controlled audit evidence.

> This plan does not implement audit endpoints, database migrations or user-interface screens. It distinguishes existing data structures from the additional coverage required before calling audit reporting complete.

## 1. Current audit-related sources

### Tenant ERP database

The tenant model `AuditLog` maps to `audit_logs` and currently stores:

- `id`
- `at` timestamp
- `username`
- `action`
- `entity`
- `detail`

The helper `log_audit()` in `backend/app/services/inventory.py` inserts records, and some route mutations call it. Current coverage is not yet proven to be complete or uniform. The model does not currently provide structured before/after values, resource ID as a separate field, success/failure outcome, request correlation ID, client context, or event schema version.

Inventory changes also have dedicated `inventory_movements` records, which are valuable for reconstructing stock history but are not a substitute for a general audit trail.

### Control-plane tenant operations

The control database contains:

- `tenant_migration_events`: tenant schema/provisioning operations, source/target migration revisions, status, principal, error and start/finish timestamps.
- `tenant_admin_events`: tenant-administration actions, status, reason, error and start/finish timestamps.

These records are operational control-plane evidence. They must not be mixed into tenant business reports or exposed to a tenant user without a separately authorized, explicit platform-admin route.

### Coverage caveat

A table's existence does not prove that all relevant actions write to it, that failure paths are captured, or that rows are immutable. Validate every event category against actual route behaviour and tests before declaring it covered.

## 2. Audit report catalogue

| Key | Report | Purpose | Access / notes |
|---|---|---|---|
| AUD-01 | Business activity register | Search actions by time, actor, action, entity type and reference | Admin; limited accountant view only if approved |
| AUD-02 | Sensitive-change report | User/role changes, password resets, company settings and other high-impact changes | Admin only; redact sensitive values |
| AUD-03 | Approval and workflow history | Submission, approval/rejection, actor, decision, reason and timestamps for PR/PO and other approval flows | Role-gated; require decision events to be consistently recorded |
| AUD-04 | Inventory adjustment and movement audit | Stock change, reference, reason, actor, before/after balance and linked movement | Admin; operational inventory access may receive a narrower ledger view |
| AUD-05 | Sales, invoice and payment change history | Creation, status transition, cancellation and payment allocation changes | Admin/accountant per report permissions |
| AUD-06 | Production and scrap activity | Production entry, scrap entry, correction and recorded reason | Admin; avoid exposing employee details unnecessarily |
| AUD-07 | Authentication and account-security events | Login success/failure, password change/reset, account activation/deactivation, permission changes | Admin only; never store credentials or tokens |
| AUD-08 | Report/export access history | Who exported what report, when, with which filters and row count | Admin; store filter metadata safely, not sensitive row contents |
| AUD-09 | Tenant administration history | Provisioning, migration, retry, backup/restore, decommission and administrative outcomes | Platform operations role only; control-plane source |
| AUD-10 | Audit coverage and logging failures | Events expected vs recorded, missing actor/context, failed audit writes and uncovered mutation routes | Platform/security admin; make gaps visible instead of assuming completeness |

## 3. Event coverage matrix

The following events should be inventoried and implemented consistently. For each event, verify both the successful mutation and applicable failed/denied path.

| Category | Events to record | Critical details |
|---|---|---|
| Identity and access | Login success/failure, password change, admin reset, user create/update/deactivate, role change | Actor/target, result, timestamp, safe reason, request correlation; never password/token |
| Master data | Create/update/deactivate party, product, raw material, scrap type, BOM, routing, work centre and employee | Entity type and ID; redacted before/after diff for material fields |
| Procurement and approvals | Requisition status, approval/rejection, PO create/update/cancel, receipt/GRN and exceptions | Document ID, state transition, decision-maker, reason and linked documents |
| Inventory | Receipt, issue, adjustment, production/scrap movement and correction | Item, movement type, quantity/unit, old/new balance, business reference, actor |
| Sales and fulfilment | Quotation/order transitions, delivery/dispatch transitions, invoice create/cancel/correction | Document IDs and transition; tax/amount deltas where allowed |
| Finance | Customer/supplier payment create/update/void and invoice allocation changes | Amount/currency, source/target reference, outcome, no bank secrets |
| Production | Production order transitions, production entry, scrap/rework/correction | Order/batch, product, quantity/unit, work centre/employee reference where captured |
| Reports | Sensitive report viewed/exported; export failure | Report key/version, allowed filter snapshot, format, row count and outcome |
| Control plane | Tenant create/provision, migration/retry, backup/restore, credential-reference changes, decommission | Company code/id, operation, principal, revisions/status/reason; never secret value |
| Platform security | Authorization denial, suspicious access, audit-write failure | Correlation ID, route/action category and outcome; rate-limit high-volume events |

A generic audit record should not replace domain history (inventory movements, payments, state changes). Reports should correlate domain records to audit events rather than duplicating every domain field in the event log.

## 4. Target event contract

Add a structured, versioned event model through a database migration after reviewing existing consumers. Proposed fields:

- **Identity:** event ID, schema version, UTC timestamp.
- **Scope:** tenant/company context for tenant events; control-plane scope for platform events.
- **Actor:** authenticated user ID/username and role, or an explicit system/service principal.
- **Action:** stable category and verb (for example, `inventory.adjust`, `purchase_order.approve`).
- **Target:** entity/resource type and stable resource ID; optionally a human-readable document number.
- **Outcome:** success, denied, failure, and a safe reason/error category.
- **Changes:** optional allow-listed before/after snapshots or field-level diff for critical mutations; exclude or redact secrets and unnecessary personal information.
- **Traceability:** request/correlation ID and source (API, worker, migration job); capture client IP/user agent only if approved by the security/privacy owner.
- **Context:** reason/comment where the workflow collects one.
- **Integrity:** append-only application interface, restricted database permissions and controlled retention. Consider stronger tamper-evidence requirements based on the threat model.

The current `audit_logs` table is simpler than this proposed contract. Do not claim field-level change history until the schema and mutation handlers actually record it.

## 5. Recording rules

1. **Commit atomically with the business change.** For a database mutation, write the corresponding audit record in the same tenant transaction. If audit insertion fails for a mandatory event, the business mutation should not silently commit without evidence.
2. **Audit failures and denials safely.** A request rejected before the tenant transaction may need a separate security event path; do not falsely attach an untrusted tenant ID.
3. **Record state transitions, not just generic updates.** Preserve old state, new state, decision-maker, timestamp and reason where the workflow supports them.
4. **Prefer stable IDs and structured fields.** Keep free-text detail for supplementary context, not as the only searchable source.
5. **Do not log secrets.** Never include passwords, password reset values, access tokens, database URLs, secret contents or payment credentials. Redact submitted payloads using an explicit allow-list.
6. **Make timestamps consistent.** Store timestamps as timezone-aware UTC and display them in the selected tenant's configured timezone where applicable.
7. **Keep tenant and platform scope separate.** Tenant audit reports query the authenticated tenant database. Tenant fleet/administration reports query control-plane tables and require platform-operation permissions.
8. **Minimize read auditing.** Log defined high-risk views/exports rather than every routine list request unless policy explicitly requires more; avoid recursively auditing the audit-list query itself.
9. **Protect exported evidence.** Apply the same RBAC as the UI/API, cap row counts, log exports, and avoid exposing other users' personal data unnecessarily.
10. **Never equate an audit record with non-repudiation.** Strong immutability/tamper evidence requires database/storage and operational controls beyond an ordinary application row.

## 6. Access model

| Role / scope | Proposed access |
|---|---|
| Tenant administrator | Full business audit reports for their own tenant; user/account and configuration changes; export history |
| Accountant | Read-only finance document/payment activity where approved; no account-security or platform-operation details by default |
| Operator | No general audit workspace under the current permission model; show only operational histories explicitly authorized for the role |
| Platform operations/security administrator | Control-plane tenant lifecycle, migration, backup/restore and platform security reports through a separate, explicit authorization boundary |
| Unauthenticated user | No audit data |

These are planned report-level rules. The current `reports` area permission is coarse and must not be used as the sole control for all audit categories.

## 7. Phased implementation

### Phase A — Coverage inventory and immediate correctness

- Enumerate each create/update/delete/status-transition endpoint and identify current `log_audit()` calls.
- Add an automated coverage matrix for high-risk mutations.
- Ensure current audit writes share the business transaction and are tested on rollback.
- Add an administrator-only, tenant-scoped query endpoint for existing `audit_logs` records with date/action/entity/actor filters, pagination and bounded exports.
- Clearly label this as **basic activity history**, not a complete audit solution.

**Exit criteria:** P1 business mutations have an explicit log/no-log decision; the log query cannot cross tenant boundaries; failed authorization does not reveal another tenant's records.

### Phase B — Structured event schema and business coverage

- Add a migration for structured event fields and schema version.
- Instrument identity, user/role changes, approvals, inventory adjustments, purchase/sales transitions, invoice/payment changes, production and scrap corrections.
- Add allow-listed before/after diffs for critical changes and preserve useful state-transition history.
- Add event-correlation IDs and safe outcome/reason categories.
- Create tests for every event category and for audit-write failures.

**Exit criteria:** high-risk change events are searchable without parsing free text, include actor/target/outcome, and do not contain secrets.

### Phase C — Control-plane and security reports

- Provide separate, platform-admin-only reports over `tenant_migration_events` and `tenant_admin_events`.
- Extend operational event coverage for backup/restore and sensitive tenant lifecycle operations where required.
- Record report exports and defined sensitive access.
- Add audit coverage diagnostics and alerting for missing/failed writes.
- Review database privileges and retention/deletion controls with the deployment owner.

**Exit criteria:** tenant business admins cannot query platform-wide control-plane data; platform events show actor, company, operation, result and timestamps; gaps are visible.

### Phase D — Hardening, retention and evidence

- Set retention and legal-hold rules with the business/security owner; do not hard-code a legal retention period in the UI.
- Restrict update/delete access to audit stores; test privileged administrative deletion paths.
- Add integrity monitoring and, if threat modelling requires it, append-only external storage or tamper-evident chaining.
- Test backup/restore of audit evidence and document evidence export procedures.
- Review privacy, employee-data and cross-border retention implications.

**Exit criteria:** approved retention policy is configured, audit reports survive restore tests, evidence exports are access controlled, and tampering risks are documented.

## 8. Audit report filters and export requirements

At minimum, the activity register should support:

- start/end timestamp;
- actor and target user;
- event category/action;
- entity type and stable reference/document ID;
- outcome (success, denied, failure);
- correlation/request ID when available;
- tenant company only in the authorized control-plane view.

Default sort is newest first. Large results must be paginated and exports bounded. Export files must include the query filters, generation timestamp, report/schema version and row count. Any truncation must be explicit. CSV formula injection must be prevented.

## 9. Validation and acceptance criteria

- [ ] Mutating a business document and its audit event succeeds or rolls back atomically where required.
- [ ] High-risk endpoints have an event coverage test or an explicitly reviewed exception.
- [ ] Actor attribution comes from trusted authentication context, not an arbitrary payload field.
- [ ] Tenant A cannot retrieve tenant B's audit rows, including through exports or guessed identifiers.
- [ ] Only the platform-operation role can access cross-tenant lifecycle events.
- [ ] Failed logins and denied access can be investigated without logging credentials or leaking tenant existence.
- [ ] Before/after values are allow-listed and sensitive values are redacted.
- [ ] Filters and pagination are stable; newest-first ordering is deterministic.
- [ ] Export contents match selected filters and exports themselves are logged when required.
- [ ] Audit-write failures are surfaced and do not silently disappear for mandatory events.
- [ ] Retention, backup, restore and evidence-handling behaviour is documented and tested.
- [ ] Existing inventory movement, migration event and tenant administration histories remain available and correctly classified.

## 10. Definition of done

Audit reporting is complete only when both the query/report layer and the event-generation coverage are validated. A searchable `audit_logs` table with partial `log_audit()` calls is a useful starting point, but it is not, by itself, a complete or tamper-proof audit trail.
