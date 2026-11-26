# Nexora HR — P0.1-09 Overtime & Compensatory Leave Specification

**Document ID:** NEX-HR-P0.1-09-SPEC-001  
**Version:** 1.0  
**Status:** Implementation specification — product decisions locked; implementation not started  
**Baseline:** 27 November 2026  
**Integration branch:** `docs/hr-phase-2-implementation-status`  
**Decision authority:** Nexora HR Decision Register v1.0 (HR-18–HR-20, HR-25–HR-27, HR-29–HR-30)  
**Prerequisite:** P0.1-08 Daily Attendance Summary & Correction Workflow (backend CI verified)

---

## 1. Purpose

P0.1-09 establishes a traceable overtime-candidate calculation and review workflow, plus the MVP compensatory-leave earning record.

It does **not** certify statutory overtime, decide a tenant's employment policy, calculate final payroll overtime earnings, or implement compensatory-leave balances/redemption.

## 2. Approved product decisions carried forward

| Decision | Requirement |
|---|---|
| HR-18 / HR-27 | Default workflow: supervisor approval followed by HR verification. Workflow routing is configurable through Core Workflow. |
| HR-19 | Overtime policies configurable by applicable employee/shift/day categories. |
| HR-20 | Rounding configurable. Preserve exact source minutes. |
| HR-25 | Work on weekly off/holiday may be compensated as overtime, compensatory leave, or both, according to tenant configuration. |
| HR-26 | MVP records approved earned compensatory-leave credits only. Balance management, requests and redemption are deferred. |
| HR-29 | Separation of duties: requester cannot approve their own overtime/credit request through normal workflow. |
| HR-30 | Payroll-prepared/finalized changes use controlled correction and audit; no silent rewriting. |

## 3. Configuration ownership and activation

All policy is configured by authorized tenant HR Admins in **HR Admin Settings**. Configuration is tenant-isolated, versioned, effective-dated, audited, and has a preview/validation step.

Policy can be scoped by:
- Tenant default.
- Branch.
- Department.
- Employee category/type.
- Shift.
- Day type (scheduled workday, weekly off, holiday).

Specificity precedence must be deterministic and displayed in the policy preview. Conflicting policies at equal specificity are invalid and must fail closed; do not select a winner silently.

**No assumed policy defaults:** if no applicable policy exists, overtime/compensatory calculation remains disabled for that employee/date and returns a configuration-required state. Do not infer a multiplier, threshold, cap, conversion ratio, or rounding rule.

## 4. Overtime candidate calculation

### 4.1 Inputs

- P0.1-08 daily attendance summary and immutable revision.
- Raw active attendance events and their provenance.
- Effective roster/shift snapshot for the local work date.
- Effective HR overtime policy version.
- Effective employee/organization assignment.
- Calendar/day classification (scheduled workday, weekly off, holiday).
- Approved leave and payroll-period state where relevant.

### 4.2 Candidate categories

- **Scheduled workday:** overtime candidate is based on the configured workday calculation mode.
- **Weekly off:** candidate is based on eligible actual work minutes; no candidate when there is no qualifying work.
- **Holiday:** candidate is based on eligible actual work minutes; holiday precedence must follow the tenant's approved calendar/roster policy.
- **No roster or unresolved day classification:** calculation requires explicit policy/configuration; do not guess.

### 4.3 Calculation modes supported by policy

The policy can select one of these calculation modes:

1. **Beyond scheduled net duration:** candidate minutes are eligible actual worked minutes beyond the shift's scheduled net working duration, with paid/unpaid break treatment taken from the effective shift rules.
2. **Outside scheduled interval:** candidate minutes are worked intervals outside the scheduled shift boundary, excluding configured non-work intervals and applying shift break rules.
3. **Off-day/holiday actual work:** eligible actual worked minutes on configured weekly-off/holiday dates.

The exact eligible intervals, thresholds, and caps are policy values, not hard-coded assumptions.

### 4.4 Source-minute integrity

- Store exact raw candidate minutes before rounding.
- Store the policy's rounding method and increment snapshot.
- Store rounded eligible minutes separately.
- Preserve event IDs, summary revision, roster/shift IDs, policy version and day classification.
- Do not discard source minutes when rounding.
- Invalid/incomplete attendance sequences do not automatically become payable overtime; candidate calculation must return an exception/blocked state requiring correction or review.
- Recalculation is idempotent for the same input fingerprint.

### 4.5 Rounding configuration

Supported rounding methods:
- No rounding.
- Floor/down.
- Ceiling/up.
- Nearest increment.

Increment is tenant-configured and validated. Exact candidate minutes remain retained. Rounding must be applied at the policy-defined stage and the stage must be snapshotted. Do not hard-code 15-minute or other common increments.

### 4.6 Eligibility, threshold and cap controls

Tenant HR Admin may configure:
- Eligible employee categories/types.
- Applicable branch, department, shift and day type.
- Minimum qualifying duration/threshold.
- Daily maximum candidate minutes.
- Whether pre-shift and post-shift work are eligible.
- Treatment of paid/unpaid break intervals.
- Whether attendance exceptions block calculation or require review.
- Overtime approval requirement.
- Compensation method: overtime, compensatory leave, or both (where permitted by tenant policy).

Values must be explicit. A missing required value disables that policy rather than inventing a default.

## 5. Overtime workflow

### 5.1 State model

`candidate → submitted → supervisor_approved → hr_verified → approved`

Alternative transitions:
- `submitted → rejected` (reason required)
- `submitted → returned` (reason required; requester may revise/resubmit)
- `supervisor_approved → returned/rejected` when configured workflow permits
- `hr_verified` is the terminal business approval for P0.1-09.

Core Workflow is the authority for routing, approver identity, delegation, transition history and notifications. HR endpoints must not bypass workflow decisions.

### 5.2 Separation of duties

- Requester cannot approve their own candidate/request.
- Supervisor approval and HR verification must be performed by distinct actors unless the tenant's approved workflow explicitly allows a distinct authorized role combination; the requester still cannot self-approve.
- HR verification is required by the default workflow.
- Rejections/returns require reasons.
- All actions are audited.

### 5.3 Review behavior

Reviewers can see:
- Employee and work date.
- Shift/day classification.
- Candidate raw and rounded minutes.
- Attendance exceptions.
- Source event and summary revision references.
- Applicable policy/version and rounding snapshot.
- Previous decision history.

Reviewers may approve/reject/return the request but must not directly edit raw attendance. Attendance correction remains P0.1-08 workflow.

## 6. Compensatory leave — MVP earning credits only

### 6.1 Scope

Create an immutable compensatory-leave earning credit after the required overtime/work-on-offday approval and HR verification.

Credit records include:
- Employee.
- Work date and earning date.
- Source overtime/candidate record.
- Exact eligible minutes.
- Credit units/minutes under the tenant conversion rule.
- Policy version and conversion snapshot.
- Approval actors and timestamps.
- Reason and audit references.
- Status (earned, reversed, superseded as needed for controlled corrections).

### 6.2 Conversion policy

Tenant HR Admin configures the conversion ratio or unit rule. No assumed 1:1 conversion or day-length is allowed. The system retains source eligible minutes and computed credit units.

### 6.3 Explicitly deferred

- Compensatory leave balance.
- Requests and approvals for taking comp leave.
- Redemption.
- Carry-forward, expiry and balance reconciliation.
- Leave-calendar integration.
- Automatic payroll substitution.
- Statutory or legal compliance interpretation.

## 7. Payroll boundary

P0.1-09 creates reviewed overtime/compensatory records only. It does not add overtime earnings to payroll or finalize payable amounts.

P0.1-10 will:
- Snapshot approved overtime and comp-credit decisions into payroll daily provenance.
- Define payroll-period readiness/blocking rules.
- Add controlled revisions and reversals.
- Preserve the payroll/Finance posting and reversal architecture.

No overtime can be represented as payroll-approved/payable merely because its candidate calculation exists.

## 8. Frozen payroll and correction behavior

- Overtime/credit records linked to a prepared/approved/finalized/locked payroll period cannot be silently recalculated or changed.
- A controlled correction/reversal with reason, actor and audit history is required.
- Source attendance corrections continue to use P0.1-08; if the source changes, affected overtime candidates become stale and require controlled recalculation/review.
- Historical policy edits do not change existing candidate snapshots.

## 9. Data model (implementation target)

Exact names may align with repository conventions, but the concepts and constraints are normative:

- Effective-dated, versioned overtime policy.
- Overtime candidate/calculation record with input fingerprint.
- Candidate revision/history or immutable decision snapshots.
- Workflow linkage and decision audit.
- Compensatory-leave earning-credit ledger (immutable credit/reversal entries).
- Policy and source provenance references.

Do not add a comp-leave balance table or redemption workflow in this slice.

## 10. API contract target

Exact paths follow current repository conventions; all are tenant- and data-scope enforced.

| Endpoint | Purpose |
|---|---|
| `GET/POST /hr/settings/overtime-policies` | List/create tenant policy versions |
| `GET/PUT /hr/settings/overtime-policies/{id}` | Read/update policy draft; published versions immutable |
| `POST /hr/settings/overtime-policies/{id}/publish` | Validate and publish effective policy |
| `POST /hr/overtime/calculate` | Calculate/recalculate candidates for date range and scope |
| `GET /hr/overtime` | Candidate/review queue and filters |
| `POST /hr/overtime/{id}/submit` | Submit candidate to configured workflow |
| `POST /hr/overtime/{id}/review` | Workflow-backed supervisor/HR decision (not a workflow bypass) |
| `GET /hr/overtime/{id}/history` | Candidate and decision history |
| `GET /hr/compensatory-leave/credits` | Read earned-credit ledger only |
| `POST /hr/compensatory-leave/credits/{id}/reverse` | Controlled reversal with reason and audit |

## 11. UI target

- HR Admin Settings: policy list, version/effective dates, scoped rules, validation, preview, publish.
- Overtime workspace: candidate list, filters, exception state, raw/rounded minutes, policy snapshot.
- Review queue: supervisor approval, HR verification, return/reject with reasons.
- Employee view: own overtime requests/status, if enabled by permission.
- Compensatory credit ledger: earned/reversed credits, source and policy traceability.
- No comp-leave balance or redemption UI.

## 12. Audit requirements

Audit:
- Policy create/edit/publish/disable.
- Candidate calculation/recalculation and blocked/exception outcomes.
- Submit, approve, HR verify, return, reject and resubmit.
- Credit creation and reversal.
- Scope/authorization failures where shared audit policy requires.
- Frozen-payroll guard outcomes.

## 13. Test and acceptance criteria

- Tenant policy isolation.
- Effective-date and specificity precedence.
- Equal-specificity conflict fails closed.
- Missing configuration disables candidate/payable path.
- Scheduled-workday modes calculate expected candidates from attendance intervals and shift/break rules.
- Weekly-off and holiday work candidates.
- Pre-shift/post-shift eligibility.
- Threshold and daily cap behavior.
- Every rounding method with exact source-minute preservation.
- Incomplete/invalid attendance sequences block automatic candidate.
- Idempotent calculation and stable input fingerprint.
- Policy changes do not mutate historical candidate snapshots.
- Supervisor approval and HR verification workflow; requester cannot self-approve.
- Return/reject reasons and resubmission.
- Compensatory conversion uses configured ratio only.
- Credit ledger immutable and reversal tested.
- Frozen payroll blocks mutation/recalculation.
- API permission/data-scope/tenant isolation.
- Migration and PostgreSQL provisioning.
- Frontend typecheck/build and browser smoke.

## 14. Release boundary

P0.1-09 is complete only when candidate calculation, policy configuration, approval/HR verification, compensatory credit ledger, audit, tests, CI and documentation pass.

**Explicitly not in P0.1-09:** payroll integration, comp-leave balances/redemption, statutory overtime certification, attendance UI/reporting completion, and policy outcomes that require tenant configuration but have not been configured.

**End of specification.**
