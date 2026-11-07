# Nexora HR & Payroll — Implementation Status and Next Work

**Document ID:** NEX-HR-STATUS-001  
**Version:** 1.0  
**Status:** Active implementation tracker  
**Baseline:** 7 November 2026  
**Repository baseline:** `main`  
**Audience:** GodlyKO and Adi Sarkale  
**Purpose:** One shared reference for completed HR/Payroll work, remaining gaps, implementation decisions, ownership, and verification. Both project contributors should read this before changing HR, Payroll, authorization, or related data models.

> This is an implementation tracker, not a claim that every planned capability is complete. “Merged” means present in the repository baseline; it does not mean this document independently reran every test or verified production deployment.

---

## 1. Current position

The existing HR foundation and payroll workspace are in place. The next phase is not a rewrite. It is a controlled extension of the current employee, payroll, authorization, and audit foundations.

| Area | Current status | Next action |
|---|---|---|
| Employee master and lifecycle | Implemented in the current baseline | Maintain regression coverage |
| Employee skills and production linkage | Implemented | Preserve cross-module ownership |
| Payroll, attendance, calendar and payslips | Implemented as the current payroll foundation | Add leave policy/accrual and statutory configuration |
| Tenant timezone | Implemented; defaults to `Asia/Kolkata` | Keep branch/site overrides deferred until the organization model supports them |
| Audit service integration | Implemented for the covered HR/P1 events | Expand the event catalogue as new capabilities are added |
| Branch/team data scopes | **Not implemented** | First establish reliable branch and reporting-manager relationships |
| Granular feature/action authorization | **Partially implemented** | Extend the existing module-level access model to feature/action grants |
| Automatic leave accrual | **Not implemented** | Design and implement configurable monthly and pro-rata accrual |
| Statutory payroll jurisdiction | **Not implemented as a jurisdiction-aware ruleset** | Introduce Maharashtra as configuration 1, with an extensible jurisdiction model |

## 2. Completed work in the current repository baseline

The following capabilities are present in the repository's merged implementation history.

### 2.1 Employee / HR foundation

- Tenant-scoped employee master and employee-type definitions.
- Backend-generated employee codes with configurable patterns and numbering.
- Employee details editing without allowing employee-code changes.
- Employee activation/deactivation with historical records retained.
- Employee skills used by production assignment workflows.
- Employee master and lifecycle API ownership placed under the HR domain rather than Manufacturing.
- Joining date and optional end date on employee records.
- New employee creation requires a joining date; an end date cannot precede it.
- Legacy employees with unknown joining dates remain explicitly unknown; migration does not invent employment history.
- Employee deactivation is blocked when unfinished production operations remain assigned.
- Tenant-isolation, lifecycle, and payroll-readiness regression coverage has been added.

### 2.2 Payroll foundation

- Annual salary profiles and salary-component breakdown.
- Configurable salary counting modes: working days, calendar days, or fixed monthly days.
- Configurable weekly offs and editable holiday/week-off calendar overrides.
- Month-wise daily attendance.
- Excel attendance template and validated attendance import.
- Payroll preview and finalized monthly payroll snapshots.
- Downloadable PDF payslips for finalized payroll periods.
- Payroll audit events for covered salary, calendar, attendance, import, finalization, and payslip operations.
- Mid-month joining/end-date proration for monthly gross and configured PF/PT/TDS deductions.
- Attendance and overtime outside the employee's employment period are excluded from payroll calculations.
- Tenant-level IANA timezone setting, defaulting to `Asia/Kolkata`; attendance punches are interpreted in tenant-local time and stored in UTC.

### 2.3 Shared platform work used by HR

- Tenant-specific database context and tenant isolation.
- Centralized Core audit event service for the covered P1 changes.
- Backend authorization guards for module/area access.
- Dedicated HR role exists in the current role model; HR access remains separate from Finance and Settings/system administration.
- HR and payroll routes enforce HR access for protected management operations.

### 2.4 Contributor history / attribution

This section records repository contribution history so both contributors can see the work already carried out. It is not a ranking of contribution.

| Contributor | Merged work referenced here | Evidence |
|---|---|---|
| **Adi Sarkale** | Payroll backend and frontend phases: salary profiles, attendance, calendar, payroll snapshots, Excel import/template, payslips, payroll UI and tests | PR [#16](https://github.com/AdiSarkale/remake-tally/pull/16) |
| **GodlyKO** | Consolidated P1 work: HR-owned employee lifecycle, employment dates, payroll employment-period safeguards, tenant timezone, centralized audit integration, deactivation safeguards and regression tests | PR [#24](https://github.com/AdiSarkale/remake-tally/pull/24) |
| **Both contributors** | Continue from the merged `main` baseline and coordinate all follow-up changes through reviewed branches/PRs | This shared tracker |

Earlier planning and authorization groundwork should also be reviewed before changing the access model. Do not assume an older closed/unmerged branch is the current source of truth.

---

## 3. Workstream A — Branch and team scopes

**Status: NOT IMPLEMENTED — blocked by missing organizational relationships.**

The current employee data model does not yet provide reliable branch membership or a dependable reporting-manager hierarchy. Department text alone is not a safe basis for team authorization.

### Required prerequisite work

1. Define the organization hierarchy and branch/site identity.
2. Add stable branch/site records and employee-to-branch relationships.
3. Define whether employees can belong to one or multiple branches, including effective dates and primary-branch rules.
4. Add a reliable reporting-manager relationship, including effective dates and reassignment history.
5. Define team membership semantics and behavior when a manager or employee changes branch/manager.
6. Backfill legacy records only where the relationship can be verified; do not infer branch or manager assignments from free-text department/designation fields.

### Target scope model

Once the prerequisite relationships exist, support scopes such as:

- Own records.
- Assigned employees/workers.
- Reporting team.
- Department.
- Branch/site.
- Whole tenant/company, subject to explicit permission.

### Acceptance requirements

- A manager cannot see another manager's team merely by guessing an employee identifier.
- Branch-scoped access cannot cross branch boundaries without an explicit higher-level grant.
- Reassignment changes future access without rewriting historical approvals or audit records.
- Missing or ambiguous branch/manager relationships fail closed for scoped access.
- API list, detail, search, export, and download paths enforce the same scope rules.

**Do not implement team/branch authorization by filtering only in the frontend or by matching department strings.**

---

## 4. Workstream B — Granular authorization

**Status: PARTIALLY IMPLEMENTED — module/area access exists; feature/action-level migration remains.**

The current access model distinguishes broad module areas. That is not yet the target Nexora authorization model.

### Target authorization dimensions

`Tenant entitlement → Module → Feature/Sub-task → Action → Data scope`

The action vocabulary should be defined per feature and may include:

- View
- Create
- Edit
- Delete
- Submit
- Approve
- Reject
- Release
- Cancel
- Export
- Download

Permission, responsibility/assignment, and approval authority must remain separate concepts.

### Required implementation

1. Inventory current module-level grants, role mappings, backend guards, frontend visibility checks, and route dependencies.
2. Define stable module and feature identifiers; avoid display-label-based permission keys.
3. Define supported actions for each feature.
4. Introduce persisted feature/action grants with tenant and role/user scope as appropriate.
5. Provide a compatibility/migration path from existing module-level grants.
6. Define allow/deny precedence, multiple-role combination, safe defaults, and permission revocation behavior.
7. Enforce the resulting policy in backend APIs, direct record access, exports/downloads, and background jobs.
8. Keep frontend controls as a usability layer only; the backend remains authoritative.
9. Add audit events for grant creation, changes, revocation, and role/profile changes.
10. Add tenant-isolation and privilege-escalation regression tests.

### Migration safety

- Existing legitimate module access must not be accidentally removed during migration.
- Migration must not silently broaden access.
- New feature/action permissions default to deny unless explicitly mapped and approved.
- Do not grant Finance, system administration, or unrelated modules merely because a user has HR access.
- Keep a reviewed mapping table from old module grants to new feature/action grants.

### Acceptance requirements

- Tests cover every role and sensitive action.
- Unauthorized API calls return a denial even when the frontend is bypassed.
- A user with View cannot Create/Edit/Approve unless separately granted.
- Approval authority is checked independently from ordinary edit permission.
- Revoked grants take effect server-side.
- Cross-tenant grants and access are impossible.

---

## 5. Workstream C — Automatic leave accrual

**Status: NOT IMPLEMENTED — entitlement is configurable, but HR currently allocates balances manually.**

The next leave implementation must support configurable accrual rather than assuming one universal company policy.

### Target accrual capabilities

- Configurable annual entitlement by leave type and policy group.
- Monthly accrual.
- Pro-rata accrual for employees joining or leaving partway through an accrual year.
- Effective-dated policy assignment.
- Accrual ledger entries with source, period, quantity, calculation details, and audit references.
- HR adjustments with reason and audit history.
- Balance calculation from opening balance, accruals, adjustments, approved leave, reversals, and carry-forward.

### Policy decisions to specify before implementation

- Accrual frequency and accrual date (monthly, daily, or another configured cycle).
- Calendar-year versus financial-year versus employee-anniversary leave year.
- Pro-rata denominator and treatment of partial months.
- Rounding precision and rounding direction.
- Treatment of unpaid leave, probation, suspension, and inactive employment.
- Carry-forward limits and expiry.
- Negative balances and advance leave.
- Policy changes during an accrual year.
- Whether balances are posted at period start, period end, or on a scheduled accrual run.
- Reversal behavior for corrected employment dates or leave transactions.

### Required safeguards

- Accrual runs must be idempotent: rerunning a period cannot double-credit leave.
- Accrual must be calculated against the policy version effective for that period.
- Historical ledger entries must not be overwritten by later policy changes.
- HR adjustments require a reason and audit event.
- Approved leave must reduce the appropriate balance exactly once; cancellation/reversal must restore it exactly once.
- Payroll and leave integration must use approved leave records, not unapproved requests.

### Acceptance requirements

- Monthly accrual produces the configured entitlement over the full policy year.
- Mid-year joining/leaving produces the configured pro-rata result.
- Re-running an accrual period does not duplicate credits.
- Policy changes preserve the historical calculation basis.
- Leave approval, cancellation, and reversal produce balanced ledger movements.
- Tenant A cannot read or modify Tenant B leave balances or policies.

---

## 6. Workstream D — Statutory payroll jurisdiction

**Status: NOT IMPLEMENTED as a jurisdiction-aware statutory ruleset.**

**Confirmed product decision:** Maharashtra is the first statutory payroll jurisdiction and will be **Configuration 1**. The design must support additional jurisdictions later without changing the core payroll calculation engine.

### Target configuration model

- Jurisdiction identifier: `IN-MH`.
- Display name: Maharashtra, India.
- Configuration sequence: 1.
- Effective-dated statutory rule sets.
- Separate rule categories for central and state-level obligations.
- Configurable thresholds, rates, caps, slabs, exemptions, employee/employer applicability, rounding, and payment/reporting periods where applicable.
- Versioned rule sources and approval metadata.
- Payroll run snapshots that retain the exact jurisdiction and rule-set versions used.

### Important design boundary

Do not hardcode Maharashtra-specific statutory values throughout payroll formulas. The calculation engine should consume effective-dated configuration.

Do not assume every statutory component is state-specific. Central and state-level obligations must be represented separately and composed for the selected jurisdiction.

### Initial statutory coverage to assess for Maharashtra

The specification must assess applicability and required calculation/data for:

- Provident Fund (central framework; applicable establishment/employee rules).
- Employees' State Insurance (central framework; applicability and wage thresholds).
- Maharashtra Profession Tax.
- Maharashtra Labour Welfare Fund.
- Income-tax/TDS under the applicable central rules.
- Any other statutory payroll obligation that a qualified compliance reviewer confirms is in scope for the target customer and release.

This list is a research/specification checklist, not a claim that every item applies to every SPW employee or that statutory rates have already been verified.

### Compliance control

Before production use, every statutory rule, threshold, slab, contribution rate, wage definition, exemption, due date, return, and effective date must be verified against authoritative government material and reviewed by a qualified payroll/compliance professional. Do not use illustrative defaults to finalize live payroll.

### Acceptance requirements

- SPW can select Maharashtra Configuration 1.
- Payroll calculation resolves the effective rule set for the payroll period.
- A later rule update does not alter already finalized payroll snapshots.
- Additional jurisdictions can be added as configuration without rewriting shared calculation logic.
- Every statutory line item exposes its calculation basis and rule version for audit.
- Missing or expired mandatory statutory configuration blocks finalization rather than silently assuming zero or using stale values.

---

## 7. Recommended implementation order

| Order | Work package | Reason |
|---:|---|---|
| 1 | Confirm and document HR/Payroll current baseline | Prevent duplicate or conflicting work |
| 2 | Specify leave policy and accrual ledger | Self-contained HR capability with clear testable outcomes |
| 3 | Implement leave accrual backend, migration, APIs and tests | Establish trustworthy leave balances |
| 4 | Specify Maharashtra statutory rule model and obtain compliance validation | Statutory values must not be guessed |
| 5 | Implement jurisdiction configuration and Maharashtra Configuration 1 | Make payroll jurisdiction-aware |
| 6 | Inventory and migrate module grants to feature/action permissions | Security-sensitive cross-module change |
| 7 | Define branch/site and reporting-manager data model | Required prerequisite for reliable scopes |
| 8 | Implement branch/team scopes | Depends on trustworthy organization relationships |
| 9 | Integrate leave and statutory payroll into payroll finalization and payslips | Only after component-level tests pass |

This order may be adjusted if repository dependencies require it, but branch/team scopes must not be simulated with unreliable data and statutory rules must not be released without compliance validation.

---

## 8. Shared working agreement for GodlyKO and Adi

1. Read this tracker and the relevant module specification before changing HR/Payroll/Core.
2. Work from the latest `main` branch, unless a task explicitly names another reviewed branch.
3. Create a focused feature branch for each work package.
4. Keep migrations, backend logic, frontend behavior, tests, and documentation in the same reviewable change where practical.
5. Do not overwrite or rewrite another contributor's unmerged work.
6. Record the responsible contributor and reviewer in the PR.
7. Do not merge a migration or security-sensitive change without reviewing upgrade/downgrade behavior and tenant isolation.
8. Record actual test/CI outcomes. “Tests added” is not the same as “tests passed.”
9. Update this tracker when a capability changes status; include the PR/commit reference.
10. Preserve historical payroll, leave ledger, approvals, and audit records.

### Suggested ownership split

Ownership is assigned per work package, not permanently by person. GodlyKO and Adi should agree the assignee/reviewer in each PR so parallel work does not collide.

| Work package | Suggested coordination |
|---|---|
| Leave accrual specification and policy decisions | Joint review before implementation |
| Leave accrual backend and tests | One implementation owner; other contributor reviews |
| Maharashtra statutory rule research/configuration | Joint review with qualified compliance input |
| Granular authorization migration | Joint architecture review; one owner for migration and backend enforcement |
| Branch/site and reporting-manager model | Joint data-model review before schema changes |
| Branch/team scopes | Start only after the organization model is accepted |

---

## 9. Definition of done

A workstream may be marked **Implemented** only when all applicable items are complete:

- Reviewed requirements and explicit decisions.
- Database migration and rollback/compatibility review.
- Backend implementation and authorization.
- Frontend integration, if required.
- Audit behavior.
- Unit and API tests, including negative cases.
- Tenant-isolation tests.
- Regression tests for existing HR, Payroll, and Production behavior.
- CI results recorded from the actual target branch/PR.
- Documentation and this tracker updated.
- PR reviewed and merged.

---

## 10. Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 7 November 2026 | Initial shared HR/Payroll implementation tracker; records current baseline, contributor history, branch/team scope gap, granular authorization migration, leave accrual gap, and Maharashtra Configuration 1 decision. |

**End of document.**
