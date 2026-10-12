# Phase 1 — Production Planning & Material Allocation

## Objective

Move Production from order creation/execution into a planned manufacturing workflow.

## Modules

### 1. Production planning lifecycle
- Planned
- Materials Pending
- Ready
- Scheduled
- In Progress
- Completed
- Cancelled

### 2. Material allocation
For each production order:
- explode the active BOM
- calculate required quantity
- compare on-hand stock
- account for already reserved quantity
- create reservations
- expose shortages

### 3. Capacity planning
For each routing operation:
- work-centre capacity
- planned duration
- scheduled start/end
- capacity conflict detection

### 4. Employee planning
- skill eligibility remains mandatory
- include employee workload/availability
- avoid assigning an employee beyond planned availability
- retain manual override

### 5. Scheduling
Generate an executable operation schedule from:
- production quantity
- routing sequence
- work-centre capacity
- employee availability
- material readiness

## Critical rules

- Reservations must not silently reduce physical stock.
- A shortage must be visible before execution.
- An inactive/broken work centre cannot receive a new scheduled operation.
- Manual employee assignment cannot bypass skill validation.
- Rescheduling must preserve operation sequence.
