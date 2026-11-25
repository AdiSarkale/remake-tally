# Phase 1 — Production Planning & Material Allocation

## Planning lifecycle
Planned -> Materials Pending / Ready -> Scheduled -> In Progress -> Completed, with Cancelled as terminal cancellation.

## Material planning
- Explode active BOM per order quantity.
- Calculate required quantity per raw material.
- Compare physical stock and active reservations.
- Reserve only available quantity; expose remaining shortage.
- Reservation records do not reduce raw-material physical stock or create inventory movements.

## Scheduling
- Preserve routing sequence.
- Calculate duration from setup and run-time-per-unit.
- Reject inactive, maintenance, breakdown, or zero-capacity work centres.
- Reject work-centre and assigned-employee overlapping schedules.
- Validate employee activity and routing skill.
- Rescheduling records reason and preserves operation row identity.

## Acceptance rules
- Material shortage is visible before execution.
- Reservation does not mutate stock.
- Scheduling rejects invalid work centres and overlaps.
- Skill validation cannot be bypassed.
