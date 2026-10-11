"""Tenant-managed HR employee types and payout classification mappings."""

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
