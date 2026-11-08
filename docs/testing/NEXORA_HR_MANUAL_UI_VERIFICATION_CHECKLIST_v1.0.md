# Nexora HR/Payroll — Manual Staging UI Verification Checklist

**Version:** 1.0  
**Status:** Pending manual execution  
**Target:** Staging tenant with representative Employee, HOD, HR, Admin and Finance accounts  
**Rule:** Do not mark a scenario PASS from mocked Playwright coverage alone. Record the tester, date, tenant, account role, evidence and actual result.

## Preconditions

- [ ] Deploy the reviewed integration branch to an isolated staging environment.
- [ ] Apply tenant migrations through `p0_authz_exact_015`.
- [ ] Create one active branch and verified employee organization assignments.
- [ ] Link employee logins to employee records.
- [ ] Configure one department HOD and confirm the reporting/approval relationship.
- [ ] Create Employee, HOD, HR, Admin and Finance test accounts with known roles.
- [ ] Configure Finance payroll account mapping to active expense/liability accounts.
- [ ] Use synthetic employee/payroll data only; do not use real bank, tax or identity data.

## Employee self-service

- [ ] Employee can sign in and open the HR/Leave workspace.
- [ ] Employee sees only their own leave balances and requests.
- [ ] Employee can submit a valid leave request.
- [ ] Employee cannot see leave-policy administration, employee-wide balances or Access Control.
- [ ] Employee cannot approve their own request or another employee's request.
- [ ] Employee cannot read another employee's payslip.

## HOD approval

- [ ] HOD sees only pending requests assigned to their login/department.
- [ ] HOD can approve an assigned request with a decision note.
- [ ] HOD can reject an assigned request with a reason.
- [ ] HOD cannot approve a request assigned to a different HOD.
- [ ] HOD cannot approve their own request.
- [ ] Approved leave updates the employee balance/attendance exactly once.
- [ ] HOD cannot administer leave policies, payroll or system authorization.

## HR workflow

- [ ] HR can create/update employee records within its allowed scope.
- [ ] HR can manage leave policies and balances.
- [ ] HR can prepare payroll after attendance readiness checks pass.
- [ ] Payroll preparer cannot approve their own run.
- [ ] A different authorized HR/Admin account can approve the prepared run.
- [ ] HR can finalize only an approved payroll run.
- [ ] HR can lock finalized payroll.
- [ ] HR can reverse finalized/locked payroll only with a reason.
- [ ] PF/PT/TDS fields are visibly labelled as manual/non-certified; users do not interpret them as statutory calculations.
- [ ] HR cannot access Admin Access Control or Finance journal administration unless explicitly granted.

## Admin authorization and organization setup

- [ ] Admin can create/update branches and effective-dated employee organization assignments.
- [ ] Admin can create employee-account links.
- [ ] Admin can view and edit explicit role/module/feature/action/data-scope grants.
- [ ] A route without an exact feature/action grant returns 403; legacy wildcard grants do not restore access.
- [ ] Explicit denied grants block the matching action.
- [ ] Branch/team scopes fail closed when employee assignments are missing or ambiguous.
- [ ] Admin can review audit events for authorization, payroll and leave transitions.

## Finance integration

- [ ] Finance can view payroll account mappings and journal history according to its explicit grants.
- [ ] Payroll finalization creates one balanced Finance journal.
- [ ] Payroll reversal creates one linked opposite journal with debit/credit lines swapped.
- [ ] Reversal journal points to the original journal and payroll run.
- [ ] Repeating a reversal request does not create a second journal.
- [ ] Missing/unposted original journal blocks payroll reversal.
- [ ] Journal totals reconcile to the payroll snapshot and remain immutable.

## Evidence and sign-off

| Field | Value |
|---|---|
| Tester | Pending |
| Date/time | Pending |
| Staging tenant | Pending |
| Build / commit SHA | Pending |
| Browser / version | Pending |
| Test evidence links | Pending |
| Open defects | Pending |
| HR sign-off | Pending |
| Finance sign-off | Pending |
| Admin/security sign-off | Pending |

**Release gate:** Do not claim manual UI verification complete until the checklist has been executed against the deployed staging build with real authenticated roles and evidence attached.
