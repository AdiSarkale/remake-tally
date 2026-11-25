# Phase 3 — Advanced Manufacturing Control

## WIP / SF
Track product-based WIP quantity, order linkage, status, and unit cost. WIP receipt, adjustment, and consumption movements are ledgered with signed quantity, resulting balance, reference/reason, actor, and timestamp. Consumption is locked and rejected when it exceeds the balance.

## Machines
Machine code, name, work-centre, capacity, hourly rate, status, active state, and maintenance due. Operation schedules are linked to machine resources when available.

## Downtime
Record machine, start/end, reason code, explanation, maintenance flag, and actor. Open downtime can change machine status; downtime overlap invalidates affected scheduled operations for rescheduling. A close-downtime API restores availability when no other open downtime remains.

## Shift calendars
Work-centre shift windows are configured by weekday, shift code, and start/end time. Schedules align to configured shifts and operations must fit within a single shift window. No shift rows means legacy unrestricted scheduling.

## Production costing
Store material, labour, machine, and overhead components; total cost; accepted quantity; unit cost; currency; and notes. Automatic calculation uses recorded material consumption × raw-material master cost, planned operation schedule minutes × machine hourly rate, and configured work-centre labour/overhead rates. The estimate is not actual-time costing until actual operation time capture is implemented.

## Analytics
Report production, accepted/rejected, scrap, quality ratio, costs, plan-vs-actual, capacity load, employee productivity, material variance, and machine-linked availability. Full OEE performance and OEE remain unavailable until target-cycle-time and actual operating-time data are available and validated.
