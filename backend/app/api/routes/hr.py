"""Tenant-managed HR employee types and payout classification mappings."""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_any_area, require_area
from app.db.session import get_db
from app.services.inventory import log_audit

router = APIRouter(prefix="/hr", tags=["hr"])
read_access = Depends(require_any_area("production", "hr"))
hr_access = Depends(require_area("hr"))


_CODE_TOKEN = re.compile(r"\{(SEQ(?::0?[1-9][0-9]?)?|YEAR|TYPE|DEPT)\}")
_ALLOWED_CODE_LITERAL = re.compile(r"^[A-Za-z0-9._{}:-]+$")


def _validate_code_pattern(pattern: str) -> str:
    pattern = pattern.strip()
    if not pattern or not _ALLOWED_CODE_LITERAL.fullmatch(pattern):
        raise HTTPException(422, "Pattern may contain only letters, numbers, dot, underscore, hyphen, colon, and supported placeholders")
    tokens = list(_CODE_TOKEN.finditer(pattern))
    if not any(token.group(1).startswith("SEQ") for token in tokens):
        raise HTTPException(422, "Employee-code pattern must contain a {SEQ} placeholder")
    residue = _CODE_TOKEN.sub("", pattern)
    if "{" in residue or "}" in residue:
        raise HTTPException(422, "Employee-code pattern contains an unsupported placeholder")
    return pattern


def _render_employee_code(pattern: str, sequence: int, employee_type: str, department: str) -> str:
    safe_type = re.sub(r"[^A-Za-z0-9_-]+", "-", employee_type).strip("-") or "TYPE"
    safe_department = re.sub(r"[^A-Za-z0-9_-]+", "-", department).strip("-") or "GENERAL"
    year = str(datetime.now().year)
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token == "YEAR":
            return year
        if token == "TYPE":
            return safe_type.upper()
        if token == "DEPT":
            return safe_department.upper()
        width = int(token.split(":", 1)[1]) if ":" in token else 0
        return str(sequence).zfill(width)
    code = _CODE_TOKEN.sub(replace, pattern)
    if len(code) > 32 or not re.fullmatch(r"[A-Za-z0-9._-]+", code):
        raise HTTPException(422, "Rendered employee code is invalid or exceeds 32 characters")
    return code


@router.get("/employee-code-config", response_model=schemas.EmployeeCodeConfigOut)
def get_employee_code_config(db: Session = Depends(get_db), user: models.User = hr_access):
    row = db.get(models.EmployeeCodeConfig, 1)
    if row is None:
        row = models.EmployeeCodeConfig(id=1, pattern="EMP-{SEQ:03}", sequence_start=1, next_sequence=1, increment_by=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.put("/employee-code-config", response_model=schemas.EmployeeCodeConfigOut)
def update_employee_code_config(
    payload: schemas.EmployeeCodeConfigIn,
    db: Session = Depends(get_db),
    user: models.User = hr_access,
):
    pattern = _validate_code_pattern(payload.pattern)
    row = db.query(models.EmployeeCodeConfig).filter_by(id=1).with_for_update().first()
    if row is None:
        row = models.EmployeeCodeConfig(id=1, pattern=pattern, sequence_start=payload.sequence_start,
                                        next_sequence=payload.sequence_start, increment_by=payload.increment_by)
        db.add(row)
    else:
        row.pattern = pattern
        row.sequence_start = payload.sequence_start
        row.increment_by = payload.increment_by
        row.next_sequence = max(row.next_sequence, payload.sequence_start)
    log_audit(db, user.username, "UPDATE", "employee_code_config", pattern)
    db.commit()
    db.refresh(row)
    return row


@router.get("/employee-types", response_model=list[schemas.EmployeeTypeOut])
def list_employee_types(db: Session = Depends(get_db), user: models.User = read_access):
    return db.query(models.EmployeeTypeDefinition).order_by(
        models.EmployeeTypeDefinition.name
    ).all()


@router.post("/employee-types", response_model=schemas.EmployeeTypeOut, status_code=201)
def create_employee_type(
    payload: schemas.EmployeeTypeIn,
    db: Session = Depends(get_db),
    user: models.User = hr_access,
):
    code = payload.code.strip().lower()
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Employee type name is required")
    if db.query(models.EmployeeTypeDefinition).filter(
        (models.EmployeeTypeDefinition.code == code)
        | (models.EmployeeTypeDefinition.name.ilike(name))
    ).first():
        raise HTTPException(409, "Employee type code or name already exists")
    row = models.EmployeeTypeDefinition(
        code=code,
        name=name,
        payout_classification=payload.payout_classification.strip(),
        active=payload.active,
    )
    db.add(row)
    try:
        db.flush()
        log_audit(db, user.username, "CREATE", "employee_type", row.code)
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Employee type code or name already exists") from exc


@router.patch("/employee-types/{type_id}", response_model=schemas.EmployeeTypeOut)
def update_employee_type(
    type_id: str,
    payload: schemas.EmployeeTypeIn,
    db: Session = Depends(get_db),
    user: models.User = hr_access,
):
    row = db.get(models.EmployeeTypeDefinition, type_id)
    if row is None:
        raise HTTPException(404, "Employee type not found")
    # Codes are stable identifiers and cannot be changed after creation.
    if payload.code.strip().lower() != row.code:
        raise HTTPException(422, "Employee type code is immutable")
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Employee type name is required")
    duplicate = db.query(models.EmployeeTypeDefinition).filter(
        models.EmployeeTypeDefinition.id != row.id,
        models.EmployeeTypeDefinition.name.ilike(name),
    ).first()
    if duplicate:
        raise HTTPException(409, "Employee type name already exists")
    row.name = name
    row.payout_classification = payload.payout_classification.strip()
    row.active = payload.active
    log_audit(db, user.username, "UPDATE", "employee_type", row.code)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/employee-types/{type_id}", status_code=204)
def delete_employee_type(
    type_id: str,
    db: Session = Depends(get_db),
    user: models.User = hr_access,
):
    row = db.get(models.EmployeeTypeDefinition, type_id)
    if row is None:
        raise HTTPException(404, "Employee type not found")
    if db.query(models.Employee).filter_by(employee_type=row.code).first():
        raise HTTPException(
            409,
            "This employee type is assigned to employees. Deactivate it instead.",
        )
    code = row.code
    db.delete(row)
    log_audit(db, user.username, "DELETE", "employee_type", code)
    db.commit()
    return None
