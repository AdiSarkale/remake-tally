"""Plants and warehouses API."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import require_area
from app.db.session import get_db

router = APIRouter(prefix="/locations", tags=["locations"])
guard = Depends(require_area("masters"))


@router.get("/plants", response_model=list[schemas.PlantOut])
def list_plants(db: Session = Depends(get_db), user: models.User = guard):
    return db.query(models.Plant).filter(models.Plant.active.is_(True)).order_by(models.Plant.name).all()


@router.get("/warehouses", response_model=list[schemas.WarehouseOut])
def list_warehouses(
    plant_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = guard,
):
    query = db.query(models.Warehouse).filter(models.Warehouse.active.is_(True))
    if plant_id:
        query = query.filter(models.Warehouse.plant_id == plant_id)
    return query.order_by(models.Warehouse.name).all()
