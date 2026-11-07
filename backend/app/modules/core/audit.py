"""Shared Core audit-event writer used by all business domains."""

from sqlalchemy.orm import Session

from app.modules.core.models import AuditLog


def log_audit(
    db: Session,
    username: str,
    action: str,
    entity: str,
    detail: str,
) -> None:
    """Stage an audit event in the caller's transaction.

    The caller remains responsible for committing or rolling back so the
    business mutation and its audit record succeed or fail atomically.
    """
    db.add(
        AuditLog(
            username=username,
            action=action,
            entity=entity,
            detail=detail,
        )
    )
