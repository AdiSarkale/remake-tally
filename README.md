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
- HR Payroll supports annual salary profiles, salary break-ups, configurable monthly salary-day counting, editable holidays/week-offs, month-wise daily attendance, finalized payroll runs and downloadable PDF salary slips.
- Leave approvals and employee self-service attendance capture remain future scope.

## CI

GitHub Actions validates backend compilation/tests and the frontend typecheck/build.

## Local frontend

The frontend is available locally at:

http://localhost:5173
