"""Recursive BOM explosion helpers with cycle and missing-BOM detection."""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import models

def _active_bom(db:Session,product_id:str):
 return db.query(models.BillOfMaterials).filter_by(product_id=product_id,active=True).order_by(models.BillOfMaterials.version.desc()).first()

def validate_bom_graph(db:Session,parent_product_id:str,child_product_ids:list[str]):
 def reaches(current:str,target:str,seen:set[str]):
  if current==target:return True
  if current in seen:return False
  seen.add(current);bom=_active_bom(db,current)
  if not bom:return False
  return any(line.subassembly_product_id and reaches(line.subassembly_product_id,target,seen) for line in bom.lines)
 for child in child_product_ids:
  if child==parent_product_id or reaches(child,parent_product_id,set()):
   raise HTTPException(400,"BOM subassembly relationship would create a circular dependency")

def explode_bom_tree(db:Session,product_id:str,quantity:float,*,strict:bool=False):
 rows=[]
 def walk(pid:str,qty:float,level:int,path:tuple[str,...]):
  if pid in path: raise HTTPException(409,"Circular BOM dependency detected: "+" -> ".join((*path,pid)))
  if level>12: raise HTTPException(409,"BOM nesting exceeds the supported depth of 12")
  bom=_active_bom(db,pid)
  if bom is None:
   if strict: raise HTTPException(409,f"Active BOM missing for subassembly product {pid}")
   return
  for line in bom.lines:
   required=round(float(line.quantity)*qty,3)
   if line.material_id:
    material=db.get(models.RawMaterial,line.material_id)
    if material is None: raise HTTPException(409,f"BOM material {line.material_id} no longer exists")
    rows.append({"line_type":"RM","item_id":material.id,"item_code":material.code,"item_name":material.name,"unit":material.unit,"required_quantity":required,"level":level+1,"parent_product_id":pid,"status":"Available" if material.stock>=required else "Shortage"})
   elif line.subassembly_product_id:
    child=db.get(models.Product,line.subassembly_product_id)
    if child is None: raise HTTPException(409,f"BOM subassembly {line.subassembly_product_id} no longer exists")
    child_bom=_active_bom(db,child.id)
    rows.append({"line_type":"SF","item_id":child.id,"item_code":child.code,"item_name":child.name,"unit":child.unit,"required_quantity":required,"level":level+1,"parent_product_id":pid,"status":"Exploded" if child_bom else "Missing BOM"})
    if child_bom: walk(child.id,required,level+1,(*path,pid))
 walk(product_id,quantity,0,())
 totals={}
 for row in rows:
  if row["line_type"]=="RM": totals[row["item_id"]]=round(totals.get(row["item_id"],0.0)+row["required_quantity"],3)
 for material_id,total in totals.items():
  material=db.get(models.RawMaterial,material_id)
  for row in rows:
   if row["line_type"]=="RM" and row["item_id"]==material_id:
    row["status"]="Available" if material and material.stock>=total else "Shortage"
 return rows

def explode_material_requirements(db:Session,product_id:str,quantity:float):
 rows=explode_bom_tree(db,product_id,quantity,strict=True)
 missing=[row for row in rows if row["line_type"]=="SF" and row["status"]=="Missing BOM"]
 if missing: raise HTTPException(409,"Active BOM missing for subassembly product(s): "+", ".join(row["item_code"] for row in missing))
 totals={}
 for row in rows:
  if row["line_type"]=="RM": totals[row["item_id"]]=round(totals.get(row["item_id"],0.0)+row["required_quantity"],3)
 return totals
