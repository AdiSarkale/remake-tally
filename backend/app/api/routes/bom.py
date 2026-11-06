"""BOM management and recursive multi-level explosion."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db
from app.services.inventory import log_audit
from app.services.bom import explode_bom_tree, validate_bom_graph
router=APIRouter(prefix="/bom",tags=["bom"])
guard=Depends(require_area("masters"))

def _get_bom(bom_id: str,db: Session):
    row=db.query(models.BillOfMaterials).options(selectinload(models.BillOfMaterials.lines)).filter_by(id=bom_id).first()
    if row is None: raise HTTPException(404,"BOM not found")
    return row

@router.get("",response_model=list[schemas.BOMOut])
def list_boms(db:Session=Depends(get_db),user:models.User=guard):
    return db.query(models.BillOfMaterials).options(selectinload(models.BillOfMaterials.lines)).order_by(models.BillOfMaterials.id.desc()).all()

@router.get("/{bom_id}",response_model=schemas.BOMOut)
def get_bom(bom_id:str,db:Session=Depends(get_db),user:models.User=guard): return _get_bom(bom_id,db)

@router.get("/{bom_id}/explode",response_model=schemas.BomExplosionOut)
def explode_bom(bom_id:str,quantity:float=1,db:Session=Depends(get_db),user:models.User=guard):
    if quantity<=0: raise HTTPException(400,"Quantity must be greater than zero")
    bom=_get_bom(bom_id,db)
    lines=explode_bom_tree(db,bom.product_id,quantity)
    available=all(x["status"]=="Available" for x in lines if x["line_type"]=="RM") and all(x["status"]!="Missing BOM" for x in lines)
    return {"bom_id":bom.id,"product_id":bom.product_id,"quantity":quantity,"lines":lines,"raw_materials_available":available}

@router.post("",response_model=schemas.BOMOut,status_code=201)
def post_bom(payload:schemas.BomIn,db:Session=Depends(get_db),user:models.User=guard):
    product=db.get(models.Product,payload.product_id)
    if product is None: raise HTTPException(400,"Product not found")
    if not payload.lines: raise HTTPException(400,"BOM should contain at least one component")
    if db.query(models.BillOfMaterials).filter_by(product_id=payload.product_id,version=payload.version).first(): raise HTTPException(409,"BOM version already exists for this product")
    if payload.scrap_type_id and (db.get(models.ScrapType,payload.scrap_type_id) is None or not db.get(models.ScrapType,payload.scrap_type_id).active): raise HTTPException(400,"Scrap type not found or inactive")
    keys=[(x.material_id,x.subassembly_product_id) for x in payload.lines]
    if len(keys)!=len(set(keys)): raise HTTPException(400,"The same material or subassembly cannot appear twice in a BOM")
    for line in payload.lines:
        if line.material_id and db.get(models.RawMaterial,line.material_id) is None: raise HTTPException(400,f"Material {line.material_id} not found")
        if line.subassembly_product_id and db.get(models.Product,line.subassembly_product_id) is None: raise HTTPException(400,f"Subassembly {line.subassembly_product_id} not found")
    validate_bom_graph(db,payload.product_id,[x.subassembly_product_id for x in payload.lines if x.subassembly_product_id])
    bom=models.BillOfMaterials(product_id=payload.product_id,version=payload.version,active=payload.active,expected_scrap_percent=payload.expected_scrap_percent,scrap_type_id=payload.scrap_type_id)
    for line in payload.lines: bom.lines.append(models.BomLine(material_id=line.material_id,subassembly_product_id=line.subassembly_product_id,line_type="RM" if line.material_id else "SF",quantity=line.quantity))
    if bom.active: db.query(models.BillOfMaterials).filter(models.BillOfMaterials.product_id==payload.product_id,models.BillOfMaterials.active.is_(True)).update({"active":False},synchronize_session=False)
    db.add(bom);log_audit(db,user.username,"CREATE","bom",f"{product.code} v{bom.version}");db.commit();db.refresh(bom);return bom

@router.put("/{bom_id}",response_model=schemas.BOMOut)
def update_bom(bom_id:str,payload:schemas.BomIn,db:Session=Depends(get_db),user:models.User=guard):
    bom=_get_bom(bom_id,db);product=db.get(models.Product,payload.product_id)
    if product is None: raise HTTPException(400,"Product not found")
    if not payload.lines: raise HTTPException(400,"BOM must contain at least one component")
    if db.query(models.BillOfMaterials).filter(models.BillOfMaterials.product_id==payload.product_id,models.BillOfMaterials.version==payload.version,models.BillOfMaterials.id!=bom_id).first(): raise HTTPException(409,"BOM version already exists")
    keys=[(x.material_id,x.subassembly_product_id) for x in payload.lines]
    if len(keys)!=len(set(keys)): raise HTTPException(400,"The same material or subassembly cannot appear twice in a BOM")
    for line in payload.lines:
        if line.material_id and db.get(models.RawMaterial,line.material_id) is None: raise HTTPException(400,f"Material {line.material_id} not found")
        if line.subassembly_product_id and db.get(models.Product,line.subassembly_product_id) is None: raise HTTPException(400,f"Subassembly {line.subassembly_product_id} not found")
    validate_bom_graph(db,payload.product_id,[x.subassembly_product_id for x in payload.lines if x.subassembly_product_id])
    bom.product_id=payload.product_id;bom.version=payload.version;bom.active=payload.active;bom.expected_scrap_percent=payload.expected_scrap_percent;bom.scrap_type_id=payload.scrap_type_id;bom.lines.clear()
    for line in payload.lines: bom.lines.append(models.BomLine(material_id=line.material_id,subassembly_product_id=line.subassembly_product_id,line_type="RM" if line.material_id else "SF",quantity=line.quantity))
    if bom.active: db.query(models.BillOfMaterials).filter(models.BillOfMaterials.product_id==payload.product_id,models.BillOfMaterials.active.is_(True),models.BillOfMaterials.id!=bom.id).update({"active":False},synchronize_session=False)
    log_audit(db,user.username,"UPDATE","bom",f"Product {product.code} v{bom.version}");db.commit();db.refresh(bom);return bom

@router.delete("/{bom_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_bom(bom_id:str,db:Session=Depends(get_db),user:models.User=guard):
    bom=_get_bom(bom_id,db);product=db.get(models.Product,bom.product_id);log_audit(db,user.username,"DELETE","bom",f"{product.code if product else bom.product_id} v{bom.version}");db.delete(bom);db.commit()
