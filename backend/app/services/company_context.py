"""Shared JWT-to-company resolution for tenant-scoped requests."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.control_models import TenantCompany


def resolve_company_from_token(token: str, control_db: Session) -> tuple[dict[str, Any], TenantCompany]:
    try:
        payload = decode_access_token(token)
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

    return payload, company
