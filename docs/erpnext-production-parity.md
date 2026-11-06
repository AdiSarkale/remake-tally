# ERPNext-inspired production parity review

**Reviewed:** 2026-11-06  
**Target:** MiniTally `production` branch  
**Reference:** Frappe ERPNext `develop` branch (public source)

This is a capability comparison, not a claim of feature equivalence. ERPNext is a mature manufacturing ERP with a substantially broader execution and stock-accounting model. The goal is to reuse the workflow ideas that fit MiniTally's current schema, not to transplant ERPNext code or its Frappe framework.

## Existing MiniTally capabilities

| Area | Current implementation | Assessment |
|---|---|---|
| Bill of Materials | Versioned BOMs with active-version selection, material quantities, and expected scrap percentage | Implemented, but single-level; no BOM explosion, sub-assemblies, operation costing, or alternate materials |
| Workcenters | Workcenter master, hourly capacity field, status, location, and supported materials | Foundation implemented; no capacity calendar or finite-capacity scheduling |
| Routing | Versioned product routing with ordered operations, workcenter, skill, setup time, and run time | Foundation implemented; no operation-level time logs or scheduling |
| Production orders | Order quantity/date/due date, generated operation rows, employee assignment, and completed quantity | Basic work-order workflow; no draft/submit/hold/stop/close lifecycle or sales-order planning |
| Production execution | Production entries, BOM consumption, finished-goods receipt, and scrap movement | Implemented at batch level; no separate job-card execution document or WIP transfer |
| Quality | Production-level quality status, accepted/rejected quantities, and remarks | Basic inspection result only; no inspection template, measured parameters, or controlled release |
| Inventory | Aggregate item stock and movement ledger | Basic stock tracking; no warehouse-level production ledger, reservation, serial/batch traceability, or WIP stock |
| Reporting | Production totals, scrap, material variance, and workcenter aggregation | Basic operational summary; no operation efficiency, capacity utilization, or production costing |

## Comparison with ERPNext patterns

ERPNext's manufacturing flow is organized around distinct responsibilities:

1. **BOM** defines component requirements and may include operations, process loss, secondary items, and multi-level sub-assemblies.
2. **Production Plan** consolidates demand and explodes BOMs to determine production and purchase requirements.
3. **Work Order** authorizes a production quantity, carries required items and operations, and can reserve stock.
4. **Job Card** tracks an individual operation, assigned employees, time logs, status, quantities, and quality checks.
5. **Stock Entry** records material issue/transfer, finished-goods receipt, WIP, and related stock effects.

MiniTally currently combines several of these responsibilities in production orders and production entries. This is simpler, but it means it does not yet have the controls or traceability of the separate ERPNext documents.

## Changes made in this update

- Registered the existing `manufacturing` router in the FastAPI application. Without this, the existing workcenter, routing, employee-skill, production-order, quality, and report endpoints were not reachable.
- Added `GET /api/v1/manufacturing/production-orders/{order_id}/material-plan`. It calculates BOM requirements for the order, subtracts recorded consumption linked to the order, compares the remaining requirement with current raw-material stock, and reports shortages.
- Added API response schemas and tests for router registration, shortages, prior consumption, and missing active BOMs.
- Corrected the production-branch CI workflow to run backend dependency installation, compilation, and pytest. This branch has no frontend directory, so a frontend `npm ci` job was not valid for this branch snapshot.

### Material-plan limitation

The material plan is a **read-only point-in-time availability check**. It does not reserve stock, lock inventory, allocate a warehouse, generate a pick list, or protect against another transaction consuming the same stock after the response. A later reservation/issue workflow must implement those controls transactionally before the API can claim materials are secured.

## Recommended next phases

| Priority | Capability | Why it matters |
|---|---|---|
| P1 | Transactional material reservation and release | Prevents two orders from claiming the same available stock |
| P1 | Explicit order lifecycle and operation state transitions | Adds controlled start, hold, resume, completion, and cancellation |
| P2 | Separate job-card execution with employee time logs | Supports operator-level accountability and actual-vs-standard time |
| P2 | Warehouse-aware material issue, WIP transfer, and finished-goods receipt | Gives traceable stock movement by production location |
| P2 | Quality inspection plans and controlled accepted/rejected release | Prevents uninspected production from being treated as releasable stock |
| P3 | Multi-level BOM explosion and sub-assembly planning | Supports products with nested manufactured components |
| P3 | Capacity scheduling, production costing, and efficiency reports | Supports planning and operational improvement |

## Branch note

At review time, `production` is 370 commits behind and 3 commits ahead of `main`. The branches have diverged substantially, and this production snapshot does not contain the current frontend tree. This update intentionally changes only `production`; it does not merge the divergent `main` history.

## Upstream reference locations

- [ERPNext BOM](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/bom)
- [ERPNext Production Plan](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/production_plan)
- [ERPNext Work Order](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/work_order)
- [ERPNext Job Card](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/job_card)
- [ERPNext Stock Entry](https://github.com/frappe/erpnext/tree/develop/erpnext/stock/doctype/stock_entry)

The implementation in this branch is original MiniTally code. These references are used for workflow comparison only.
