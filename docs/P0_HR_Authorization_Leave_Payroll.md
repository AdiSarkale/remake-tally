# P0 HR, Authorization and Payroll Workflows

This document describes the current P0 backend implementation on
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
- Employee data scope enforcement currently supports:
  - `tenant`
  - `self`, requiring an explicit account-to-employee link
  - `department`, requiring a mapped actor and a matching persisted employee department
- Branch and team scopes are deliberately not enabled: the current schema does not yet provide reliable branch or manager/team relationships.
- Existing non-P0 modules still have legacy area/role guards; full migration of every module to feature/action grants remains a follow-on within authorization completion.

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
- Annual entitlement is stored on the leave type, but accrual is allocated through HR-managed balance records; automatic monthly/pro-rata accrual is not inferred.
- Carry-forward limit is stored, but year-end carry-forward execution is not automated yet.
- Leave year is calendar-year based; requests crossing calendar years are rejected.
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
- Reversal does not yet create a Finance reversal journal; HR-to-Finance posting/reversal is a separate integration requirement.
- PF/PT/TDS calculations remain configured/manual and are not represented as statutory-compliance certified.
- No automatic bank payment, payslip email delivery or statutory filing is included.

## Required verification before P0 sign-off

- Run full backend unit and integration tests.
- Run tenant PostgreSQL migration tests against a real disposable PostgreSQL instance.
- Exercise Admin/HR/Operator and mapped/unmapped employee scenarios.
- Test department approver, self-approval rejection, overlap, insufficient balance and payroll freeze behavior.
- Verify concurrent preparation/approval/reversal and database locking.
- Verify migration upgrade and downgrade paths on supported databases.
- Complete UI workflow integration and API contract review.
