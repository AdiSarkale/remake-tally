# Nexora HR — P0.1-08 Daily Attendance Summary & Correction Workflow Specification

**Document ID:** NEX-HR-P0.1-08-SPEC-001  
**Version:** 1.0  
**Status:** Implementation specification — approved decisions reused; implementation in progress  
**Baseline:** 27 November 2026  
**Integration baseline:** `docs/hr-phase-2-implementation-status`  
**Feature branch:** `feat/p0-1-08-attendance-summary-corrections`

## 1. Purpose

P0.1-08 derives a traceable daily attendance projection from immutable raw attendance events and the effective roster. It identifies incomplete or invalid punch sequences and provides a reasoned, reviewed correction workflow. It does not rewrite source facts or silently choose between conflicting sources.

## 2. Governing decisions and boundaries

This slice follows HR-13, HR-14, HR-17, HR-28, HR-29, HR-30, HR-31, HR-42 and HR-47 from the approved HR Decision Register, and the P0.1 Architecture v1.0.

- Raw attendance events remain the evidence ledger. A correction is a new linked event; the prior event is retained.
- One primary shift per employee/local work date remains the MVP assumption.
- Branch timezone with tenant fallback; work date is the local shift-start date.
- Employees, supervisors and HR may initiate corrections according to their granted scope, but only a separate authorized reviewer can approve/reject/return a request. A requester cannot approve their own request.
- Missing-punch cases are calculated from available evidence and flagged. A correction must be resolved before payroll finalization when the missing punch is grievance/correction-relevant (HR-42).
- Prepared/approved/finalized/locked payroll periods are protected from attendance event mutation/correction; finalized payroll is never rewritten.
- No last-write-wins source reconciliation. P0.1-07 anomaly resolution remains a source selection decision; it does not rewrite raw events.
- T-02, T-03, T-04, T-06, T-07, T-09, T-10, T-11 and T-13 remain deferred where their detailed policy is not already approved. This implementation must not invent pay consequences, late/early thresholds, break edge-case rules, holiday precedence, or payroll reopening behavior.

## 3. Daily summary projection

### 3.1 Inputs

- Active, non-voided, non-superseded raw events for employee and local work date.
- Roster entry and its stored shift/break/timezone snapshots, if one exists.
- Effective workforce policy version where a rule is explicitly defined.
- Existing legacy attendance row for compatibility/initialization only; it is not silently overwritten by projection.

### 3.2 Projection and provenance

The projection is versioned. Each calculation records:

- Employee and local work date.
- Roster ID and snapshot references where applicable.
- Timezone snapshot.
- Source event IDs used, excluding voided/superseded facts.
- First/last punch timestamps, elapsed duration and paired break durations when calculable.
- Classification and exception codes.
- Calculation actor, timestamp, revision and calculation-input fingerprint.

A revision is immutable. A current-summary pointer/row may be updated transactionally to reference the latest revision. Recalculating unchanged inputs is idempotent.

### 3.3 MVP classifications

- `no_events`: no active raw events for the date.
- `complete`: a valid punch sequence contains a complete attendance interval.
- `incomplete`: evidence exists but a required punch/break pair is missing.
- `invalid_sequence`: event ordering or pairing is not safely interpretable.
- Roster non-working states (`weekly_off`, `holiday`, `cancelled`) remain schedule states and must not be converted into absence by this projection.

The projection does not automatically classify absence, half-day, late, early departure or payable overtime. Those decisions require the approved policy matrix and/or HR review.

## 4. Event-sequence validation

- Events are ordered by UTC instant with a stable tie-breaker.
- A punch-out without a preceding punch-in is an exception.
- A punch-in without a matching punch-out is an incomplete interval.
- Break-start/end pairing must be valid; unmatched break events are exceptions.
- Duplicate or contradictory event sequences are flagged, not silently discarded.
- Overnight events remain attributed to the local work-start date and must be within the effective roster window where a roster exists.
- For employees without a roster, the projection uses the available event evidence and does not invent a scheduled window.
- Detailed break/pay treatment remains outside this slice.

## 5. Correction workflow

### 5.1 Request types

MVP correction requests are limited to punch-event corrections: add a missing event, or replace/correct a referenced event timestamp/type. Daily status overrides, arbitrary overtime edits, and historical payroll reopening are not part of this request type.

### 5.2 State machine

`submitted → approved | rejected | returned`  
`returned → submitted` (requester resubmits with updated proposal/reason)  
`approved → applied` (system appends the superseding event and recalculates projection)

- A rejected request is terminal; a new request is required.
- Return/reject/approve decisions require reviewer reason.
- Approval and application are one transaction: event append, summary recalculation, request status and audit must commit or roll back together.
- The requester cannot approve their own request through normal workflow.
- Requester and reviewer must both satisfy employee data scope for the target work date.
- A correction requires a reason and optional evidence reference; file upload is not included in this slice.
- Raw event records are never deleted. Corrected events link to the prior source event through `supersedes_event_id`; the prior fact remains retained and excluded from the active projection after it is superseded.
- No automatic approval or fallback reviewer is invented. Emergency override/additional review remains governed by DEP-06 and is not silently implemented as a bypass.

## 6. Payroll protection

- A correction is rejected while the work date's payroll period has a prepared, approved, finalized or locked run.
- Projection writes do not silently change existing legacy payroll attendance records in this slice.
- P0.1-10 owns payroll readiness/finalization integration and immutable daily payroll snapshots.
- Existing payroll state and Finance journal/reversal safeguards remain unchanged.

## 7. API and permissions

All APIs are tenant-scoped and employee data-scope enforced server-side.

- Summary list/detail/recalculate: explicit `hr.attendance_summaries.view` and `hr.attendance_summaries.calculate` grants.
- Correction request create/list: `hr.attendance_corrections.create/view` grants, with tenant or self scope as granted.
- Correction decision: `hr.attendance_corrections.review` grant; approve/reject/return are explicit actions, not read/write fallback.
- Every mutation is audited with actor, target employee/date, request/event IDs, decision and reason.
- Route authorization fails closed when exact grants are missing.

## 8. Acceptance criteria

1. Projection handles no events, complete in/out, missing in/out, unmatched break and invalid sequence cases.
2. Active-event filtering excludes voided and superseded facts without deleting source history.
3. Projection revisions are immutable, versioned and reproducible from stored inputs.
4. Recalculation with unchanged input is idempotent.
5. Roster/branch timezone snapshots are respected; overnight work-date attribution is preserved.
6. Corrections require reason, authorized scope and separate reviewer.
7. Requester self-approval is denied.
8. Approve/reject/return/resubmit transitions are validated.
9. Approved correction creates a new linked raw event and recalculates summary atomically.
10. Payroll prepared/approved/finalized/locked periods reject correction mutation.
11. Tenant isolation, exact authorization, audit and concurrency/idempotency tests pass.
12. Backend tests, PostgreSQL migrations, tenant-isolation suite, frontend typecheck/build and integrated CI pass.
13. Documentation tracker records the exact CI evidence. No production readiness claim is made.

## 9. Explicit non-goals

- Late/early threshold and consequence calculations.
- Absence/half-day auto-classification.
- Overtime calculation or approval.
- Compensatory leave.
- Payroll snapshot/finalization blocking integration beyond existing prepared/frozen-period protection.
- UI/reporting; P0.1-11 owns attendance UI and reports.
- Device/offline attendance integrations.
- File upload/evidence storage.
- Reopening finalized payroll or modifying Finance journals.

**End of specification.**
