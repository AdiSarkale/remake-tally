# Nexora HR — P0.1-10 Payroll Integration Specification

**Document ID:** NEX-HR-P0.1-10-SPEC-001  
**Version:** 1.0  
**Status:** Implementation in progress — Slice 01  
**Baseline:** 27 November 2026  
**Integration branch:** `docs/hr-phase-2-implementation-status`  
**Dependencies:** P0.1-08 Daily Attendance Summary & Correction; P0.1-09 Overtime & Compensatory Leave  
**Architecture authority:** Nexora HR P0.1 Architecture Specification v1.0 and HR Decision Register v1.0

---

## 1. Purpose

P0.1-10 connects the shift/roster, daily attendance projection, reviewed overtime, existing payroll calculations, payroll revision lifecycle and Finance posting boundary. It must make payroll reproducible and prevent unresolved attendance or configuration issues from being silently finalized.

This package does not change the existing salary-count modes or independently invent statutory overtime rules.

## 2. Scope

### 2.1 Included

- Shift-aware scheduled-day attendance readiness.
- Attendance completeness checks using roster scheduled days for employees with effective shift schedules.
- Legacy calendar-based readiness for employees without shift schedules.
- Working-days divisor compatibility guard.
- Payroll daily provenance snapshots for each employee/work date included in a payroll revision, including unresolved source-reconciliation anomaly references.
- Approved overtime integration into payroll exactly once.
- Payroll exception storage and finalization blocking for unresolved blocking attendance exceptions.
- Controlled supersession of prepared/approved snapshots and revision preparation.
- Preserve existing Finance posting and reversal service.

### 2.2 Excluded

- Statutory overtime certification or multiplier/rate compliance.
- Employee-specific salary divisor/proration policy beyond the existing approved salary-count modes.
- Comp-Off consumption, redemption, carry-forward, expiry calculation and spendable balance.
- Automatic payroll reopening after finalization.
- New Finance journal logic.
- A general multi-stage approval engine.

## 3. Shift-aware readiness

### 3.1 Employees without an effective shift schedule

- Continue to use the existing tenant calendar and week-off configuration.
- Existing attendance statuses and payroll readiness behavior remain in place.

### 3.2 Employees with an effective shift schedule

- A roster row with status `scheduled` defines an attendance-required day.
- Roster `weekly_off`, `holiday`, and `cancelled` rows are not treated as scheduled workdays for absence classification.
- An effective assignment on an assigned weekday without a generated roster row is a configuration/readiness blocker.
- Conflicting effective assignments fail closed.
- Payroll attendance completeness is checked against the resolved roster schedule rather than the tenant calendar.

### 3.3 Divisor compatibility

- Existing `working_days`, `calendar_days`, and `fixed_days` modes remain unchanged.
- In `working_days` mode, the full-month roster scheduled-day count is compared with the existing tenant divisor.
- If the employee schedule and tenant divisor basis are incompatible, preparation is blocked for the affected period; the engine must not silently calculate an employee-specific divisor.
- `calendar_days` and `fixed_days` preserve their existing divisor behavior.

## 4. Overtime integration

### 4.1 Payable gate

A candidate is payroll-eligible only when its domain status is `approved`, which represents completion of supervisor approval and HR verification. Candidate, submitted, supervisor-approved, returned, and rejected states are excluded.

### 4.2 Compensation method

- `overtime` and `both`: rounded approved candidate minutes are eligible for payroll overtime.
- `compensatory_leave`: candidate minutes do not become overtime pay.
- The candidate and policy snapshot remain the authoritative source.
- Candidate IDs, revisions, policy versions, fingerprints and source-event IDs are included in daily provenance.
- Payroll inclusion must be idempotent and exactly once per employee/work date/candidate revision.

### 4.3 Rate boundary

The current legacy overtime-pay calculation remains the provisional existing calculation: daily payroll rate divided by eight hours, applied to approved overtime hours. This is **not** a statutory-compliance claim. P0.1-10 must not advertise compliant overtime rates until a tenant-effective overtime rate/multiplier policy is separately defined, reviewed and tested.

### 4.4 Legacy overtime

For employees without shift/roster context, the existing legacy attendance overtime input continues to be used. For employees with shift context, legacy attendance overtime is not added on top of approved candidate minutes; this prevents duplicate payable time.

## 5. Immutable daily provenance

For each payroll revision and salaried employee, retain a daily source snapshot containing:

- Local work date and calendar/day classification.
- Roster identity, status, version, shift code/name, schedule boundaries, timezone, branch/department and break-rule snapshot.
- Legacy attendance record identity, status, punch values, note and legacy OT field where present.
- Daily attendance summary identity, revision, classification, source-event IDs, timezone, exception codes and fingerprint.
- Approved overtime candidate identity/revision, rounded minutes, compensation method, policy/version, source events and candidate fingerprint.
- Approved payable OT minutes derived from the candidate records.
- Snapshot fingerprint and capture timestamp.

A prepared, approved, finalized or locked payroll revision must not mutate these snapshots.

## 6. Exceptions and finalization

Blocking exceptions include, at minimum:

- Missing daily summary for a scheduled shift day.
- Incomplete, invalid-sequence or no-event daily summary on a scheduled shift day.
- Missing or ambiguous roster/assignment configuration.
- Working-days divisor incompatibility.
- Material attendance/source reconciliation exception when the source reconciliation gate is available.

Finalization must fail closed while open blocking exceptions remain. A corrected attendance source is applied through the P0.1-08 correction process. The prepared/approved payroll snapshot must then be explicitly superseded; the old revision remains queryable and the new revision is prepared from corrected inputs and independently approved.

Warnings may be acknowledged only through an explicit authorized action and must retain actor, time and reason. Blocking errors must not be converted into warnings merely to finalize payroll.

## 7. Revision lifecycle

- Draft/preview is mutable and provisional.
- Prepared and approved snapshots are retained.
- A prepared or approved revision may be explicitly superseded with a reason, creating a new revision on the next prepare action.
- Superseded revisions are never eligible for Finance posting.
- Approval is cleared when an approved revision is superseded.
- Finalized and locked revisions are never silently reopened.
- Post-finalization corrections use a later-period adjustment under the existing payroll/Finance correction process.
- Finance posting and reversal remain delegated to the existing shared service and must remain idempotent.

## 8. API and screen targets

- Payroll preview: shift-aware readiness, approved OT minutes and warnings.
- Prepare: blocking readiness issues; snapshot daily inputs and exceptions.
- Payroll run exception list.
- Supersede prepared/approved payroll with reason.
- New revision prepare after supersession.
- Finalize: independently recheck workflow state and unresolved blocking exceptions.
- UI: exception list/detail, supersession reason dialog, revision history, daily provenance detail.

## 9. Acceptance criteria

- AC-10-01: Legacy employees without shift schedules retain legacy readiness behavior.
- AC-10-02: Shift employees are checked against roster scheduled days.
- AC-10-03: Effective assignment weekday with missing roster blocks preparation.
- AC-10-04: Ambiguous assignment fails closed.
- AC-10-05: Shift/working-days divisor incompatibility blocks preparation.
- AC-10-06: Employees in calendar-days/fixed-days modes retain existing divisor behavior.
- AC-10-07: Only fully approved overtime candidate minutes are included.
- AC-10-08: Overtime candidate inclusion is idempotent and exactly once.
- AC-10-09: Comp-Off-only candidates are excluded from payable overtime.
- AC-10-10: Shift employees do not double-count legacy overtime.
- AC-10-11: Daily snapshots contain attendance, roster, summary, approved OT and source provenance.
- AC-10-12: Snapshot rows are immutable and unique per payroll run/employee/work date.
- AC-10-13: Missing/incomplete/invalid scheduled-shift attendance creates blocking exceptions.
- AC-10-14: Payroll finalization fails while blocking exceptions remain open.
- AC-10-15: Prepared/approved runs can be superseded with reason; prior snapshot remains queryable.
- AC-10-16: New revisions require separate approval; superseded runs cannot post Finance journals.
- AC-10-17: Existing payroll calculation, Finance posting/reversal, tenant isolation and authorization regressions pass.
- AC-10-18: Migration, backend, frontend, PostgreSQL provisioning, tenant isolation and browser CI pass before package completion.

## 10. Implementation progress

### Slice 01 — data foundation and initial integration (in progress)

Implemented in the integration branch:

- Migrations `p0_hr_payroll_daily_snapshots_026` and `p0_hr_payroll_supersession_027`: immutable daily provenance/exception tables and supersession attribution.
- Added ORM models and compatibility exports.
- Batch daily-input resolver for roster, assignment, attendance, daily summary and approved overtime.
- Payroll preview uses approved overtime candidates for shift-context employees and retains legacy OT behavior for employees without shift context.
- Shift roster day flags drive scheduled-day classification for shift-context payroll calculations.
- Shift-aware attendance readiness and working-days divisor compatibility checks.
- Prepare persists daily provenance and blocking attendance-summary exceptions.
- Finalization blocks open blocking payroll exceptions.
- Exception-list API and controlled prepared/approved run supersession endpoint.
- Prepare supports new revisions after supersession.
- Added initial unit tests for approved OT gating, roster-based absence classification, scheduled-day helper, daily OT/source-anomaly provenance and controlled supersession.

**Not yet release-complete:** current CI is pending; additional tests and exception/UI workflow validation are required. The existing overtime-pay rate formula is provisional and must not be marketed as statutory compliance. The current implementation is an initial slice, not the complete P0.1-10 package.

### Slice 02 — pending

- Revisions and correction lifecycle regression tests.
- Finalization readiness recheck against current source revisions.
- Payroll exception UI and provenance detail UI.
- Additional missing/ambiguous roster, divisor, OT duplication, stale input, and Finance-posting tests.
- Review of source data scope/tenant authorization.
- Full CI and acceptance review.

---

## 11. Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 27 November 2026 | Initial P0.1-10 integration specification and implementation tracker. |
