"""Sales invoice routes: sequential numbering, GST, duplicate guard, history."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.models import ItemKind, MovementType
from app.services.gst import compute_line, is_inter_state, round_off
from app.services.inventory import apply_movement, log_audit

router = APIRouter(prefix="/sales", tags=["sales"])
guard = Depends(require_area("sales"))


def _settings(db: Session) -> models.CompanySettings:
    row = db.get(models.CompanySettings, 1)
    if row is None:
        row = models.CompanySettings(id=1)
        db.add(row)
        db.flush()
    return row


def next_invoice_no(db: Session, prefix: str) -> str:
    """Gapless sequence per prefix, e.g. SPW/26-27/0007."""
    numbers = [
        int(tail)
        for (no,) in db.query(models.Invoice.invoice_no).filter(models.Invoice.invoice_no.like(f"{prefix}%")).all()
        if (tail := "".join(ch for ch in no[len(prefix) :] if ch.isdigit()))
    ]
    return f"{prefix}{(max(numbers) + 1 if numbers else 1):04d}"


def _signature(payload: schemas.InvoiceIn) -> str:
    parts = sorted(f"{l.product_id}:{l.quantity}:{l.rate}:{l.discount_percent}" for l in payload.lines)
    raw = "|".join([payload.customer_id, payload.invoice_date.isoformat(), *parts])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@router.get("/invoices", response_model=list[schemas.InvoiceOut])
def list_invoices(
    q: str | None = Query(default=None, description="Search invoice no, customer or PO reference"),
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    query = db.query(models.Invoice)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                models.Invoice.invoice_no.ilike(like),
                models.Invoice.customer_name.ilike(like),
                models.Invoice.po_reference.ilike(like),
            )
        )
    return query.order_by(models.Invoice.invoice_date.desc(), models.Invoice.invoice_no.desc()).all()


@router.get("/invoices/next-number")
def peek_next_number(db: Session = Depends(get_db), user: models.User = guard) -> dict[str, str]:
    return {"invoice_no": next_invoice_no(db, _settings(db).invoice_prefix)}


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(invoice_id: str, db: Session = Depends(get_db), user: models.User = guard):
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/invoices", response_model=schemas.InvoiceOut, status_code=201)
def create_invoice(payload: schemas.InvoiceIn, db: Session = Depends(get_db), user: models.User = guard):
    customer = db.get(models.Party, payload.customer_id)
    if customer is None or customer.kind != "customer":
        raise HTTPException(status_code=404, detail="Customer not found")

    product_ids = [l.product_id for l in payload.lines]
    if len(set(product_ids)) != len(product_ids):
        raise HTTPException(status_code=400, detail="The same product is listed twice — merge those lines")

    signature = _signature(payload)
    clash = db.query(models.Invoice).filter(models.Invoice.signature == signature).first()
    if clash is not None:
        raise HTTPException(status_code=409, detail=f"Identical invoice already exists ({clash.invoice_no})")

    settings = _settings(db)
    inter_state = is_inter_state(settings.gst_number, customer.gst_number)

    invoice = models.Invoice(
        invoice_no=next_invoice_no(db, settings.invoice_prefix),
        invoice_date=payload.invoice_date,
        customer_id=customer.id,
        customer_name=customer.name,
        po_reference=payload.po_reference,
        notes=payload.notes,
        inter_state=int(inter_state),
        status=payload.status,
        signature=signature,
        created_by=user.username,
    )

    sub_total = discount_total = 0.0
    for line in payload.lines:
        product = db.get(models.Product, line.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product {line.product_id} not found")
        tax = compute_line(
            quantity=line.quantity,
            rate=line.rate,
            discount_percent=line.discount_percent,
            gst_rate=product.gst_rate,
            inter_state=inter_state,
        )
        gross = round(line.quantity * line.rate, 2)
        sub_total += gross
        discount_total += round(gross - tax.taxable, 2)
        invoice.lines.append(
            models.InvoiceLine(
                product_id=product.id,
                product_name=product.name,
                hsn=product.hsn,
                unit=product.unit,
                quantity=line.quantity,
                rate=line.rate,
                discount_percent=line.discount_percent,
                gst_rate=product.gst_rate,
                taxable=tax.taxable,
                cgst=tax.cgst,
                sgst=tax.sgst,
                igst=tax.igst,
                total=tax.total,
            )
        )
        invoice.taxable_total += tax.taxable
        invoice.cgst += tax.cgst
        invoice.sgst += tax.sgst
        invoice.igst += tax.igst

    invoice.sub_total = round(sub_total, 2)
    invoice.discount_total = round(discount_total, 2)
    invoice.taxable_total = round(invoice.taxable_total, 2)
    invoice.cgst, invoice.sgst, invoice.igst = round(invoice.cgst, 2), round(invoice.sgst, 2), round(invoice.igst, 2)
    pre_round = invoice.taxable_total + invoice.cgst + invoice.sgst + invoice.igst
    invoice.grand_total, invoice.round_off = round_off(pre_round)
    db.add(invoice)

    # Finished goods leave stock; a shortage aborts the whole invoice.
    for line in invoice.lines:
        apply_movement(
            db,
            kind=ItemKind.product,
            item_id=line.product_id,
            movement_type=MovementType.OUT,
            quantity=line.quantity,
            reference=invoice.invoice_no,
            reason=f"Sales invoice — {customer.name}",
            entry_date=payload.invoice_date,
            user_id=user.id,
        )

    log_audit(db, user.username, "create", "invoice", f"{invoice.invoice_no} · {customer.name}")
    db.commit()
    db.refresh(invoice)
    return invoice


@router.patch("/invoices/{invoice_id}/status", response_model=schemas.InvoiceOut)
def set_status(
    invoice_id: str, payload: schemas.InvoiceStatusIn, db: Session = Depends(get_db), user: models.User = guard
):
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = payload.status
    log_audit(db, user.username, "update", "invoice", f"{invoice.invoice_no} -> {payload.status.value}")
    db.commit()
    db.refresh(invoice)
    return invoice
