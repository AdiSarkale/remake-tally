# MiniTally: Railway demo deployment (2-day demo)

This deployment guide is for a short, disposable demo, not production. The backend is deployed to Railway and the Vite frontend can be deployed to Vercel. Railway trial credits and free-tier policies can change; check the current dashboard before deploying.

## Architecture

- Frontend: Vercel, project root `frontend/`
- API: Railway, service root `backend/` (Dockerfile deployment)
- Tenant ERP PostgreSQL database: one PostgreSQL service
- Control-plane PostgreSQL database: a second PostgreSQL service

**Use separate PostgreSQL databases/services for control-plane and tenant data.** Both Alembic environments use the default `alembic_version` table name; sharing a database can make the migration histories conflict. For this demo, use two separate Railway PostgreSQL services or two separate databases with explicitly configured, non-overlapping migration version tables (the former is the supported path in this guide).

## 1. Deploy PostgreSQL

Create two PostgreSQL services in Railway:

1. `minitally-tenant-db`: tenant ERP tables.
2. `minitally-control-db`: tenant registry and tenant administration audit tables.

Copy each service's connection URL from Railway's **private/internal networking** details when available. The app uses SQLAlchemy's Psycopg 3 driver, so set URLs in this form:

```text
postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

Use the actual host, port, username, password and database name supplied by Railway. Do not commit credentials to GitHub. If using Railway's private network, confirm that the provider supports TLS on that endpoint before adding `sslmode=require`; the application's production settings require explicit TLS for the control database.

## 2. Deploy the API to Railway

Create a Railway service from this repository and configure its **Root Directory** as `/backend`. Railway should detect `backend/railway.json` and build `backend/Dockerfile`.

Set these service variables in Railway (replace every placeholder with a real value):

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `CONTROL_DATABASE_URL` | Control-plane PostgreSQL URL using `postgresql+psycopg://` and explicit `sslmode=require` |
| `DATABASE_URL` | Tenant ERP PostgreSQL URL using `postgresql+psycopg://` |
| `TENANT_DB_URL_LOCAL_DEFAULT` | Same tenant ERP PostgreSQL URL as `DATABASE_URL`; used to resolve the demo tenant's `LOCAL_DEFAULT` secret reference |
| `JWT_SECRET` | Random secret of at least 32 characters |
| `CORS_ORIGINS` | JSON array containing only the deployed frontend origin, e.g. `["https://your-project.vercel.app"]` |
| `SECRET_PROVIDER` | `environment` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `TENANT_DB_REQUIRE_TLS` | `true` |

The `start.sh` script applies tenant migrations and control-plane migrations before starting Uvicorn. Railway supplies `PORT`; the API binds to it. The health check uses `/health/ready`, which confirms control-plane database connectivity.

Do not set `CORS_ORIGINS` to `*` and do not use the repository's development JWT secret.

## 3. Deploy the frontend to Vercel

1. Import `AdiSarkale/remake-tally` in Vercel.
2. Set the project root directory to `frontend`.
3. Framework preset: Vite.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Add `VITE_API_URL` with the public Railway API origin only, e.g. `https://your-api.up.railway.app` (no trailing slash and no `/api/v1` suffix).
7. Deploy, then copy the actual Vercel URL into Railway's `CORS_ORIGINS` JSON array and redeploy the API if needed.

The `frontend/vercel.json` rewrite keeps client-side routes working on direct navigation and refresh.

## 4. Initialize demo data (one time)

After the API's first successful deployment and migrations, open a Railway shell for the API service and run from `/app`:

```sh
python -m app.seed
```

Do **not** run `python -m app.seed --reset-demo` unless you intentionally want to reset demo transactions and HR/payroll data. Do not run seeding as part of every application startup.

The seed script creates the SPW demo tenant and prints demo credentials. Change the seeded passwords before sharing the URL if the application permits it, or use only synthetic demo data and restrict access to the intended audience. The seeded default passwords are public in source code and must never be used for real accounts.

## 5. Smoke-test before sharing

- `https://YOUR-API/health/live` returns `{"status":"ok"}`.
- `https://YOUR-API/health/ready` returns `{"status":"ready"}`.
- `https://YOUR-API/docs` loads.
- Login works from the deployed frontend.
- Purchase, inventory, production, HR/payroll and finance screens can load and save.
- Refresh a nested frontend route; it should still load.
- Confirm that the demo data is synthetic and that tenant isolation works.

## Known constraints and cautions

- Railway trial credits may expire or be exhausted; monitor usage. A successful build does not guarantee the service remains online for two full days.
- Do not expose real employee, payroll, financial or customer information.
- Do not share the Railway shell, database URL, JWT secret, or environment-variable screenshots.
- Seeding is a manual one-time operation. The deployment is not complete until a demo tenant exists and seeded data is loaded.
- This setup is for a short demo only. It is not a production security, backup, availability or disaster-recovery configuration.
