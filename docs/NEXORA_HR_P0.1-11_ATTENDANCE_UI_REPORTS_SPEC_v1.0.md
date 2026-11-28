# Nexora HR — P0.1-11 Attendance UI & Reports Specification

**Document ID:** NEX-HR-P0.1-11-SPEC-001  
**Version:** 1.0  
**Status:** Implementation started  
**Baseline:** 27 November 2026  
**Integration branch:** `docs/hr-phase-2-implementation-status`  
**Dependencies:** P0.1-03/04 shift assignments and rosters; P0.1-05 timezone; P0.1-06 raw events; P0.1-07 anomaly review; P0.1-08 daily summary/corrections; P0.1-09 overtime/comp-off; P0.1-10 payroll provenance  
**Authority:** Approved P0.1 Architecture Specification v1.0 and HR Decision Register v1.0

## 1. Purpose
Deliver the missing HR-facing and employee-facing screens and reports that make P0.1 workforce/attendance capabilities usable. This package is UI, read/report API completion, and acceptance integration—not a rewrite of the underlying event, summary, payroll or workflow services.

## 2. Scope
- Shift catalog and break-rule management, using existing authorized APIs.
- Effective-dated employee/department shift assignment view and management.
- Daily roster calendar/list, roster generation, and date-specific overrides.
- Raw attendance event and daily summary views, with source and revision inspection.
- Attendance correction request submission, employee self-view, and HR/supervisor review queues.
- Cross-source attendance anomaly queue, resolution and false-positive actions.
- Daily, monthly, shift-wise, and overtime reporting.
- Supervisor-scoped attendance dashboard.
- Employee self-service assigned shift, attendance summary, and correction request screens.
- Existing backend authorization, employee scope, frozen payroll, audit and separation-of-duties rules remain authoritative.

## 3. Explicit exclusions
- New attendance/payroll policy defaults or statutory interpretation.
- Automatic inference of absence, half-day, late/early consequences or payable OT beyond configured policies.
- Comp-Off consumption/redemption/balance.
- General workflow engine expansion, delegation or notification platform changes.
- Evidence-file upload (evidence reference remains text until file capability is separately scoped).
- Payroll reopening or mutation of finalized snapshots.

## 4. Implementation slices
1. **API read completion:** roster list/detail query with employee-scope enforcement; bounded date filters; route-isolation tests.
2. **Shift & roster workspace:** shift catalog, break rules, assignments, roster generation, overrides and read-only roster view.
3. **Attendance workspace:** daily summary and revision inspection; raw event detail; correction create/resubmit/review queues.
4. **Anomaly review:** filter, compare source events, resolve/false-positive with required reason.
5. **Reports & dashboard:** daily/monthly attendance, shift-wise roster/attendance, OT review summary; scoped aggregation only.
6. **Self-service:** own assigned shift, summary and correction request.
7. **Verification:** backend, tenant isolation, PostgreSQL migrations, typecheck, production build and Playwright workflows plus business acceptance.

## 5. Acceptance criteria
- All data reads and writes use backend endpoints and are tenant-/employee-scope protected.
- UI does not treat hidden controls as authorization; unauthorized API requests remain denied.
- Roster reads are bounded and scoped; no unbounded roster export.
- Generation and override inputs surface backend validation and conflict errors.
- Corrections and anomaly decisions require reasons and preserve immutable source records.
- Summary revisions/fingerprints and raw source references are inspectable.
- Reports clearly label their basis and do not infer policy outcomes not present in source records.
- Daily/monthly reports are date-filtered; shift-wise reports use effective roster snapshots.
- Employee self-service is restricted to linked employee identity.
- Playwright verifies real HR screens and critical interactions; existing API-mocked smoke alone is insufficient.
- All CI jobs pass and product owner acceptance walkthrough is recorded before P0.1-11 is called complete.

## 6. Definition of Done
Implementation, regression tests, scope/authorization tests, migration verification (if any), browser workflows, documentation/tracker updates, and a focused acceptance review all pass. UI presence or compilation alone does not complete this package.

## 7. Implementation status (27 November 2026)

**Slice 01 started:** the bounded roster read API is implemented with effective-date employee read-scope filtering and tenant grants for Admin/HR. Initial HR workspace tabs are present for roster generation/override/view, attendance summaries/raw event inspection/recalculation, anomaly resolution/false-positive review, correction submission/review, attendance/shift/OT reports, shift creation/activation, break-rule creation and employee assignment/end.

**Verification status:** backend unit and tenant-isolation checks passed for the first implementation commit; integrated CI is still running for the latest frontend additions. A frontend strict-TypeScript issue was discovered by CI and corrected; final rerun pending.

**Still incomplete:** department-default assignment UI; roster pagination; comprehensive shift/break-rule edit/update UI; explicit daily/monthly report views and export; supervisor dashboard; live API-backed browser acceptance beyond the current mock smoke. These are tracked as remaining slices, not silently considered complete.


## Implementation status update — 28 November 2026

This update supersedes the earlier "Still incomplete" list in Section 7. The implementation is now materially expanded, but P0.1-11 is **not accepted/closed until CI and owner walkthrough pass**.

### Implemented in the integration branch
- Bounded, stable-offset read pagination for roster, daily summary, raw events, anomalies, correction queues, overtime candidates, and shift assignments.
- Employee-scope filtering is applied before page slicing on the affected list routes; offsets are validated and date windows are capped at 31 calendar days.
- A bounded complete-list client helper loads all API pages for report aggregation/export; workspace tables use visible page controls and row-count metadata.
- Daily and explicit monthly attendance reports, employee-period rollups, shift-wise roster/summary coverage, overtime candidate summaries, anomaly/correction status summaries, and raw source-event summaries.
- Full-dataset CSV exports with metadata and formula-injection-safe cell escaping.
- Supervisor/team overview with rostered days, missing summaries, summary classifications, elapsed/break time, open anomalies, pending corrections and OT candidates; queues are separately paginated.
- Shift and break-rule edit/reactivation controls; department-default assignment creation is present.
- Date filters use local calendar dates; attendance timestamps render using their recorded timezone.
- Regression tests cover scope-safe offset pagination; browser smoke coverage now includes report views/exports, team overview, shift/break edits and department assignment.

### Verification added
- Backend live API integration acceptance uses FastAPI TestClient and isolated tenant SQLite fixtures for paginated roster/summary reads and tenant isolation.
- A separate CI Playwright flow is added to log in to a real ephemeral FastAPI + SQLite server and exercise roster, summary/events, corrections, daily/monthly reporting, supervisor overview, shift/break-rule updates and department-default assignment. This is distinct from the API-mocked smoke test.

### Acceptance status
**P0.1-11 — IN PROGRESS.** CI for the latest commit must complete successfully, including strict TypeScript, production build, API-mocked smoke, live API-backed Playwright, backend tests, tenant isolation, and PostgreSQL migration lifecycle. A focused owner walkthrough must then be recorded. No final CI/acceptance claim is made in this update.
