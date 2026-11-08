# Nexora HR Enhancement Specification v1.1
## P0.1 — Shift & Roster Management

**Document ID:** NEX-HR-ENH-001  
**Version:** 1.1 — P0.1  
**Status:** Historical audit and design draft — superseded for approved MVP architecture by [P0.1 Architecture Specification v1.0](NEXORA_HR_P0.1_ARCHITECTURE_SPECIFICATION_v1.0.md)  
**Date:** 8 November 2026  
**Module:** HR & Payroll  
**Priority:** P0.1  
**Related implementation tracker:** [Nexora HR & Payroll — Implementation Status and Next Work](NEXORA_HR_PAYROLL_IMPLEMENTATION_STATUS_v1.0.md)  
**Related decision register:** [Nexora HR — Final Product Decision Register v1.0](NEXORA_HR_DECISION_REGISTER_v1.0.md)  
**Related roadmap:** [Nexora HR — High-Value Implementation Roadmap v1.0](NEXORA_HR_HIGH_VALUE_IMPLEMENTATION_ROADMAP_v1.0.md)  
**Repository branch audited:** `docs/hr-phase-2-implementation-status`

> This is an enhancement specification for review. It does not replace or silently modify the locked HR baseline specification. Implementation must begin only after the scope, decisions, migrations and acceptance criteria are approved by both project contributors.

> **Document status note (9 November 2026):** Retained for its existing attendance/payroll source audit and design history. Its proposed defaults and Section 19 decision questions are superseded by the approved [HR Decision Register v1.0](NEXORA_HR_DECISION_REGISTER_v1.0.md) and the completed [P0.1 Architecture & MVP Implementation Specification v1.0](NEXORA_HR_P0.1_ARCHITECTURE_SPECIFICATION_v1.0.md). Use the architecture specification for current MVP design. No implementation or test completion is implied.

---

# Part A — Existing attendance implementation audit

## 1. Audit objective and method

The current attendance implementation was inspected before designing shift and roster functionality. The audit focused on:

- Attendance database models and constraints.
- Attendance API endpoints and validation.
- Manual attendance entry and monthly attendance UI.
- Excel template and import behavior.
- Calendar and weekly-off configuration.
- Payroll attendance readiness and calculation logic.
- Timezone conversion.
- Payroll snapshot and post-preparation input protections.
- Existing attendance/payroll tests.

**Audit type:** Static source-code inspection of the integration branch.  
**Tests executed as part of this audit:** None. Existing test source was inspected; no new code was changed and no new test run is claimed here.

### Source files inspected

- [HR payroll and attendance models](../backend/app/modules/hr/payroll.py)
- [Payroll and attendance schemas](../backend/app/modules/hr/payroll_schemas.py)
- [HR payroll and attendance API routes](../backend/app/api/routes/hr_payroll.py)
- [Payroll migration](../backend/alembic/versions/hr_payroll_005.py)
- [Timezone migration](../backend/alembic/versions/hr_timezone_006.py)
- [Payroll and attendance tests](../backend/tests/test_hr_payroll.py)
- [Payroll workspace UI](../frontend/src/components/hr-payroll-panel.tsx)

---

## 2. Existing data model

### 2.1 HR payroll settings

Current model: `HRPayrollSettings`  
Table: `hr_payroll_settings`

Current settings include:

| Field | Current behavior |
|---|---|
| `salary_count_mode` | `working_days`, `calendar_days`, or `fixed_days` |
| `monthly_salary_days` | Fixed monthly salary divisor, default 26 |
| `week_off_days` | Tenant-level weekday list; default Saturday and Sunday |
| `timezone` | Tenant IANA timezone; default `Asia/Kolkata` |

The current implementation retrieves a singleton settings row using ID 1 within the tenant database.

### 2.2 HR calendar

Current model: `HRCalendarDay`  
Table: `hr_calendar_days`

- Stores a date, day type and description.
- Supported day types are `working_day`, `holiday` and `week_off`.
- The unique key is the date.
- Calendar overrides take precedence over default tenant week-off weekdays.
- The calendar is tenant-wide; it is not currently branch- or shift-specific.

### 2.3 Employee attendance

Current model: `EmployeeAttendance`  
Table: `employee_attendance`

| Field | Current purpose |
|---|---|
| `id` | Attendance record identifier |
| `employee_id` | Employee reference |
| `work_date` | Attendance calendar date |
| `status` | Daily status |
| `punch_in` | Optional timestamp |
| `punch_out` | Optional timestamp |
| `overtime_minutes` | Daily overtime input |
| `note` | Attendance note |
| `updated_at` | Last update timestamp |

**Critical constraint:** A unique constraint exists on `employee_id + work_date`. The current model therefore supports only one attendance summary record per employee per date.

There is no shift ID, roster ID, raw punch-event table, break-event table, shift assignment reference or per-shift attendance segment in this model.

### 2.4 Current attendance statuses

The schema accepts:

- `present`
- `absent`
- `half_day`
- `paid_leave`
- `unpaid_leave`
- `paid_half_day`
- `unpaid_half_day`
- `unmarked`

The `unmarked` value is used by the API/import workflow to clear an existing attendance record. It is not a persisted attendance status.

---

## 3. Existing attendance workflows

### 3.1 Manual attendance

The current monthly attendance API is:

- `GET /api/v1/hr/attendance/monthly`
- `PUT /api/v1/hr/attendance`
- `DELETE /api/v1/hr/attendance/{employee_id}/{work_date}`

The monthly UI renders one row per calendar date for the selected employee. HR can set the daily status, punch-in, punch-out, overtime minutes and note.

The PUT endpoint converts naive punch timestamps from tenant-local time to UTC, checks that punch-out is later than punch-in, and creates or updates the one employee/day record.

### 3.2 Excel attendance import

Current endpoints:

- `GET /api/v1/hr/attendance/template`
- `POST /api/v1/hr/attendance/import`

Current workbook contract:

| Column | Meaning |
|---|---|
| Employee Code | Active employee code |
| Work Date | Date within the selected payroll month |
| Status | One of the supported attendance statuses |
| Overtime Minutes | Integer from 0 to 1440 |
| Punch In | Optional time |
| Punch Out | Optional time |
| Note | Optional note |

Current safeguards:

- Workbook size is limited to 5 MB.
- Import is limited to 10,000 non-empty rows.
- Exact worksheet name and column headers are required.
- Duplicate employee/date pairs are rejected.
- The entire workbook is validated before database writes begin.
- Any invalid row rejects the whole workbook.
- `unmarked` clears an existing employee/day record.
- Import is blocked when the selected payroll period already has a prepared, approved, finalized or locked snapshot.
- The import is audited.

**Important limitation:** The current Excel template stores punch-in and punch-out as times only. It cannot express a punch-out date on the following day, so it cannot reliably represent an overnight shift.

### 3.3 Calendar and weekly offs

The current calendar is based on:

1. Tenant-wide default week-off weekdays.
2. Tenant-wide date overrides.
3. No employee-specific or shift-specific working-day pattern.

A date override takes precedence over the default week-off rule.

---

## 4. Existing payroll dependency on attendance

The payroll calculation currently depends directly on the daily attendance model and global calendar settings.

### 4.1 Salary count divisor

The current divisor is calculated using one of three modes:

| Mode | Current divisor |
|---|---|
| `working_days` | Number of dates in the month classified as `working_day` by tenant week-offs and calendar overrides |
| `calendar_days` | Number of calendar days in the month |
| `fixed_days` | Configured fixed monthly days, bounded from 1 to 31 |

The current calculation does not resolve an employee-specific shift schedule.

### 4.2 Absence and leave deduction

- An absence or unpaid leave creates an unpaid equivalent only when the date is considered a scheduled working day by the current tenant calendar.
- Half-day and unpaid-half-day statuses contribute fractional unpaid equivalents.
- Absence deduction uses the configured salary basis and is capped at the effective monthly gross.
- Holidays and default week-offs do not create absence deductions under the current calendar logic.

### 4.3 Overtime

Current behavior:

- Overtime is stored as integer minutes on the employee/day attendance record.
- Overtime is included in payroll only for attendance statuses `present` and `half_day`.
- Overtime is counted only when the attendance date falls inside the employee's employment period.
- Current overtime pay formula is based on daily rate divided by 8 hours, multiplied by overtime hours.
- The current model does not contain a separate overtime approval record, shift duration, scheduled end time or overtime policy.

This is a payroll calculation rule, not yet a complete overtime policy. Do not assume the current formula is legally or contractually correct for every customer.

### 4.4 Payroll readiness

Before preparing payroll, the current readiness check requires explicit attendance statuses for each scheduled working day for active salaried employees, excluding dates outside known employment dates.

The readiness calculation uses the tenant calendar and week-off list. It does not use an employee shift or roster because those records do not exist yet.

### 4.5 Payroll snapshot protection

The existing implementation protects payroll input integrity:

- Attendance and calendar inputs cannot be changed for a period with a prepared, approved, finalized or locked payroll run.
- Salary profile and payroll setting changes are blocked while prepared or approved snapshots exist.
- Payroll preparation stores employee-level payroll items.
- Finalized/locked payroll is handled through the controlled payroll workflow and reversal process.

Shift and roster integration must preserve these protections. A schedule change must not silently recalculate an existing payroll snapshot.

---

## 5. Audit findings and risk register

| ID | Finding | Risk | Required action |
|---|---|---|---|
| AUD-01 | Attendance is one row per employee per calendar date | Cannot represent multiple shift segments or multiple attendance summaries on one day | Preserve the daily summary contract initially; introduce separate shift/roster records rather than adding only a shift field |
| AUD-02 | No shift type, shift assignment or roster models exist in the inspected HR payroll model | Payroll readiness and attendance cannot determine employee-specific scheduled workdays | Add effective-dated shift definitions and roster/assignment records |
| AUD-03 | Payroll working-day divisor and missing-attendance readiness use tenant-wide week-offs/calendar | Employees on different shifts or weekly-off patterns may be incorrectly marked missing or deducted | Make attendance readiness and absence evaluation shift-aware while retaining legacy behavior for employees without a shift during migration |
| AUD-04 | Overnight shifts are not represented by the Excel template's time-only punch fields | Punch-out on the next date cannot be imported reliably | Change the import contract to accept explicit local datetimes or a documented next-day offset |
| AUD-05 | Excel parser converts Punch In using tenant timezone but constructs Punch Out with UTC directly | Imported punch-out timestamps are offset incorrectly for non-UTC tenants; in India, a local 17:00 punch-out is stored as 17:00 UTC rather than 11:30 UTC | Correct timezone conversion and replace the current test expectation with an explicit UTC/local round-trip test |
| AUD-06 | Daily attendance DELETE endpoint uses the shared payroll read dependency and does not declare an explicit write permission dependency | A user with read permission may be able to clear attendance | Require explicit `hr/payroll/write` or a dedicated attendance-delete permission; add negative authorization tests |
| AUD-07 | Attendance routes use tenant-level permission scope and do not show employee branch/team scope filtering in these handlers | HR users may access or alter employees outside their intended data scope if route grants permit tenant scope | Apply server-side employee scope checks consistently to attendance read/write/import/delete |
| AUD-08 | Attendance counters for present/half/absent/leave are incremented before the employment-period check | Stale attendance rows outside an employee's employment dates can inflate day totals even where deductions/overtime are excluded | Filter or explicitly classify out-of-employment attendance before payroll summary counters |
| AUD-09 | Overtime is a daily editable minute value without a dedicated approval or policy record | Unapproved or unsupported overtime can flow into payroll | Define supervisor approval and payroll inclusion policy before treating overtime as payable |
| AUD-10 | Branch records have timezone metadata, but attendance conversion currently resolves the tenant payroll timezone | Branch-local time handling is not yet aligned with multi-branch scheduling | Decide timezone resolution for a shift/roster; do not assume branch timezone is already applied |
| AUD-11 | Payroll items snapshot aggregate day totals and overtime minutes, not roster/shift provenance | A future shift-based payroll calculation may be difficult to explain or reproduce | Snapshot schedule/shift references and calculation basis for each payroll period |

### 5.1 Severity and implementation gate

**Must resolve before or within P0.1 implementation:**

- AUD-01, AUD-02, AUD-03, AUD-04, AUD-05, AUD-06, AUD-07, AUD-08, AUD-10 and AUD-11.

**Must resolve before overtime is treated as approved payable time:**

- AUD-09.

The timezone import defect and DELETE authorization gap are existing defects. They should be tracked as explicit corrective tasks and not hidden inside the shift feature.

---

# Part B — P0.1 target specification

## 6. Objective

Introduce shift definitions, effective-dated employee shift assignments and date-specific rosters, then make attendance and payroll readiness understand the expected work schedule without breaking the existing monthly attendance and payroll contracts.

The first release should support manufacturing teams with normal, rotating-by-date and overnight shifts, while keeping the payroll engine's salary counting modes available.

## 7. Scope

### In scope

1. Shift type configuration.
2. Effective-dated shift assignment.
3. Daily/weekly roster visibility.
4. Employee-specific scheduled workdays and weekly offs.
5. Overnight shift boundary handling.
6. Shift-aware attendance presentation and calculation inputs.
7. Shift-aware payroll readiness.
8. Shift-aware absence/unpaid-time calculation.
9. Overtime capture with explicit approval boundary.
10. Audit, authorization, tenant isolation and payroll snapshot safeguards.
11. Correct timezone handling for manual and Excel attendance.
12. Migration compatibility with existing daily attendance records.

### Out of scope for P0.1

- Biometric device integration.
- Facial recognition.
- GPS/geofencing attendance.
- Employee self-service mobile check-in application.
- Complex split shifts with multiple paid segments per employee per work date.
- Automated statutory overtime compliance.
- Automatic wage-rule interpretation.
- Production-machine or job-level labor costing.
- Advanced shift bidding or employee shift-swap marketplace.
- Automatic roster optimization.

---

## 8. Recommended business decisions for v1.1

These are proposed defaults to confirm during joint review.

| Decision | Proposed v1.1 default |
|---|---|
| Primary shift per employee per work date | One primary shift per employee per local work date |
| Overnight shifts | Supported; shift belongs to the local date on which it starts |
| Multiple shifts in one day | Not in MVP; data model must not make future support impossible |
| Shift assignment | Effective-dated recurring assignment, with date-specific roster override |
| Weekly offs | Defined by assigned schedule/roster; not inferred solely from tenant defaults once an employee has a shift assignment |
| Public holidays | Tenant calendar remains the baseline; branch-specific calendars are a later extension unless required by the first deployment |
| Time storage | Store punch instants in UTC; resolve local time using the applicable shift/branch timezone |
| Work date | Local shift-start date, including for overnight shifts |
| Attendance daily summary | Keep one employee/day summary for compatibility in v1.1 |
| Overtime | Captured separately and requires supervisor approval before being included as payable overtime |
| Existing employees without shifts | Continue using the legacy calendar behavior until HR assigns a shift; do not invent assignments |

These decisions are not final until approved by both contributors.

---

## 9. Proposed conceptual data model

The model should separate the employee's expected schedule from actual attendance.

### 9.1 Shift type

Proposed table: `hr_shift_types`

| Field | Purpose |
|---|---|
| `id` | Stable identifier |
| `code` | Tenant-unique shift code |
| `name` | Display name |
| `start_time` | Local scheduled start time |
| `end_time` | Local scheduled end time |
| `ends_next_day` | Explicit overnight marker or deterministic derived behavior |
| `break_minutes` | Planned unpaid/paid break duration; policy must define treatment |
| `grace_minutes` | Late-arrival grace threshold |
| `early_exit_grace_minutes` | Early-exit tolerance |
| `timezone` | Optional IANA timezone override; otherwise resolved from branch/tenant policy |
| `active` | Whether new assignments may use this shift |
| `created_at`, `updated_at` | Audit timestamps |

Validation:

- Start and end times must be valid.
- Overnight behavior must be explicit and unambiguous.
- Break duration and grace periods cannot be negative.
- Shift code must be unique within the tenant.
- A shift referenced by historical assignments cannot be physically deleted; deactivate it instead.

### 9.2 Effective-dated shift assignment

Proposed table: `employee_shift_assignments`

| Field | Purpose |
|---|---|
| `id` | Assignment identifier |
| `employee_id` | Employee reference |
| `shift_type_id` | Shift definition |
| `valid_from` | Inclusive effective start date |
| `valid_to` | Inclusive optional end date |
| `week_pattern` | Scheduled weekdays or referenced schedule pattern |
| `branch_id` | Optional branch context where assignment applies |
| `source` | Assignment origin: individual, team, import or roster override |
| `created_by`, `created_at` | Audit attribution |

Rules:

- Assignment dates are interpreted in the applicable local work-date context.
- Overlapping primary assignments for the same employee are rejected unless an explicit override rule applies.
- Changes close or supersede prior effective-dated assignments; they do not rewrite history.
- A new assignment must not modify already prepared or finalized payroll inputs without controlled reversal/revision.
- Branch and reporting scope validation must use existing effective-dated employee organization assignments where available.

### 9.3 Date-specific roster

Proposed table: `hr_shift_roster_entries`

| Field | Purpose |
|---|---|
| `id` | Roster entry identifier |
| `employee_id` | Employee reference |
| `shift_type_id` | Assigned shift for the work date |
| `work_date` | Local shift-start date |
| `source_assignment_id` | Recurring assignment that generated the roster entry |
| `status` | Scheduled, weekly off, holiday, cancelled or other approved state |
| `is_override` | Whether the entry overrides recurring assignment |
| `reason` | Reason for override |
| `created_by`, `updated_by` | Audit attribution |

Rules:

- At most one primary roster entry per employee per work date in P0.1.
- A roster override must have a reason and audit record.
- A generated roster must preserve the assignment version/source that generated it.
- Roster changes for payroll-locked periods are blocked.
- The system must not silently regenerate historical rosters after an assignment changes.

### 9.4 Attendance compatibility

For v1.1, retain the existing `employee_attendance` daily summary contract and its current employee/date uniqueness.

Do not simply add `shift_id` to the existing table and treat it as a complete shift model.

The attendance summary should be associated with the resolved roster entry through a nullable reference or an equivalent immutable provenance record after migration design is approved.

If the implementation requires multiple raw punch events, model them separately in a future extension rather than overloading the one daily summary row.

**Migration must preserve all existing attendance IDs, employee/date pairs, statuses, punches, overtime minutes, notes and timestamps.**

---

## 10. Attendance calculation rules

### 10.1 Schedule resolution

For each employee and local work date:

1. Resolve a date-specific roster override if one exists.
2. Otherwise resolve the effective-dated shift assignment.
3. Otherwise use legacy tenant week-off/calendar behavior for employees not yet migrated to shift scheduling.
4. Resolve holiday/week-off status using the agreed calendar precedence.
5. Persist or otherwise make reproducible the resolved schedule basis used for attendance and payroll.

### 10.2 Overnight shifts

Example: Shift A starts at 22:00 on 10 November and ends at 06:00 on 11 November.

- `work_date` is 10 November, the local shift-start date.
- Expected shift end is 11 November at 06:00 local time.
- Punch timestamps are stored as UTC instants.
- UI displays local time in the applicable timezone.
- Punch-out after midnight belongs to the 10 November shift attendance summary.
- Payroll period allocation must be explicitly defined for a shift crossing month-end. Proposed default: allocate the shift to its local shift-start work date; confirm this with payroll policy before implementation.

### 10.3 Late entry and early exit

- Compare actual punch-in to scheduled shift start plus grace period.
- Compare actual punch-out to scheduled shift end minus allowed early-exit grace.
- Do not automatically convert late/early minutes into salary deductions in P0.1.
- Record calculated deviations for review/reporting.
- Payroll deduction behavior requires an explicit approved policy in a later enhancement.

### 10.4 Missing punches

- A scheduled employee-day with no attendance status remains a payroll readiness issue.
- A present status with a missing punch should be a configurable warning or blocker according to the approved attendance policy.
- Overnight shifts must not be marked incomplete at midnight merely because their scheduled end is on the next date.
- Manual correction must be audited and permission-controlled.

### 10.5 Weekly offs and holidays

- Employee-specific schedule determines expected workdays once a shift assignment exists.
- Tenant calendar remains a baseline source for holidays in the first release.
- A roster override can explicitly schedule a person on a normally non-working date.
- The payroll calculation must distinguish a normal scheduled day, weekly off, holiday, and a scheduled shift on a holiday.
- Holiday-work compensation is out of scope until the relevant policy is specified.

---

## 11. Payroll integration contract

This is the most important section for preventing regressions.

### 11.1 Salary divisor modes remain available

Do not remove or silently redefine:

- `working_days`
- `calendar_days`
- `fixed_days`

For v1.1, define how the existing `working_days` mode interacts with employee-specific roster days before implementation. Proposed approach:

- The tenant-wide divisor remains the existing compatibility default for legacy employees.
- Shift-assigned employees use their eligible scheduled days for attendance completeness and absence calculations.
- Monthly gross proration and daily-rate divisor behavior must be separately specified and tested; do not assume that changing the absence divisor should also change monthly gross.

### 11.2 Payroll readiness

Replace the current global-calendar-only missing-attendance calculation with a schedule resolver:

- For shift-assigned employees, require explicit attendance for each scheduled roster work date.
- Do not require attendance on assigned weekly-off or non-working dates unless a roster override schedules work.
- For employees without an assignment, preserve current legacy readiness behavior.
- Include employee, work date, shift and reason in missing-attendance diagnostics.

### 11.3 Absence and leave deductions

- Apply absence/unpaid leave deductions only to dates classified as scheduled work for that employee.
- Paid leave remains paid according to the assigned leave policy.
- Half-day and paid/unpaid half-day semantics must remain compatible.
- A roster change must not retrospectively change an already calculated payroll run.
- Confirm how leave on a scheduled holiday or weekly off is treated before implementing.

### 11.4 Overtime

P0.1 should separate overtime capture from overtime approval.

Proposed flow:

1. Attendance records actual punch times and/or reported overtime.
2. System calculates candidate overtime against scheduled shift boundaries and configured break rules.
3. Supervisor reviews and approves/rejects overtime.
4. Payroll consumes only approved payable overtime.
5. Payroll snapshot records approved minutes and the rule basis.

Until this approval workflow is implemented, retain the current overtime behavior only as a legacy compatibility path and label it clearly. Do not silently reinterpret existing overtime minutes.

### 11.5 Payroll snapshot provenance

A prepared payroll run must preserve enough information to explain its calculation later, including:

- Resolved shift/roster reference or immutable snapshot.
- Employee local work date.
- Scheduled start/end instants or local schedule plus timezone.
- Attendance status and relevant punch instants.
- Approved overtime minutes and approval reference.
- Salary count mode and divisor.
- Calendar/holiday classification.
- Calculation version or rule identifier.

The implementation may choose normalized snapshot tables or structured snapshot payloads, but finalized payroll must not depend on reading mutable current shift definitions to reproduce past results.

### 11.6 Existing payroll freeze protections

All new roster/assignment/attendance mutation endpoints must use the existing payroll period guard or a stronger period-aware equivalent.

- Prepared/approved/finalized/locked periods must not accept silent schedule or attendance mutation.
- Corrections after finalization must follow the controlled reversal/revision process.
- Schedule generation must be idempotent.
- Re-running a generation job must not duplicate roster entries.

---

## 12. Timezone requirements

The existing tenant timezone is an IANA timezone. Branch records also store timezone metadata, but current attendance conversion uses the tenant payroll timezone.

P0.1 must make an explicit timezone resolver decision:

1. Branch timezone for the employee's effective branch assignment on the shift work date; otherwise
2. Tenant timezone as fallback.

If the team chooses tenant timezone only for the first release, document this as a deliberate limitation and do not imply branch-local time is already supported.

All punch instants must be stored in UTC. Local schedule boundaries must be converted using the resolved IANA timezone. Do not construct one endpoint as UTC while interpreting the other as tenant-local time.

**Corrective task AUD-05:** Fix Excel Punch Out conversion so it uses the same timezone conversion path as Punch In and manual attendance. Update tests to assert UTC storage and local-time round-trip, not merely the raw UTC hour.

---

## 13. API and UI scope

Exact endpoint names are subject to the repository's API conventions and authorization registry.

### 13.1 Proposed API capabilities

| Capability | Proposed operation |
|---|---|
| Shift types | List, create, update, deactivate |
| Shift assignments | List, create, update/close, inspect history |
| Roster | Generate, list by date range/employee/team, create override, cancel/replace |
| Attendance | Monthly view enriched with scheduled shift and deviations |
| Attendance correction | Correct status/punches with reason and audit |
| Payroll readiness | Return missing attendance by employee/date/shift |
| Overtime | List candidate overtime, approve/reject with reason |

All write operations require explicit feature/action grants. Read/write/delete operations must not inherit access from a read-only dependency.

### 13.2 Proposed UI areas

1. **Shift Types:** configure shift start/end, overnight, breaks and grace periods.
2. **Shift Assignments:** assign a recurring shift to an employee with effective dates and weekly pattern.
3. **Roster Calendar:** view shifts by employee/team/date and apply controlled overrides.
4. **Attendance:** show scheduled shift, actual punch times, late/early deviations and status.
5. **Payroll Readiness:** show missing attendance and shift-related blockers.
6. **Overtime Review:** supervisor approval of candidate overtime.

### 13.3 Permissions and data scopes

Reuse Nexora Core authorization and data-scope services.

At minimum define exact grants for:

- Shift type read/write/deactivate.
- Shift assignment read/create/update/close.
- Roster read/generate/override/cancel.
- Attendance read/write/correct/delete.
- Overtime read/approve/reject.

Apply tenant, branch, department, team and self scopes as appropriate. Do not rely on frontend filtering.

---

## 14. Migration and backward compatibility

### 14.1 Migration principles

- Do not delete or rewrite existing attendance records.
- Do not fabricate historical shift assignments.
- Existing employees without an assigned shift continue on legacy calendar logic.
- New shift assignment starts from an explicit effective date.
- Add nullable provenance fields or new related tables without making legacy rows invalid.
- Avoid changing the unique employee/date attendance constraint in P0.1 unless an approved use case requires multiple daily shift segments.
- Provide a rollback strategy and test migration on supported database engines.

### 14.2 Backfill policy

Do not infer historical shift assignments from department names, punch times or attendance notes. HR must explicitly assign shifts from a verified date.

### 14.3 Payroll history

Historical payroll runs and payroll items remain unchanged. New schedule snapshots apply only to payroll periods prepared after the approved feature release.

---

## 15. Security, audit and operational controls

- Every shift definition, assignment and roster override mutation must be audited.
- Every attendance correction must retain before/after values and actor/reason.
- Overtime approval must retain approver, decision, timestamp and reason.
- Read-only users must not be able to delete or mutate attendance.
- All employee-targeted operations must enforce tenant and employee data scope on the backend.
- Do not expose punch or roster information outside the user's permitted scope.
- Concurrent roster generation and attendance updates must be protected against duplicate/overlapping records.
- Deactivated shifts cannot be assigned to future rosters.
- Historical assignments and payroll snapshots must remain queryable after employee separation.

---

## 16. Required test matrix

### 16.1 Shift definition and assignment

- Valid day shift.
- Valid overnight shift.
- Invalid start/end configuration.
- Negative break/grace values.
- Duplicate shift code.
- Inactive shift cannot be assigned to a future date.
- Assignment effective-date boundaries.
- Overlapping assignment rejection.
- Assignment change preserves historical assignment.
- Tenant isolation for shift types and assignments.

### 16.2 Roster

- Generate roster for a normal week.
- Generate roster for rotating weekdays.
- Weekly off is not treated as missing attendance.
- Date-specific override schedules a normally off day.
- Repeated generation is idempotent.
- Concurrent generation does not duplicate employee/date entries.
- Roster change is blocked for frozen payroll period.
- Supervisor can only view/update permitted team or branch.

### 16.3 Attendance and timezone

- Normal shift punch-in/out.
- Overnight shift punch-out next day.
- Local-to-UTC conversion and UTC-to-local round-trip.
- Excel import uses the same timezone behavior as manual API entry.
- Excel import rejects malformed timestamps.
- Missing punch detection.
- Duplicate employee/date import rejection.
- Import atomicity when one row is invalid.
- Attendance correction retains original values and reason.
- Read-only user cannot delete attendance.
- Cross-tenant and out-of-scope employee access is denied.

### 16.4 Payroll regression

- Legacy employee without shift uses existing calendar behavior.
- Shift-assigned employee readiness uses roster days.
- Absence on employee weekly off does not create a deduction.
- Absence on scheduled shift day is handled correctly.
- Holiday override and roster override precedence.
- Overnight shift crossing calendar date.
- Overnight shift crossing month boundary.
- Employment start/end dates with shift assignments.
- Present/absence counters exclude records outside employment period.
- Overtime candidate is not payable before approval.
- Approved overtime is included exactly once.
- Payroll snapshot retains shift/roster provenance.
- Prepared/approved/finalized/locked period protections remain effective.
- Existing salary count modes retain their documented behavior.

### 16.5 Regression suites

Run and record actual results for:

- Existing HR payroll unit tests.
- Attendance import tests.
- Tenant route isolation tests.
- Authorization feature/action tests.
- Leave/attendance integration tests.
- Finance payroll posting and reversal tests.
- Frontend typecheck/build.
- Browser smoke tests for HR attendance and payroll.

---

## 17. Definition of Done

P0.1 is complete only when:

1. Shift types, effective-dated assignments and roster entries are implemented.
2. Normal and overnight shifts are supported.
3. Attendance can resolve its expected schedule without breaking the legacy daily attendance contract.
4. Payroll readiness and absence calculations use the correct employee schedule.
5. Existing salary count modes are preserved or explicitly versioned through an approved change.
6. Payroll snapshots preserve schedule provenance.
7. Timezone import defect is corrected and covered by tests.
8. Attendance delete authorization and employee data scopes are corrected and tested.
9. Existing attendance records and finalized payroll history remain intact.
10. Tenant isolation, permission, audit, migration and regression tests pass.
11. Documentation and implementation tracker are updated.
12. The PR is reviewed and merged into the agreed integration branch.

---

## 18. Implementation task breakdown

| Task ID | Task | Dependency |
|---|---|---|
| P0.1-A | Correct Excel punch-out timezone conversion and add round-trip regression test | None |
| P0.1-B | Fix attendance DELETE write authorization and add negative permission test | None |
| P0.1-C | Add employee-scope enforcement to attendance endpoints/import | Confirm scope helper/API contract |
| P0.1-D | Correct out-of-employment attendance summary counting | Payroll regression tests |
| P0.1-E | Finalize timezone resolution and work-date convention | Joint product decision |
| P0.1-F | Implement shift type model, migration and APIs | Approved shift schema |
| P0.1-G | Implement effective-dated shift assignments | Shift type model |
| P0.1-H | Implement date-specific roster generation and overrides | Assignment model |
| P0.1-I | Integrate roster schedule with attendance view and readiness | Roster resolver |
| P0.1-J | Integrate shift schedule with payroll calculations and snapshot provenance | Payroll policy decisions |
| P0.1-K | Implement overtime review/approval boundary | Overtime policy decision |
| P0.1-L | Complete tenant, authorization, migration and regression test suite | All prior tasks |

---

## 19. Decisions required before implementation

The following must be confirmed by both contributors:

1. **Shift granularity:** Confirm one primary shift per employee per local work date for P0.1; split/multiple shifts in one day are deferred.
2. **Timezone resolution:** Confirm branch timezone with tenant timezone fallback, or deliberately tenant timezone only for v1.1.
3. **Holiday precedence:** Confirm how a roster override interacts with a tenant holiday and whether holiday work is recorded separately.
4. **Payroll period boundary:** Confirm that an overnight shift is allocated to the month containing its local shift-start date.
5. **Working-days salary mode:** Confirm whether shift-assigned employees use individual scheduled days for the absence divisor while monthly gross proration remains based on the existing monthly salary policy.
6. **Overtime:** Confirm whether supervisor approval is mandatory before overtime can be included in payroll.
7. **Attendance correction:** Confirm whether employees can submit requests directly in P0.1 or whether HR/supervisors are the only correction initiators initially.

No implementation should infer these decisions silently.

---

## 20. Change log

| Version | Date | Change |
|---|---|---|
| 1.1 — P0.1 | 8 November 2026 | Initial draft. Includes audit of current attendance/payroll implementation, risk register, proposed shift/roster model, payroll integration contract, migration plan, test matrix and decisions requiring joint approval. |
| 1.1 status note | 9 November 2026 | Retained as historical audit/design draft. Approved decisions and MVP architecture are now maintained in Decision Register v1.0 and P0.1 Architecture Specification v1.0. |

**End of specification.**
