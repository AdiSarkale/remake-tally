# Minitally ERP

A full-stack lightweight ERP for manufacturing operations, built around the existing FastAPI backend and a React + TypeScript frontend.

## Repository structure

```text
remake-tally/
├── backend/   # FastAPI API, database models, migrations, seed data and tests
└── frontend/  # React + TypeScript + Vite + npm ERP client
```

## Frontend

The frontend lives in `frontend/` and uses the real FastAPI API under `backend/`.

### Run locally

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Set `VITE_API_URL` in `.env` to the backend base URL. The frontend appends `/api/v1` to that value.

Useful commands:

```bash
npm run typecheck
npm run build
npm run preview
```

## Backend

```bash
cd backend
pip install -r requirements.txt
```

The FastAPI application exposes the REST API under `/api/v1`.

## Demo

Known demo accounts:

- `admin / admin123`
- `accounts / accounts123`
- `operator / operator123`

Known demo flow:

```text
PO-DEMO-001
    ↓
GRN-DEMO-001
    ↓
Inventory
    ↓
BOM
    ↓
Routing
    ↓
Work Center
    ↓
Employee
    ↓
Production Order
    ↓
Production Entry
    ↓
Scrap / Finished Goods
```

## Current frontend scope

- Dashboard
- Sales
- Procurement
- Inventory
- Production / Manufacturing
- Finance
- Production-side Employees

Current known gaps:

- Purchase Requisition is a stored manual document with draft/submitted/approved workflow; MRP-generated PRs are reserved through the source field for future planning.
- Employee codes are assigned by the backend and immutable; employee details can be edited without changing codes.
- HR users can deactivate/reactivate employees; lifecycle changes are audited and employee records are preserved.
- Reports and Settings are placeholders.
- Full Payroll, Attendance and Leave are intentionally out of current scope.

## CI

GitHub Actions validates backend compilation/tests and the frontend typecheck/build.

## Local frontend

The frontend is available locally at:

http://localhost:5173
