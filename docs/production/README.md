# Production Roadmap (Backend Implementation)

This work is based on current `main`. The frontend is intentionally untouched.

## Scope
- Phase 1: production planning lifecycle, material reservation, capacity and operation scheduling.
- Phase 2: MRP net-requirement calculation and traceability **only**. Smart Purchase Request creation is explicitly excluded.
- Phase 3: machine/resource master, downtime, WIP stage records, production cost components, yield/OEE reporting.

## Implemented API surface
- `POST /production-planning/orders/{id}/plan-materials`
- `POST /production-planning/orders/{id}/schedule`
- `GET /production-planning/mrp`
- `GET/POST /production-planning/machines`
- `GET/POST /production-planning/downtime`
- `GET/POST /production-planning/wip`, `PATCH /production-planning/wip/{id}/close`
- `GET/PUT /production-planning/orders/{id}/cost`
- `GET /production-planning/oee`

All endpoints are backend-only and require the Production area permission.

## Safety rules
- Reservation is logical and does not change physical stock.
- Reservation uses a database row lock on raw material during allocation.
- Scheduling requires material-ready status.
- Routing order is preserved.
- Work-centre and machine conflicts are checked.
- Machine downtime moves a candidate schedule forward.
- MRP calculates net requirements; it does not create purchase requisitions.
- WIP entries are validated against the production order's routing.

## Known limitations to resolve before production use
- Scheduling is a basic single-window scheduler, not a shift/calendar-aware finite-capacity optimizer.
- Material allocation is a reservation ledger; consumption still occurs through existing production execution.
- Machine assignment currently applies one optional machine selection across the scheduled order; richer operation-specific machine selection is a follow-up.
- Cost component values are captured and totaled; automatic labour/machine/material costing integration is not yet complete.
- OEE is a basic scheduled-minute/downtime/production-quality calculation and needs operational validation.
- The frontend workflow is not implemented by design in this work.

## Definition of done
Backend tests and migration tests pass; CI is green; business rules are manually validated. Do not mark the full roadmap production-ready until known limitations are resolved.
