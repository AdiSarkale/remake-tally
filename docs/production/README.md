# Production Module Roadmap

This branch extends the existing Production module after the multi-company architecture was merged in PR #5.

## Current baseline

The following capabilities already exist on `main` and are intentionally treated as the baseline rather than rewritten:

- Product and raw-material masters
- BOM management and active BOM selection
- Routing and routing operations
- Work-centre master and status handling
- Employee and employee-skill management
- Automatic skill-based employee assignment
- Manual employee reassignment
- Production orders and generated operations
- Production execution
- RM consumption and FG inventory movement
- Scrap and basic quality
- Production/material variance reporting

## Roadmap

### Phase 1 — Production Planning & Material Allocation

**Goal:** turn a production order into a planned, executable manufacturing job.

Scope:

- Production order planning lifecycle
- Material requirement calculation
- Material reservation/allocation
- Material shortage visibility
- Work-centre capacity checks
- Operation planned start/end
- Basic production scheduling
- Employee workload/availability checks
- Rescheduling when capacity is insufficient
- Planning status and audit trail

Acceptance:

```
Production Order
  -> BOM explosion
  -> Material requirement
  -> Stock availability
  -> Reservation / shortage
  -> Capacity check
  -> Operation schedule
  -> Employee assignment
  -> Planned production
```

### Phase 2 — MRP / Smart PR Integration

**Goal:** connect production demand to procurement.

Scope:

- MRP demand aggregation
- Net material requirement
- Existing stock deduction
- Reserved stock deduction
- Open PO deduction
- Safety stock
- Shortage calculation
- Purchase requisition generation
- PR traceability back to production demand
- Re-planning after PO/GRN changes

Acceptance:

```
Production Demand
  -> MRP
  -> Net Requirement
  -> Available / Reserved / On-order
  -> Shortage
  -> Smart Purchase Request
```

### Phase 3 — Advanced Manufacturing Control

**Goal:** provide production execution controls expected from a serious manufacturing ERP.

Scope:

- Multi-stage WIP / SF tracking
- Machine/resource master
- Machine capacity and hourly rates
- Downtime and maintenance impact
- Operation rescheduling
- Production costing
- Labour cost
- Machine cost
- Overhead allocation
- Yield and efficiency
- OEE
- Advanced production dashboards

Acceptance:

```
Scheduled Production
  -> WIP / SF
  -> Machine + labour
  -> Downtime
  -> Cost
  -> Quality / yield
  -> OEE
  -> Management analytics
```

## Commit policy

Each phase is implemented as an isolated commit series so it can be reviewed, tested and reverted independently.

- `phase 1`: planning, allocation and scheduling
- `phase 2`: MRP and Smart PR
- `phase 3`: advanced manufacturing, costing and OEE

Do not mix unrelated architecture changes into this branch.

## Non-goals

This branch does not rewrite the multi-tenant architecture, authentication, tenant migration system, backup/restore system, or lifecycle controls already merged through PR #5.

## Definition of done

A phase is complete only when:

1. Backend behavior is implemented.
2. Frontend workflow is usable.
3. Database migrations are included where required.
4. Tests cover the critical business rules.
5. Existing Production flows continue to pass.
6. CI is green.
