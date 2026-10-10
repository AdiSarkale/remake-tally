# Nexora Master Module Planning & Requirements v1.0

**Status:** Working specification  
**Scope:** Multi-tenant ERP foundation, configurable module access, authorization workflows, HR-to-user provisioning, and future workforce billing.

This document separates confirmed product decisions from proposed implementation. A feature is not considered implemented merely because it appears here.

## 1. Confirmed decisions

1. Nexora is a multi-tenant ERP. Each tenant must be able to configure its modules, sub-tasks, roles, permissions, and approval workflows.
2. Configuration should be data-driven wherever possible; tenant-specific behaviour should not normally require a fork or custom code.
3. SPW's initial HR account should have full HR management access, including payroll when the payroll capability is implemented, while accounting and system administration remain restricted.
4. An employee record does not automatically imply a Nexora login account.
5. Employee creation should optionally create an account-access request routed to the shared Authorization module.
6. The configured responsible HR/Admin/authorization person should review and execute approved requests using a permitted access profile.
7. Future versions may distinguish Employee and Worker as separate commercial categories with different pricing.
8. The product should retain audit history for sensitive operations and configuration changes.
9. Major module work should not start until scope, dependencies, permissions, workflows, data, acceptance criteria, and tests are documented.

## 2. Target platform architecture

- **Tenant/company configuration:** enabled modules, features, defaults, and workflow settings scoped to one tenant.
- **Module and feature registry:** stable identifiers for modules, sub-tasks, and supported actions.
- **Identity and access:** login accounts, roles/profiles, permission assignments, and account lifecycle.
- **Authorization workflow:** request, route, approve/reject, execute/provision, and audit.
- **Shared workflow engine:** configurable stages, approver assignment, delegation, conditions, and versioned configuration.
- **Audit service:** actor, action, entity, timestamp, outcome, and relevant before/after details.
- **Commercial entitlement:** subscription/module entitlements and future employee/worker billing categories.

These are target capabilities. Existing implementation must be checked separately.

## 3. HR-to-Authorization flow

1. HR creates an employee record.
2. HR may select **Request Nexora user account**.
3. The request captures the employee, tenant, requested profile/access, business reason, requester, and current workflow version.
4. The shared Authorization module routes the request using tenant configuration.
5. An authorized person approves or rejects it. Approval must not itself bypass provisioning validation.
6. An authorized executor provisions the account and applies only the approved profile.
7. The system records request, decision, execution, and subsequent account changes in the audit trail.
8. Employee offboarding can suspend/revoke access without deleting historical employee or audit records.

A requester must not be able to grant themselves privileges. Approval/execution separation should be configurable, with enforced separation-of-duties rules where the tenant requires it.

## 4. Role and permission model

Permissions must be enforced by the backend, not just hidden in the frontend. The platform should distinguish:

- Module enabled for a tenant.
- Feature/sub-task enabled for a tenant.
- Permission to perform an action.
- Permission to assign that action to another user.
- Approval authority for a particular workflow step.
- Commercial entitlement to use a feature.

A user may hold multiple roles. Custom profiles must be constrained by the permissions and subscription entitlements available to the tenant. System administration remains separate from ordinary HR administration.

## 5. HR and workforce model

### Current foundation
Employee lifecycle and immutable employee codes are part of the existing HR work.

### Planned
- Optional account-access request at employee creation.
- Attendance, leave, payroll and related workflows as separately scoped capabilities.
- Future Employee and Worker classifications for different commercial pricing.
- Person/employment records remain separate from login identities and subscription entitlements.

Do not force the future Worker classification into the current employee model until its operational meaning, lifecycle, and pricing rules are specified.

## 6. Tenant configuration requirements

Authorized tenant administrators should eventually configure:

- Enabled modules and sub-tasks.
- Roles and permission profiles.
- User-to-role assignments.
- Workflow stages and responsible approvers.
- Conditions, optional steps, delegation and escalation.
- Separation-of-duties requirements.
- Defaults and controlled configuration versions.

A workflow version already used by an in-progress request must remain traceable; publishing a new workflow should not silently rewrite historical decisions.

## 7. Security and data integrity requirements

- Every tenant-scoped request must resolve the tenant from trusted authentication context.
- No client-provided tenant ID may override the authenticated tenant.
- Backend authorization is mandatory for every protected operation.
- Access requests must not permit assignment of system-administration privileges through an ordinary HR flow.
- Passwords, access tokens, and secrets must never be written to audit details.
- Account provisioning must use secure initial-credential or invitation flows and require credential setup where appropriate.
- Revocation disables access while retaining records needed for audit and business history.
- Tenant configuration and authorization actions must be auditable.
- Database migrations must be reviewed and tested against the supported database engines before deployment.

## 8. Module delivery checklist

Before implementing any module or major enhancement, document:

1. Purpose, scope, exclusions, and user personas.
2. Feature and sub-task inventory.
3. Screens and user journeys.
4. Data entities, ownership, and relationships.
5. APIs, validation, errors, and integration dependencies.
6. Role/action permission matrix.
7. Approval workflow and exception paths.
8. Audit and reporting requirements.
9. Tenant configuration options and safe defaults.
10. Acceptance criteria and automated/manual tests.
11. Current implementation status and known gaps.
12. Migration, rollout, rollback, and compatibility plan.

## 9. Implementation sequence

1. Complete and verify the current HR foundation.
2. Establish the dedicated HR role and confirm its backend/frontend permission boundary.
3. Design the shared authorization request and configurable-profile data model.
4. Implement the account-access request lifecycle and execution controls.
5. Introduce the module/feature registry and tenant configuration storage.
6. Add the shared configurable workflow engine.
7. Integrate HR employee creation with account-access requests.
8. Extend to payroll and other modules after their specifications are reviewed.
9. Add Employee/Worker commercial classification when the subscription/pricing design is ready.

## 10. Open decisions

- Exact permission actions and the custom-profile representation.
- Which roles may approve, execute, and delegate each authorization request.
- Secure invitation and initial-credential delivery method.
- Payroll scope, approval steps, and permitted integration with Finance.
- Exact Employee versus Worker definitions and pricing/billing rules.
- Which tenant configuration functions are available to tenant Admin versus Nexora platform operators.
- Supported database engines and migration guarantees for role/profile storage.

## 11. Definition of done

A capability is done only when its implementation, database migration, backend authorization, frontend behaviour, automated tests, tenant-isolation checks, audit behaviour, and documentation have been reviewed. CI or local test results must be recorded; tests must not be described as passing without actual output.
