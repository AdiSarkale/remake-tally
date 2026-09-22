"""Dashboard KPIs and company settings."""

from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import current_user, require_area
from app.db.session import get_db
from app.services.inventory import log_audit


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=schemas.DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    today = date.today()
    month = today.strftime("%Y-%m")

    # ---------------------------------------------------------
    # Production / Scrap
    # ---------------------------------------------------------

    production_entries = (
        db.query(models.ProductionEntry)
        .order_by(models.ProductionEntry.entry_date.desc())
        .all()
    )

    scrap_entries = (
        db.query(models.ScrapEntry)
        .order_by(models.ScrapEntry.entry_date.desc())
        .all()
    )
    scrap_reason_totals: dict[str, float] = defaultdict(float)

    for entry in scrap_entries:
        reason = entry.reason.strip() or "Unspecified"
        scrap_reason_totals[reason] += entry.quantity

    top_scrap_reasons = [
        schemas.ScrapReasonOut(
            reason=reason,
            quantity=quantity,
        )
        for reason, quantity in sorted(
            scrap_reason_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]
    ]

    produced_today = sum(
        e.quantity
        for e in production_entries
        if e.entry_date == today
    )

    produced_month = sum(
        e.quantity
        for e in production_entries
        if e.entry_date.strftime("%Y-%m") == month
    )

    scrap_month = sum(
        s.quantity
        for s in scrap_entries
        if s.entry_date.strftime("%Y-%m") == month
    )

    scrap_rate = (
        scrap_month / produced_month * 100
        if produced_month
        else 0.0
    )

    # ---------------------------------------------------------
    # Finished Goods
    # ---------------------------------------------------------

    products = db.query(models.Product).all()

    finished_goods_quantity = sum(
        p.stock for p in products
    )

    finished_goods_sku_count = len(products)

    finished_goods_value = sum(
        p.stock * p.cost_price
        for p in products
    )

    # ---------------------------------------------------------
    # Raw Materials
    # ---------------------------------------------------------

    materials = db.query(models.RawMaterial).all()

    raw_material_value = sum(
        m.stock * m.cost
        for m in materials
    )

    raw_material_count = len(materials)

    # ---------------------------------------------------------
    # Scrap Stock
    # ---------------------------------------------------------

    scrap_types = db.query(models.ScrapType).all()

    scrap_stock_quantity = sum(
        s.stock for s in scrap_types
    )

    scrap_stock_value = sum(
        s.stock * s.selling_rate
        for s in scrap_types
    )

    # ---------------------------------------------------------
    # Total Inventory
    # ---------------------------------------------------------

    inventory_value = (
        finished_goods_value
        + raw_material_value
        + scrap_stock_value
    )

    # ---------------------------------------------------------
    # Low Stock
    # ---------------------------------------------------------

    low_stock_items: list[schemas.LowStockOut] = []

    for product in products:
        if product.stock <= product.min_stock:
            low_stock_items.append(
                schemas.LowStockOut(
                    id=product.id,
                    name=product.name,
                    stock=product.stock,
                    min_stock=product.min_stock,
                    unit=product.unit,
                    kind="Finished good",
                )
            )

    for material in materials:
        if material.stock <= material.min_stock:
            low_stock_items.append(
                schemas.LowStockOut(
                    id=material.id,
                    name=material.name,
                    stock=material.stock,
                    min_stock=material.min_stock,
                    unit=material.unit,
                    kind="Raw material",
                )
            )

    # ---------------------------------------------------------
    # 14-Day Production / Scrap Chart
    # ---------------------------------------------------------

    production_series: list[schemas.ProductionSeriesOut] = []

    for days_ago in range(13, -1, -1):
        current_date = today - timedelta(days=days_ago)

        produced = sum(
            e.quantity
            for e in production_entries
            if e.entry_date == current_date
        )

        scrap = sum(
            s.quantity
            for s in scrap_entries
            if s.entry_date == current_date
        )

        production_series.append(
            schemas.ProductionSeriesOut(
                date=current_date,
                label=current_date.strftime("%m-%d"),
                produced=produced,
                scrap=scrap,
            )
        )

    # ---------------------------------------------------------
    # Recent Production
    # ---------------------------------------------------------

    product_map = {
        p.id: p.name
        for p in products
    }

    recent_production = [
        schemas.RecentProductionOut(
            id=entry.id,
            batch_no=entry.batch_no,
            entry_date=entry.entry_date,
            product_name=product_map.get(
                entry.product_id,
                "Unknown product",
            ),
            quantity=entry.quantity,
            machine=entry.machine,
            operator=entry.operator,
            shift=entry.shift,
        )
        for entry in production_entries[:6]
    ]

    # ---------------------------------------------------------
    # Response
    # ---------------------------------------------------------

    return schemas.DashboardOut(
        produced_today=produced_today,
        produced_month=produced_month,
        scrap_month=scrap_month,
        scrap_rate=scrap_rate,
        inventory_value=inventory_value,
        low_stock_count=len(low_stock_items),

        finished_goods_quantity=finished_goods_quantity,
        finished_goods_sku_count=finished_goods_sku_count,
        finished_goods_value=finished_goods_value,

        scrap_stock_quantity=scrap_stock_quantity,
        scrap_stock_value=scrap_stock_value,

        raw_material_value=raw_material_value,
        raw_material_count=raw_material_count,

        production_series=production_series,
        recent_production=recent_production,
        low_stock_items=low_stock_items,
        top_scrap_reasons=top_scrap_reasons,
    )


@router.get(
    "/settings",
    response_model=schemas.SettingsOut,
)
def get_settings_row(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_area("settings")),
):
    row = db.get(models.CompanySettings, 1)

    if row is None:
        row = models.CompanySettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)

    return row


@router.put(
    "/settings",
    response_model=schemas.SettingsOut,
)
def update_settings(
    payload: schemas.SettingsIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_area("settings")),
):
    row = db.get(models.CompanySettings, 1) or models.CompanySettings(id=1)

    for field, value in payload.model_dump().items():
        setattr(row, field, value)

    db.add(row)

    log_audit(
        db,
        user.username,
        "UPDATE",
        "settings",
        "Company profile updated",
    )

    db.commit()
    db.refresh(row)

    return row


@router.get(
    "/audit",
    response_model=list[schemas.AuditOut],
)
def audit_trail(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    return (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.at.desc())
        .limit(limit)
        .all()
    )
