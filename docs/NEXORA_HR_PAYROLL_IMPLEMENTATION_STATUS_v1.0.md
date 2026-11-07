# Nexora HR & Payroll — Implementation Status and Next Work

**Document ID:** NEX-HR-STATUS-001  
**Version:** 1.1  
**Status:** Active implementation tracker  
**Baseline:** 8 November 2026  
**Integration branch:** `docs/hr-phase-2-implementation-status`  
**Integration PR:** [#27](https://github.com/AdiSarkale/remake-tally/pull/27) — open, not merged into `main`  
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
| Payroll, attendance, calendar, payslips and leave workflows | Implemented as the current payroll foundation | Add Maharashtra statutory configuration after compliance review |
| Tenant timezone | Implemented; defaults to `Asia/Kolkata`; branch records also store IANA timezones | Payroll still uses the tenant timezone; branch-specific payroll timezone behavior remains future work |
| Audit service integration | Implemented for the covered HR/P1 events | Expand the event catalogue as new capabilities are added |
| Branch/team data scopes | **Implemented in the P0 branch** | Admin must configure verified employee assignments; no legacy auto-backfill |
| Granular feature/action authorization | **Implemented as an override-capable framework; compatibility fallback remains** | Complete role-by-role least-privilege matrix and remove legacy wildcard fallback when approved |
| Automatic leave accrual | **Implemented for monthly and monthly-prorated policies** | HR triggers each accrual period; background scheduling and annual-upfront automation remain out of scope |
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
- P0 adds persisted role/module/feature/action/data-scope grants, explicit employee-account links, branch/site records, effective-dated reporting assignments, leave workflows and an accrual ledger.
- P0 adds payroll preparation, separate approval, finalization, locking, reversal and Finance journal posting safeguards.

### 2.4 Contributor history / attribution

This section records repository contribution history so both contributors can see the work already carried out. It is not a ranking of contribution.

| Contributor | Merged work referenced here | Evidence |
|---|---|---|
| **Adi Sarkale** | Payroll backend and frontend phases: salary profiles, attendance, calendar, payroll snapshots, Excel import/template, payslips, payroll UI and tests | PR [#16](https://github.com/AdiSarkale/remake-tally/pull/16) |
| **GodlyKO** | Consolidated P1 work: HR-owned employee lifecycle, employment dates, payroll employment-period safeguards, tenant timezone, centralized audit integration, deactivation safeguards and regression tests | PR [#24](https://github.com/AdiSarkale/remake-tally/pull/24) |
| **Both contributors** | Continue from the reviewed integration branch and coordinate follow-up work through reviewed branches/PRs | PR [#28](https://github.com/AdiSarkale/remake-tally/pull/28), merged into the PR #27 head branch only |

Earlier planning and authorization groundwork should also be reviewed before changing the access model. Do not assume an older closed/unmerged branch is the current source of truth.

---

## 3. Workstream A — Branch and team scopes

**Status: Implemented in P0 integration**

The data model and backend scope enforcement are now present. The implementation uses stable tenant-local branch records and effective-dated employee organization assignments rather than inferring authorization from free-text department fields.

### Implemented data model and APIs

- `hr_branches`: tenant-local branch code, name, address, IANA timezone and active status.
- `employee_org_assignments`: employee, branch, department, reporting manager, `valid_from`, `valid_to`, creator and creation timestamp.
- Admin APIs:
  - `GET/POST /api/v1/authorization/branches`
  - `PUT /api/v1/authorization/branches/{branch_id}`
  - `GET/POST /api/v1/authorization/employee-org-assignments`
- A new assignment closes a prior overlapping open assignment on the day before the new effective date.
- The API rejects self-reporting and reporting cycles and validates branch/manager references.
- Existing employees are deliberately **not auto-assigned**. Admin must create verified assignments; no relationships are fabricated from legacy department/designation text.

### Implemented data scopes

- `tenant`: tenant-wide records.
- `self`: only the employee linked to the authenticated login.
- `department`: employee department relationship.
- `branch`: employees with the same current effective branch assignment.
- `team`: direct and indirect reports through effective-dated manager assignments.

Scope filtering is applied to employee lists and leave balance/request collections. Direct employee mutation and skill routes also enforce the configured employee scope. Missing or ambiguous branch/team relationships fail closed.

### Operational requirements still remaining

1. Admin must configure branch records and employee assignments before granting branch/team-scoped access.
2. Backfill legacy employee relationships only after HR verifies them.
3. Extend the same scope policy to any future employee-backed exports, reports, bulk actions and newly added APIs.
4. Add organization assignment history review/reporting and optional multiple-branch membership only if the business requires it.

### Acceptance checks

- Branch/team grants cannot cross tenant boundaries.
- Team access follows direct and indirect reporting relationships.
- Reassignment changes current scope without rewriting prior assignment or audit history.
- Unlinked users cannot obtain self/branch/team access.
- Employee list, duplicate search, update, status and skills endpoints apply scope checks.

**Status:** Core branch/team data model and employee/leave scope enforcement implemented; operational configuration and broader future endpoint coverage remain ongoing responsibilities.

---

## 4. Workstream B — Granular authorization

**Status: Implemented with backward-compatible migration**

The P0 implementation adds persisted role grants at module, feature, action and data-scope level.

### Implemented authorization model

`Role → Module → Feature → Action → Data scope`

Persisted grant fields:

- Role
- Module
- Feature
- Action
- Data scope (`tenant`, `self`, `department`, `branch`, `team`)
- Allowed/denied
- Updated by and timestamp

### Implemented components

- `role_permission_grants` with a unique constraint across role/module/feature/action/data-scope.
- `require_permission(module, feature, action, data_scope)` for explicit protected actions.
- Route-level feature/action derivation for module-guarded endpoints; explicit workflow transitions such as approve, prepare, finalize, lock, reverse and cancel are mapped to their action names.
- Exact feature/action grants take precedence over compatibility wildcard grants.
- Explicit denied grants block the matching route even when the legacy module wildcard would otherwise allow it.
- Admin-only APIs to list and upsert role grants.
- Audit events for permission grant creation and changes.
- Admin UI to manage role grants and their data scopes.
- Tenant isolation and regression tests for denial, role boundaries, route action mapping and grant revocation.

### Migration behavior and honest limitation

The migration seeds compatibility wildcard grants from the existing role/module matrix so existing users do not unexpectedly lose access during the transition. Exact feature/action grants can then narrow or deny individual capabilities.

**This means the framework is implemented, but the full least-privilege conversion is not yet complete.** The old module-level wildcard fallback remains active for routes without an exact grant. A role-by-role feature/action matrix must be reviewed and approved before wildcard defaults are removed; removing them prematurely could break existing ERP workflows.

### Remaining authorization work

1. Approve the complete role-by-role feature/action matrix for every ERP module.
2. Replace remaining compatibility wildcard grants with explicit grants after route inventory and regression testing.
3. Review routes that use bespoke role checks or do not use the common module guard.
4. Extend feature/action checks to new background jobs, exports and integration endpoints as they are introduced.
5. Add permission administration UX for bulk profile management only after the permission registry is stable.

**Status:** Persisted granular grant framework, route enforcement, scoped grants, migration compatibility and Admin management UI implemented. Full removal of legacy wildcard access remains a controlled follow-up, not a completed claim.

---

## 5. Workstream C — Automatic leave accrual

**Status: Implemented for monthly and monthly-prorated policies**

Leave policy, balance, request and approval workflows are present. The P0 implementation adds automatic accrual calculation and a period ledger so HR no longer needs to manually allocate every monthly credit.

### Implemented policy methods

- `annual_upfront`: annual entitlement is still allocated by HR.
- `monthly`: one-twelfth of annual entitlement is accrued for each eligible month.
- `monthly_prorated`: monthly entitlement is prorated by eligible calendar days in the month, considering employee joining date, end date and policy effective date.

The current v1 leave year is calendar-year based. A leave request cannot span two calendar years.

### Implemented accrual engine

- `hr_leave_accrual_ledger` stores employee, leave type, year, month, accrued amount, actor and timestamp.
- Unique constraint on employee + leave type + year + month prevents duplicate period entries.
- HR can trigger the accrual run from the Leave workspace.
- Re-running an already processed period skips existing ledger entries.
- Accrual calculations round to two decimal places.
- Inactive employees without a verified end date are excluded; a known end date is respected even if the legacy active flag was not updated.
- Balance records are created/updated in the same transaction as ledger entries and audit events.
- Leave requests check available balance; approval updates attendance and consumes the balance once.
- Leave type policy becomes immutable once it is referenced by balances or requests, preserving the calculation basis.

### Operational limitations

- Accrual execution is **HR-triggered**, not a scheduled background job. A scheduler/automation can be added after deployment cadence and failure/retry ownership are defined.
- `annual_upfront` remains HR-managed.
- Carry-forward is HR-triggered and limited by the configured cap; it is not automatically scheduled.
- Policy year is calendar-year based in this release.
- Historical balances created manually before enabling monthly accrual must be reconciled before the first run to avoid duplicating already-allocated entitlement.

### Verification coverage added

- Full monthly accrual amount.
- Mid-month joining pro-rata.
- Mid-month exit pro-rata.
- Policy effective-date pro-rata.
- Unique ledger constraint.
- Existing API integration coverage runs the same period twice and checks that the second run does not create duplicate accrual.

**Status:** Monthly and monthly-prorated calculation, ledger, HR trigger, idempotency and balance integration implemented. Scheduled execution, financial-year policy support and annual-upfront automation remain future enhancements.

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
| 1 | Verify P0 branch integration and run full CI | Confirm migrations, tenant isolation, backend and frontend behavior |
| 2 | Configure real branch and reporting-manager assignments | Existing employees are not auto-assigned |
| 3 | Approve role-by-role feature/action matrix | Required before removing compatibility wildcard grants |
| 4 | Reconcile legacy leave balances and run first monthly accrual | Prevent duplicate opening credits |
| 5 | Decide whether monthly accrual should be scheduled | Current implementation is HR-triggered |
| 6 | Specify Maharashtra statutory rule model and obtain compliance validation | Statutory values must not be guessed |
| 7 | Implement jurisdiction configuration and Maharashtra Configuration 1 | Make payroll jurisdiction-aware |
| 8 | Extend branch/team scopes to future employee-backed exports and reports | Maintain consistent server-side scope enforcement |

This order may be adjusted if repository dependencies require it, but branch/team scopes must not be simulated with unreliable data and statutory rules must not be released without compliance validation.

---

## 8. Shared working agreement for GodlyKO and Adi

1. Both GodlyKO and Adi must read this tracker and the relevant module specification before changing HR/Payroll/Core.
2. For this integration, use `docs/hr-phase-2-implementation-status` as the shared PR #27 head branch. Do not merge PR #27 into `main` until both contributors approve.
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
| Leave accrual backend and tests | Implemented in P0; both contributors review operational policy and first-run reconciliation |
| Maharashtra statutory rule research/configuration | Joint review with qualified compliance input |
| Granular authorization migration | Framework implemented; jointly approve the role-by-role matrix before removing wildcard fallback |
| Branch/site and reporting-manager model | Data model implemented; Admin/HR must verify and configure assignments |
| Branch/team scopes | Core enforcement implemented; jointly review coverage as new employee-backed endpoints are added |

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
| 1.0 | 7 November 2026 | Initial shared HR/Payroll implementation tracker. |
| 1.1 | 8 November 2026 | Updated after P0 integration into the PR #27 head branch: records branch/team scopes, granular authorization framework and monthly/pro-rata leave accrual as implemented, with operational and migration limitations explicitly retained. |

## 11. Integration and verification record

- P0 feature branch: `feat/p0-hr-leave-payroll-authorization`.
- Integrated into the PR #27 head branch through [PR #28](https://github.com/AdiSarkale/remake-tally/pull/28), merged on 8 November 2026.
- Integration commit: `5bf82aab2db2944e54a9ac001fdbef2b9cd47d81`.
- PR #27 remains open and unmerged; its target is `main`, but no merge to `main` has been performed.
- Automated test status must be taken from the current PR #27 checks. Do not treat code presence or tests added as proof that CI passed.

**End of document.**
