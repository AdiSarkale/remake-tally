# Backend domain packages

SQLAlchemy entities and Pydantic schemas live under `app.modules.<domain>.models` and `schemas`.

Legacy `app.models` and `app.schemas` are compatibility facades so routes, seed scripts, Alembic and tests do not need a simultaneous import rewrite. New code should use the domain package directly. Domains include core, inventory, production, HR, sales, purchasing, finance, dispatch, dashboard and approvals.
