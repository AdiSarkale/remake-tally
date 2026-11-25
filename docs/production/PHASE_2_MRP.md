# Phase 2 — MRP Net Requirement Calculation (Smart PR Excluded)

The endpoint aggregates demand from active production orders and direct BOM raw materials.

Supply is netted using:
- Physical stock.
- Open purchase order quantities (sent and partially received, less received quantity).
- Raw-material minimum stock as safety stock.
- Reservation quantities are displayed for traceability; they are not subtracted a second time from aggregated gross demand.

Formula:
`Net Requirement = max(0, Gross Demand + Safety Stock - Physical Stock - Open PO Supply)`

This phase returns calculation results only. It does **not** create Smart Purchase Requests or purchase requisitions.
