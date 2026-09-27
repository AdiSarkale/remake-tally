"""SQLAlchemy metadata plus the canonical tenant-scoped FastAPI DB dependency."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


# Used only for migrations / metadata inspection. Runtime authenticated routes
# MUST use get_db(), which resolves the company from the JWT.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db(
    company = Depends("current_company"),  # resolved lazily below to avoid import cycle
) -> Generator[Session, None, None]:
    from app.api.deps import current_company
    from app.db.tenant import get_tenant_db

    # FastAPI replaces this dependency marker with the actual callable at runtime.
    # The explicit annotation is intentionally omitted because TenantCompany lives
    # in the application model layer.
    raise RuntimeError("get_db dependency was not initialized")


# FastAPI dependency override with a real callable; kept separate so importing
# session.py never imports the auth dependency graph.
def tenant_db_dependency():
    from fastapi import Depends
    from app.api.deps import current_company
    from app.db.tenant import get_tenant_db

    def _dependency(company=Depends(current_company)):
        db = get_tenant_db(company)
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return _dependency


get_db = tenant_db_dependency()
