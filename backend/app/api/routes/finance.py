"""Customer/supplier payment records and outstanding balances."""

from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.modules.core.audit import log_audit

router = APIRouter(prefix="/finance", tags=["finance"])
guard = Depends(require_area("finance"))


def _next_payment_no(db: Session, model: type, prefix: str) -> str:
    rows = db.query(model.payment_no).all()
    numbers = []
    for (number,) in rows:
        if number.startswith(prefix):
            tail = "".join(ch for ch in number[len(prefix):] if ch.isdigit())
            if tail:
                numbers.append(int(tail))
    return f"{prefix}{(max(numbers) + 1 if numbers else 1):04d}"


@router.get("/customer-payments", response_model=list[schemas.CustomerPaymentOut])
def list_customer_payments(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return db.query(models.CustomerPayment).order_by(
        models.CustomerPayment.payment_date.desc(),
        models.CustomerPayment.payment_no.desc(),
    ).all()


@router.post("/customer-payments", response_model=schemas.CustomerPaymentOut, status_code=201)
def create_customer_payment(
    payload: schemas.CustomerPaymentIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    customer = db.get(models.Party, payload.customer_id)
    if customer is None or customer.kind != "customer":
        raise HTTPException(status_code=404, detail="Customer not found")

    invoice = None
    if payload.invoice_id:
        invoice = db.get(models.Invoice, payload.invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.customer_id != customer.id:
            raise HTTPException(status_code=400, detail="Invoice does not belong to this customer")
        if invoice.status == models.InvoiceStatus.cancelled:
            raise HTTPException(status_code=400, detail="Cannot pay a cancelled invoice")

        existing = (
            db.query(models.CustomerPayment)
            .filter(models.CustomerPayment.invoice_id == invoice.id)
            .all()
        )
        allocated = round(sum(p.amount for p in existing), 2)
        remaining = round(invoice.grand_total - allocated, 2)
        if payload.amount > remaining + 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Payment exceeds invoice balance of ₹{remaining:.2f}",
            )

    payment = models.CustomerPayment(
        payment_no=_next_payment_no(db, models.CustomerPayment, "CPAY"),
        payment_date=payload.payment_date,
        customer_id=customer.id,
        customer_name=customer.name,
        invoice_id=invoice.id if invoice else None,
        invoice_no=invoice.invoice_no if invoice else "",
        amount=round(payload.amount, 2),
        mode=payload.mode,
        reference=payload.reference,
        remarks=payload.remarks,
        created_by=user.username,
    )
    if invoice:
        existing_paid = round(sum(
            p.amount for p in db.query(models.CustomerPayment).filter(
                models.CustomerPayment.invoice_id == invoice.id
            ).all()
        ), 2)
        invoice.paid_amount = round(existing_paid + payload.amount, 2)
        invoice.balance_amount = round(invoice.grand_total - invoice.paid_amount, 2)
        if invoice.balance_amount <= 0.01:
            invoice.paid_amount = invoice.grand_total
            invoice.balance_amount = 0
            invoice.status = models.InvoiceStatus.paid
        elif invoice.paid_amount > 0:
            invoice.status = models.InvoiceStatus.partial

    db.add(payment)

    log_audit(
        db, user.username, "CREATE", "customer_payment",
        f"{payment.payment_no} · {customer.name} · ₹{payment.amount:.2f}",
    )
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/supplier-payments", response_model=list[schemas.SupplierPaymentOut])
def list_supplier_payments(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return db.query(models.SupplierPayment).order_by(
        models.SupplierPayment.payment_date.desc(),
        models.SupplierPayment.payment_no.desc(),
    ).all()


@router.post("/supplier-payments", response_model=schemas.SupplierPaymentOut, status_code=201)
def create_supplier_payment(
    payload: schemas.SupplierPaymentIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    supplier = db.get(models.Party, payload.supplier_id)
    if supplier is None or supplier.kind != "supplier":
        raise HTTPException(status_code=404, detail="Supplier not found")

    po = None
    if payload.purchase_order_id:
        po = db.get(models.PurchaseOrder, payload.purchase_order_id)
        if po is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if po.supplier_id != supplier.id:
            raise HTTPException(status_code=400, detail="Purchase order does not belong to this supplier")

        existing = (
            db.query(models.SupplierPayment)
            .filter(models.SupplierPayment.purchase_order_id == po.id)
            .all()
        )
        allocated = round(sum(p.amount for p in existing), 2)
        remaining = round(po.grand_total - allocated, 2)
        if payload.amount > remaining + 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Payment exceeds purchase order balance of ₹{remaining:.2f}",
            )

    payment = models.SupplierPayment(
        payment_no=_next_payment_no(db, models.SupplierPayment, "SPAY"),
        payment_date=payload.payment_date,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        purchase_order_id=po.id if po else None,
        po_no=po.po_no if po else "",
        amount=round(payload.amount, 2),
        mode=payload.mode,
        reference=payload.reference,
        remarks=payload.remarks,
        created_by=user.username,
    )
    db.add(payment)

    log_audit(
        db, user.username, "CREATE", "supplier_payment",
        f"{payment.payment_no} · {supplier.name} · ₹{payment.amount:.2f}",
    )
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/receivables", response_model=list[schemas.ReceivableOut])
def list_receivables(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    invoices = db.query(models.Invoice).filter(
        models.Invoice.status != models.InvoiceStatus.cancelled
    ).order_by(models.Invoice.invoice_date.desc()).all()

    result = []
    for invoice in invoices:
        paid = round(sum(
            p.amount for p in db.query(models.CustomerPayment).filter(
                models.CustomerPayment.invoice_id == invoice.id
            ).all()
        ), 2)
        balance = round(invoice.grand_total - paid, 2)
        result.append(schemas.ReceivableOut(
            invoice_id=invoice.id,
            invoice_no=invoice.invoice_no,
            invoice_date=invoice.invoice_date,
            customer_id=invoice.customer_id,
            customer_name=invoice.customer_name,
            grand_total=invoice.grand_total,
            paid_amount=paid,
            balance_amount=max(balance, 0),
            status=models.InvoiceStatus.paid if balance <= 0.01 else (
                models.InvoiceStatus.partial if paid > 0 else models.InvoiceStatus.unpaid
            ),
        ))
    return result


@router.get("/payables", response_model=list[schemas.PayableOut])
def list_payables(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    orders = db.query(models.PurchaseOrder).order_by(
        models.PurchaseOrder.po_date.desc()
    ).all()

    result = []
    for po in orders:
        paid = round(sum(
            p.amount for p in db.query(models.SupplierPayment).filter(
                models.SupplierPayment.purchase_order_id == po.id
            ).all()
        ), 2)
        balance = round(po.grand_total - paid, 2)
        result.append(schemas.PayableOut(
            purchase_order_id=po.id,
            po_no=po.po_no,
            po_date=po.po_date,
            supplier_id=po.supplier_id,
            supplier_name=po.supplier_name,
            grand_total=po.grand_total,
            paid_amount=paid,
            balance_amount=max(balance, 0),
            status=po.status,
        ))
    return result


class FinanceAccountIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    account_type: Literal["asset", "liability", "equity", "income", "expense"]
    active: bool = True


class FinanceAccountOut(FinanceAccountIn):
    id: str
    system_account: bool
    created_by: str
    model_config = {"from_attributes": True}


class PayrollAccountMappingIn(BaseModel):
    salary_expense_account_id: str
    salary_payable_account_id: str
    employee_pf_payable_account_id: str
    professional_tax_payable_account_id: str
    tds_payable_account_id: str


class PayrollAccountMappingOut(PayrollAccountMappingIn):
    id: int
    updated_by: str
    model_config = {"from_attributes": True}


class FinanceJournalLineOut(BaseModel):
    id: str
    account_id: str
    description: str
    debit: float
    credit: float
    model_config = {"from_attributes": True}


class FinanceJournalOut(BaseModel):
    id: str
    journal_no: str
    entry_date: date
    narration: str
    source_type: str
    source_id: str
    status: str
    reversal_of_id: str | None
    created_by: str
    lines: list[FinanceJournalLineOut]


@router.get("/accounts", response_model=list[FinanceAccountOut])
def list_finance_accounts(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.FinanceAccount).order_by(models.FinanceAccount.code).all()


@router.post("/accounts", response_model=FinanceAccountOut, status_code=201)
def create_finance_account(payload: FinanceAccountIn, db: Session = Depends(get_db), user: models.User = guard):
    row = models.FinanceAccount(**payload.model_dump(), system_account=False, created_by=user.username)
    db.add(row)
    log_audit(db, user.username, "CREATE", "finance_account", f"{payload.code}; {payload.name}; {payload.account_type}")
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        if "unique" in str(exc).lower():
            raise HTTPException(409, "Finance account code already exists") from exc
        raise
    db.refresh(row)
    return row


@router.get("/payroll-account-mapping", response_model=PayrollAccountMappingOut)
def get_payroll_account_mapping(db: Session = Depends(get_db), user: models.User = guard):
    row = db.get(models.FinancePayrollAccountMapping, 1)
    if row is None:
        raise HTTPException(404, "Payroll account mapping is not configured")
    return row


@router.put("/payroll-account-mapping", response_model=PayrollAccountMappingOut)
def update_payroll_account_mapping(
    payload: PayrollAccountMappingIn, db: Session = Depends(get_db), user: models.User = guard,
):
    values = payload.model_dump()
    ids = list(values.values())
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Each payroll component must map to a distinct ledger account")
    accounts = {row.id: row for row in db.query(models.FinanceAccount).filter(
        models.FinanceAccount.id.in_(ids), models.FinanceAccount.active.is_(True)
    ).all()}
    if len(accounts) != len(ids):
        raise HTTPException(422, "Every mapped account must exist and be active")
    if accounts[values["salary_expense_account_id"]].account_type != "expense":
        raise HTTPException(422, "Salary expense must map to an expense account")
    for key, account_id in values.items():
        if key != "salary_expense_account_id" and accounts[account_id].account_type != "liability":
            raise HTTPException(422, f"{key} must map to a liability account")
    row = db.get(models.FinancePayrollAccountMapping, 1)
    if row is None:
        row = models.FinancePayrollAccountMapping(id=1, **values, updated_by=user.username)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_by = user.username
    log_audit(db, user.username, "UPDATE", "finance_payroll_account_mapping", str(values))
    db.commit()
    db.refresh(row)
    return row


@router.get("/journals", response_model=list[FinanceJournalOut])
def list_finance_journals(
    source_type: str | None = None, db: Session = Depends(get_db), user: models.User = guard,
):
    query = db.query(models.FinanceJournalEntry)
    if source_type:
        query = query.filter(models.FinanceJournalEntry.source_type == source_type)
    entries = query.order_by(
        models.FinanceJournalEntry.entry_date.desc(),
        models.FinanceJournalEntry.created_at.desc(),
    ).limit(500).all()
    result = []
    for entry in entries:
        result.append({
            "id": entry.id, "journal_no": entry.journal_no, "entry_date": entry.entry_date,
            "narration": entry.narration, "source_type": entry.source_type,
            "source_id": entry.source_id, "status": entry.status,
            "reversal_of_id": entry.reversal_of_id, "created_by": entry.created_by,
            "lines": db.query(models.FinanceJournalLine).filter_by(journal_entry_id=entry.id).all(),
        })
    return result
