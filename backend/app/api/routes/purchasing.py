"""Supplier products, purchase orders and GRNs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.models import ItemKind, MovementType
from app.services.inventory import apply_movement, log_audit

router = APIRouter(prefix="/purchasing", tags=["purchasing"])
guard = Depends(require_area("masters"))


def next_number(db: Session, model, field, prefix: str) -> str:
    values = db.query(field).filter(field.like(f"{prefix}%")).all()
    nums = []
    for (value,) in values:
        tail = "".join(ch for ch in value[len(prefix):] if ch.isdigit())
        if tail:
            nums.append(int(tail))
    return f"{prefix}{(max(nums) + 1 if nums else 1):04d}"


@router.get("/supplier-products", response_model=list[schemas.SupplierProductOut])
def list_supplier_products(
    supplier_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    query = db.query(models.SupplierProduct).filter(models.SupplierProduct.active.is_(True))
    if supplier_id:
        query = query.filter(models.SupplierProduct.supplier_id == supplier_id)
    return query.order_by(models.SupplierProduct.id.desc()).all()


@router.get("/orders", response_model=list[schemas.PurchaseOrderOut])
def list_purchase_orders(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.PurchaseOrder).order_by(models.PurchaseOrder.po_date.desc()).all()


@router.post("/orders", response_model=schemas.PurchaseOrderOut, status_code=201)
def create_purchase_order(
    payload: schemas.PurchaseOrderIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    supplier = db.get(models.Party, payload.supplier_id)
    if supplier is None or supplier.kind != "supplier":
        raise HTTPException(404, "Supplier not found")
    if not payload.lines:
        raise HTTPException(400, "Purchase order must contain at least one line")

    po = models.PurchaseOrder(
        po_no=next_number(db, models.PurchaseOrder, models.PurchaseOrder.po_no, "PO"),
        po_date=payload.po_date,
        expected_date=payload.expected_date,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        warehouse_id=payload.warehouse_id,
        notes=payload.notes,
        status=models.PurchaseOrderStatus.draft,
        created_by=user.username,
        sub_total=0,
        gst_total=0,
        grand_total=0,
    )

    for item in payload.lines:
        material = db.get(models.RawMaterial, item.material_id)
        if material is None:
            raise HTTPException(404, f"Material {item.material_id} not found")
        taxable = round(item.quantity * item.rate, 2)
        tax = round(taxable * item.gst_rate / 100, 2)
        po.lines.append(models.PurchaseOrderLine(
            material_id=material.id,
            material_name=material.name,
            unit=material.unit,
            quantity=item.quantity,
            received_quantity=0,
            rate=item.rate,
            gst_rate=item.gst_rate,
            taxable=taxable,
            tax=tax,
            total=round(taxable + tax, 2),
        ))
        po.sub_total += taxable
        po.gst_total += tax

    po.sub_total = round(po.sub_total, 2)
    po.gst_total = round(po.gst_total, 2)
    po.grand_total = round(po.sub_total + po.gst_total, 2)

    db.add(po)
    db.flush()
    log_audit(db, user.username, "CREATE", "purchase_order", f"{po.po_no} · {supplier.name}")
    db.commit()
    db.refresh(po)
    return po


@router.patch("/orders/{purchase_order_id}/status", response_model=schemas.PurchaseOrderOut)
def set_purchase_order_status(
    purchase_order_id: str,
    payload: schemas.PurchaseOrderStatusIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    po = db.get(models.PurchaseOrder, purchase_order_id)
    if po is None:
        raise HTTPException(404, "Purchase order not found")
    po.status = payload.status
    log_audit(db, user.username, "UPDATE", "purchase_order", f"{po.po_no} -> {po.status.value}")
    db.commit()
    db.refresh(po)
    return po


@router.get("/grns", response_model=list[schemas.GRNOut])
def list_grns(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.GRN).order_by(models.GRN.grn_date.desc()).all()


@router.post("/grns", response_model=schemas.GRNOut, status_code=201)
def create_grn(
    payload: schemas.GRNIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    po = db.get(models.PurchaseOrder, payload.purchase_order_id)
    if po is None:
        raise HTTPException(404, "Purchase order not found")
    warehouse = db.get(models.Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise HTTPException(404, "Warehouse not found")
    if not payload.lines:
        raise HTTPException(400, "GRN must contain at least one line")

    grn = models.GRN(
        grn_no=next_number(db, models.GRN, models.GRN.grn_no, "GRN"),
        grn_date=payload.grn_date,
        purchase_order_id=po.id,
        po_no=po.po_no,
        supplier_id=po.supplier_id,
        supplier_name=po.supplier_name,
        warehouse_id=warehouse.id,
        remarks=payload.remarks,
        created_by=user.username,
    )
    db.add(grn)
    db.flush()

    for item in payload.lines:
        line = next((x for x in po.lines if x.material_id == item.material_id), None)
        if line is None:
            raise HTTPException(400, f"Material {item.material_id} is not on {po.po_no}")
        remaining = round(line.quantity - line.received_quantity, 3)
        if item.quantity > remaining:
            raise HTTPException(400, f"Only {remaining} {line.unit} remains on {po.po_no} for {line.material_name}")
        material = db.get(models.RawMaterial, item.material_id)
        if material is None:
            raise HTTPException(404, f"Material {item.material_id} not found")

        grn.lines.append(models.GRNLine(
            material_id=material.id,
            material_name=material.name,
            unit=material.unit,
            quantity=item.quantity,
            batch_no=item.batch_no,
        ))
        line.received_quantity = round(line.received_quantity + item.quantity, 3)
        apply_movement(
            db,
            kind=ItemKind.material,
            item_id=material.id,
            movement_type=MovementType.IN,
            quantity=item.quantity,
            reference=grn.grn_no,
            reason=f"GRN {grn.grn_no} — {po.po_no}",
            entry_date=payload.grn_date,
            user_id=user.id,
        )

    if all(round(x.received_quantity, 3) >= round(x.quantity, 3) for x in po.lines):
        po.status = models.PurchaseOrderStatus.received
    else:
        po.status = models.PurchaseOrderStatus.partially_received

    log_audit(db, user.username, "CREATE", "grn", f"{grn.grn_no} · {po.po_no} · {po.supplier_name}")
    db.commit()
    db.refresh(grn)
    return grn
