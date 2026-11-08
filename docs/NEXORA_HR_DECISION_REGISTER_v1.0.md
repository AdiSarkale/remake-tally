# Nexora HR — Final Product Decision Register

**Document ID:** NEX-HR-DEC-001  
**Version:** 1.0  
**Status:** Product decisions approved; technical specification and implementation pending  
**Decision baseline:** 9 November 2026  
**Module:** HR & Payroll  
**P0.1 architecture:** [Nexora HR P0.1 Architecture & MVP Implementation Specification v1.0](NEXORA_HR_P0.1_ARCHITECTURE_SPECIFICATION_v1.0.md)  
**Historical audit/design draft:** [P0.1 Shift & Roster Enhancement Specification v1.1](NEXORA_HR_ENHANCEMENT_SPECIFICATION_v1.1_P0.1_SHIFT_ROSTER.md)  
**Related tracker:** [Nexora HR & Payroll Implementation Status](NEXORA_HR_PAYROLL_IMPLEMENTATION_STATUS_v1.0.md)  
**Integration branch:** `docs/hr-phase-2-implementation-status`

> This register records the product decisions supplied and approved by the project user in the Nexora project discussion. It is the source of truth for the selected product direction. It does not, by itself, constitute a complete technical specification, authorize implementation beyond the agreed MVP scope, or claim that any listed capability is implemented.

---

## 1. Decision summary

- Original questionnaire: 39 of 39 decisions answered.
- Follow-up clarifications: 8 of 8 answered.
- Architectural dependencies 1–6: accepted, with the additional tenant-configurable compensatory-leave rule recorded below.
- Additional technical questions T-01 to T-14: explicitly deferred until after MVP and retained in the post-MVP backlog.
- No direct product-policy contradiction was identified in the selected answers. Detailed technical rules remain subject to the scope and gates in this register.

## 2. Approved decisions — original questionnaire

### 2.1 Shift architecture

| ID | Decision | Approved direction |
|---|---|---|
| HR-01 | Shift structure | One primary shift per employee per local work date in the MVP; data design should not prevent additional shift segments in a later phase. |
| HR-02 | Assignment model | Support recurring assignments and date-specific roster overrides. |
| HR-03 | Assignment permissions | HR, branch managers and department supervisors may manage assignments within their authorized data scope. |
| HR-04 | Assignment hierarchy | Support department-level default shifts and employee-specific assignments. |
| HR-05 | Employees without assigned shifts | Preserve the existing tenant/global attendance calendar behavior for employees without a shift assignment. |
| HR-06 | Shift changes | Use selected effective dates and preserve historical assignment history. |
| HR-07 | Employee visibility | Employees may view their own assigned shifts. |

### 2.2 Timezone and calendar

| ID | Decision | Approved direction |
|---|---|---|
| HR-08 | Operational timezone | Use branch timezone, falling back to tenant timezone. |
| HR-09 | Overnight shift allocation | Allocate the shift to the local work date on which the shift starts. |
| HR-10 | Holiday precedence | Support configurable holiday and roster precedence, including explicit holiday-work treatment. |
| HR-11 | Weekly offs | Support tenant defaults, branch calendars and employee/shift-specific schedules. |

### 2.3 Attendance and time capture

| ID | Decision | Approved direction |
|---|---|---|
| HR-12 | Attendance sources | Support manual entry, Excel import and employee punch capture. |
| HR-13 | Punch model | Retain multiple raw punch events and derive a daily attendance summary. |
| HR-14 | Missing punches | Flag incomplete/missing punch cases; permit authorized HR correction with a reason. |
| HR-15 | Late/early policy scope | Make rules configurable by branch, shift and employee category. |
| HR-16 | Late-arrival consequences | Support configurable thresholds and consequences, including attendance-status outcomes. |
| HR-17 | Corrections | Employees, supervisors and HR may initiate corrections, subject to correction-type approval rules. |

### 2.4 Overtime and payroll

| ID | Decision | Approved direction |
|---|---|---|
| HR-18 | Overtime approval | Supervisor approval followed by HR verification is the default workflow. |
| HR-19 | Overtime calculation | Support configurable policies by relevant employee/shift/day categories. |
| HR-20 | Overtime rounding | Make rounding configurable; retain exact source minutes. |
| HR-21 | Payroll deduction basis | Preserve the existing salary-count modes: working days, calendar days and fixed days. |
| HR-22 | Shift changes during payroll | Resolve the shift effective on each individual work date. |
| HR-23 | Payroll provenance | Preserve a complete immutable payroll calculation snapshot, including relevant schedule, attendance, policy and source references. |

### 2.5 Leave and employee availability

| ID | Decision | Approved direction |
|---|---|---|
| HR-24 | Leave overlapping a shift | Apply approved leave against the scheduled working day and adjust attendance accordingly. |
| HR-25 | Work on weekly offs/holidays | Support configurable compensation through overtime, compensatory leave, or both. |
| HR-26 | Compensatory leave in MVP | Record approved earned compensatory-leave credits initially; defer balance management and redemption. |

### 2.6 Permissions and approvals

| ID | Decision | Approved direction |
|---|---|---|
| HR-27 | Overtime approver | Use configurable approval workflows; supervisor approval and HR verification are the default. |
| HR-28 | Attendance finalization | Use configurable approval/finalization workflows. |
| HR-29 | Separation of duties | Enforce separation of duties for sensitive requests and approvals; a requester must not approve their own transaction through the normal workflow. |
| HR-30 | Changes after payroll preparation/finalization | Require controlled correction workflow and audit history; never silently rewrite finalized payroll. |

### 2.7 Data, audit and lifecycle

| ID | Decision | Approved direction |
|---|---|---|
| HR-31 | Historical shift records | Preserve history; corrections use versioned changes with reasons and audit history. |
| HR-32 | Import timezone | Retain the selected import timezone in the import-batch audit record. |
| HR-33 | Workbook timezone | One selected timezone applies to an import workbook in the MVP. |
| HR-34 | Historical migration | Preserve existing historical attendance; do not infer or backfill historical shift assignments automatically. |
| HR-35 | Audit coverage | Audit all significant actions, including imports, corrections, approvals, reversals and material authorization events. |
| HR-36 | Employee offboarding | Deactivate future assignments and preserve historical assignments, attendance, payroll and audit records. |

### 2.8 Reports and management controls

| ID | Decision | Approved direction |
|---|---|---|
| HR-37 | Initial reports | Provide daily attendance, monthly attendance/payroll summary, shift-wise attendance and overtime reports. |
| HR-38 | Supervisor dashboard | Scope dashboard visibility according to configurable organizational/data permissions. |
| HR-39 | Anomaly detection | Flag missing punches, overlapping shifts, excessive overtime, late/early patterns and payroll discrepancies. |

---

## 3. Approved architectural dependency resolutions

The project user accepted the recommendations for Dependencies 1–6, with the explicit compensatory-leave configuration addition below.

### DEP-01 — Branch timezone and Excel import

1. Operational attendance calculations use branch timezone, with tenant timezone fallback.
2. The MVP import batch is restricted to one branch and one timezone.
3. The selected branch timezone is the default import timezone.
4. An authorized importer may override the timezone for the batch.
5. A workbook containing employees from incompatible branches/timezones is rejected in the MVP.
6. Multi-branch workbook import with per-row timezone resolution is deferred.
7. UTC remains the canonical storage representation for actual timestamp instants; local timezone is used to interpret work schedules, work dates and payroll periods.

### DEP-02 — Shift assignment and raw punch architecture

1. One primary shift per employee per local work date in the MVP.
2. Multiple raw punch events are retained separately from the daily attendance summary.
3. The attendance calculation derives worked time, breaks, late/early minutes, overtime candidates and exceptions from applicable schedule and source events.
4. A reviewed daily attendance summary remains available for payroll compatibility.
5. Manual attendance and Excel imports may enter source events and/or an authorized reviewed daily summary, according to the defined workflow. Source type and calculation/provenance must be retained.
6. Additional shift segments remain a later-phase capability.

### DEP-03 — Overtime workflow

1. Default workflow: supervisor approval, followed by HR verification.
2. Tenant-configurable workflow may add or change authorized approver roles/levels.
3. Detected extra time is not automatically payable overtime.
4. Rejected overtime remains traceable but is excluded from payable overtime.
5. Approval/rejection records actor, timestamp and reason.
6. Payroll includes only overtime that satisfies the applicable approval and policy rules.

### DEP-04 — Compensatory-leave earning records

1. The MVP records approved compensatory-leave credits earned from eligible work.
2. Each credit retains its source work date, earning/approval provenance and applicable policy reference.
3. The earning-date rule and expiry policy reference must be tenant-configurable.
4. The MVP does not provide leave-credit consumption/redemption or a complete available-balance workflow.
5. Redemption and balance management are deferred; earned credits must not be presented as consumable leave until that capability exists.

### DEP-05 — Payroll states and post-preparation corrections

| Payroll state | Approved handling direction |
|---|---|
| Draft | Attendance inputs may be corrected subject to validation and authorization. |
| Prepared | Changes require an authorized correction workflow and controlled recalculation. |
| Approved | Changes require controlled correction and reapproval. |
| Finalized | Original snapshot is immutable; financial differences are handled through an eligible later-period adjustment. |
| Locked | Historical snapshot remains immutable; no silent mutation. |

The exact state names and transition permissions must be aligned with the existing payroll state machine during technical specification. The table expresses the approved control intent, not a claim that every state transition already exists.

### DEP-06 — Separation of duties and emergency override

1. The requester cannot approve their own sensitive request through the normal workflow.
2. When no alternate authorized approver is available, an HR/Admin emergency override may be used.
3. The override requires a recorded reason and complete audit attribution.
4. An additional review must be required after the emergency override.
5. The override must not become a general permission bypass.

---

## 4. Approved follow-up clarifications

| ID | Question | Approved answer |
|---|---|---|
| HR-40 | Department default vs employee assignment conflict | Employee-specific assignment wins. |
| HR-41 | Shift breaks | Configurable paid/unpaid breaks, with scheduled duration and actual punch support. |
| HR-42 | Missing punch handling | Calculate available attendance for the payroll draft and flag the missing-punch exception. If a grievance/correction is raised, HR must correct the missing punch before payroll finalization. |
| HR-43 | Late-arrival consequences | Configurable thresholds may automatically determine late, half-day or other configured consequences. |
| HR-44 | Overtime eligibility | Configurable minimum thresholds, grace periods and approved payable overtime. |
| HR-45 | Correction after finalized payroll | Record the resulting financial difference as an adjustment in the next eligible payroll period; do not reopen or rewrite the finalized snapshot. |
| HR-46 | No alternate approver | Permit an audited HR/Admin emergency override with a reason and additional review. |
| HR-47 | Multiple attendance sources | Compare available sources and flag anomalies instead of blindly overwriting one source with another. The tenant configures the error margin/threshold used for anomaly flagging. |

### HR-47 implementation intent

- Preserve source records and source identity.
- Compare relevant values from available sources.
- Apply tenant-configured error margins to determine when a discrepancy should be flagged.
- Record the discrepancy, source values, comparison result and resolution.
- Do not treat the latest submitted record as automatically authoritative.
- Define source-specific reconciliation and authorized resolution rules in the MVP technical specification.

---

## 5. MVP boundary and deferred technical register

The project user explicitly requested that the following 14 technical details be revisited after MVP. They remain recorded as open post-MVP design items and must not be silently treated as decided.

| Backlog ID | Deferred technical decision | Status |
|---|---|---|
| T-01 | Detailed department-default and employee-override precedence beyond the approved employee-wins rule | Deferred post-MVP |
| T-02 | Detailed shift-break calculation edge cases and payable-minute treatment | Deferred post-MVP |
| T-03 | Detailed missing-punch calculation, exception and correction rules beyond HR-42 | Deferred post-MVP |
| T-04 | Detailed late/early thresholds and consequence matrix beyond HR-43 | Deferred post-MVP |
| T-05 | Detailed overtime eligibility, rate, threshold and rounding configuration | Deferred post-MVP |
| T-06 | Full holiday/roster precedence matrix and holiday-work calculation | Deferred post-MVP |
| T-07 | Shift-specific scheduled-day and absence-divisor interaction with existing salary-count modes | Deferred post-MVP |
| T-08 | Compensatory-leave credit expiry, balance and redemption lifecycle beyond tenant-configurable earning/expiry policy references | Deferred post-MVP |
| T-09 | Detailed payroll adjustment and reopening/state-transition rules beyond DEP-05 and HR-45 | Deferred post-MVP |
| T-10 | Approval fallback, delegation and emergency-override implementation details beyond DEP-06 | Deferred post-MVP |
| T-11 | Raw punch source priority, duplicate detection and reconciliation details beyond HR-47 | Deferred post-MVP |
| T-12 | Device punch integration, synchronization and offline behavior | Deferred post-MVP |
| T-13 | Audit retention and detailed access controls for sensitive attendance data | Deferred post-MVP |
| T-14 | Full shift assignment conflict and overlap validation beyond HR-40 | Deferred post-MVP |

**Important MVP constraint:** Deferring these details does not authorize developers to invent business behavior. Where an unresolved detail blocks safe implementation, record the blocker and bring back the smallest necessary decision rather than making an undocumented assumption.

---

## 6. MVP implementation guardrails

1. Preserve existing attendance and payroll behavior for employees without assigned shifts.
2. Preserve the existing salary-count modes: working days, calendar days and fixed days.
3. Do not infer historical shifts or rewrite historical attendance.
4. Store actual timestamps consistently in UTC and resolve operational dates/times using branch timezone with tenant fallback.
5. Preserve raw punch source data and reviewed daily attendance separately.
6. Keep one primary shift per employee per local work date in the MVP.
7. Do not make detected extra time payable until required overtime approval is complete.
8. Preserve immutable finalized payroll snapshots; use later-period adjustments for post-finalization differences.
9. Enforce tenant, branch, department and employee data scopes on the backend, not only in the UI.
10. Reuse Nexora Core authorization, audit and approval services rather than creating parallel HR-only frameworks.
11. Record tenant-configured anomaly thresholds and compensatory-leave earning/expiry policy references.
12. Do not claim a feature is implemented until migrations, backend, frontend, authorization, audit, tests and CI evidence satisfy the applicable definition of done.

---

## 7. Existing audit remediation — separate from new shift scope

These previously identified items remain tracked independently from the new product decisions:

| Audit ID | Finding / required work | Current record |
|---|---|---|
| AUD-05 | Excel punch-out timezone conversion defect | Code correction committed; verification still required. |
| AUD-06 | Attendance DELETE authorization gap | Permission correction committed; verification still required. |
| AUD-07 | Enforce employee branch/team scopes in attendance handlers | Outstanding remediation. |
| AUD-08 | Correct payroll attendance counters outside employee employment dates | Outstanding remediation. |

The latest timezone/import and authorization changes must not be described as verified until the relevant tests and CI have actually run and passed.

---

## 8. Required specification and implementation sequence

1. Link this register from the P0.1 enhancement specification and active HR implementation tracker.
2. Update the P0.1 specification so its proposed defaults are replaced by the approved decisions in this register.
3. Produce the MVP technical specification: entities, migrations, API contracts, UI behavior, state transitions, authorization, audit, calculation rules, failure handling and acceptance tests.
4. Complete and verify AUD-05 through AUD-08, recording actual test/CI evidence.
5. Implement in dependency order: shift definitions and assignments; branch-aware calendar/timezone; raw punch ingestion and reconciliation; attendance calculation and summary; corrections and approvals; overtime; payroll integration and immutable provenance; reports and anomaly handling.
6. Keep T-01 through T-14 in the post-MVP backlog and schedule a separate review after MVP scope is delivered.

---

## 9. Approval and change control

This document records the product user's decisions as of 9 November 2026. Any later change to an approved decision must be recorded as a versioned change with:

- Decision ID affected.
- Previous and proposed behavior.
- Reason for change.
- Impact on data model, migration, APIs, payroll, permissions, reports and existing customers.
- Approval attribution and effective version.

**Current approval boundary:** Product decision direction is approved by the project user. Detailed technical specification, contributor review, implementation authorization and release acceptance remain separate gates.

**End of register.**
