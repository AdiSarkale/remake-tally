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

- Purchase Requisition is a computed view because the backend does not store a requisition entity.
- Employee edit/deactivate is not implemented.
- Reports and Settings are placeholders.
- Full Payroll, Attendance and Leave are intentionally out of current scope.

## CI

GitHub Actions validates backend compilation/tests and the frontend typecheck/build.

## Live app

https://remake-tally.lovable.app
