# Phase 3 — Advanced Manufacturing Control

## WIP / SF
Track product-based WIP quantity, order linkage, status, and unit cost.

## Machines
Machine code, name, work-centre, capacity, hourly rate, status, active state, and maintenance due.

## Downtime
Record machine, start/end, reason code, explanation, maintenance flag, and actor. Open downtime can change machine status; downtime overlap invalidates affected scheduled operations for rescheduling. A close-downtime API restores availability when no other open downtime remains.

## Production costing
Store material, labour, machine, and overhead components; total cost; accepted quantity; unit cost; currency; and notes.

## Analytics
Report production, accepted/rejected, scrap, quality ratio, costs, plan-vs-actual, capacity load, employee productivity, material variance, and machine-linked availability. Performance and full OEE remain unavailable until reliable target-cycle-time data and validated manufacturing definitions are added.
