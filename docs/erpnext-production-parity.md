# Manufacturing capability parity review

This document is the detailed manufacturing capability assessment for MiniTally. The consolidated cross-cutting release plan, including branch reconciliation, multi-company architecture, tenant backup/restore, deployment readiness and manufacturing delivery gates, is maintained in [Production Roadmap](production-roadmap.md). The multi-company operating guide is maintained alongside it in [Multi-company production deployment](multi-company-production.md).

**Reviewed:** 2026-11-06  
**Branch:** `production`  
**Reference:** Frappe ERPNext `develop` branch.

## Current manufacturing assessment

See [Production Roadmap — Manufacturing MVP roadmap](production-roadmap.md#6-manufacturing-mvp-roadmap) for the authoritative DONE / PARTIAL / NOT DONE status table and prioritized delivery sequence.

The current branch has versioned BOMs, workcenters, routings, production orders, batch-level production entries, basic production quality results and a summary manufacturing report. It also exposes a read-only material-plan endpoint with focused tests.

The material plan is a point-in-time availability check. It does not reserve stock, lock inventory, allocate a warehouse, generate a pick list or guarantee that the quantity remains available when a later transaction runs.

## ERPNext workflow comparison

ERPNext separates responsibilities across:

1. **BOM** — component requirements, operations, process loss and nested sub-assemblies.
2. **Production Plan** — demand consolidation, BOM explosion and production/purchase requirements.
3. **Work Order** — authorization of a production quantity, required items and operations, with stock reservation.
4. **Job Card** — operation execution, employee assignment, time logs, status and quality checks.
5. **Stock Entry** — material issue/transfer, finished-goods receipt, WIP and stock effects.

MiniTally currently combines several responsibilities in production orders and production entries. It does not yet provide the same document separation or execution controls.

## Upstream workflow references

- [ERPNext BOM](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/bom)
- [ERPNext Production Plan](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/production_plan)
- [ERPNext Work Order](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/work_order)
- [ERPNext Job Card](https://github.com/frappe/erpnext/tree/develop/erpnext/manufacturing/doctype/job_card)
- [ERPNext Stock Entry](https://github.com/frappe/erpnext/tree/develop/erpnext/stock/doctype/stock_entry)

These references are workflow comparisons, not claims of MiniTally feature equivalence.
