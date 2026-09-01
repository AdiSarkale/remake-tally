from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload


from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit


router = APIRouter(prefix='/bom', tags=['bom'])
guard = Depends(require_area('masters'))


def _get_bom(bom_id: str,db: Session) -> models.BillOfMaterials:
    bom = (
        db.query(models.BillOfMaterials)
        .options(selectinload(models.BillOfMaterials.lines))
        .filter(models.BillOfMaterials.id == bom_id)
        .first()
        )

    if bom is None:
        raise HTTPException(
            status_code=404,
            detail='BOM not found')

    return bom


@router.get('',response_model=list[schemas.BOMOut])
def list_boms(db: Session = Depends(get_db), user: models.User = guard):

    return (
        db.query(models.BillOfMaterials)
        .options(selectinload(models.BillOfMaterials.lines))
        .order_by(models.BillOfMaterials.id.desc())
        .all()
        )


@router.get('/{bom_id}',response_model=schemas.BOMOut)
def get_bom(bom_id: str,db: Session = Depends(get_db), user:models.User = guard):
    return _get_bom(bom_id=bom_id, db=db)


@router.post('',response_model=schemas.BOMOut)
def post_bom(payload: schemas.BomIn,
             db: Session = Depends(get_db),
             user: models.User = guard):

    product = db.get(models.Product,payload.product_id)
    if product is None:
        raise HTTPException(
            status_code=400,
            detail='Product not found')

    if not payload.lines:
        raise HTTPException(
            status_code=400,
            detail='BOM should contain atleast one material')

    existing = (
        db.query(models.BillOfMaterials)
        .filter(
            models.BillOfMaterials.product_id == payload.product_id,
            models.BillOfMaterials.version == payload.version)
        .first()
        )

    if existing:
        raise HTTPException(
            status_code=409,
            detail='BOM Version already exist from this product')

    material_ids = [line.material_id  for line in payload.lines]

    if len(material_ids) != len(set(material_ids)):
        raise HTTPException(status_code=400, detail='Same material cannot appear in twice in a BOM')

    bom = models.BillOfMaterials(
        product_id = payload.product_id,
        version = payload.version,
        active = payload.active,
    expected_scrap_percent=payload.expected_scrap_percent,
    scrap_type_id=payload.scrap_type_id,)

    for line in payload.lines:
        material = db.get(models.RawMaterial, line.material_id)

        if material is None:
            raise HTTPException(status_code=400, detail=f'Material f{line.material_id} not found')


        bom.lines.append(
            models.BomLine(
                material_id = material.id,
                quantity = line.quantity
                ))

    db.add(bom)

    log_audit(
        db,
        user.username,
        "CREATE",
        'bom',
        f'{product.code} v{bom.version}'
        )

    db.commit()
    db.refresh(bom)

    return bom


@router.put('/{bom_id}',response_model=schemas.BOMOut)
def update_bom(
    bom_id: str,
    payload: schemas.BomIn,
    db: Session = Depends(get_db),
    user: models.User = guard
    ):

    bom = _get_bom(bom_id,db)

    product = db.get(models.Product, payload.product_id)

    if product is None:
        raise HTTPException(status_code=400, detail='Product not found')

    if not payload.lines:
        raise HTTPException(status_code=400,detail='BOM must contain at least one material')

    material_ids = [line.material_id for line in payload.lines]
    if len(material_ids) != len(set(material_ids)):
        raise HTTPException(
            status_code=400,
            detail="The same material cannot appear twice in a BOM",
        )

    duplicate = (
        db.query(models.BillOfMaterials)
        .filter(models.BillOfMaterials.product_id == payload.product_id,
                models.BillOfMaterials.version == payload.version,
                models.BillOfMaterials.id != bom_id
                ).first()
        )

    if duplicate:
        raise HTTPException(
            status_code=400,
            detail='BOM version already exists for this product')

    bom.product_id = payload.product_id
    bom.version = payload.version
    bom.active = payload.active
    bom.expected_scrap_percent=payload.expected_scrap_percent
    bom.scrap_type_id=payload.scrap_type_id

    bom.lines.clear()

    for line in payload.lines:
        material = db.get(models.RawMaterial, line.material_id)

        if material is None:
            raise HTTPException(
                status_code=400,
                detail=f"Material {line.material_id} not found",
            )

        bom.lines.append(
            models.BomLine(
                material_id=line.material_id,
                quantity=line.quantity,
            )
        )

    log_audit(
        db,
        user.username,
        "UPDATE",
        "bom",
        f"Product {product.code} v{bom.version}",
    )

    db.commit()
    db.refresh(bom)
    return bom


@router.delete('/{bom_id}',status_code=status.HTTP_204_NO_CONTENT)
def delete_bom(
    bom_id: str,
    db: Session =  Depends(get_db),
    user:  models.User = guard):

    bom = _get_bom(bom_id, db)

    product = db.get(models.Product, bom.product_id)

    log_audit(
        db,
        user.username,
        'DELETE',
        'bom',
        f'{product.code if  product else bom.product_id} v{bom.version}')

    db.delete(bom)
    db.commit()
