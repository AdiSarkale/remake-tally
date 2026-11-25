# Phase 2 — MRP (Smart PR excluded)

## Demand
Aggregate material demand from plannable production orders and active BOMs.

## Supply
Report physical stock, active reservations, open purchase-order supply, expected PO receipts, and safety stock.

## Net requirement
Net Requirement = max(0, Gross Demand + Safety Stock - Physical Stock - Open PO Supply)

Reservations are reported for traceability and allocation, but are not deducted again from physical supply when their associated production orders are included in gross demand. This avoids double-counting the same demand.

## Replanning
The calculation is on-demand and reflects current production orders, reservations, stock, and open PO lines.

## Explicit non-goal
No automatic or Smart PR creation, no purchase requisition mutation.
