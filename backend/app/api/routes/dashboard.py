"""Dashboard KPIs and company settings."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import current_user, require_area
from app.db.session import get_db
from app.services.inventory import log_audit

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=schemas.DashboardOut)
def dashboard(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    today = date.today()
    entries = db.query(models.ProductionEntry).all()
    scrap = db.query(models.ScrapEntry).all()

    produced_today = sum(e.quantity for e in entries if e.entry_date == today)
    produced_month = sum(e.quantity for e in entries if e.entry_date.strftime("%Y-%m") == today.strftime("%Y-%m"))
    scrap_month = sum(s.quantity for s in scrap if s.entry_date.strftime("%Y-%m") == today.strftime("%Y-%m"))

    fg = sum(p.stock * p.cost_price for p in db.query(models.Product).all())
    rm = sum(m.stock * m.cost for m in db.query(models.RawMaterial).all())
    sc = sum(s.stock * s.selling_rate for s in db.query(models.ScrapType).all())
    low = db.query(models.Product).filter(models.Product.stock <= models.Product.min_stock).count()
    low += db.query(models.RawMaterial).filter(models.RawMaterial.stock <= models.RawMaterial.min_stock).count()

    return schemas.DashboardOut(
        produced_today=produced_today,
        produced_month=produced_month,
        scrap_month=scrap_month,
        scrap_rate=(scrap_month / produced_month * 100) if produced_month else 0.0,
        inventory_value=fg + rm + sc,
        low_stock_count=low,
    )


@router.get("/settings", response_model=schemas.SettingsOut)
def get_settings_row(db: Session = Depends(get_db), user: models.User = Depends(require_area("settings"))):
    row = db.get(models.CompanySettings, 1)
    if row is None:
        row = models.CompanySettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.put("/settings", response_model=schemas.SettingsOut)
def update_settings(
    payload: schemas.SettingsIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_area("settings")),
):
    row = db.get(models.CompanySettings, 1) or models.CompanySettings(id=1)
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    db.add(row)
    log_audit(db, user.username, "UPDATE", "settings", "Company profile updated")
    db.commit()
    db.refresh(row)
    return row


@router.get("/audit", response_model=list[schemas.AuditOut])
def audit_trail(limit: int = 100, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    return db.query(models.AuditLog).order_by(models.AuditLog.at.desc()).limit(limit).all()
