"""HR-owned employee master, employee lifecycle metadata and employee-type APIs."""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import apply_employee_scope, employee_scope_ids, require_any_area, require_area
from app.db.session import get_db
from app.modules.core.audit import log_audit

router = APIRouter(prefix="/hr", tags=["hr"])
read_access = Depends(require_any_area("production", "hr"))
hr_access = Depends(require_area("hr"))
employee_access = Depends(require_any_area("production", "hr"))
hr_employee_access = Depends(require_area("hr"))

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
def update_employee_code_config(payload: schemas.EmployeeCodeConfigIn, db: Session = Depends(get_db), user: models.User = hr_access):
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


@router.get("/employee-duplicates", response_model=list[schemas.EmployeeOut])
def find_possible_employee_duplicates(name: str, db: Session = Depends(get_db), user: models.User = hr_access):
    normalized = " ".join(name.split()).casefold()
    if len(normalized) < 3:
        return []
    query = db.query(models.Employee).filter(
        func.lower(func.trim(models.Employee.name)) == normalized,
    )
    module = "hr" if user.role in (models.Role.admin, models.Role.hr) else "production"
    query = apply_employee_scope(query, db, user, module, "employees", "read")
    return query.order_by(models.Employee.emp_code).limit(20).all()


def _enforce_employee_scope(db: Session, user: models.User, employee_id: str, action: str) -> None:
    """Fail closed when a role's employee permission is scoped below tenant level."""
    module = "hr" if user.role in (models.Role.admin, models.Role.hr) else "production"
    scoped_ids = employee_scope_ids(db, user, module, "employees", action)
    if scoped_ids is not None and employee_id not in scoped_ids:
        raise HTTPException(403, "Employee is outside your configured access scope")


def _validate_employee_type(db: Session, code: str, *, allow_inactive_existing: bool = False) -> models.EmployeeTypeDefinition:
    normalized = code.strip().lower()
    row = db.query(models.EmployeeTypeDefinition).filter_by(code=normalized).first()
    if row is None:
        raise HTTPException(422, "Select a valid employee type")
    if not row.active and not allow_inactive_existing:
        raise HTTPException(409, "This employee type is inactive. Reassign the employee to an active type first.")
    return row


def _next_employee_code(db: Session, employee_type: str, department: str) -> str:
    """Allocate tenant-configured code with database lock and collision checks."""
    config = db.query(models.EmployeeCodeConfig).filter_by(id=1).with_for_update().first()
    if config is None:
        codes = db.query(models.Employee.emp_code).all()
        highest = 0
        for (code,) in codes:
            match = re.fullmatch(r"EMP-(\d+)", code or "", flags=re.IGNORECASE)
            if match:
                highest = max(highest, int(match.group(1)))
        config = models.EmployeeCodeConfig(
            id=1, pattern="EMP-{SEQ:03}", sequence_start=1,
            next_sequence=max(highest + 1, 1), increment_by=1,
        )
        db.add(config)
        db.flush()
    sequence = max(config.next_sequence, config.sequence_start)
    pattern = _validate_code_pattern(config.pattern)
    for _attempt in range(1000):
        code = _render_employee_code(pattern, sequence, employee_type, department)
        exists = db.query(models.Employee.id).filter(models.Employee.emp_code == code).first()
        config.next_sequence = sequence + config.increment_by
        if not exists:
            return code
        sequence += config.increment_by
    raise HTTPException(409, "Could not allocate a unique employee code; review the configured pattern")


@router.get("/employees", response_model=list[schemas.EmployeeOut])
def list_employees(include_inactive: bool = False, db: Session = Depends(get_db), user: models.User = employee_access):
    query = db.query(models.Employee)
    if include_inactive:
        if user.role not in (models.Role.admin, models.Role.hr):
            raise HTTPException(403, "Historical employee access requires Admin or HR authorization")
    else:
        query = query.filter(models.Employee.active.is_(True))
    module = "hr" if user.role in (models.Role.admin, models.Role.hr) else "production"
    query = apply_employee_scope(query, db, user, module, "employees", "read")
    return query.order_by(models.Employee.emp_code).all()


@router.post("/employees", response_model=schemas.EmployeeOut, status_code=201)
def create_employee(payload: schemas.EmployeeIn, db: Session = Depends(get_db), user: models.User = hr_employee_access):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Employee name is required")
    if payload.joining_date is None:
        raise HTTPException(422, "Joining date is required for new employees")
    if payload.end_date is not None and payload.end_date < payload.joining_date:
        raise HTTPException(422, "End date cannot be earlier than joining date")
    _validate_employee_type(db, payload.employee_type)
    for _attempt in range(5):
        row = models.Employee(
            emp_code=_next_employee_code(db, payload.employee_type.strip().lower(), payload.department.strip()),
            name=name, employee_type=payload.employee_type.strip().lower(),
            department=payload.department.strip(), designation=payload.designation.strip(),
            joining_date=payload.joining_date, end_date=payload.end_date, active=True,
        )
        db.add(row)
        try:
            db.flush()
            log_audit(db, user.username, "CREATE", "employee", row.emp_code)
            db.commit()
            db.refresh(row)
            return row
        except IntegrityError:
            db.rollback()
    raise HTTPException(409, "Could not allocate a unique employee code; please retry")


@router.put("/employees/{employee_id}", response_model=schemas.EmployeeOut)
def update_employee(employee_id: str, payload: schemas.EmployeeUpdate, db: Session = Depends(get_db), user: models.User = hr_employee_access):
    row = db.get(models.Employee, employee_id)
    if row is None:
        raise HTTPException(404, "Employee not found")
    _enforce_employee_scope(db, user, row.id, "update")
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Employee name is required")
    # PUT updates may omit employment dates; omission preserves the current
    # values. Explicit null is accepted only for end_date (to clear it), while
    # a known joining date cannot be cleared through this endpoint.
    fields_set = payload.model_fields_set
    joining_date = payload.joining_date if "joining_date" in fields_set else row.joining_date
    end_date = payload.end_date if "end_date" in fields_set else row.end_date
    if "joining_date" in fields_set and joining_date is None:
        raise HTTPException(422, "Joining date cannot be cleared")
    if end_date is not None and (joining_date is None or end_date < joining_date):
        raise HTTPException(422, "End date requires a valid joining date and cannot be earlier than it")
    if payload.employee_type.strip().lower() != row.employee_type:
        _validate_employee_type(db, payload.employee_type)
    row.name = name
    row.employee_type = payload.employee_type.strip().lower()
    row.department = payload.department.strip()
    row.designation = payload.designation.strip()
    row.joining_date = joining_date
    row.end_date = end_date
    log_audit(db, user.username, "UPDATE", "employee", f"{row.emp_code}; details updated")
    db.commit()
    db.refresh(row)
    return row


def _employee_has_open_production_assignments(db: Session, employee_id: str) -> bool:
    return db.query(models.ProductionOrderOperation.id).filter(
        models.ProductionOrderOperation.assigned_employee_id == employee_id,
        models.ProductionOrderOperation.completed_qty < models.ProductionOrderOperation.planned_qty,
    ).first() is not None


@router.patch("/employees/{employee_id}/status", response_model=schemas.EmployeeOut)
def set_employee_status(employee_id: str, payload: schemas.EmployeeStatusUpdate, db: Session = Depends(get_db), user: models.User = hr_employee_access):
    row = db.get(models.Employee, employee_id)
    if row is None:
        raise HTTPException(404, "Employee not found")
    _enforce_employee_scope(db, user, row.id, "update")
    if row.active == payload.active:
        return row
    if payload.active:
        _validate_employee_type(db, row.employee_type)
    elif _employee_has_open_production_assignments(db, row.id):
        raise HTTPException(409, "Cannot deactivate an employee with unfinished production assignments. Reassign or complete those operations first.")
    row.active = payload.active
    log_audit(db, user.username, "REACTIVATE" if row.active else "DEACTIVATE", "employee", row.emp_code)
    db.commit()
    db.refresh(row)
    return row


@router.get("/employees/{employee_id}/skills", response_model=list[schemas.EmployeeSkillOut])
def list_employee_skills(employee_id: str, db: Session = Depends(get_db), user: models.User = employee_access):
    if not db.get(models.Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    _enforce_employee_scope(db, user, employee_id, "read")
    return db.query(models.EmployeeSkill).filter_by(employee_id=employee_id).order_by(models.EmployeeSkill.skill).all()


@router.post("/employees/{employee_id}/skills", response_model=schemas.EmployeeSkillOut, status_code=201)
def add_employee_skill(employee_id: str, payload: schemas.EmployeeSkillIn, db: Session = Depends(get_db), user: models.User = hr_employee_access):
    if not db.get(models.Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    _enforce_employee_scope(db, user, employee_id, "create")
    if db.query(models.EmployeeSkill).filter_by(employee_id=employee_id, skill=payload.skill).first():
        raise HTTPException(400, "Employee already has this skill")
    row = models.EmployeeSkill(employee_id=employee_id, **payload.model_dump())
    db.add(row)
    log_audit(db, user.username, "CREATE", "employee_skill", f"{employee_id}: {payload.skill}")
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
