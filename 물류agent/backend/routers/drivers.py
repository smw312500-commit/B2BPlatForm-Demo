from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Driver
from schemas import DriverCreate, DriverUpdate, DriverOut
from services.platform_sync import sync_drivers_to_platform

router = APIRouter()


def _to_driver_out(driver: Driver) -> DriverOut:
    item = DriverOut.from_orm(driver)
    vehicle = None
    if driver.vehicles:
        vehicle = sorted(driver.vehicles, key=lambda current: current.id or 0)[0]

    if vehicle:
        item.vehicle_id = vehicle.id
        item.vehicle_plate = vehicle.plate_no
        item.vehicle_max_weight = float(vehicle.max_weight) if vehicle.max_weight is not None else None
        item.vehicle_type = vehicle.vehicle_type

    return item


@router.get("/", response_model=List[DriverOut])
def get_drivers(db: Session = Depends(get_db)):
    drivers = db.query(Driver).all()
    return [_to_driver_out(driver) for driver in drivers]


@router.post("/", response_model=DriverOut)
def create_driver(data: DriverCreate, db: Session = Depends(get_db)):
    driver = Driver(**data.dict())
    db.add(driver)
    db.commit()
    db.refresh(driver)
    sync_drivers_to_platform(db)
    return _to_driver_out(driver)


@router.put("/{driver_id}", response_model=DriverOut)
def update_driver(driver_id: int, data: DriverUpdate, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다")
    for key, value in data.dict(exclude_none=True).items():
        setattr(driver, key, value)
    db.commit()
    db.refresh(driver)
    sync_drivers_to_platform(db)
    return _to_driver_out(driver)


@router.delete("/{driver_id}")
def delete_driver(driver_id: int, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다")
    db.delete(driver)
    db.commit()
    sync_drivers_to_platform(db)
    return {"message": "삭제 완료"}
