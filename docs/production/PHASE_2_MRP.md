# Phase 2 — MRP / Smart PR

## Objective

Convert production demand into net material requirements and actionable purchase requests.

## Modules

### Demand
Aggregate material demand from:
- planned production orders
- approved production requirements
- existing reservations

### Supply
Account for:
- on-hand stock
- reserved stock
- open purchase orders
- expected receipts
- safety stock

### Net requirement

Net Requirement = Gross Demand + Safety Stock - Available Supply

Never create a purchase request when the net requirement is zero or negative.

### Smart PR
Generate purchase requisitions containing:
- material
- required quantity
- required-by date
- originating production order(s)
- shortage quantity
- suggested supplier where available

### Traceability

Every MRP result and generated PR must be traceable back to its demand source.

### Replanning

MRP must be recalculable after:
- production quantity changes
- reservation changes
- GRN receipt
- PO cancellation
- stock changes
