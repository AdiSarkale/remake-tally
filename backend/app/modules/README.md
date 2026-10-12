# Backend domain packages

The backend's SQLAlchemy entities and Pydantic schemas are organized by domain in this directory.

- `core`: users, master data, audit log and company settings
- `inventory`: stock movement models and schemas
- `production`: BOM, production, workcenter, routing and manufacturing assignments
- `hr`: employee and skill models/schemas
- `sales`: invoices, quotations, sales orders, deliveries and customer POs
- `purchasing`: requisitions, purchase orders, GRNs, suppliers and warehouses
- `finance`: customer/supplier payments, receivables and payables
- `dispatch`: dispatch tracking
- `dashboard`: dashboard response schemas
- `approvals`: reserved for approval-domain extraction

`app.models` and `app.schemas` are deliberate compatibility facades. Existing routes, the seed script,
Alembic metadata setup and tests do not need a simultaneous import rewrite. New code should import from
the specific domain package; old imports remain supported during incremental migration.
