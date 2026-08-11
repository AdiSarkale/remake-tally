"""Master data CRUD: customers, suppliers, products, raw materials, scrap types."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit

router = APIRouter(prefix="/masters", tags=["masters"])
guard = Depends(require_area("masters"))


def _get_or_404(db: Session, model, pk: str):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return obj


# ---------------- Customers ----------------


@router.get("/customers", response_model=list[schemas.PartyOut])
def list_customers(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.Party)
        .filter(models.Party.kind == "customer")
        .order_by(models.Party.name)
        .all()
    )


@router.post(
    "/customers",
    response_model=schemas.PartyOut,
    status_code=201,
)
def create_customer(
    payload: schemas.PartyIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    party = models.Party(
        kind="customer",
        **payload.model_dump(),
    )

    db.add(party)

    log_audit(
        db,
        user.username,
        "CREATE",
        "customer",
        party.name,
    )

    db.commit()
    db.refresh(party)

    return party


@router.put(
    "/customers/{party_id}",
    response_model=schemas.PartyOut,
)
def update_customer(
    party_id: str,
    payload: schemas.PartyIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    party = _get_or_404(db, models.Party, party_id)

    if party.kind != "customer":
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    for field, value in payload.model_dump().items():
        setattr(party, field, value)

    log_audit(
        db,
        user.username,
        "UPDATE",
        "customer",
        party.name,
    )

    db.commit()
    db.refresh(party)

    return party


@router.delete(
    "/customers/{party_id}",
    status_code=204,
)
def delete_customer(
    party_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    party = _get_or_404(db, models.Party, party_id)

    if party.kind != "customer":
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    log_audit(
        db,
        user.username,
        "DELETE",
        "customer",
        party.name,
    )

    db.delete(party)
    db.commit()


# ---------------- Suppliers ----------------


@router.get("/suppliers", response_model=list[schemas.PartyOut])
def list_suppliers(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.Party)
        .filter(models.Party.kind == "supplier")
        .order_by(models.Party.name)
        .all()
    )


@router.post(
    "/suppliers",
    response_model=schemas.PartyOut,
    status_code=201,
)
def create_supplier(
    payload: schemas.PartyIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    party = models.Party(
        kind="supplier",
        **payload.model_dump(),
    )

    db.add(party)

    log_audit(
        db,
        user.username,
        "CREATE",
        "supplier",
        party.name,
    )

    db.commit()
    db.refresh(party)

    return party


@router.put(
    "/suppliers/{party_id}",
    response_model=schemas.PartyOut,
)
def update_supplier(
    party_id: str,
    payload: schemas.PartyIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    party = _get_or_404(db, models.Party, party_id)

    if party.kind != "supplier":
        raise HTTPException(
            status_code=404,
            detail="Supplier not found",
        )

    for field, value in payload.model_dump().items():
        setattr(party, field, value)

    log_audit(
        db,
        user.username,
        "UPDATE",
        "supplier",
        party.name,
    )

    db.commit()
    db.refresh(party)

    return party


@router.delete(
    "/suppliers/{party_id}",
    status_code=204,
)
def delete_supplier(
    party_id: str,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    party = _get_or_404(db, models.Party, party_id)

    if party.kind != "supplier":
        raise HTTPException(
            status_code=404,
            detail="Supplier not found",
        )

    log_audit(
        db,
        user.username,
        "DELETE",
        "supplier",
        party.name,
    )

    db.delete(party)
    db.commit()


# ---------------- Products ----------------


@router.get(
    "/products",
    response_model=list[schemas.ProductOut],
)
def list_products(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.Product)
        .order_by(models.Product.code)
        .all()
    )


@router.post(
    "/products",
    response_model=schemas.ProductOut,
    status_code=201,
)
def create_product(
    payload: schemas.ProductIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    if (
        db.query(models.Product)
        .filter(models.Product.code == payload.code)
        .first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Product code already exists",
        )

    product = models.Product(**payload.model_dump())

    db.add(product)

    log_audit(
        db,
        user.username,
        "CREATE",
        "product",
        product.name,
    )

    db.commit()
    db.refresh(product)

    return product


@router.put(
    "/products/{product_id}",
    response_model=schemas.ProductOut,
)
def update_product(
    product_id: str,
    payload: schemas.ProductIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    product = _get_or_404(
        db,
        models.Product,
        product_id,
    )

    for field, value in payload.model_dump().items():
        setattr(product, field, value)

    log_audit(
        db,
        user.username,
        "UPDATE",
        "product",
        product.name,
    )

    db.commit()
    db.refresh(product)

    return product


# ---------------- Raw materials ----------------


@router.get(
    "/materials",
    response_model=list[schemas.RawMaterialOut],
)
def list_materials(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.RawMaterial)
        .order_by(models.RawMaterial.name)
        .all()
    )


@router.post(
    "/materials",
    response_model=schemas.RawMaterialOut,
    status_code=201,
)
def create_material(
    payload: schemas.RawMaterialIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    material = models.RawMaterial(
        **payload.model_dump()
    )

    db.add(material)

    log_audit(
        db,
        user.username,
        "CREATE",
        "material",
        material.name,
    )

    db.commit()
    db.refresh(material)

    return material


# ---------------- Scrap types ----------------


@router.get(
    "/scrap-types",
    response_model=list[schemas.ScrapTypeOut],
)
def list_scrap_types(
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    return (
        db.query(models.ScrapType)
        .order_by(models.ScrapType.name)
        .all()
    )


@router.post(
    "/scrap-types",
    response_model=schemas.ScrapTypeOut,
    status_code=201,
)
def create_scrap_type(
    payload: schemas.ScrapTypeIn,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    scrap_type = models.ScrapType(
        **payload.model_dump()
    )

    db.add(scrap_type)

    log_audit(
        db,
        user.username,
        "CREATE",
        "scrap_type",
        scrap_type.name,
    )

    db.commit()
    db.refresh(scrap_type)

    return scrap_type
