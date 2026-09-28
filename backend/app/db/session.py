"""SQLAlchemy metadata plus the canonical tenant-scoped FastAPI DB dependency."""

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.control import get_control_db
from app.db.control_models import TenantCompany
from app.db.tenant import get_tenant_db

settings = get_settings()


class Base(DeclarativeBase):
    pass


# Used only for migrations / metadata inspection. Runtime authenticated routes
# MUST use get_db(), which resolves the company from the JWT.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

bearer = HTTPBearer(auto_error=False)


def get_db(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    control_db: Session = Depends(get_control_db),
) -> Generator[Session, None, None]:
    """Resolve the ERP session exclusively from the signed JWT company context.

    Kept in the DB layer so models.py can import Base without creating an
    import cycle through api.deps.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(creds.credentials)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    company_id = payload.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has no company context",
        )

    company = control_db.get(TenantCompany, str(company_id))
    if company is None or not company.active or company.provisioning_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Company no longer exists or is inactive",
        )

    db = get_tenant_db(company)
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
