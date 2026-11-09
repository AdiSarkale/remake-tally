# Nexora HR — High-Value Implementation Roadmap

**Document ID:** NEX-HR-ROADMAP-001  
**Version:** 1.0  
**Status:** Proposed implementation roadmap  
**Baseline:** 8 November 2026  
**Related tracker:** [Nexora HR & Payroll — Implementation Status and Next Work](NEXORA_HR_PAYROLL_IMPLEMENTATION_STATUS_v1.0.md)  
**Scope:** HR and Payroll enhancements for the Nexora ERP repository.

> This roadmap prioritizes future work. It does not mark planned capabilities as implemented, authorize changes to locked specifications by itself, or replace detailed feature specifications. Before implementation, confirm the current code and data model, approve the required change request, and document acceptance criteria.

---

## 1. Objective and guiding principles

Extend Nexora's existing HR, attendance, leave, payroll, authorization and audit foundations into a commercially useful manufacturing-focused workforce solution.

The strategy is incremental extension, not a rewrite.

1. Prioritize daily workforce operations and payroll correctness before advanced HR features.
2. Reuse Nexora Core services for authorization, audit, approvals and tenant isolation. Do not create parallel HR-only frameworks.
3. Preserve historical attendance, leave ledgers, salary history, finalized payroll snapshots and financial journals.
4. Enforce permissions and data scopes in backend services; UI visibility is not authorization.
5. Treat statutory payroll as a compliance-sensitive capability. Do not claim legal compliance until rules and applicability are independently verified.
6. Build around manufacturing workflows where this creates genuine value: shifts, workforce availability, skills and operation qualifications.

## 2. Priority overview

| Phase | Priority | Focus | Outcome |
|---|---|---|---|
| Phase 1 | P0 | Workforce foundations | Reliable shift-based attendance, payroll inputs and payroll controls |
| Phase 2 | P1 | Employee lifecycle | Traceable employee joining, changes, separation and settlement |
| Phase 3 | P1 | Manufacturing workforce intelligence | Verified skills, training and workforce visibility linked to operations |
| Phase 4 | P2 | Advanced HR and compliance | Statutory configuration, recruitment, performance and employee financial services |

Priority labels express recommended implementation order, not a delivery commitment or estimate.

---

## 3. Phase 1 — P0 workforce foundations

Implement these packages in the order below, subject to the baseline audit and dependency review.

### P0.0 — Baseline verification and change control

Before feature coding:

- Review the current employee, attendance, leave, payroll, authorization and audit models, APIs, UI and tests.
- Identify implemented, partial and missing behavior; do not infer implementation from a screen or documentation alone.
- Record data migration and backward-compatibility risks.
- Confirm the shared approval, permission and audit services that each package must reuse.
- Raise and approve the change request required to extend the locked HR specification.
- Produce a feature-level specification, API contract, migration plan and acceptance tests.

**Exit criteria:** An agreed baseline and reviewed implementation specification exist; no existing behavior is silently redefined.

### P0.1 — Shift and roster management

**Why first:** Manufacturing employees may work different shifts, weekly-off patterns and overnight schedules. Monthly attendance alone cannot reliably represent those conditions.

**Initial scope**

- Shift types: name/code, start and end time, break duration, grace periods and active status.
- Shift assignments to employees and, where appropriate, teams/departments.
- Effective-dated assignments with preserved history.
- Daily and weekly schedules and roster calendar.
- Configurable weekly-off patterns.
- Overnight shifts crossing midnight.
- Shift-aware attendance evaluation.
- Overtime duration capture as a separate, reviewable input; do not assume overtime is payable until approved payroll policy defines it.

**Business and data rules**

- Store timestamps consistently and interpret schedules using the applicable tenant/branch timezone policy.
- An assignment change must not rewrite historical schedules or attendance.
- Define behavior for overlapping assignments, missing assignments, holidays, shift swaps and partial shifts.
- Define whether a shift can span a daylight-saving transition where relevant.
- A supervisor can manage only employees within their authorized data scope.
- Preserve the source assignment used when attendance is calculated.

**MVP acceptance criteria**

- HR can configure shifts and assign them with effective dates.
- HR/supervisors can view daily and weekly rosters within their scope.
- Normal and overnight shifts produce correct attendance boundaries.
- Historical attendance remains unchanged after future assignment edits.
- Invalid or overlapping assignments are rejected or explicitly resolved.
- Tenant isolation, authorization, audit and regression tests pass.

### P0.2 — Attendance correction and approval

**Initial scope**

- Employee/supervisor correction request for a specific date and attendance event/status.
- Requested value, existing value, reason and optional supporting attachment reference.
- Configurable approver resolution using the approved organization/manager hierarchy.
- Submit, approve, reject and return-for-correction states.
- Approved correction updates the operational attendance record with actor and timestamp.
- Original value, corrected value, reason and decision remain auditable.
- Payroll-period lock/finalization checks.

**Critical rule:** A correction after payroll finalization must not silently mutate a finalized payroll snapshot. It must follow an explicit post-finalization adjustment or next-period correction process.

**MVP acceptance criteria**

- Every correction has a traceable request and decision.
- Unauthorized users cannot approve their own request unless an explicitly approved policy allows it.
- Corrections are idempotent and cannot be applied twice.
- Finalized payroll remains reproducible and unchanged.

### P0.3 — Effective-dated salary revisions

**Initial scope**

- Salary revision proposal with previous and proposed salary structure.
- Effective-from date, reason, initiator and approver.
- Employee salary history and revision status.
- Future-dated salary revisions.
- Payroll period calculation resolves the applicable approved salary version.
- Revision audit and historical view.

**Example:** If monthly basic salary is ₹18,000 through June and ₹21,000 from 1 July, June payroll must continue to use ₹18,000 even if the July revision was entered earlier.

**MVP acceptance criteria**

- Salary history is preserved; revisions do not overwrite prior salary records.
- Payroll uses the approved salary version applicable to the relevant period.
- A revision cannot alter a finalized payroll snapshot.
- Overlapping or ambiguous effective periods are rejected or resolved through a controlled workflow.

### P0.4 — Additional earnings, deductions and payroll adjustments

**Initial scope**

- Configurable earning and deduction component types.
- One-time and recurring entries.
- Incentives, bonuses, allowances, arrears, recoveries and approved deductions as configured components.
- Effective period and intended payment period.
- Approval before payroll inclusion.
- Duplicate prevention and clear payslip breakdown.
- Correction/reversal process with audit history.

**MVP acceptance criteria**

- An approved item is included exactly once in the intended payroll period.
- Unapproved, expired or duplicate items are excluded or block finalization according to policy.
- Payroll snapshots retain the exact adjustment inputs used.
- Reversal does not erase the original transaction history.

### P0.5 — Leave and holiday improvements

Extend the existing leave type, balance, request, approval, accrual and ledger foundations.

**Initial scope**

- Employee-specific holiday list assignment.
- Configurable leave periods, including financial-year support where approved.
- Compensatory leave request and approval.
- Audited leave balance adjustments with reason.
- Leave encashment as a controlled, separately authorized process.
- Improved leave calendar, balance and ledger reports.

**MVP acceptance criteria**

- Balance calculations use the employee's assigned policy and calendar.
- Adjustments and encashments are traceable and cannot be duplicated.
- Existing monthly/monthly-prorated accrual and idempotency behavior remains intact.
- Historical leave transactions are preserved during policy changes.

### P0.6 — Payroll validation and reconciliation

**Initial scope**

- Pre-finalization exception report.
- Missing attendance and invalid employment-period checks.
- Missing/overlapping salary structure checks.
- Duplicate payroll-period/run prevention.
- Salary component and adjustment reconciliation.
- Payroll register and employee-level calculation breakdown.
- Payroll-to-Finance journal reconciliation.
- Explicit handling of corrections received after payroll finalization.

**MVP acceptance criteria**

- Blocking errors prevent finalization.
- Warnings are visible and require an explicit resolution or authorized acknowledgement.
- Finalized payroll retains reproducible calculation inputs and outputs.
- Payroll posting and reversal reconcile to linked Finance journals.

---

## 4. Phase 2 — P1 employee lifecycle

Build employee lifecycle workflows after P0 foundations are stable.

| Package | Capability | Initial scope |
|---|---|---|
| P1.1 | Onboarding | Joining workflow, checklist, department/manager assignment and required documents |
| P1.2 | Employee documents | Controlled document metadata, access, expiry reminders and retention policy |
| P1.3 | Transfer | Effective-dated branch, department, designation and manager changes with approval |
| P1.4 | Promotion | Promotion proposal, approval, effective date and linked salary revision where applicable |
| P1.5 | Separation | Resignation, notice period, approval, last working day and access-deactivation coordination |
| P1.6 | Full and final settlement | Outstanding salary, leave encashment, recoveries, advances and settlement status |

**Design requirements**

- Employee history must not be overwritten by current-state edits.
- HR employee records and login identities are separate entities.
- Employment termination must not delete historical HR, payroll, attendance or audit records.
- Full and final settlement must coordinate with Payroll, Leave and Finance through explicit ownership and transaction boundaries.

**Exit criteria:** Joining, transfer, promotion and separation can be completed with effective dates, approvals, audit history and downstream payroll/access consequences.

---

## 5. Phase 3 — P1 manufacturing workforce intelligence

This phase differentiates Nexora from a generic HR system by connecting verified workforce capability to manufacturing execution.

| Package | Capability | Initial scope |
|---|---|---|
| P1.7 | Training management | Training programs, sessions, attendance, results and feedback |
| P1.8 | Certification management | Certificate records, issuer, validity, expiry and renewal |
| P1.9 | Skill matrix | Employee skills, proficiency levels, evidence and verification |
| P1.10 | Workforce qualification | Compare verified employee qualifications with operation requirements |
| P1.11 | Workforce reports | Attendance, availability and workforce analysis by department/branch/shift |
| P1.12 | Overtime analytics | Approved overtime analysis by employee, shift and department |

**Ownership boundary**

- HR owns employee skill, training and certification records.
- Manufacturing owns operation requirements, production assignments and execution status.
- Integration links employee qualifications to operation requirements without duplicating employee master data.

**MVP acceptance criteria**

- Skills and certifications have clear verification status and validity.
- Expired or unverified qualifications are not treated as valid.
- Supervisors can identify qualified employees within their authorized scope.
- Manufacturing assignment checks consume HR qualification data through a documented service/API contract.

---

## 6. Phase 4 — P2 advanced HR and compliance

| Capability | Recommended scope and caution |
|---|---|
| Statutory payroll | Effective-dated, jurisdiction-aware rules for applicable PF, ESI, PT, LWF and TDS obligations; independent compliance verification required |
| Tax declarations and proofs | Employee declarations, document submission, review and payroll-period linkage |
| Recruitment | Manpower plan, requisition, applicant tracking, interviews, feedback and offers |
| Performance management | Goals, KRAs, appraisal templates/cycles and manager reviews |
| Employee advances | Request, approval, disbursement and repayment/recovery integration |
| Expense claims | Claim submission, evidence, approval and Finance-owned accounting integration |
| Employee loans | Loan application, approval, repayment schedule and payroll deductions |
| Grievance management | Confidential cases, restricted access, assignment, resolution and audit |
| Benefits and insurance | Configurable benefits, eligibility and employee records |

### Statutory compliance release gate

Do not advertise statutory calculations as legally compliant merely because sample calculations work. Each rule requires authoritative verification of applicability, wage definitions, rates, thresholds, caps, exemptions, effective dates, rounding, exceptions and reporting obligations. A qualified payroll/compliance professional must review the implementation before production use. Missing mandatory configuration must not silently default to zero or stale values.

---

## 7. Dependencies and architecture boundaries

| Capability | Required foundation |
|---|---|
| Shift and roster | Employee master, organization assignments, timezone policy and attendance |
| Attendance correction | Attendance records, shared approval workflow, audit and payroll lock/snapshot controls |
| Salary revision | Salary structures, effective-dated history and immutable payroll snapshots |
| Payroll adjustments | Salary components, approvals, payroll calculation and audit |
| Leave improvements | Leave ledger, policy, holiday calendar and accrual engine |
| Full and final settlement | Separation, payroll, leave, advances and Finance |
| Expense claims | Finance accounting ownership and approval integration |
| Skill matrix | Employee skills, training/certification and Manufacturing operation requirements |
| Statutory payroll | Jurisdiction model, effective-dated rule sets, source/version tracking and compliance review |

**Non-negotiable architecture rules**

1. Reuse Core authorization, audit and approval services; do not create parallel HR frameworks.
2. Enforce tenant and employee data scopes on the backend for APIs, exports, reports and background jobs.
3. Preserve immutable historical records and finalized payroll snapshots.
4. Use effective dates for organization assignments, shifts, salary revisions and policy/rule changes.
5. Define transaction boundaries for payroll and Finance posting/reversal.
6. Keep HR as owner of employee master and employee capability data; other modules consume documented interfaces.

---

## 8. Recommended implementation sequence

1. Baseline verification and approved change request.
2. Shift and roster data model, APIs, UI and tests.
3. Shift-aware attendance calculation and regression tests.
4. Attendance correction workflow and post-finalization safeguards.
5. Effective-dated salary revisions.
6. Additional earnings, deductions and payroll adjustments.
7. Leave and holiday enhancements.
8. Payroll validation and reconciliation.
9. Onboarding, documents, transfer, promotion and separation.
10. Full and final settlement.
11. Training, certifications, skill matrix and Manufacturing integration.
12. Advanced statutory, recruitment, performance and employee financial capabilities.

The order may be adjusted based on dependency findings, but do not begin downstream UI work before the relevant data model, authorization and business rules are agreed.

---

## 9. Definition of done

A package is not complete merely because its UI exists. Mark a capability **Implemented** only when all applicable requirements are satisfied:

- Reviewed requirements, explicit business decisions and exclusions.
- Database migration and compatibility/rollback review.
- Backend logic and server-side authorization.
- Frontend integration, where required.
- Audit and approval behavior.
- Unit, API and negative-path tests.
- Tenant-isolation and data-scope tests.
- Regression tests for existing HR, Payroll, Finance and Manufacturing behavior.
- Actual CI results recorded.
- Documentation and implementation tracker updated.
- Reviewed and merged PR.

Use status labels consistently: **Not started**, **In specification**, **In development**, **In review**, **Implemented**, or **Blocked**. Do not label planned work as implemented.

---

## 10. Immediate next deliverable

The first feature-level specification should be:

**[Nexora HR Enhancement Specification v1.1 — Phase P0.1: Shift & Roster Management](NEXORA_HR_ENHANCEMENT_SPECIFICATION_v1.1_P0.1_SHIFT_ROSTER.md)**

It must define:

1. Scope and exclusions.
2. Shift type and shift assignment data models.
3. Daily, weekly and overnight shift behavior.
4. Attendance integration and calculation rules.
5. Employee, supervisor and HR permissions/data scopes.
6. API and screen specifications.
7. Audit and approval requirements.
8. Edge cases and acceptance tests.
9. Migration strategy for existing attendance records.
10. Repository task breakdown.

Before implementing P0.1, audit the current attendance model to confirm whether it can support shift-based calculations without corrupting existing attendance or payroll history.

---

## 11. Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 8 November 2026 | Initial high-value, phased HR implementation roadmap. |
