"""Core domain Pydantic schemas."""

from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules._base import Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    full_name: str

class UserOut(ORMModel):
    id: str
    username: str
    full_name: str
    role: Role
    email: str = ""
    active: bool = True

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)
    email: str = ""
    role: Role = Role.operator
    password: str = Field(min_length=6, max_length=128)
    active: bool = True

class UserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = ""
    role: Role
    active: bool = True

class PasswordReset(BaseModel):
    """Admin reset — the target user's current password is NOT required."""

    new_password: str = Field(min_length=6, max_length=128)

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


# ---------- Masters ----------

class PartyIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    gst_number: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""

class PartyOut(PartyIn, ORMModel):
    id: str
    kind: str

class ProductIn(BaseModel):
    code: str
    name: str
    unit: str = "PCS"
    hsn: str = ""
    cost_price: float = 0
    selling_price: float = 0
    gst_rate: float = 18
    min_stock: float = 0

class ProductOut(ProductIn, ORMModel):
    id: str
    stock: float

class RawMaterialIn(BaseModel):
    name: str
    code: str
    unit: str = "KG"
    cost: float = 0
    min_stock: float = 0

class RawMaterialOut(RawMaterialIn, ORMModel):
    id: str
    stock: float

class ScrapTypeIn(BaseModel):
    code: str
    name: str
    unit: str = "KG"
    selling_rate: float = 0
    min_stock: float = 0
    active: bool = True

class ScrapTypeOut(ScrapTypeIn, ORMModel):
    id: str
    code: str
    name: str
    unit: str
    stock: float
    min_stock: float
    selling_rate: float
    active: bool

class AuditOut(ORMModel):
    id: str
    at: datetime
    username: str
    action: str
    entity: str
    detail: str

class SettingsIn(BaseModel):
    name: str
    gst_number: str | None = None
    address: str | None = None
    invoice_prefix: str = "INV"
    financial_year: str = "2026-2027"

class SettingsOut(SettingsIn, ORMModel):
    id: int


# ---------- Sales invoices ----------
# ---------- Sales invoices ----------
