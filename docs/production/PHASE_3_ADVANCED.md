# Phase 3 — Advanced Manufacturing Control

## Objective

Complete the manufacturing-control layer beyond basic production execution.

## Modules

### WIP / Semi-finished goods
Support material flow such as:

RM -> Operation 10 -> SF -> Operation 20 -> SF -> Operation 30 -> FG

### Machine resources
Track:
- machine code
- work centre
- capacity
- hourly rate
- status
- maintenance state

### Downtime
Record:
- machine/work-centre downtime
- reason
- duration
- affected operations

Downtime must be able to invalidate or move a schedule.

### Production costing
Calculate:
- material cost
- labour cost
- machine cost
- overhead
- total production cost
- FG unit cost

### Quality and yield
Track:
- produced quantity
- accepted quantity
- rejected quantity
- scrap
- yield
- first-pass yield where applicable

### OEE
Provide:
- availability
- performance
- quality
- OEE

### Analytics
Expose:
- plan vs actual
- work-centre utilization
- employee productivity
- material variance
- scrap rate
- yield
- downtime
- production cost
- OEE
