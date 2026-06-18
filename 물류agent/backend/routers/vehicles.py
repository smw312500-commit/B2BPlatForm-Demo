from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Vehicle
from schemas import VehicleCreate, VehicleUpdate, VehicleOut
from services.platform_sync import sync_drivers_to_platform

router = APIRouter()


@router.get("/", response_model=List[VehicleOut])
def get_vehicles(db: Session = Depends(get_db)):
    vehicles = db.query(Vehicle).all()
    result = []
    for v in vehicles:
        item = VehicleOut.from_orm(v)
        if v.driver:
            item.driver_name = v.driver.name
        result.append(item)
    return result


@router.post("/", response_model=VehicleOut)
def create_vehicle(data: VehicleCreate, db: Session = Depends(get_db)):
    vehicle = Vehicle(**data.dict())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    sync_drivers_to_platform(db)
    out = VehicleOut.from_orm(vehicle)
    if vehicle.driver:
        out.driver_name = vehicle.driver.name
    return out


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, data: VehicleUpdate, db: Session = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="차량을 찾을 수 없습니다")
    for key, value in data.dict(exclude_none=True).items():
        setattr(vehicle, key, value)
    db.commit()
    db.refresh(vehicle)
    sync_drivers_to_platform(db)
    out = VehicleOut.from_orm(vehicle)
    if vehicle.driver:
        out.driver_name = vehicle.driver.name
    return out


@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="차량을 찾을 수 없습니다")
    db.delete(vehicle)
    db.commit()
    sync_drivers_to_platform(db)
    return {"message": "삭제 완료"}
