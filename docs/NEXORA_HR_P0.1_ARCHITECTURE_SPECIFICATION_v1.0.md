# Nexora HR — P0.1 Architecture & MVP Implementation Specification

**Document ID:** NEX-HR-ARCH-001  
**Version:** 1.0  
**Status:** Approved for implementation by project owner — P0.1 implementation in progress  
**Decision baseline:** 9 November 2026  
**Module:** HR & Payroll / People Management  
**Priority:** P0.1 — Workforce foundations  
**Integration branch:** `docs/hr-phase-2-implementation-status`  
**Approved product decisions:** [Nexora HR Decision Register v1.0](NEXORA_HR_DECISION_REGISTER_v1.0.md)  
**Existing audit/design draft:** [P0.1 Shift & Roster Enhancement Specification v1.1](NEXORA_HR_ENHANCEMENT_SPECIFICATION_v1.1_P0.1_SHIFT_ROSTER.md)  
**Implementation tracker:** [Nexora HR & Payroll Implementation Status](NEXORA_HR_PAYROLL_IMPLEMENTATION_STATUS_v1.0.md)  
**Roadmap:** [Nexora HR High-Value Implementation Roadmap v1.0](NEXORA_HR_HIGH_VALUE_IMPLEMENTATION_ROADMAP_v1.0.md)

> This document converts the approved product decisions into the P0.1 MVP architecture. The project owner authorized implementation on 9 November 2026. This specification remains the design authority; implementation progress and verification evidence are tracked separately in the HR/Payroll Implementation Status document.

---

## 1. Purpose and specification authority

### 1.1 Purpose

Define the architecture and MVP implementation contract for:

- Shift definitions and effective-dated shift assignments.
- Department default shifts and employee-specific overrides.
- Daily/weekly roster generation and date-specific overrides.
- Branch-aware timezone and overnight shift handling.
- Raw attendance events from manual, Excel and employee punch sources.
- Attendance source comparison and anomaly flagging.
- Daily attendance summaries and correction workflow.
- Late/early calculation inputs and overtime review.
- Compensatory-leave earning records.
- Shift-aware payroll readiness and immutable calculation provenance.
- Authorization, data scope, audit, migration, APIs, UI, tests and release gates.

### 1.2 Source-of-truth hierarchy

1. **NEXORA HR Decision Register v1.0** is authoritative for the product decisions approved on 9 November 2026.
2. This architecture specification defines the MVP technical interpretation of those decisions.
3. The earlier P0.1 v1.1 document remains the source audit and historical draft; its proposed defaults and its seven-question decision list are superseded by the approved Decision Register.
4. Nexora Core and Master Module Planning documents govern shared-service boundaries: authorization, organization, audit, notifications and workflow remain Core responsibilities; HR owns HR business rules and records.
5. Existing repository code is the implementation baseline, not an authority to contradict an approved product decision. Existing behavior must be preserved unless this specification explicitly changes it.

### 1.3 Status vocabulary

| Status | Meaning |
|---|---|
| Approved product decision | Explicitly selected by the project user. |
| Architecture specified | MVP design is documented here. |
| Configuration required | Tenant must configure the value before the related feature is activated. |
| Deferred post-MVP | Explicitly deferred in the Decision Register; do not silently implement a guessed policy. |
| Implementation pending | No implementation claim is made. |
| Release blocker | Must be resolved before the affected workflow can be used safely. |

### 1.4 Architecture principles inherited from Nexora Core

- HR owns employee, employment, attendance, leave, overtime and payroll domain records.
- Core owns identity, tenant/organization boundaries, permission evaluation, approval authority, shared workflow, audit infrastructure and notifications.
- Permission, assignment/responsibility and approval authority are separate checks.
- Backend enforcement is mandatory. Frontend visibility is not authorization.
- Tenant data and configuration must remain isolated.
- Important configuration is tenant-configurable, versioned and auditable.
- A change in current configuration must not silently change historical attendance or in-progress/finalized payroll.
- Employee records do not imply login-account provisioning.

---

## 2. Current implementation baseline

The following is based on source inspection of the integration branch. It is a description of the code baseline, not a fresh test result.

### 2.1 Existing entities and behavior

| Existing entity | Current purpose | P0.1 treatment |
|---|---|---|
| `Employee` / `employees` | Employee master, code, name, department text, joining/end dates, active state | Reuse. Do not create a second employee master. |
| `HRBranch` / `hr_branches` | Branch code, name, address, IANA timezone, active state | Reuse as branch and timezone source. |
| `EmployeeOrgAssignment` / `employee_org_assignments` | Effective-dated employee branch, department and reporting-manager assignment | Reuse to resolve branch/department for a work date and enforce scope. |
| `HRPayrollSettings` / `hr_payroll_settings` | Salary-count mode, monthly salary days, tenant week-offs and tenant timezone | Preserve. Tenant timezone remains fallback. |
| `HRCalendarDay` / `hr_calendar_days` | Tenant-wide working-day, holiday and week-off override | Preserve as the existing holiday/calendar baseline. |
| `EmployeeAttendance` / `employee_attendance` | One daily attendance summary per employee/work date | Preserve unique employee/date contract; extend with nullable provenance/review fields only through migration. |
| `HRPayrollRun` / `hr_payroll_runs` | Payroll period, revision and lifecycle state | Extend in a backward-compatible manner for controlled supersession if required. |
| `HRPayrollItem` / `hr_payroll_items` | Employee-level payroll calculation snapshot | Preserve existing fields and add related daily schedule provenance records. |

Current payroll salary-count modes remain:

- `working_days`
- `calendar_days`
- `fixed_days`

Current payroll lifecycle includes prepared, approved, finalized, locked and reversed behavior. The exact state machine must be reconciled with this specification during implementation; do not replace existing reversal or Finance journal behavior.

### 2.2 Existing limitations addressed by P0.1

- No shift definition, assignment or roster entities currently exist in the inspected payroll model.
- Attendance is currently one summary row per employee/date.
- Raw punch events and source reconciliation are not represented separately.
- Existing calendar and attendance readiness use tenant-level week-offs/calendar.
- Branch records have timezones, but current attendance conversion uses tenant timezone.
- Existing Excel import has a selected IANA timezone parameter but defaults to tenant timezone and does not yet enforce the new one-branch-per-batch rule.
- Current Excel template is based on daily summaries and time-only punch columns; it cannot reliably represent multiple events or next-day punch timestamps.
- Existing payroll items store aggregate day totals and overtime, not a per-day roster/shift snapshot.
- Branch/team employee-scope infrastructure exists in the P0 integration baseline. New attendance, roster, import, anomaly, correction and overtime endpoints must use it; do not assume all new endpoints are automatically scoped.

### 2.3 Existing corrective work

Track separately from feature delivery:

| ID | Required action | Status recorded in tracker |
|---|---|---|
| AUD-05 | Verify punch-in and punch-out use the selected import timezone consistently | **Verified** — both fields use selected IANA timezone; regression tests passed. |
| AUD-06 | Verify attendance DELETE requires write authorization | **Verified** — exact payroll write dependency and denial/allow regression test passed. |
| AUD-07 | Extend employee branch/team scope checks to all attendance-backed endpoints, imports, exports and new P0.1 routes | **Existing attendance routes verified** — monthly read, manual upsert, DELETE and Excel import enforce effective-date employee scopes. Blank template contains no employee data. New P0.1 routes must apply the same backend scope checks. |
| AUD-08 | Ensure payroll day counters exclude attendance outside the employee employment period | **Verified** — counters and overtime exclude pre-joining/post-exit attendance; regression test passed. |

Do not describe these as verified until actual test and CI evidence is recorded.

---

## 3. MVP scope and exclusions

### 3.1 In scope

1. Shift type create, read, update and deactivate.
2. Paid/unpaid break definitions with scheduled duration and actual break-event capture.
3. Recurring department-level and employee-level shift assignments.
4. Employee assignment takes precedence over department default.
5. Date-specific roster override takes precedence over recurring assignment.
6. Effective dates and preserved assignment history.
7. Daily and weekly roster views.
8. One primary shift per employee per local work date.
9. Weekly-off and holiday classification with required tenant policy configuration.
10. Branch timezone with tenant timezone fallback.
11. Overnight shifts allocated to the local shift-start work date.
12. Raw attendance events from manual HR, Excel and employee punch capture.
13. Daily attendance summary retained for payroll compatibility.
14. Cross-source comparison and tenant-configurable discrepancy margin.
15. Missing-punch and source-discrepancy exception queues.
16. Correction initiation by employee, supervisor or HR through configured approval.
17. Candidate overtime capture, supervisor approval and HR verification.
18. Compensatory-leave earning credits with tenant-configurable earning-date and expiry-policy references; no consumption/balance workflow.
19. Shift-aware payroll attendance readiness and immutable daily calculation provenance.
20. Daily, monthly, shift-wise and overtime reporting, plus scoped supervisor dashboard.
21. Full material-action audit, tenant isolation and branch/team/self scope enforcement.

### 3.2 Explicitly out of scope

- More than one primary shift per employee/local work date or complex split-shift segments.
- Biometric/time-clock device integration.
- Facial recognition, GPS or geofencing.
- Offline punch synchronization.
- Native mobile application.
- Shift bidding, employee shift swapping and automated roster optimization.
- Full compensatory-leave balance, request and redemption lifecycle.
- Statutory overtime interpretation or automatic legal compliance.
- Production-machine/job-level labor costing.
- Advanced predictive attendance analytics.
- Automatic historical shift inference or historical attendance rewriting.

### 3.3 MVP operating constraint

The MVP may record and display more complex operational facts only where the calculation and approval behavior is explicitly specified. It must not silently invent payroll, legal or policy rules to make a screen appear complete.

---

## 4. Target architecture

### 4.1 Logical component map

```text
                 NEXORA CORE
  Identity | Organization | Permissions | Workflow
             Audit | Notifications
                       |
                       v
                HR / WORKFORCE
                       |
       +---------------+----------------+
       |               |                |
       v               v                v
  Shift & Roster   Attendance       HR Policies
       |           Event Intake     & Exceptions
       |               |                |
       +---------------+----------------+
                       |
                       v
             Attendance Calculation
                       |
              +--------+---------+
              |                  |
              v                  v
       Daily Attendance     Overtime Review
          Summary           Supervisor -> HR
              |                  |
              +--------+---------+
                       |
                       v
                Payroll Engine
                       |
          Immutable Payroll Snapshots
                       |
                       v
             Finance Posting / Reversal
```

### 4.2 Ownership boundaries

| Concern | Owner | Boundary |
|---|---|---|
| Employee and employment record | HR | Canonical employee identity and employment dates. |
| Branch, department and reporting structure | Core organization model / existing HR organization assignment | HR consumes effective-dated organization assignment; it must not infer branch from free text. |
| Shift definitions and roster | HR | HR owns schedule rules and assignment history. |
| Raw punch events and attendance summary | HR | HR owns event capture, reconciliation and daily result. |
| Permission and data scope | Core | HR endpoints call shared authorization/scope services. |
| Approval routing and approver authority | Core Workflow | HR defines business transition requirements; Core resolves configured approvers and records workflow decisions. |
| Audit event persistence | Core Audit | HR emits attributable domain events; do not create a parallel audit system. |
| Notifications | Core Notifications | HR emits notification intents for configured events. |
| Payroll calculation and employee payroll snapshot | HR/Payroll | HR owns calculation inputs and results. |
| Accounting journal | Finance | HR invokes existing Finance posting/reversal contract; HR does not duplicate ledger ownership. |
| Manufacturing labor-cost analytics | Manufacturing/Finance consuming HR facts | Not part of this P0.1 implementation. |

### 4.3 Tenant and branch boundaries

- Follow the repository's existing tenant database/provisioning model. Do not add a redundant `tenant_id` to every table if tenant isolation is already implemented by database boundary.
- All queries must still use the authenticated tenant database/session.
- Branch is resolved from the employee's effective `EmployeeOrgAssignment` on the local work date.
- Branch timezone is read from `HRBranch.timezone`; if no effective branch is assigned, use `HRPayrollSettings.timezone`.
- Invalid IANA timezone configuration fails closed with a configuration error. Never silently reinterpret a timestamp as UTC or another branch's local time.
- Branch/team/department/self data scopes are checked on the backend for every employee-targeted read, write, import, export and approval.

---

## 5. Schedule resolution and precedence

### 5.1 Work-date definition

A work date is the local calendar date on which the assigned shift starts. For an overnight shift, all events belonging to that shift retain the shift-start work date even when the event timestamp falls after midnight.

### 5.2 Assignment resolution

For an employee and local work date, resolve:

1. Date-specific roster override for that employee/work date, if present.
2. Effective employee-specific recurring assignment.
3. Effective department default assignment matching the employee's effective department and branch.
4. Legacy tenant calendar/week-off behavior if no shift assignment applies.

The approved rule is that an employee-specific recurring assignment wins over a department default. A date-specific roster override is the explicit per-date exception.

If two department defaults or two employee assignments both match the same employee/date, treat this as an invalid configuration. Do not pick one based on insertion order or latest update time.

### 5.3 Department matching

- Use the department value from the effective employee organization assignment where available.
- The existing organization assignment currently stores department as a string. P0.1 must use that existing representation consistently and must not create a competing department master.
- Employees without an effective organization assignment must not be assigned a department default by guessing from display text.
- A department default may be branch-scoped. Conflicting global and branch-specific matches are configuration errors until a later explicit precedence rule is approved.

### 5.4 Weekly-off resolution

- Once an employee has an applicable shift assignment, its weekday pattern determines scheduled workdays and weekly offs.
- A date-specific roster override can schedule or remove a work date with a reason.
- Employees without a shift assignment continue using existing tenant week-off and calendar logic.
- The system must distinguish `scheduled`, `weekly_off`, `holiday` and `cancelled` roster outcomes.

### 5.5 Holiday precedence

Holiday precedence is tenant-configurable and must be represented in a versioned policy configuration.

**Configuration gate:** A tenant must select a holiday/roster precedence policy before creating a roster override that schedules work on a date marked as a holiday. If the required policy is unset, reject the conflicting operation with a configuration error. Do not invent a default.

The existing tenant-wide `HRCalendarDay` remains the holiday baseline for this MVP. A separate branch-specific holiday calendar is not introduced by this specification.

### 5.6 Roster generation

- Roster generation is an explicit, authorized operation over a date range and selected employee/branch/department scope.
- It resolves effective organization assignment, branch timezone and applicable shift assignment for each employee/date.
- It creates one roster entry per employee/local work date, including explicit weekly-off/holiday outcomes where needed for the roster view.
- Generation is idempotent. Re-running the same request must not duplicate entries.
- Existing manually overridden entries are not overwritten by generation.
- Historical entries are never regenerated from today's assignment.
- Future generated entries may be changed only through a controlled roster update that preserves the previous version and reason.
- Generation is blocked for a payroll-frozen period unless a permitted correction workflow explicitly authorizes a new payroll revision.

---

## 6. Time and timezone architecture

### 6.1 Canonical time handling

- Store actual event instants and resolved scheduled instants as timezone-aware UTC timestamps.
- Store the IANA timezone name used to interpret each schedule/event alongside the relevant provenance record.
- Store work dates as local calendar dates, not UTC dates.
- UI displays times in the timezone associated with the employee's applicable branch/work date, falling back to tenant timezone.
- Do not use the browser timezone as the authoritative attendance timezone.

### 6.2 Shift boundary calculation

A shift definition stores local start time, local end time and an explicit end-day offset (same day or next day). Roster generation resolves these local boundaries using the applicable IANA timezone and stores the resulting UTC instants and timezone name on the roster entry.

For example:

- Local shift start: 10 November, 22:00.
- Local shift end: 11 November, 06:00.
- Work date: 10 November.
- Punch-out at 11 November, 06:05 local remains attached to the 10 November roster entry.

If the timezone configuration is invalid or a local boundary cannot be resolved unambiguously, roster generation must fail with a clear error rather than silently selecting an offset. Daylight-saving edge-case policy beyond safe validation is retained in the post-MVP technical backlog.

### 6.3 Import timezone and branch validation

- Each import batch contains one branch and one selected IANA timezone.
- The selected branch timezone is the default in the UI.
- An authorized importer may select a different timezone for the whole batch; the selected value is recorded.
- The API validates the IANA identifier.
- Every employee/date row must resolve to the selected branch for that work date. A workbook containing employees from incompatible branches is rejected atomically.
- If employees have no branch assignment, the batch may use tenant timezone fallback only when all rows are consistently unassigned and the user has the required tenant scope.
- Multi-branch/per-row timezone import is deferred.
- UTC remains internal canonical storage; the user selects the timezone in which workbook wall-clock times were recorded.

### 6.4 Import workbook versions

**Legacy summary workbook**
- Continue accepting the current daily-summary format for backward compatibility.
- Legacy punch-in/punch-out values are interpreted in the selected batch timezone.
- For shift-enabled employees, the importer resolves event instants against the roster and creates source events plus a daily summary.
- A legacy time-only workbook cannot represent an explicit next-day timestamp. Reject ambiguous overnight rows and direct the user to the v2 event workbook.

**Event workbook v2**
- One row represents one raw attendance event.
- Required columns: Employee Code, Work Date, Event Type, Event DateTime (Local).
- Optional columns: Source Reference, Break Code, Note.
- Event DateTime is a local datetime interpreted in the batch timezone, so overnight punches are expressible.
- Supported MVP event types: `punch_in`, `punch_out`, `break_start`, `break_end`.
- The entire workbook is validated before writes. Any invalid row rejects the batch atomically.
- Import row identity is retained to make retries idempotent.

---

## 7. Data model

All identifiers, SQLAlchemy conventions, timestamp defaults, indexes and migration naming must follow the current repository patterns. Proposed table names below are logical architecture names; implementation may adjust naming to established conventions without changing semantics.

### 7.1 `hr_shift_types`

One reusable definition of a shift.

| Field | Type / rule | Purpose |
|---|---|---|
| `id` | UUID/string PK | Stable identity. |
| `code` | Required, tenant-unique | Short code. |
| `name` | Required | Display name. |
| `start_time` | Local time | Scheduled start. |
| `end_time` | Local time | Scheduled end. |
| `end_day_offset` | Integer 0 or 1 | Same-day or next-day end. |
| `active` | Boolean | Deactivate instead of deleting referenced shift. |
| `created_by`, `created_at`, `updated_at` | Audit attribution/timestamps | Lifecycle. |

Constraints:
- Unique shift code within tenant.
- End boundary must be later than start after applying day offset.
- Referenced shift types cannot be physically deleted.
- Shift definition edits must create a new effective version or preserve a version snapshot; existing roster entries retain their original schedule snapshot.

### 7.2 `hr_shift_break_rules`

One configured break rule belonging to a shift.

| Field | Purpose |
|---|---|
| `id`, `shift_type_id` | Identity and parent shift. |
| `code`, `name`, `sequence` | Break identity and display order. |
| `is_paid` | Whether the configured break is paid. |
| `planned_duration_minutes` | Scheduled duration. |
| `scheduled_start_time`, `scheduled_end_time` | Optional local scheduled window. |
| `active` | Whether new rosters use the rule. |

Actual break start/end events reference the applicable break rule when known. The exact fallback, rounding and exception rules for incomplete break pairs are deferred under T-02; incomplete break data must be visible and must not be silently treated as paid or unpaid time.

### 7.3 `hr_shift_assignments`

Supports department defaults and employee-specific recurring assignments in one effective-dated model.

| Field | Purpose |
|---|---|
| `id` | Assignment identity. |
| `scope_type` | `employee` or `department`. |
| `employee_id` | Required for employee scope; otherwise null. |
| `branch_id` | Optional branch scope for department defaults or employee assignment context. |
| `department` | Required for department scope; uses existing organization department representation. |
| `shift_type_id` | Assigned shift. |
| `weekdays` | Set of local weekdays on which the assignment schedules work. |
| `valid_from`, `valid_to` | Inclusive effective dates. |
| `supersedes_assignment_id` | Prior assignment reference when replaced. |
| `created_by`, `created_at` | Audit attribution. |

Constraints and service validation:
- Exactly one target is set according to `scope_type`.
- `valid_to` is null or on/after `valid_from`.
- Referenced employee, branch and shift must belong to the same tenant context and be valid.
- No overlapping employee-specific primary assignments for the same employee/date.
- No overlapping department defaults for the same department/branch/date.
- Assignment change closes/supersedes prior effective period; it never edits past roster snapshots.
- Employee-specific assignment wins over department default.

### 7.4 `hr_shift_roster_entries`

One resolved schedule outcome per employee/local work date.

| Field | Purpose |
|---|---|
| `id` | Roster entry identity. |
| `employee_id` | Employee reference. |
| `work_date` | Local shift-start date. |
| `status` | `scheduled`, `weekly_off`, `holiday`, `cancelled`. |
| `shift_type_id` | Nullable for non-working roster outcome. |
| `source_assignment_id` | Assignment that generated the entry, if applicable. |
| `is_override`, `override_reason` | Date-specific override and reason. |
| `branch_id`, `department_snapshot` | Organizational context at generation. |
| `timezone_name` | IANA timezone used. |
| `scheduled_start_at_utc`, `scheduled_end_at_utc` | Resolved schedule boundaries for scheduled entries. |
| `shift_code_snapshot`, `shift_name_snapshot` | Human-readable historical identity. |
| `break_rules_snapshot` | Break configuration used by this roster. |
| `policy_version_id` | Policy version used to resolve calendar/attendance rules. |
| `created_by`, `created_at`, `updated_at` | Audit attribution. |

Constraints:
- Unique `employee_id + work_date` for MVP.
- Scheduled rows require shift and valid start/end boundaries.
- Non-working rows do not have scheduled instants.
- An override requires a reason and actor.
- Referenced assignment and policy version remain traceable.
- Historical rows are not physically deleted or regenerated.

### 7.5 `hr_attendance_import_batches`

One workbook upload and its interpretation context.

| Field | Purpose |
|---|---|
| `id` | Batch identity. |
| `branch_id` | Selected single branch; nullable only for consistently unassigned legacy employees. |
| `import_timezone` | Selected IANA timezone. |
| `template_version` | Legacy summary or v2 event workbook. |
| `file_name`, `file_hash` | File provenance; avoid storing file contents in this table. |
| `uploaded_by`, `uploaded_at` | Actor/time. |
| `status` | `validated`, `imported`, `rejected`. |
| `rows_total`, `rows_imported`, `rows_rejected` | Import summary. |
| `error_summary` | Safe, bounded validation summary. |

A batch is atomic: rejected batches do not partially mutate attendance events or summaries.

### 7.6 `hr_attendance_events`

Immutable source event log for actual time capture.

| Field | Purpose |
|---|---|
| `id` | Event identity. |
| `employee_id` | Employee reference. |
| `roster_entry_id` | Resolved roster entry when applicable. |
| `work_date` | Local shift-start date to which event belongs. |
| `event_type` | `punch_in`, `punch_out`, `break_start`, `break_end`. |
| `occurred_at_utc` | Actual event instant. |
| `timezone_name` | Local timezone used to interpret input. |
| `source_type` | `manual_hr`, `excel_import`, `employee`; device is future. |
| `source_reference` | Source row/event identifier for idempotency and traceability. |
| `import_batch_id` | Nullable import batch reference. |
| `break_rule_id` | Nullable break rule reference. |
| `recorded_by` | Authenticated actor/service. |
| `supersedes_event_id` | Optional prior event corrected by this event. |
| `voided_at`, `voided_by`, `void_reason` | Controlled invalidation; no hard delete. |
| `created_at` | Immutable creation timestamp. |

Rules:
- Raw events are append-only. Corrections append a replacement event and mark the prior event superseded/voided through an audited action.
- Employee punch endpoints derive employee identity from the authenticated employee-user link; clients cannot submit arbitrary employee IDs for self-punch.
- HR/manual/import operations must pass employee scope checks.
- Event idempotency uses a stable source reference or request idempotency key. Duplicate retries must not create duplicate events.
- Event timestamps are stored in UTC; `work_date` is local and resolved against the roster.
- Event time outside the assigned roster boundary is retained but flagged for review; it is not silently discarded.

### 7.7 Existing `employee_attendance` daily summary extension

Retain the current table and unique `employee_id + work_date` constraint.

Add only nullable/backward-compatible fields required for provenance and review, subject to migration review:
- `roster_entry_id` nullable FK.
- `review_state` such as `unreviewed`, `needs_review`, `reviewed`.
- `calculation_version` / `last_calculated_at`.
- `source_resolution_state` or equivalent reference to open anomaly state.

The existing `status`, `punch_in`, `punch_out`, `overtime_minutes`, `note` fields remain compatible. Daily summary is the payroll-facing reviewed result, not the raw source log.

### 7.8 `hr_attendance_anomalies`

Records discrepancies and attendance exceptions.

| Field | Purpose |
|---|---|
| `id` | Anomaly identity. |
| `employee_id`, `work_date`, `roster_entry_id` | Affected employee/date/schedule. |
| `anomaly_type` | Source mismatch, missing punch, overlapping shift, excessive overtime, incomplete break, etc. |
| `source_event_ids` | References to compared source events. |
| `observed_delta_minutes` | Measured difference where applicable. |
| `threshold_minutes` | Tenant-configured threshold snapshot used. |
| `policy_version_id` | Configuration version used. |
| `status` | `open`, `acknowledged`, `resolved`, `false_positive`. |
| `resolution_reason`, `resolved_by`, `resolved_at` | Resolution audit. |
| `created_at` | Creation time. |

Comparison rule:
- Compare equivalent event types for the same employee/work date across available source types.
- If the absolute difference exceeds the configured tenant margin, create an anomaly.
- Do not automatically choose a winning source or overwrite existing events.
- Preserve each source value.
- If the tenant has not configured the required error margin, show the comparison as not configured and do not silently use a guessed threshold.
- A material unresolved anomaly must be resolved or explicitly marked false positive with a reason before payroll finalization.

### 7.9 `hr_attendance_correction_requests`

Stores HR-domain correction intent; Core Workflow owns approval routing and decisions.

| Field | Purpose |
|---|---|
| `id` | Request identity. |
| `employee_id`, `work_date` | Affected employee/date. |
| `attendance_id` | Daily summary reference, nullable for event-only correction. |
| `proposed_change` | Validated structured before/after proposal; sensitive fields controlled. |
| `reason` | Required correction reason. |
| `workflow_instance_id` | Core workflow reference. |
| `status` | HR projection of workflow state. |
| `submitted_by`, `applied_at` | Attribution. |
| `created_at`, `updated_at` | Lifecycle. |

Rules:
- Employee, supervisor or HR may initiate according to the configured correction workflow.
- Requester cannot approve their own request through the normal flow.
- HR applies an approved correction; workflow approval alone does not bypass HR domain validation.
- Original raw events and prior daily summary values remain auditable.
- After payroll preparation/approval, use the controlled payroll correction/revision path.
- After finalization/lock, do not rewrite payroll; use a later-period adjustment.

### 7.10 `hr_overtime_records`

Stores candidate overtime and its approval result.

| Field | Purpose |
|---|---|
| `id` | Overtime record identity. |
| `employee_id`, `work_date`, `roster_entry_id` | Employee/date/schedule. |
| `candidate_minutes` | System-calculated candidate amount. |
| `requested_minutes` | Amount submitted for approval, if adjusted. |
| `approved_minutes` | Final approved payable amount; null until fully verified. |
| `policy_version_id` | Overtime policy/configuration used. |
| `workflow_instance_id` | Core workflow reference. |
| `business_status` | Candidate, submitted, supervisor-approved, HR-verified, rejected, returned. |
| `created_at`, `updated_at` | Lifecycle. |

Default workflow:
1. Candidate overtime is calculated from roster and available attendance events.
2. Supervisor approves/rejects.
3. HR verifies.
4. Only HR-verified approved minutes can enter payroll.
5. Rejected candidate minutes remain in history but are excluded from payable overtime.

Tenant-configurable workflows may add/change authorized approver roles, but cannot bypass separation of duties. No overtime rate or rounding default is invented here; a valid tenant overtime policy is required before candidate minutes become payable.

### 7.11 `hr_comp_leave_credits`

Records earned compensatory-leave credits only.

| Field | Purpose |
|---|---|
| `id` | Credit identity. |
| `employee_id` | Employee reference. |
| `source_work_date` | Eligible holiday/weekly-off work date. |
| `credit_days` | Approved earned credit quantity. |
| `earning_date` | Date determined by tenant policy. |
| `earning_date_policy_ref` | Tenant-configured policy reference. |
| `expiry_policy_ref` | Tenant-configured expiry policy reference. |
| `workflow_instance_id` | Approval reference where required. |
| `created_at`, `created_by` | Attribution. |

This is not a leave balance ledger and does not permit redemption. Credit earning/expiry policy references must be tenant-configurable and snapshotted. Balance calculation, expiry execution and consumption remain deferred.

### 7.12 `hr_workforce_policy_versions`

Versioned tenant configuration used by workforce operations.

MVP configuration includes:
- Attendance source discrepancy margin in minutes (required before automated cross-source anomaly comparison is activated).
- Holiday/roster precedence policy reference or selected policy value (required before a holiday roster override is allowed).
- Compensatory-leave earning-date policy reference.
- Compensatory-leave expiry policy reference.
- Effective date/version/active state and change attribution.

Rules:
- Policy changes create a new version; do not overwrite historical policy versions.
- Anomaly records, roster entries, overtime records and compensatory-leave credits retain the policy version/reference used.
- Configuration writes require explicit permission and Core audit.
- Late/early and overtime detailed policy configuration is added only to the extent needed by the approved MVP; exact rule matrices remain deferred under T-04/T-05.

### 7.13 `hr_payroll_attendance_snapshots`

Immutable per-employee/per-work-date inputs used by a payroll run.

| Field | Purpose |
|---|---|
| `id` | Snapshot identity. |
| `payroll_run_id`, `employee_id` | Parent payroll revision and employee. |
| `work_date` | Local work date. |
| `attendance_id`, `roster_entry_id` | Source references. |
| `shift_code_snapshot`, `shift_name_snapshot` | Shift identity at calculation time. |
| `timezone_name` | Timezone used. |
| `scheduled_start_at_utc`, `scheduled_end_at_utc` | Scheduled boundaries. |
| `attendance_status` | Status used. |
| `punch_event_ids` | Raw event references used. |
| `punch_in_utc`, `punch_out_utc` | Actual times used. |
| `approved_overtime_minutes` | Only verified payable overtime. |
| `calendar_classification` | Scheduled/weekly-off/holiday etc. |
| `salary_count_mode`, `divisor_value` | Payroll divisor inputs. |
| `policy_version_id`, `calculation_version` | Rule provenance. |
| `calculation_inputs_snapshot` | Structured immutable input snapshot for reproducibility. |

Unique constraint: `payroll_run_id + employee_id + work_date`.

Finalized payroll snapshots are immutable. They must not rely on mutable current shift definitions, roster rows or policy settings to reproduce a past calculation.

---

## 8. Attendance event processing and daily summary

### 8.1 Sources

| Source | Initiator | Employee identity |
|---|---|---|
| Manual HR | HR or authorized supervisor | Selected employee, validated against scope. |
| Excel import | Authorized importer | Resolved by employee code and validated against selected branch/date. |
| Employee punch | Authenticated employee | Derived from employee-user link; client cannot select another employee. |
| Device | Future | Not in MVP. |

### 8.2 Event intake sequence

```text
Receive event / import row
        |
Authenticate actor and tenant
        |
Resolve employee + effective organization assignment
        |
Resolve branch timezone + roster work date
        |
Validate event type, timestamp and roster relation
        |
Check idempotency / duplicate source reference
        |
Persist immutable raw event
        |
Compare equivalent source events
        |
Create anomaly if configured margin is exceeded
        |
Recalculate candidate daily summary
        |
Mark summary reviewed / needs review
        |
Expose exceptions to HR and payroll draft
```

### 8.3 Summary calculation

- The existing daily attendance summary remains the payroll-facing row.
- Summary calculation consumes raw events and the roster snapshot.
- Actual punch-in/out and break events remain individually traceable.
- A daily summary may also be entered directly by authorized HR for legacy/manual workflows; its source and actor must be retained.
- The calculation must not overwrite raw events.
- A changed source event triggers a new calculation version and audit event; it does not erase the prior result.
- Multiple raw punches are supported, but only one primary shift/daily summary per employee/work date is in MVP.

### 8.4 Missing punch handling — approved rule

- Payroll draft/preview calculates using available attendance information.
- Missing punch is raised as an exception and displayed with employee, date, shift and missing event type.
- A grievance/correction request may be raised by an employee, supervisor or HR according to configured workflow.
- HR must correct the missing punch through the authorized correction process before payroll finalization.
- Payroll finalization is blocked while a material missing-punch exception remains unresolved.
- A missing punch must not be silently fabricated or auto-filled from a scheduled time.

### 8.5 Source discrepancy handling — approved rule

- Compare sources; do not use last-write-wins.
- Tenant-configured error margin is captured with each comparison.
- A discrepancy above the configured margin creates an anomaly.
- HR reviews the sources and records a resolution.
- No raw source is deleted because another source disagrees.
- Payroll finalization is blocked while a payroll-material source anomaly remains unresolved or unacknowledged as false positive.

### 8.6 Late and early handling

- Calculate deviations against scheduled shift start/end and the applicable grace configuration.
- Tenant policies may define thresholds by branch, shift and employee category.
- The policy engine must detect overlapping/ambiguous applicable configurations and fail closed rather than applying arbitrary precedence.
- Configured thresholds may determine late/half-day/other attendance consequences.
- Exact thresholds, rounding and consequence matrix are deferred under T-04; they must be configured before automatic status consequences are activated.

---

## 9. Overtime and compensatory leave

### 9.1 Overtime calculation boundary

- Candidate overtime is derived from actual event times, roster boundaries and configured break rules.
- Candidate overtime is not payable merely because the system detected it.
- A tenant policy must define eligibility threshold, rounding and payable rate before the record can be treated as payable.
- Default approval sequence: supervisor approval, then HR verification.
- Core Workflow resolves authorized approvers. Requesters cannot choose their own approvers.
- Separation of duties is mandatory.
- Rejected records remain traceable and are excluded from payroll.
- Only HR-verified approved minutes are consumed by payroll.

### 9.2 Overtime state model

```text
candidate
   |
submit for approval
   v
pending_supervisor
   | approve                 | reject / return
   v                         v
pending_hr_verification    rejected / returned
   | verify                  |
   v                         |
approved_payable <----------+
```

The actual workflow state and approver identity are owned by Core Workflow. HR stores the domain record and a synchronized status projection. The MVP must prevent duplicate approval application and duplicate payroll inclusion.

### 9.3 Compensatory-leave earning

- Eligible holiday/weekly-off work can create an approved compensatory-leave credit according to tenant policy.
- Earning date and expiry policy reference are tenant-configurable.
- Store source work date, credit quantity, policy references, approver/workflow reference and creation attribution.
- Do not expose the credit as consumable leave until balance and redemption functionality is delivered.
- Do not assume a default expiry duration or earning-date rule.

---

## 10. Payroll integration and financial integrity

### 10.1 Existing salary-count modes

Preserve `working_days`, `calendar_days` and `fixed_days`. Do not silently remove or redefine them.

P0.1 uses the resolved roster to determine attendance completeness and whether a day was scheduled for attendance/absence classification. The existing salary divisor calculation remains unchanged until the post-MVP T-07 policy is decided.

**Safety restriction:** If an employee's shift schedule materially differs from the tenant-wide working-day calendar while the tenant uses `working_days`, the payroll engine must not silently calculate an employee-specific divisor. The MVP must flag this as a payroll configuration limitation and block finalization for the affected employee/period unless the schedule and existing divisor basis are compatible. A later approved T-07 design will define employee-specific divisor/proration behavior. `calendar_days` and `fixed_days` retain their existing divisor behavior.

### 10.2 Payroll draft, preparation and finalization

- Payroll draft/preview can calculate from available attendance and display warnings/exceptions.
- Missing status records that make calculation impossible remain preparation blockers under existing readiness requirements.
- A present/half-day record with an incomplete punch may be included in the draft calculation using available approved inputs, but creates a missing-punch exception.
- Finalization is blocked until material missing-punch and source-reconciliation exceptions are resolved.
- Overtime is included only after the complete supervisor + HR verification flow and applicable policy configuration.
- Payroll preview must display the warnings and the data source used; it must not present provisional calculations as finalized payroll.

### 10.3 Payroll state and correction behavior

| State | Approved behavior |
|---|---|
| Draft/preview | Calculate and show warnings. No immutable payroll posting. |
| Prepared | Snapshot is retained. Attendance correction requires authorized workflow and controlled recalculation into a new revision; the old snapshot is retained as superseded. |
| Approved | Correction requires controlled approval revocation/withdrawal, correction workflow, supersession and re-approval of a new revision. |
| Finalized | Never silently rewrite or reopen. Record financial difference as an adjustment in the next eligible payroll period. |
| Locked | Immutable historical record. A later-period adjustment is used where applicable. |
| Reversed | Preserve existing Finance reversal linkage and create a new payroll revision only through existing controlled process. |
| Superseded | New non-finalized revision replaces an earlier prepared/approved calculation; old snapshot remains queryable and is never overwritten. |

The `superseded` state is a proposed minimal lifecycle extension required to preserve snapshots when a prepared/approved run is recalculated. It must be reviewed against the existing payroll state machine and Finance posting constraints before implementation. Superseded runs must never have a Finance journal posted.

### 10.4 Daily payroll snapshot

For each payroll run, store the exact per-day roster, attendance, timezone, source event references, approved overtime, calendar classification, divisor basis and policy/calculation versions used.

A finalized payroll must be reproducible without reading mutable current schedule or policy definitions.

### 10.5 Finance boundary

- HR calculates payroll and owns payroll run/items.
- Finance owns accounting journal creation, posting and reversal.
- Use the existing payroll-to-Finance posting/reversal service.
- Do not create duplicate salary expense/payable accounting logic inside HR.
- A payroll revision must not duplicate a journal posting.
- Corrections after finalization flow through the approved next-period adjustment mechanism and corresponding Finance treatment.

### 10.6 Payroll blockers vs warnings

| Condition | Draft/preview | Prepare/approve | Finalize |
|---|---|---|---|
| Missing attendance status on scheduled day | Show blocking calculation issue | Block unless resolved | Block |
| Missing punch with a usable daily status | Calculate provisionally; warn | May snapshot with open exception | Block until HR correction/resolution |
| Source mismatch above configured margin | Show anomaly | May snapshot with exception | Block until resolved/false-positive decision |
| Unconfigured source discrepancy margin | Show configuration warning; no guessed threshold | Block activation of automated comparison for that tenant | Block finalization where multiple sources cannot be reconciled safely |
| Unapproved overtime | Exclude from payable overtime; show candidate | Exclude | Exclude |
| Approved but not HR-verified overtime | Exclude from payable overtime | Exclude | Exclude |
| Shift/working-days divisor incompatibility | Show payroll configuration blocker | Block affected employee calculation | Block affected employee/period finalization |
| Invalid branch timezone | Block schedule/event interpretation | Block | Block |

---

## 11. Approval workflows and permissions

### 11.1 Shared workflow boundary

Core Workflow provides request, rule validation, configured approver resolution, approve/reject/return, workflow state and audit. HR provides domain-specific validation and applies the approved business change.

Requesters must not freely choose approvers.

### 11.2 Required workflows

| Workflow | Default/required path | Domain effect |
|---|---|---|
| Shift assignment/override | Permission-based write; approval only if tenant config requires it | Creates effective-dated assignment or roster override. |
| Attendance correction | Configured approver(s); requester cannot self-approve | HR applies validated correction and appends audit/source history. |
| Overtime | Supervisor approval → HR verification | Approved payable minutes become eligible for payroll. |
| Emergency approval override | HR/Admin emergency action with reason and mandatory additional review | Allows progress only with full audit and post-review. |
| Payroll approval | Preserve existing independent preparer/approver rule | Prepared payroll moves to approved. |
| Payroll finalization | Authorized finalizer after all blocking exceptions resolved | Finance journal posting and finalized snapshot. |

### 11.3 Permission matrix

The permission registry must use the Core vocabulary (module → feature → action → data scope). Names below are proposed feature/action identifiers; implementation must register them in the central authorization registry and use exact grants.

| Role / actor | View | Create/edit | Approve/reject | Scope |
|---|---|---|---|---|
| HR Admin | Shifts, assignments, rosters, attendance, exceptions, overtime, reports | Configure and correct within granted authority | HR verification and configured approvals; emergency override only if explicitly granted | Authorized organization/branch/tenant |
| Branch Manager | Branch workforce schedules and attendance | Manage branch assignments/rosters within grant | Only where configured as approver; never self-approve own request | Assigned branch |
| Department Supervisor | Team schedules, attendance and overtime | Manage team roster/submit corrections | Supervisor overtime step and configured corrections | Direct/indirect reports or assigned team |
| Employee | Own shifts, own attendance and own requests | Submit own punch events and correction request | No self-approval | Self |
| Payroll Approver | Payroll preview/snapshots and exceptions within grant | No source mutation by virtue of approval role | Approve payroll only if independent from preparer | Configured payroll scope |
| System/Admin | Configuration screens only where explicit permission is granted | Controlled configuration | Emergency override only with reason and additional review | Explicitly granted scope |

Rules:
- Role does not automatically grant every module feature.
- Permission does not imply assignment.
- Permission does not imply approval authority.
- Employee self-punch derives employee identity from authenticated linkage.
- Branch/team scope is enforced in query and mutation services, including imports and bulk operations.
- Cross-tenant access is always denied.
- An approver must be distinct from the requester for sensitive actions.
- Emergency override cannot become a generic bypass.

### 11.4 Suggested exact feature grants

- `hr.shifts.read/write` (the implemented shift catalog API uses exact tenant grants; do not add a wildcard fallback)
- `hr.shift_assignments.view/create/edit/close`
- `hr.rosters.view/generate/override/cancel`
- `hr.attendance.view/event_create/summary_edit/correct/delete/import/export`
- `hr.attendance_anomalies.view/resolve/false_positive`
- `hr.overtime.view/submit/approve/reject/verify`
- `hr.comp_leave_credits.view/create`
- `hr.workforce_settings.view/edit`
- `hr.payroll.view/prepare/approve/finalize/lock/reverse`

The implemented shift catalog endpoints require exact `hr.shifts.read` or `hr.shifts.write` grants with `tenant` scope. Role grants are configured explicitly by Admin in Authorization; no role receives access implicitly. Do not add a wildcard permission fallback.

---

## 12. API contracts

All endpoints are proposed under the existing `/api/v1/hr` route prefix. Exact naming may follow current route conventions, but request semantics and authorization requirements are normative.

### 12.1 Shift types

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/shifts` | List active shifts; optionally include inactive definitions. |
| POST | `/shifts` | Create a shift definition. |
| GET | `/shifts/{shift_id}` | Read shift detail including its break rules. |
| PUT | `/shifts/{shift_id}` | Update name/timing before the shift is referenced; code is immutable. |
| PATCH | `/shifts/{shift_id}/active` | Activate/deactivate without hard delete. |
| GET/POST | `/shifts/{shift_id}/break-rules` | List or create paid/unpaid break rules. |
| PUT | `/shifts/{shift_id}/break-rules/{rule_id}` | Update a break rule; code is immutable. |
| PATCH | `/shifts/{shift_id}/break-rules/{rule_id}/active` | Activate/deactivate a break rule without hard delete. |

Create shift payload concept (break rules are managed through the nested break-rule endpoints):

```json
{
  "code": "DAY",
  "name": "Day Shift",
  "start_time": "09:00",
  "end_time": "18:00",
  "end_day_offset": 0,
  "break_rules": [
    {
      "code": "LUNCH",
      "name": "Lunch",
      "is_paid": false,
      "planned_duration_minutes": 45
    }
  ]
}
```

### 12.2 Shift assignments

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/shift-assignments` | Filter assignments by employee, branch, department and effective date. |
| POST | `/shift-assignments` | Create employee or department recurring assignment. |
| GET | `/shift-assignments/{id}` | Read assignment and history. |
| POST | `/shift-assignments/{id}/close` | Close at an effective date without deleting history. |

Payload must include `scope_type`, one valid target, shift ID, weekday set, `valid_from`, optional `valid_to` and optional branch context. Service validates overlaps and scope.

### 12.3 Roster

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/rosters/generate` | Idempotently generate a roster for a date range and authorized scope. |
| GET | `/rosters` | Read daily/weekly roster by date range and scope. |
| PATCH | `/rosters/{entry_id}` | Create a date-specific override with required reason. |
| POST | `/rosters/{entry_id}/cancel` | Cancel a scheduled entry with reason and audit. |

Generate payload concept:

```json
{
  "from_date": "2026-11-09",
  "to_date": "2026-11-15",
  "branch_id": "branch-id",
  "department": "Production"
}
```

### 12.4 Attendance events and summaries

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/attendance/events` | Read raw events within authorized scope. |
| POST | `/attendance/events` | Create manual/employee event; actor identity rules apply. |
| POST | `/attendance/events/{id}/void` | Controlled void/supersession with reason. |
| GET | `/attendance/monthly` | Preserve existing monthly summary API; enrich with roster and exceptions. |
| PUT | `/attendance` | Preserve legacy summary upsert for authorized HR and compatible use cases. |
| DELETE | Existing daily attendance route | Require explicit write/delete grant, employee scope and payroll-period guard; raw events are not deleted. |

Event payload concept:

```json
{
  "work_date": "2026-11-10",
  "roster_entry_id": "roster-entry-id",
  "event_type": "punch_out",
  "occurred_at": "2026-11-11T06:04:00+05:30",
  "source_reference": "client-event-uuid"
}
```

Employee self-punch requests must not accept `employee_id`; server derives the linked employee.

### 12.5 Attendance import

Preserve existing `POST /attendance/import` and add/require:
- `year`, `month`.
- `branch_id` for branch-scoped import.
- `import_timezone` IANA identifier; defaults to selected branch timezone, then tenant fallback only when branch is absent and all rows are unassigned.
- Workbook template version.
- Atomic validation and import-batch audit.

The API rejects mixed-branch workbooks, invalid timezone identifiers, payroll-frozen periods, duplicate source references and invalid event/work-date relationships.

### 12.6 Anomalies and corrections

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/attendance/anomalies` | List/filter open and historical anomalies. |
| POST | `/attendance/anomalies/{id}/resolve` | Resolve with reason and selected reviewed result. |
| POST | `/attendance/anomalies/{id}/false-positive` | Mark false positive with reason and actor. |
| POST | `/attendance/corrections` | Submit employee/supervisor/HR correction request. |
| GET | `/attendance/corrections` | List correction requests within scope. |
| POST | `/attendance/corrections/{id}/apply` | Apply only after Core workflow approval and HR validation. |

Approval decisions are routed through Core Workflow; HR endpoints must not bypass workflow state.

### 12.7 Overtime and compensatory leave

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/overtime` | List candidate and reviewed overtime. |
| POST | `/overtime/{id}/submit` | Submit candidate for configured approval. |
| POST | `/overtime/{id}/verify` | HR verification after supervisor approval. |
| POST | `/overtime/{id}/reject` | Reject with reason through workflow. |
| GET | `/comp-leave/credits` | Read earned credits; not a spendable balance. |

### 12.8 Workforce configuration and payroll

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/workforce/policies` | Read active/effective policy versions. |
| POST | `/workforce/policies` | Create a new versioned tenant policy. |
| GET | Existing payroll preview | Add schedule, anomaly and overtime warnings. |
| Existing prepare/approve/finalize endpoints | Preserve route contracts where possible; enforce new exception and snapshot rules. |

### 12.9 API error contract

Use existing FastAPI error conventions. Minimum expected outcomes:

| HTTP | Use |
|---|---|
| 400 | Invalid operation for current workflow state. |
| 401 | Unauthenticated. |
| 403 | Permission, approval authority or employee data scope denied. |
| 404 | Record absent or outside permitted visibility (avoid leaking cross-scope existence). |
| 409 | Overlap, payroll freeze, stale revision, duplicate/idempotency conflict or unresolved configuration conflict. |
| 422 | Invalid field, date/time, IANA timezone, event type or workbook validation. |

Errors must be actionable but must not disclose another tenant's or out-of-scope employee's records.

---

## 13. User interface and user flows

### 13.1 Shift Types screen

- List shift code/name, local start/end, overnight marker, active state and break summary.
- Create/edit shift and paid/unpaid break rules.
- Deactivate referenced shifts; never offer hard delete.
- Warn when a change affects future roster generation. Historical roster snapshots remain unchanged.

### 13.2 Shift Assignment screen

- Assign recurring shift to department or employee.
- Display branch, department, weekdays, effective dates and assignment source.
- Show employee-specific override clearly.
- Reject overlapping assignment conflicts with a precise explanation.
- Show history and who changed the assignment.

### 13.3 Roster Calendar

- Daily and weekly views.
- Filter by branch, department, employee and shift.
- Display scheduled, weekly off, holiday and cancelled states.
- Permit date-specific override only with reason and appropriate scope.
- Do not show employees outside the user's scope.

### 13.4 Attendance workspace

- Timeline of raw punch and break events.
- Daily summary and resolved roster.
- Late/early values and candidate overtime.
- Source comparison and anomaly badge/queue.
- Missing punch exception with correction request status.
- HR correction controls only for authorized roles.
- Employee self-service shows own shifts, own punch actions and own correction request history.

### 13.5 Overtime review

- Candidate minutes, schedule basis and source event references.
- Supervisor approve/reject/return.
- HR verification after supervisor approval.
- Rejection reason and audit history.
- Only verified payable minutes are marked payroll-eligible.

### 13.6 Payroll draft and exception panel

- Show attendance completeness by employee/work date/shift.
- Separate blocking issues from warnings.
- Show provisional calculations when punch data is incomplete but a usable daily status exists.
- Show source discrepancy and unresolved missing-punch exceptions.
- Prevent finalization until material exceptions are resolved.
- Show shift/divisor compatibility warnings and block affected payroll where the existing salary divisor cannot safely represent the schedule.

### 13.7 Workforce policy settings

- Tenant-configurable source discrepancy margin.
- Holiday/roster precedence selection.
- Compensatory-leave earning-date policy reference.
- Compensatory-leave expiry policy reference.
- Effective date and version history.
- Clear warning where a setting is required but missing.

### 13.8 Dashboard and reports

MVP reports:
- Daily attendance.
- Monthly attendance and payroll summary.
- Shift-wise attendance.
- Overtime candidate/approved/rejected/verified report.
- Missing punch and anomaly report.
- Roster coverage and weekly-off report.

Supervisor dashboard is configurable by data scope. Anomaly detection includes missing punches, overlapping shifts, excessive overtime, late/early patterns and payroll discrepancies.

---

## 14. Audit and notification requirements

### 14.1 Minimum audit events

Emit Core Audit events for:
- Shift create/update/deactivate.
- Assignment create/close/supersede.
- Roster generation, override and cancellation.
- Workforce policy create/version/change.
- Attendance event create/void/supersede.
- Excel batch upload, validation, rejection and import.
- Source anomaly create/resolve/false-positive.
- Attendance correction submit/approve/reject/apply.
- Overtime submit/approve/reject/HR verify.
- Compensatory-leave credit create.
- Payroll preview warnings, prepare, supersede, approve, finalize, lock, reverse and adjustment linkage.
- Permission/scope-denial events where supported by Core security audit.

Each event should include actor, timestamp, tenant context, employee/record reference, action, reason/correlation ID and before/after values where appropriate. Sensitive values must follow Core masking rules.

### 14.2 Notifications

Use Core Notifications for:
- Correction request submitted/returned/approved/rejected.
- Overtime awaiting supervisor review.
- Overtime awaiting HR verification.
- Missing punch or material anomaly assigned to HR.
- Roster assignment/override affecting an employee.
- Payroll finalization blocked by unresolved attendance exceptions.

Notification channels, retry and user preferences remain Core configuration; HR must not create its own notification delivery subsystem.

---

## 15. Migration and rollout plan

### 15.1 Migration principles

- Add new tables and nullable references; do not rewrite existing attendance rows.
- Preserve existing `employee_attendance` primary keys, unique employee/date constraint, statuses, punch timestamps, overtime minutes, notes and timestamps.
- Do not create historical shift assignments from department text, punch patterns or manager assumptions.
- Do not backfill a branch for employees whose organization assignment has not been verified.
- Use existing `HRBranch` and `EmployeeOrgAssignment` records.
- Preserve all existing payroll runs, payroll items, Finance journal references and reversals.
- Add a migration only after checking the current branch migration head; do not hardcode the old `hr_timezone_006` revision as the parent.
- Use `RESTRICT`/soft-deactivation semantics for new historical references where appropriate; employee offboarding must not cascade-delete roster, attendance, overtime or payroll provenance.
- Provide a downgrade plan for schema additions; do not promise data-destructive rollback of imported events.

### 15.2 Deployment sequence

1. Deploy additive schema migrations and indexes.
2. Deploy shift type and policy APIs with feature access disabled by default.
3. Configure tenant branch timezone and verified employee organization assignments.
4. Configure required workforce policies: source error margin and holiday precedence before activating related flows.
5. Create shift definitions and effective-dated assignments from a verified date.
6. Generate future rosters only.
7. Enable event capture/import and source reconciliation.
8. Enable daily summary calculation and correction workflow.
9. Enable overtime review and payroll integration only after valid policy configuration.
10. Enable shift-aware payroll finalization only after divisor compatibility checks pass.

### 15.3 Feature flags / tenant enablement

Proposed tenant capabilities:
- `hr_shift_roster_enabled`
- `hr_attendance_event_capture_enabled`
- `hr_attendance_source_reconciliation_enabled`
- `hr_overtime_approval_enabled`
- `hr_shift_aware_payroll_enabled`

A dependent capability cannot be enabled before its required policy/configuration and permission grants exist. Feature activation does not grant users permission automatically.

### 15.4 Rollback

- Disable new feature flags first.
- Keep raw events and audit records; do not delete imported source history.
- Revert to legacy attendance display/calculation only for employees without a shift assignment and only where no new payroll snapshot depends on the new model.
- If a payroll snapshot has used P0.1 inputs, use controlled payroll reversal/revision; never delete or mutate finalized history.
- Database downgrade may remove unused nullable columns/tables only if no persisted data depends on them. Destructive data rollback requires a separately approved migration plan.

---

## 16. Security, privacy and operational requirements

- Every route checks authentication, module/feature/action permission, tenant context and employee data scope.
- Employee self-service event creation derives employee identity server-side.
- Branch/team/department scope applies to list, detail, export, import, bulk generation, correction and approval routes.
- Approval authority is evaluated separately from ordinary edit permission.
- Requester/approver separation is enforced.
- Emergency override requires explicit permission, reason, audit and additional review.
- Raw attendance events are append-only; corrections are traceable.
- Historical attendance, payroll, leave-credit and audit references survive employee offboarding.
- Payroll and attendance exports are scope-checked and audited.
- Input validation protects against invalid timezone names, malformed timestamps, oversized files, duplicate source references and invalid employee/date mappings.
- Import remains atomic.
- Concurrent roster generation and event ingestion must be protected by database constraints and transactional conflict handling.
- Sensitive attendance and payroll information must not be included in broad notifications or logs.
- Audit retention, masking and detailed retention durations follow Core policy; if no Core policy is available, record as a release dependency rather than inventing a duration.

---

## 17. Acceptance criteria

### 17.1 Shift and assignment

- AC-01: HR can create, edit/version and deactivate shift types.
- AC-02: Shift definition supports normal and overnight end-day behavior.
- AC-03: Shift break rules support paid/unpaid flag, scheduled duration and actual break-event linkage.
- AC-04: Department defaults and employee-specific assignments can be created with effective dates and weekday patterns.
- AC-05: Employee-specific assignment wins over department default.
- AC-06: Date-specific roster override wins for that work date and requires a reason.
- AC-07: Overlapping/ambiguous assignments are rejected; no arbitrary assignment is selected.
- AC-08: Assignment changes do not rewrite historical roster entries.
- AC-09: One primary roster entry per employee/local work date is enforced in MVP.

### 17.2 Timezone and roster

- AC-10: Branch timezone is used for the employee's effective branch; tenant timezone is fallback.
- AC-11: Roster entries retain timezone name and resolved UTC boundaries.
- AC-12: Overnight shift work date remains the local shift-start date.
- AC-13: Employee without a shift continues using legacy calendar behavior.
- AC-14: Holiday roster override is rejected until required tenant holiday policy is configured.
- AC-15: Roster generation is idempotent and does not overwrite manual overrides or historical entries.

### 17.3 Attendance events and anomaly handling

- AC-16: Manual HR, Excel and employee punch sources create traceable raw events.
- AC-17: Employee self-punch cannot submit another employee's ID.
- AC-18: Raw events are not overwritten/deleted by later source data.
- AC-19: Equivalent source events are compared using tenant-configured error margin.
- AC-20: Margin exceeded creates an anomaly with source references and threshold snapshot.
- AC-21: No automatic last-write-wins source selection occurs.
- AC-22: One-branch workbook validation rejects mixed-branch data atomically.
- AC-23: Event workbook v2 supports next-day local datetimes for overnight shifts.
- AC-24: Missing punch is visible in payroll draft; HR correction is required before finalization.
- AC-25: Corrections retain before/after values, actor, reason and approval history.

### 17.4 Overtime and compensatory leave

- AC-26: Candidate overtime is not payable before supervisor approval and HR verification.
- AC-27: Rejected overtime remains traceable and is excluded from payroll.
- AC-28: Approved payable minutes are included exactly once.
- AC-29: Compensatory-leave credit records preserve source work date, tenant earning-date policy reference and expiry policy reference.
- AC-30: MVP does not allow credit consumption or present earned credits as a spendable balance.

### 17.5 Payroll and Finance

- AC-31: Existing salary-count modes remain available and retain their documented behavior.
- AC-32: Shift-assigned employee payroll readiness uses roster scheduled days.
- AC-33: Employees without shifts retain legacy readiness behavior.
- AC-34: Shift/working-days divisor incompatibility is flagged and cannot silently produce a finalized incorrect payroll.
- AC-35: Payroll draft can calculate with available punch data while showing unresolved exceptions.
- AC-36: Payroll finalization is blocked by unresolved material missing-punch/source anomalies.
- AC-37: Prepared/approved correction creates a controlled new revision; prior snapshot is retained as superseded.
- AC-38: Finalized/locked payroll is not silently reopened; post-finalization difference is a later-period adjustment.
- AC-39: Daily schedule/attendance/policy provenance is immutable and sufficient to reproduce payroll.
- AC-40: Existing Finance posting/reversal integration remains idempotent and regression-tested.

### 17.6 Security and quality

- AC-41: Read-only users cannot mutate or delete attendance.
- AC-42: Employee scope is enforced on every new and modified endpoint, including imports and bulk operations.
- AC-43: Cross-tenant and out-of-scope access attempts fail closed.
- AC-44: Requester cannot approve own correction/overtime/payroll request through normal workflow.
- AC-45: Emergency override records reason and requires additional review.
- AC-46: Offboarding deactivates future assignments and preserves history.
- AC-47: Migrations preserve legacy attendance and payroll data.
- AC-48: Backend, frontend, migration, authorization, tenant-isolation and regression CI pass before the feature is marked implemented.

---

## 18. Test strategy

### 18.1 Unit tests

- Shift boundary resolution and overnight work date.
- Assignment effective-date selection and precedence.
- Department default/employee override.
- Holiday policy required-config behavior.
- Branch timezone and tenant fallback.
- UTC/local conversion round-trip.
- Break rule paid/unpaid representation and paired event handling.
- Source comparison threshold behavior.
- Idempotent event ingestion.
- Missing-punch exception creation.
- Overtime payable eligibility only after HR verification.
- Compensatory-leave policy reference capture.
- Payroll schedule/divisor compatibility guard.

### 18.2 API and authorization tests

- CRUD/deactivate permissions for shifts.
- Employee/department assignment scope checks.
- Branch/department/team/self read and write scope.
- Employee self-punch cannot spoof employee ID.
- Read-only attendance user cannot delete.
- Importer cannot import another branch's employee rows.
- Mixed-branch import rejects atomically.
- Correction requester cannot approve own request.
- Overtime supervisor and HR steps are separate.
- Emergency override audit and additional review.
- Cross-tenant isolation for all new tables and APIs.

### 18.3 Integration and regression tests

- Legacy employee without shift retains current attendance and payroll behavior.
- Shift-assigned employee payroll readiness uses roster.
- Weekly off is not a missing attendance day.
- Date override schedules a normally off day.
- Holiday roster conflict requires tenant policy.
- Overnight shift crosses midnight correctly.
- Overnight shift crosses month boundary and is allocated to start-date month.
- Multiple source events create anomaly above configured margin.
- Source discrepancy below/equal threshold does not create mismatch anomaly.
- Missing punch appears in draft and blocks finalization until corrected.
- Prepared/approved payroll correction supersedes prior revision and creates a new revision.
- Finalized correction becomes later-period adjustment.
- Payroll-to-Finance journal posting/reversal remains correct.
- Employee end-date and joining-date counters remain correct.
- Existing salary-count mode tests remain unchanged unless a documented approved migration updates them.

### 18.4 Required verification record

Before release, record actual results for:
- Backend focused HR tests.
- Full backend suite.
- Database migration upgrade and downgrade checks on supported engines.
- Tenant provisioning/migration lifecycle.
- Frontend typecheck and production build.
- Browser smoke tests for shift, roster, attendance and payroll exception screens.
- Authorization and tenant-isolation tests.
- Finance posting/reversal regressions.

A test plan is not a test result. Do not mark CI passed until the run exists and is green.

---

## 19. Implementation work breakdown

| Work package | Deliverable | Dependency / exit condition |
|---|---|---|
| P0.1-00 Baseline verification | Re-run current tests/CI for existing timezone and DELETE fixes; verify branch/team scope on attendance routes; verify AUD-08 | **Complete** — AUD-05–AUD-08 verified; integrated CI and tenant-isolation checks passed. |
| P0.1-01 Schema/migrations | Initial slice delivered: shift types, break rules, assignments, roster entries and workforce policy versions. Attendance event, import batch, anomaly, correction, overtime, comp-leave credit and payroll daily snapshot tables remain subsequent migrations. | **In progress** — migration `p0_hr_shift_roster_016` and PostgreSQL migration/provisioning CI passed. |
| P0.1-02 Shift catalog | Shift type and break configuration APIs/UI | Permission and audit tests pass. |
| P0.1-03 Assignment engine | Department defaults, employee overrides, effective dates and conflict validation | **Core resolver implemented and unit-tested** — APIs, audit integration and authorization wiring remain pending. |
| P0.1-04 Roster engine | Idempotent generation, date overrides, weekly-off/holiday states | Roster constraints and scope tests pass. |
| P0.1-05 Timezone engine | Branch timezone with tenant fallback, overnight boundaries, branch-scoped import context | **Shift-window core implemented** — UTC boundary and DST rejection tests pass; branch-aware attendance/import context remains pending. |
| P0.1-06 Attendance event intake | Manual, employee and Excel raw event ingestion; legacy summary compatibility | Event idempotency and import atomicity pass. |
| P0.1-07 Reconciliation | Tenant margin setting, source comparison, anomaly queue and resolution | No last-write-wins; anomaly tests pass. |
| P0.1-08 Attendance summary/correction | Daily summary projection, missing punch exception, correction workflow | HR correction and audit tests pass. |
| P0.1-09 Overtime | Candidate calculation, supervisor approval, HR verification | Payable gating tests pass. |
| P0.1-10 Payroll integration | Shift-aware readiness, divisor safety guard, daily snapshot, exception blocking, revisions | Payroll and Finance regressions pass. |
| P0.1-11 Reports/UI | Roster, attendance, overtime and exception screens/reports | Frontend typecheck/build and browser smoke pass. |
| P0.1-12 Release hardening | Authorization, tenant isolation, audit, migration, CI and documentation | All applicable acceptance criteria pass. |

Recommended order: P0.1-00 is complete. The initial shift schema and tested resolver are committed. Next implement shift catalog and assignment APIs with scope enforcement/audit, then idempotent roster generation and date-specific overrides. Do not implement payroll shift logic ahead of a persisted, tested roster.

---

## 20. MVP configuration checklist

A tenant cannot activate the corresponding capability until the required configuration is present.

| Configuration | Required before |
|---|---|
| Valid tenant IANA timezone | Any local time interpretation. |
| Valid branch IANA timezone for assigned branch | Branch-based shift/attendance use. |
| Verified employee branch/department organization assignment | Branch/department schedule and scoped supervisor access. |
| Active shift type and valid break definitions | Assigning/generating a shift roster. |
| Non-overlapping effective shift assignment | Roster generation. |
| Holiday/roster precedence policy | Scheduling work on a calendar holiday. |
| Attendance source error margin | Automated source discrepancy anomaly detection. |
| Correction workflow and approver configuration | Employee/supervisor correction submissions. |
| Supervisor-to-HR overtime workflow | Overtime can become payable. |
| Overtime eligibility/rate/rounding policy | Payroll inclusion of overtime. |
| Compensatory-leave earning-date and expiry policy references | Creating compensatory-leave credit. |
| Salary divisor compatibility | Shift-aware payroll finalization. |
| Explicit permissions and data scopes | User access to every protected P0.1 feature. |

---

## 21. Deferred post-MVP register

The following items were explicitly deferred by the project user. Keep them visible in the backlog and revisit after MVP. They are not cancelled.

| ID | Deferred detail |
|---|---|
| T-01 | Further department/employee assignment precedence beyond employee-specific assignment wins. |
| T-02 | Detailed break calculation edge cases, fallback and rounding. |
| T-03 | Further missing-punch calculation and exception policy beyond the approved payroll-draft/HR-correction/finalization rule. |
| T-04 | Detailed late/early threshold and consequence matrix. |
| T-05 | Detailed overtime eligibility, rate, threshold and rounding configuration. |
| T-06 | Full holiday/roster precedence and holiday-work calculation matrix beyond required tenant policy selection. |
| T-07 | Full interaction of employee-specific scheduled days with working-days absence divisor and monthly salary proration. |
| T-08 | Compensatory-leave expiry execution, balance and redemption lifecycle. |
| T-09 | Further payroll adjustment/reopening rules beyond approved revision and next-period adjustment behavior. |
| T-10 | Advanced approval fallback/delegation details beyond audited emergency override. |
| T-11 | Advanced raw punch source priority and duplicate detection beyond idempotency and anomaly comparison. |
| T-12 | Device integration, offline capture and synchronization. |
| T-13 | Detailed audit retention, masking and sensitive attendance access policy. |
| T-14 | Further shift assignment conflict/overlap cases beyond MVP validation. |

**Deferred-work rule:** Do not invent behavior for a deferred item. If an implementation task encounters a case that cannot be safely completed without one of these decisions, stop that narrow path, record the blocker and request the smallest necessary decision.

---

## 22. Release gates and definition of done

P0.1 may be called **implemented** only when:

1. The product decisions and this architecture are approved by the project owner.
2. Database migrations are reviewed, additive where possible and tested.
3. Shift types, assignments and roster generation work as specified.
4. Branch timezone, tenant fallback and overnight work-date behavior pass tests.
5. Manual, Excel and employee punch events are traceable and idempotent.
6. Source comparison uses tenant-configured margin and never silently overwrites source records.
7. Missing punches and correction workflows behave as approved.
8. Overtime is excluded until supervisor approval and HR verification.
9. Compensatory-leave credits preserve tenant policy references and are not spendable.
10. Payroll readiness and snapshots preserve legacy behavior and prevent unsafe divisor use.
11. Finalized payroll remains immutable and Finance journal/reversal integrity is preserved.
12. Tenant isolation, employee scope, separation of duties and audit tests pass.
13. Backend, frontend, migration and browser CI results are recorded as passing.
14. Documentation and implementation tracker are updated.
15. Changes are committed to the agreed integration branch and pass required code review/CI; merging the integration PR into `main` remains a separate explicit authorization.

### Current gate status

- Product decisions: **Approved by project owner.**
- MVP architecture: **Approved for implementation by project owner on 9 November 2026.**
- Contributor architecture review: **Not a prerequisite; no longer a release gate.**
- Implementation authorization: **Approved on 9 November 2026.**
- Code implementation: **In progress** — initial shift schema/migration and effective-dated shift assignment resolver committed.
- Test/CI verification: **Initial implementation verified** — integrated Minitally CI #42519334843 passed; backend 123 passed, 5 skipped, 7 warnings; tenant-isolation #42519334849 passed; PostgreSQL migrations/provisioning, frontend typecheck/build and Playwright smoke passed. Remaining P0.1 capabilities are not yet implemented.

---

## 23. Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 9 November 2026 | Initial complete P0.1 MVP architecture based on HR Decision Register v1.0; defines ownership, schedule resolution, entities, attendance event processing, source reconciliation, approvals, payroll integration, APIs, UI, migrations, security, tests, implementation packages and deferred post-MVP decisions. Status subsequently updated after owner authorization and initial schema/resolver implementation; no approved product decisions were reopened. |

**End of specification.**
