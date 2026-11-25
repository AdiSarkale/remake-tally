# Production Module Roadmap

This implementation builds on the current production baseline in `main`.

## Baseline
- Product/raw-material masters and active BOM
- Routing, operations, work-centres
- Employee skills and assignment
- Production orders and execution
- RM consumption, FG movements, scrap, quality and variance reporting

## Phase 1 — Planning & Material Allocation
- Planning lifecycle
- BOM explosion and requirements
- Reservations without changing physical stock
- Shortage visibility
- Work-centre and employee checks
- Operation schedule/reschedule
- Routing sequence and resource conflict validation

## Phase 2 — MRP (Smart PR excluded)
- Demand aggregation
- Net requirements against on-hand, open PO supply, and safety stock
- Reservation visibility for traceability, without double-counting it as physical supply
- Shortage calculations and demand traceability
- Recalculation from current supply/demand data
- **Smart Purchase Requisition generation is explicitly excluded.**

## Phase 3 — Advanced Manufacturing
- WIP / semi-finished tracking with a movement ledger (receipts, adjustments, consumption)
- Machine/resource master, capacity, rates, and maintenance state
- Machine-linked operation schedules and downtime-aware resource selection
- Downtime invalidates affected schedules for explicit rescheduling
- Work-centre shift calendar and schedule fit validation
- Automatic cost calculation from actual material consumption and planned operation duration
- Configurable work-centre labor and overhead rates
- Machine hourly cost from machine master rates
- Production yield, accepted/rejected, scrap and quality metrics
- Analytics: plan-vs-actual, capacity load, employee productivity, material variance, yield, cost, and machine availability

## Constraints
- Backend only: frontend is intentionally unchanged.
- All API access remains tenant-scoped via the existing tenant DB dependency.
- Schema changes use Alembic; no runtime auto-create.
- Smart PR generation is out of scope.
- Automatic costing is an estimate until actual operation time capture is implemented; labor and overhead use configured work-centre hourly rates.
- Full OEE performance requires target-cycle-time and actual operating-time data; those are not fabricated.
- Shift scheduling does not split a single operation across multiple shift windows; it requires the operation to fit in a configured shift.
- CI must be green before completion.
