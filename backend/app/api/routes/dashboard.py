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

    products = db.query(models.Product).all()
    materials = db.query(models.RawMaterial).all()
    scrap_types = db.query(models.ScrapType).all()

    finished_goods_quantity = sum(p.stock for p in products)
    finished_goods_sku_count = len(products)
    finished_goods_value = sum(p.stock * p.cost_price for p in products)

    raw_material_value = sum(m.stock * m.cost for m in materials)
    raw_material_count = len(materials)

    scrap_stock_quantity = sum(s.stock for s in scrap_types)
    scrap_stock_value = sum(s.stock * s.selling_rate for s in scrap_types)

    inventory_value = (
        finished_goods_value
        + raw_material_value
        + scrap_stock_value
    )
    low = db.query(models.Product).filter(models.Product.stock <= models.Product.min_stock).count()
    low += db.query(models.RawMaterial).filter(models.RawMaterial.stock <= models.RawMaterial.min_stock).count()

    return schemas.DashboardOut(
        produced_today=produced_today,
        produced_month=produced_month,
        scrap_month=scrap_month,
        scrap_rate=(scrap_month / produced_month * 100) if produced_month else 0.0,
        inventory_value=inventory_value,
        low_stock_count=low,

        finished_goods_quantity=finished_goods_quantity,
        finished_goods_sku_count=finished_goods_sku_count,
        finished_goods_value=finished_goods_value,

        scrap_stock_quantity=scrap_stock_quantity,
        scrap_stock_value=scrap_stock_value,

        raw_material_value=raw_material_value,
        raw_material_count=raw_material_count,
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
