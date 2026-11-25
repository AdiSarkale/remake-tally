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

## Phase 2 — MRP (Smart PR excluded)
- Demand aggregation
- Net requirements against on-hand, reservations, open PO supply, and safety stock
- Shortage calculations and traceability
- Recalculation after supply/demand changes
- **Smart Purchase Requisition generation is explicitly excluded.**

## Phase 3 — Advanced Manufacturing
- WIP / semi-finished tracking
- Machine/resource master and rates\n- Machine-linked operation schedules and downtime-aware resource selection\n- Downtime invalidates affected schedules for explicit rescheduling\n- Machine-schedule availability analytics
- Downtime records and maintenance state
- Production costing
- Yield and quality metrics
- Analytics: plan-vs-actual, capacity load, employee productivity, material variance, yield, cost, machine availability\n- Analytics

## Constraints
- Backend only: frontend is intentionally unchanged.
- All API access remains tenant-scoped via the existing tenant DB dependency.
- Schema changes use Alembic; no runtime auto-create.
- Smart PR generation is out of scope.
- CI must be green before completion.
