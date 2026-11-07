# P0 HR, Authorization and Payroll Workflows

This document describes the current P0 backend and frontend implementation on
`feat/p0-hr-leave-payroll-authorization`. It is a working implementation note,
not a release sign-off.

## Authorization foundation

- Tenant isolation remains enforced by the authenticated tenant database dependency.
- `employee_user_links` provides a one-to-one link between a login and an employee record.
- `role_permission_grants` stores role grants by module, feature, action and data scope.
- Authorization management APIs are restricted to Admin:
  - `GET/POST /api/v1/authorization/employee-links`
  - `DELETE /api/v1/authorization/employee-links/{link_id}`
  - `GET/PUT /api/v1/authorization/role-grants`
- The generic dependency `require_permission` checks explicit grants.
- Employee data scope enforcement supports `tenant`, `self`, `department`, `branch` and hierarchical `team` scopes. Self requires an account-to-employee link; branch/team require effective-dated organisation assignments.
- `hr_branches` stores tenant-local branches. `employee_org_assignments` stores effective-dated branch, department and manager relationships. New assignments close the prior active assignment and reject reporting cycles.
- Admin APIs manage branches and employee organisation assignments. Existing employees are intentionally not auto-assigned; HR/Admin must configure their real relationships.
- Route-level authorization derives a feature from the resource path and an action from the HTTP method or explicit workflow transition. Exact feature/action grants override a compatibility wildcard grant seeded from the old role matrix.
- This is a safe migration path, not yet a fully least-privilege redesign: legacy module roles still receive wildcard defaults until the business approves a role-by-role feature matrix. Admin can explicitly deny individual feature/action grants.

## Leave management

Endpoints under `/api/v1/hr/leave`:

- `GET/POST /types`, `PUT /types/{leave_type_id}`
- `GET /balances`, `PUT /balances`
- `POST /requests`, `GET /requests`
- `PATCH /requests/{request_id}` for approval or rejection
- `DELETE /requests/{request_id}` for cancellation of pending requests

Controls implemented:
- Requester identity is derived from the authenticated user and explicit employee link.
- Approver is resolved from the employee department's configured HOD; requesters cannot submit an approver identity.
- Requester cannot approve their own request.
- Pending/approved overlap, invalid date range, missing balance, insufficient balance and missing/inactive approver are rejected.
- Leave approval updates attendance using paid/unpaid leave statuses; half-day leave uses separate paid/unpaid half-day attendance statuses.
- Leave policy types become immutable after balances or requests reference them. Create a new leave type code for a changed policy rather than rewriting history.
- Approved leave cannot be applied to a payroll period with a prepared or finalized snapshot.

Policy limitations requiring business decisions:
- Annual entitlement supports `annual_upfront`, `monthly` and `monthly_prorated` methods. HR can run monthly accrual for a period; an idempotent ledger prevents duplicate employee/type/month accrual. Monthly-prorated policy uses eligible employment/effective-date calendar days in that month.
- HR can trigger a policy-limited carry-forward from one calendar year to the next; it is idempotent and not scheduled automatically.
- Leave year is calendar-year based; requests crossing calendar years are rejected. Annual entitlement accrual remains HR-managed through balance allocation; monthly/pro-rata accrual is not inferred.
- Department HOD matching currently uses employee department name against the configured department name.
- Half-day requests must be single-date requests.
- Holiday and week-off counting is configurable per leave type; default is not to count them.

## Payroll safeguards

Payroll lifecycle:
1. Prepare — validates payroll readiness and writes immutable employee/pay components into a revisioned snapshot.
2. Approve — requires a different authorized HR/Admin user from the preparer.
3. Finalize — only an approved snapshot can be finalized.
4. Lock — finalized payroll can be locked.
5. Reverse — finalized or locked payroll can be reversed only with a reason; the original snapshot remains preserved.
6. Prepare a later revision — a new revision can be prepared after the prior revision is reversed.

Additional controls:
- Unique period revision prevents overwriting historical snapshots.
- Salary slips are available only after finalization/locking and only to HR/Admin or the linked employee.
- Attendance and calendar inputs for a prepared/finalized period are frozen.
- Salary profile and payroll settings cannot change while a run is awaiting approval.
- Payroll transitions and sensitive leave/authorization changes are audited.

Payroll limitations:
- Existing legacy finalized runs remain legacy-finalized and are not retroactively assigned an approver.
- Payroll finalization posts a balanced Finance journal using tenant payroll account mappings. Payroll reversal posts a linked opposite journal in the same transaction; legacy finalized payroll without an original journal cannot be reversed through this integrated path.
- PF/PT/TDS calculations remain configured/manual and are not represented as statutory-compliance certified.
- No automatic bank payment, payslip email delivery or statutory filing is included.

## Frontend implementation\n\nThe HR workspace includes Leave, Admin Access Control (branch, reporting assignments and role grants), and payroll state-transition controls. Finance includes chart-of-accounts, payroll account mapping and journal history. Frontend typecheck and production build have passed on earlier commits; the latest changes are under CI verification. Manual browser verification across employee, HOD, HR, Admin and Finance personas remains outstanding.\n\n## Required verification before P0 sign-off

- Run full backend unit and integration tests.
- Run tenant PostgreSQL migration tests against a real disposable PostgreSQL instance.
- Exercise Admin/HR/Operator and mapped/unmapped employee scenarios.
- Test department approver, self-approval rejection, overlap, insufficient balance and payroll freeze behavior.
- Verify concurrent preparation/approval/reversal and database locking.
- Verify migration upgrade and downgrade paths on supported databases.
- Run manual browser workflow verification for employee, HOD, HR and Admin personas; complete final API contract review.


## Finance journal integration

- Minimal tenant chart of accounts and immutable journal header/line tables were added because the previous Finance module only exposed receivables, payables and payment records; it had no general ledger.
- Migration seeds five default payroll accounts and a tenant mapping. Finance can add accounts and change the mapping.
- Payroll finalization debits gross salary expense and credits net salary payable, employee PF payable, professional tax payable and salary TDS payable.
- Journal posting validates reconciliation and is atomic with payroll finalization. Reversal swaps debit/credit lines and links to the original journal. No direct journal edit/delete API is exposed.
- Employer statutory contributions are not yet calculated or posted. The journal currently records the existing employee deduction components only.

## Payroll statutory compliance status

- Statutory calculations are not yet certified or enabled as a compliance engine. PF/PT/TDS values remain manual/configured and must not be marketed as statutory-compliant.
- The rule framework must be configured by tenant jurisdiction and effective date. It must include establishment applicability, employee eligibility, PF membership/wage basis, state-specific professional tax classification, tax regime and annual projected taxable income.
- Do not activate statutory auto-calculation until the applicable rules and employee data have been reviewed by a qualified payroll/compliance professional. See source notes in the implementation review before adding jurisdiction defaults.


### Statutory source review (India, checked 7 November 2026)

These sources demonstrate why static PF/PT/TDS constants are unsafe:

- EPFO/Ministry of Labour announcement: mandatory EPF wage ceiling raised from ₹15,000 to ₹25,000 effective 17 September 2026, subject to applicable membership and scheme conditions: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2310973
- Income Tax Department transition guidance: salary TDS for payments from 1 April 2026 is under section 392(1) of the Income-tax Act, 2025; tax computation must use projected income, deductions and the selected regime for Tax Year 2026-27: https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/tds-compliance
- Maharashtra GST Department PT schedule, published as updated to 31 March 2025: https://www.mahagst.gov.in/public/uploads/mvatservices/1761635685PT%20Rate%20Schedule%20updated_0%20%2801.04.2023%29_0.pdf
- Maharashtra notification dated 28 February 2026 amends PT return/payment due-date rules; it is not itself a replacement salary-rate schedule: https://www.mahagst.gov.in/public/uploads/mvatservices/1772710759_PT%20Notification%2028.2.2026.pdf

Before statutory auto-calculation can be enabled, each tenant must specify its operating state(s), establishment PF applicability and contribution category, employee PF membership/entry status and wage basis, Maharashtra PT exemption/category where applicable, and employee tax regime/declarations/prior-employer income. A compliance reviewer must approve the effective-dated rule set. TDS cannot be calculated correctly from a single fixed monthly amount alone.


## Browser workflow verification

A Playwright smoke suite runs in CI against the frontend with isolated API mocks. It checks:
- Operator/employee can open Leave self-service but cannot see policy administration or Access Control.
- HR can open Leave policy administration and Payroll but cannot see Access Control.
- Admin can open branch/reporting assignment controls and Finance ledger/journal history.

These are browser-level UI smoke tests, not end-to-end backend integration. The final release still requires a manual staging walkthrough with real tenant data and authenticated Employee, HOD, HR, Admin and Finance accounts, including leave submission/decision, account mapping, payroll approval/finalization/reversal, and journal reconciliation.
