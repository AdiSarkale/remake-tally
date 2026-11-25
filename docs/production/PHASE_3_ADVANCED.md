# Phase 3 — Advanced Manufacturing Backend

Included structures and endpoints:
- Machine/resource master with work-centre assignment, capacity and hourly rate.
- Downtime/breakdown recording.
- Basic WIP/semi-finished stage records tied to order operations.
- Production cost components and total/unit-cost calculation.
- Basic OEE report: availability, performance, quality and OEE.

Not yet production-grade:
- Automatic costing based on consumption, employee payroll and machine runtime.
- WIP stock/ledger integration with inventory.
- OEE formula and planned shift time require manufacturing-policy validation.
- Maintenance lifecycle and preventive maintenance are not implemented.
- Detailed machine selection and operation-specific resources are not yet supported.

- Downtime records now have an explicit close action; open breakdowns block machine scheduling until closed.
- Material cost can be auto-derived from production-entry actual consumption and raw-material cost when no manual material cost is supplied.
