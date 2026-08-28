"""Database-backed purchasing master, purchase order, and GRN CRUD."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit
from app.models import ItemKind, MovementType
from app.services.inventory import apply_movement, log_audit

router = APIRouter(prefix="/purchasing", tags=["purchasing"])

guard = Depends(require_area("masters"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(db: Session, model, pk: str):
    row = db.get(model, pk)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Record not found",
        )
    return row


def _get_or_404(db: Session, model, record_id: str):
    row = db.get(model, record_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )

    return row


def _replace_fields(row, payload, *, exclude: set[str] | None = None):
    excluded = exclude or set()

    for key, value in payload.model_dump(exclude=excluded).items():
        setattr(row, key, value)


# ---------------------------------------------------------------------------
# Supplier Products
# ---------------------------------------------------------------------------

@router.get(
    "/supplier-products",
    response_model=list[schemas.SupplierProductOut],
)
def list_supplier_products(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.SupplierProduct)
        .order_by(models.SupplierProduct.supplier_code)
        .all()
    )

@router.post(
    "/supplier-products",
    response_model=schemas.SupplierProductOut,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_product(
    payload: schemas.SupplierProductIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    # ---------------------------------------------------------------
    # Basic validation
    # ---------------------------------------------------------------
    if payload.purchase_rate < 0:
        raise HTTPException(
            status_code=400,
            detail="Purchase rate cannot be negative",
        )

    if payload.minimum_order_qty <= 0:
        raise HTTPException(
            status_code=400,
            detail="Minimum order quantity must be greater than zero",
        )

    if payload.lead_time_days < 0:
        raise HTTPException(
            status_code=400,
            detail="Lead time cannot be negative",
        )

    # ---------------------------------------------------------------
    # Supplier validation
    # ---------------------------------------------------------------
    supplier = db.get(
        models.Party,
        payload.supplier_id,
    )

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found",
        )

    if supplier.kind != "supplier":
        raise HTTPException(
            status_code=400,
            detail="Selected party is not a supplier",
        )

    # ---------------------------------------------------------------
    # Material validation
    # ---------------------------------------------------------------
    material = db.get(
        models.RawMaterial,
        payload.product_id,
    )

    if material is None:
        raise HTTPException(
            status_code=404,
            detail="Raw material not found",
        )

    # ---------------------------------------------------------------
    # Duplicate supplier/material mapping
    # ---------------------------------------------------------------
    duplicate = (
        db.query(models.SupplierProduct)
        .filter(
            models.SupplierProduct.supplier_id == payload.supplier_id,
            models.SupplierProduct.product_id == payload.product_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{material.name} is already mapped to "
                f"supplier {supplier.name}"
            ),
        )

    # ---------------------------------------------------------------
    # Create mapping
    # ---------------------------------------------------------------
    row = models.SupplierProduct(
        **payload.model_dump()
    )

    db.add(row)

    log_audit(
        db,
        user.username,
        "CREATE",
        "supplier_product",
        payload.supplier_code,
    )

    db.commit()
    db.refresh(row)

    return row
@router.put(
    "/supplier-products/{row_id}",
    response_model=schemas.SupplierProductOut,
)
def update_supplier_product(
    row_id: str,
    payload: schemas.SupplierProductIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    row = _get_or_404(
        db,
        models.SupplierProduct,
        row_id,
    )

    # ---------------------------------------------------------------
    # Basic validation
    # ---------------------------------------------------------------
    if payload.purchase_rate < 0:
        raise HTTPException(
            status_code=400,
            detail="Purchase rate cannot be negative",
        )

    if payload.minimum_order_qty <= 0:
        raise HTTPException(
            status_code=400,
            detail="Minimum order quantity must be greater than zero",
        )

    if payload.lead_time_days < 0:
        raise HTTPException(
            status_code=400,
            detail="Lead time cannot be negative",
        )

    # ---------------------------------------------------------------
    # Supplier validation
    # ---------------------------------------------------------------
    supplier = db.get(
        models.Party,
        payload.supplier_id,
    )

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found",
        )

    if supplier.kind != "supplier":
        raise HTTPException(
            status_code=400,
            detail="Selected party is not a supplier",
        )

    # ---------------------------------------------------------------
    # Material validation
    # ---------------------------------------------------------------
    material = db.get(
        models.RawMaterial,
        payload.product_id,
    )

    if material is None:
        raise HTTPException(
            status_code=404,
            detail="Raw material not found",
        )

    # ---------------------------------------------------------------
    # Prevent duplicate supplier/material mapping
    # ---------------------------------------------------------------
    duplicate = (
        db.query(models.SupplierProduct)
        .filter(
            models.SupplierProduct.supplier_id == payload.supplier_id,
            models.SupplierProduct.product_id == payload.product_id,
            models.SupplierProduct.id != row_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{material.name} is already mapped to "
                f"supplier {supplier.name}"
            ),
        )

    # ---------------------------------------------------------------
    # Update
    # ---------------------------------------------------------------
    _replace_fields(row, payload)

    log_audit(
        db,
        user.username,
        "UPDATE",
        "supplier_product",
        row.supplier_code,
    )

    db.commit()
    db.refresh(row)

    return row


@router.delete(
    "/supplier-products/{row_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_supplier_product(
    row_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    row = _get_or_404(db, models.SupplierProduct, row_id)

    identifier = row.supplier_code

    db.delete(row)

    log_audit(
        db,
        user.username,
        "DELETE",
        "supplier_product",
        identifier,
    )

    db.commit()


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------

@router.post(
    "/orders",
    response_model=schemas.PurchaseOrderOut,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order(
    payload: schemas.PurchaseOrderIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    if not payload.lines:
        raise HTTPException(
            status_code=400,
            detail="At least one purchase order line is required",
        )

    if payload.expected_date and payload.expected_date < payload.po_date:
        raise HTTPException(
            status_code=400,
            detail="Expected date cannot be before PO date",
        )

    # ---------------------------------------------------------------
    # PO number uniqueness
    # ---------------------------------------------------------------
    duplicate = (
        db.query(models.PurchaseOrder)
        .filter(models.PurchaseOrder.po_no == payload.po_no)
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Purchase order number already exists",
        )

    # ---------------------------------------------------------------
    # Supplier validation
    # ---------------------------------------------------------------
    supplier = db.get(models.Party, payload.supplier_id)

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found",
        )

    if supplier.kind != "supplier":
        raise HTTPException(
            status_code=400,
            detail="Selected party is not a supplier",
        )

    if payload.supplier_name != supplier.name:
        raise HTTPException(
            status_code=400,
            detail="Supplier name does not match supplier record",
        )

    # ---------------------------------------------------------------
    # Warehouse validation
    # ---------------------------------------------------------------
    if payload.warehouse_id:
        warehouse = db.get(
            models.Warehouse,
            payload.warehouse_id,
        )

        if warehouse is None:
            raise HTTPException(
                status_code=404,
                detail="Warehouse not found",
            )

        if not warehouse.active:
            raise HTTPException(
                status_code=400,
                detail="Selected warehouse is inactive",
            )

    # ---------------------------------------------------------------
    # Validate lines
    # ---------------------------------------------------------------
    material_ids: set[str] = set()
    validated_lines = []

    for line in payload.lines:
        if not line.material_id:
            raise HTTPException(
                status_code=400,
                detail="Material is required on every purchase order line",
            )

        if line.material_id in material_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Material {line.material_id} appears more than once",
            )

        material_ids.add(line.material_id)

        if line.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Purchase quantity must be greater than zero",
            )

        if line.rate < 0:
            raise HTTPException(
                status_code=400,
                detail="Purchase rate cannot be negative",
            )

        if line.gst_rate < 0:
            raise HTTPException(
                status_code=400,
                detail="GST rate cannot be negative",
            )

        material = db.get(
            models.RawMaterial,
            line.material_id,
        )

        if material is None:
            raise HTTPException(
                status_code=404,
                detail=f"Raw material {line.material_id} not found",
            )

        if line.material_name != material.name:
            raise HTTPException(
                status_code=400,
                detail=f"Material name does not match {material.name}",
            )

        mapping = (
            db.query(models.SupplierProduct)
            .filter(
                models.SupplierProduct.supplier_id == supplier.id,
                models.SupplierProduct.product_id == material.id,
            )
            .first()
        )

        if mapping is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{material.name} is not mapped to supplier "
                    f"{supplier.name}"
                ),
            )

        validated_lines.append((line, material))

    # ---------------------------------------------------------------
    # Validate totals
    # ---------------------------------------------------------------
    calculated_subtotal = round(
        sum(line.quantity * line.rate for line in payload.lines),
        2,
    )

    calculated_gst = round(
        sum(
            line.quantity
            * line.rate
            * line.gst_rate
            / 100
            for line in payload.lines
        ),
        2,
    )

    calculated_grand_total = round(
        calculated_subtotal + calculated_gst,
        2,
    )

    if abs(payload.sub_total - calculated_subtotal) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Sub-total mismatch: expected {calculated_subtotal}",
        )

    if abs(payload.gst_total - calculated_gst) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"GST total mismatch: expected {calculated_gst}",
        )

    if abs(payload.grand_total - calculated_grand_total) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Grand total mismatch: expected {calculated_grand_total}",
        )

    # ---------------------------------------------------------------
    # Create PO
    # ---------------------------------------------------------------
    row = models.PurchaseOrder(
        po_no=payload.po_no,
        po_date=payload.po_date,
        expected_date=payload.expected_date,
        supplier_id=payload.supplier_id,
        supplier_name=payload.supplier_name,
        warehouse_id=payload.warehouse_id,
        notes=payload.notes,
        status=models.PurchaseOrderStatus.draft,
        sub_total=calculated_subtotal,
        gst_total=calculated_gst,
        grand_total=calculated_grand_total,
        created_by=user.username,
    )

    row.lines = [
        models.PurchaseOrderLine(
            material_id=line.material_id,
            material_name=material.name,
            quantity=line.quantity,
            rate=line.rate,
            gst_rate=line.gst_rate,
            received_quantity=0,
            tax=round(
                line.quantity * line.rate * line.gst_rate / 100,
                2,
            ),
            total=round(
                line.quantity * line.rate
                + line.quantity * line.rate * line.gst_rate / 100,
                2,
            ),
        )
        for line, material in validated_lines
    ]

    db.add(row)

    log_audit(
        db,
        user.username,
        "CREATE",
        "purchase_order",
        row.po_no,
    )

    db.commit()
    db.refresh(row)

    return row


@router.get(
    "/orders",
    response_model=list[schemas.PurchaseOrderOut],
)
def list_purchase_orders(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.PurchaseOrder)
        .options(selectinload(models.PurchaseOrder.lines))
        .order_by(models.PurchaseOrder.po_date.desc())
        .all()
    )


@router.get(
    "/orders/{order_id}",
    response_model=schemas.PurchaseOrderOut,
)
def get_purchase_order(
    order_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    row = (
        db.query(models.PurchaseOrder)
        .options(selectinload(models.PurchaseOrder.lines))
        .filter(models.PurchaseOrder.id == order_id)
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    return row


@router.put("/orders/{order_id}", response_model=schemas.PurchaseOrderOut)
def update_purchase_order(
    order_id: str,
    payload: schemas.PurchaseOrderIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    row = _get(db, models.PurchaseOrder, order_id)

    if not payload.lines:
        raise HTTPException(
            status_code=400,
            detail="At least one purchase order line is required",
        )

    if payload.expected_date and payload.expected_date < payload.po_date:
        raise HTTPException(
            status_code=400,
            detail="Expected date cannot be before PO date",
        )

    # ---------------------------------------------------------------
    # PO number uniqueness
    # ---------------------------------------------------------------
    duplicate = (
        db.query(models.PurchaseOrder)
        .filter(
            models.PurchaseOrder.po_no == payload.po_no,
            models.PurchaseOrder.id != order_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Purchase order number already exists",
        )

    # ---------------------------------------------------------------
    # Supplier
    # ---------------------------------------------------------------
    supplier = db.get(models.Party, payload.supplier_id)

    if supplier is None:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found",
        )

    if supplier.kind != "supplier":
        raise HTTPException(
            status_code=400,
            detail="Selected party is not a supplier",
        )

    if payload.supplier_name != supplier.name:
        raise HTTPException(
            status_code=400,
            detail="Supplier name does not match supplier record",
        )

    # Don't allow moving an existing PO to another supplier.
    if row.supplier_id != payload.supplier_id:
        raise HTTPException(
            status_code=400,
            detail="An existing purchase order cannot be moved to another supplier",
        )

    # ---------------------------------------------------------------
    # Warehouse
    # ---------------------------------------------------------------
    if payload.warehouse_id:
        warehouse = db.get(
            models.Warehouse,
            payload.warehouse_id,
        )

        if warehouse is None:
            raise HTTPException(
                status_code=404,
                detail="Warehouse not found",
            )

        if not warehouse.active:
            raise HTTPException(
                status_code=400,
                detail="Selected warehouse is inactive",
            )

    # Don't move an existing PO between warehouses once created.
    if (
        row.warehouse_id is not None
        and row.warehouse_id != payload.warehouse_id
    ):
        raise HTTPException(
            status_code=400,
            detail="An existing purchase order cannot be moved to another warehouse",
        )

    # ---------------------------------------------------------------
    # Validate lines
    # ---------------------------------------------------------------
    material_ids: set[str] = set()

    for line in payload.lines:
        if not line.material_id:
            raise HTTPException(
                status_code=400,
                detail="Material is required on every purchase order line",
            )

        if line.material_id in material_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Material {line.material_id} appears more than once",
            )

        material_ids.add(line.material_id)

        if line.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Purchase quantity must be greater than zero",
            )

        if line.rate < 0:
            raise HTTPException(
                status_code=400,
                detail="Purchase rate cannot be negative",
            )

        if line.gst_rate < 0:
            raise HTTPException(
                status_code=400,
                detail="GST rate cannot be negative",
            )

        material = db.get(
            models.RawMaterial,
            line.material_id,
        )

        if material is None:
            raise HTTPException(
                status_code=404,
                detail=f"Raw material {line.material_id} not found",
            )

        if line.material_name != material.name:
            raise HTTPException(
                status_code=400,
                detail=f"Material name does not match {material.name}",
            )

        mapping = (
            db.query(models.SupplierProduct)
            .filter(
                models.SupplierProduct.supplier_id == supplier.id,
                models.SupplierProduct.product_id == material.id,
            )
            .first()
        )

        if mapping is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{material.name} is not mapped to supplier "
                    f"{supplier.name}"
                ),
            )

    # ---------------------------------------------------------------
    # Existing receipts must remain valid.
    # ---------------------------------------------------------------
    existing_received = {
        line.material_id: line.received_quantity
        for line in row.lines
        if line.material_id
    }

    for line in payload.lines:
        received = existing_received.get(line.material_id, 0)

        if line.quantity < received:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot reduce {line.material_name} quantity below "
                    f"already received quantity ({received})"
                ),
            )

        if abs(line.received_quantity - received) > 0.000001:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Received quantity for {line.material_name} "
                    f"is managed by GRNs and cannot be changed here"
                ),
            )

    # Don't silently remove a material that already has receipts.
    submitted_materials = {
        line.material_id
        for line in payload.lines
    }

    removed_received = [
        line.material_name
        for line in row.lines
        if line.material_id
        and line.received_quantity > 0
        and line.material_id not in submitted_materials
    ]

    if removed_received:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot remove materials that already have GRN receipts: "
                + ", ".join(removed_received)
            ),
        )

    # ---------------------------------------------------------------
    # Validate totals
    # ---------------------------------------------------------------
    calculated_subtotal = round(
        sum(line.quantity * line.rate for line in payload.lines),
        2,
    )

    calculated_gst = round(
        sum(
            line.quantity
            * line.rate
            * line.gst_rate
            / 100
            for line in payload.lines
        ),
        2,
    )

    calculated_grand_total = round(
        calculated_subtotal + calculated_gst,
        2,
    )

    if abs(payload.sub_total - calculated_subtotal) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Sub-total mismatch: expected {calculated_subtotal}",
        )

    if abs(payload.gst_total - calculated_gst) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"GST total mismatch: expected {calculated_gst}",
        )

    if abs(payload.grand_total - calculated_grand_total) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Grand total mismatch: expected {calculated_grand_total}",
        )

    # ---------------------------------------------------------------
    # Update header
    # ---------------------------------------------------------------
    for key, value in payload.model_dump(exclude={"lines"}).items():
        setattr(row, key, value)

    # Preserve server-controlled received quantities.
    row.lines[:] = [
        models.PurchaseOrderLine(
            material_id=line.material_id,
            material_name=line.material_name,
            quantity=line.quantity,
            rate=line.rate,
            gst_rate=line.gst_rate,
            received_quantity=existing_received.get(
                line.material_id,
                0,
            ),
            tax=line.tax,
            total=line.total,
        )
        for line in payload.lines
    ]

    # ---------------------------------------------------------------
    # Recalculate status from actual receipts.
    # ---------------------------------------------------------------
    if all(
        line.received_quantity >= line.quantity
        for line in row.lines
    ):
        row.status = models.PurchaseOrderStatus.received
    elif any(
        line.received_quantity > 0
        for line in row.lines
    ):
        row.status = models.PurchaseOrderStatus.partially_received
    else:
        row.status = models.PurchaseOrderStatus.draft

    log_audit(
        db,
        user.username,
        "UPDATE",
        "purchase_order",
        row.po_no,
    )

    db.commit()
    db.refresh(row)

    return row


@router.delete(
    "/orders/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_purchase_order(
    order_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    row = _get_or_404(
        db,
        models.PurchaseOrder,
        order_id,
    )

    # Do not allow deletion once the PO has been received against.
    grn_count = (
        db.query(models.GRN)
        .filter(
            models.GRN.purchase_order_id == row.id
        )
        .count()
    )

    if grn_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Purchase order cannot be deleted because "
                "it has GRN receipts"
            ),
        )

    identifier = row.po_no

    db.delete(row)

    log_audit(
        db,
        user.username,
        "DELETE",
        "purchase_order",
        identifier,
    )

    db.commit()


# ---------------------------------------------------------------------------
# GRNs
# ---------------------------------------------------------------------------

@router.get(
    "/grns",
    response_model=list[schemas.GRNOut],
)
def list_grns(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.GRN)
        .options(selectinload(models.GRN.lines))
        .order_by(models.GRN.grn_date.desc())
        .all()
    )


@router.get(
    "/grns/{grn_id}",
    response_model=schemas.GRNOut,
)
def get_grn(
    grn_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    row = (
        db.query(models.GRN)
        .options(selectinload(models.GRN.lines))
        .filter(models.GRN.id == grn_id)
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GRN not found",
        )

    return row


@router.post("/grns", response_model=schemas.GRNOut, status_code=201)
def create_grn(
    payload: schemas.GRNIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    if db.query(models.GRN).filter(
        models.GRN.grn_no == payload.grn_no
    ).first():
        raise HTTPException(
            status_code=409,
            detail="GRN number already exists",
        )

    po = db.get(models.PurchaseOrder, payload.purchase_order_id)

    if po is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found",
        )

    if po.status == models.PurchaseOrderStatus.received:
        raise HTTPException(
            status_code=400,
            detail="Purchase order is already fully received",
        )

    if not payload.lines:
        raise HTTPException(
            status_code=400,
            detail="At least one GRN line is required",
        )

    warehouse_id = payload.warehouse_id

    if po.warehouse_id and po.warehouse_id != warehouse_id:
        raise HTTPException(
            status_code=400,
            detail="GRN warehouse does not match the purchase order warehouse",
        )

    # Validate the entire receipt BEFORE changing anything.
    receipt_lines = []

    for line in payload.lines:
        if line.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="GRN quantity must be greater than zero",
            )

        material = db.get(
            models.RawMaterial,
            line.material_id,
        )

        if material is None:
            raise HTTPException(
                status_code=404,
                detail=f"Raw material {line.material_id} not found",
            )

        po_line = next(
            (
                x
                for x in po.lines
                if x.material_id == line.material_id
            ),
            None,
        )

        if po_line is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Material {line.material_id} "
                    f"is not present on purchase order {po.po_no}"
                ),
            )

        pending = round(
            po_line.quantity - po_line.received_quantity,
            6,
        )

        if pending <= 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{material.name} is already fully received "
                    f"on {po.po_no}"
                ),
            )

        if line.quantity > pending:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only {pending} {material.unit} of "
                    f"{material.name} is pending on {po.po_no}"
                ),
            )

        receipt_lines.append(
            (line, material, po_line)
        )

    # Create the GRN only after every line has passed validation.
    grn = models.GRN(
        **payload.model_dump(exclude={"lines"})
    )

    grn.lines = [
        models.GRNLine(
            material_id=line.material_id,
            material_name=material.name,
            quantity=line.quantity,
            batch_no=line.batch_no,
        )
        for line, material, _ in receipt_lines
    ]

    db.add(grn)

    # Apply the complete receipt as one DB transaction.
    for line, material, po_line in receipt_lines:
        po_line.received_quantity = round(
            po_line.received_quantity + line.quantity,
            6,
        )

        material.stock = round(
            material.stock + line.quantity,
            6,
        )

        # InventoryMovement is the durable movement ledger.
        movement = models.InventoryMovement(
            id=models._uuid(),
            entry_date=payload.grn_date,
            item_kind=models.ItemKind.material,
            item_id=material.id,
            item_name=material.name,
            movement_type=models.MovementType.IN,
            quantity=line.quantity,
            unit=material.unit,
            balance=material.stock,
            reference=payload.grn_no,
            reason=f"Purchase receipt — {po.po_no}",
            user_id=user.id,
        )

        db.add(movement)

    # Determine PO completion only after all receipt quantities
    # have been applied.
    if all(
        line.received_quantity >= line.quantity
        for line in po.lines
    ):
        po.status = models.PurchaseOrderStatus.received
    else:
        po.status = models.PurchaseOrderStatus.partially_received

    log_audit(
        db,
        user.username,
        "CREATE",
        "grn",
        f"{payload.grn_no} against {po.po_no}",
    )

    db.commit()
    db.refresh(grn)

    return grn

@router.put("/grns/{grn_id}", response_model=schemas.GRNOut)
def update_grn(
    grn_id: str,
    payload: schemas.GRNIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    grn = _get(db, models.GRN, grn_id)

    if not payload.lines:
        raise HTTPException(
            status_code=400,
            detail="At least one GRN line is required",
        )

    # Do not allow changing the GRN number to another existing GRN.
    duplicate = (
        db.query(models.GRN)
        .filter(
            models.GRN.grn_no == payload.grn_no,
            models.GRN.id != grn_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="GRN number already exists",
        )

    po = db.get(models.PurchaseOrder, payload.purchase_order_id)

    if po is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found",
        )

    # The GRN must continue to belong to the same PO.
    if grn.purchase_order_id != payload.purchase_order_id:
        raise HTTPException(
            status_code=400,
            detail="A GRN cannot be moved to another purchase order",
        )

    if po.warehouse_id and po.warehouse_id != payload.warehouse_id:
        raise HTTPException(
            status_code=400,
            detail="GRN warehouse does not match the purchase order warehouse",
        )

    # ---------------------------------------------------------------
    # Build the old receipt quantities by material.
    # ---------------------------------------------------------------
    old_receipts: dict[str, float] = {}

    for line in grn.lines:
        old_receipts[line.material_id] = (
            old_receipts.get(line.material_id, 0)
            + line.quantity
        )

    # ---------------------------------------------------------------
    # Remove the old receipt from PO received quantities.
    # ---------------------------------------------------------------
    for material_id, quantity in old_receipts.items():
        po_line = next(
            (
                line
                for line in po.lines
                if line.material_id == material_id
            ),
            None,
        )

        if po_line is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Existing GRN material {material_id} "
                    f"is no longer present on purchase order {po.po_no}"
                ),
            )

        po_line.received_quantity = round(
            po_line.received_quantity - quantity,
            6,
        )

        if po_line.received_quantity < 0:
            raise HTTPException(
                status_code=400,
                detail="Purchase order received quantity cannot become negative",
            )

    # ---------------------------------------------------------------
    # Validate the replacement receipt BEFORE applying stock changes.
    # ---------------------------------------------------------------
    new_lines = []

    for line in payload.lines:
        if line.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="GRN quantity must be greater than zero",
            )

        material = db.get(
            models.RawMaterial,
            line.material_id,
        )

        if material is None:
            raise HTTPException(
                status_code=404,
                detail=f"Raw material {line.material_id} not found",
            )

        po_line = next(
            (
                x
                for x in po.lines
                if x.material_id == line.material_id
            ),
            None,
        )

        if po_line is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Material {material.name} "
                    f"is not present on purchase order {po.po_no}"
                ),
            )

        pending = round(
            po_line.quantity - po_line.received_quantity,
            6,
        )

        if line.quantity > pending:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only {pending} {material.unit} of "
                    f"{material.name} is available to receive"
                ),
            )

        new_lines.append((line, material, po_line))

    # ---------------------------------------------------------------
    # Reverse the old inventory receipt.
    # ---------------------------------------------------------------
    for material_id, quantity in old_receipts.items():
        material = db.get(models.RawMaterial, material_id)

        if material is None:
            raise HTTPException(
                status_code=404,
                detail=f"Raw material {material_id} not found",
            )

        apply_movement(
            db,
            kind=ItemKind.material,
            item_id=material.id,
            movement_type=MovementType.OUT,
            quantity=quantity,
            reference=grn.grn_no,
            reason=f"Reverse GRN - {grn.grn_no}",
            entry_date=payload.grn_date,
            user_id=user.id,
        )

    # ---------------------------------------------------------------
    # Apply the replacement inventory receipt.
    # ---------------------------------------------------------------
    for line, material, po_line in new_lines:
        apply_movement(
            db,
            kind=ItemKind.material,
            item_id=material.id,
            movement_type=MovementType.IN,
            quantity=line.quantity,
            reference=payload.grn_no,
            reason=f"GRN update — {po.po_no}",
            entry_date=payload.grn_date,
            user_id=user.id,
        )

        po_line.received_quantity = round(
            po_line.received_quantity + line.quantity,
            6,
        )

    # Replace GRN header.
    for key, value in payload.model_dump(exclude={"lines"}).items():
        setattr(grn, key, value)

    # Replace GRN lines.
    grn.lines[:] = [
        models.GRNLine(
            material_id=line.material_id,
            material_name=material.name,
            quantity=line.quantity,
            batch_no=line.batch_no,
        )
        for line, material, _ in new_lines
    ]

    # Recalculate PO status.
    if all(
        line.received_quantity >= line.quantity
        for line in po.lines
    ):
        po.status = models.PurchaseOrderStatus.received
    elif any(
        line.received_quantity > 0
        for line in po.lines
    ):
        po.status = models.PurchaseOrderStatus.partially_received
    else:
        po.status = models.PurchaseOrderStatus.draft

    log_audit(
        db,
        user.username,
        "UPDATE",
        "grn",
        f"{grn.grn_no} against {po.po_no}",
    )

    db.commit()
    db.refresh(grn)

    return grn

@router.delete("/grns/{grn_id}", status_code=204)
def delete_grn(
    grn_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    grn = _get(db, models.GRN, grn_id)

    po = db.get(models.PurchaseOrder, grn.purchase_order_id)

    if po is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found",
        )

    # Aggregate the GRN quantities by material.
    receipts: dict[str, float] = {}

    for line in grn.lines:
        receipts[line.material_id] = (
            receipts.get(line.material_id, 0)
            + line.quantity
        )

    # Reverse stock and PO received quantities.
    for material_id, quantity in receipts.items():
        material = db.get(
            models.RawMaterial,
            material_id,
        )

        if material is None:
            raise HTTPException(
                status_code=404,
                detail=f"Raw material {material_id} not found",
            )

        po_line = next(
            (
                line
                for line in po.lines
                if line.material_id == material_id
            ),
            None,
        )

        if po_line is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Material {material_id} "
                    f"is not present on purchase order {po.po_no}"
                ),
            )

        if po_line.received_quantity < quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot reverse {quantity} received units of "
                    f"{material.name}; PO only records "
                    f"{po_line.received_quantity}"
                ),
            )

        # apply_movement() protects against negative stock.
        apply_movement(
            db,
            kind=ItemKind.material,
            item_id=material.id,
            movement_type=MovementType.OUT,
            quantity=quantity,
            reference=grn.grn_no,
            reason=f"Reverse deleted GRN {grn.grn_no}",
            entry_date=grn.grn_date,
            user_id=user.id,
        )

        po_line.received_quantity = round(
            po_line.received_quantity - quantity,
            6,
        )

    # Recalculate PO status.
    if all(
        line.received_quantity >= line.quantity
        for line in po.lines
    ):
        po.status = models.PurchaseOrderStatus.received
    elif any(
        line.received_quantity > 0
        for line in po.lines
    ):
        po.status = models.PurchaseOrderStatus.partially_received
    else:
        po.status = models.PurchaseOrderStatus.draft

    grn_no = grn.grn_no
    po_no = po.po_no

    db.delete(grn)

    log_audit(
        db,
        user.username,
        "DELETE",
        "grn",
        f"{grn_no} against {po_no}",
    )

    db.commit()
