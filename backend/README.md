# MiniTally ERP — FastAPI backend

Scaffolded API for the MiniTally ERP frontend.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://minitally:minitally@localhost:5432/minitally"
export JWT_SECRET="replace-me"
python -m app.seed          # creates demo users, masters and stock
uvicorn app.main:app --reload --port 8000
```

Docs: http://localhost:8000/docs

## Layout

- `app/core/` — settings, password hashing, JWT
- `app/db/session.py` — engine, session, declarative base
- `app/models.py` — ORM tables (users, parties, products, materials, scrap, movements, production, audit)
- `app/schemas.py` — Pydantic request/response models
- `app/services/inventory.py` — the inventory engine (every stock change flows through `apply_movement`)
- `app/api/routes/` — auth, masters, inventory, production, scrap, dashboard/settings

## Stock rules

| Action | Effect |
| --- | --- |
| Production | finished goods IN, raw materials OUT |
| Scrap | scrap stock IN |
| Purchase | raw materials IN |
| Sales invoice | finished goods OUT |

## Demo logins

`admin/admin123`, `accounts/accounts123`, `operator/operator123`
