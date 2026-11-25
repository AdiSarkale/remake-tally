# Phase 1 — Planning and Material Allocation

- Planning state is persisted on production orders.
- BOM is exploded into direct raw-material requirements.
- Reservations allocate available physical stock logically and expose shortage.
- Physical stock is unchanged by reservation.
- Reservation conflicts are protected by raw-material row locking.
- Scheduling preserves routing sequence and calculates operation durations from setup/run times or work-centre/machine capacity.
- Scheduling checks work-centre conflicts, employee conflicts when enabled, employee active/shop-floor status and required skill.
- Material shortage prevents scheduling.

## Remaining hardening
- Shift/calendar-aware capacity.
- Multi-machine assignment per operation.
- More robust concurrent reservation tests on PostgreSQL.
- Reschedule/undo reservation workflow and cancellation release rules.
