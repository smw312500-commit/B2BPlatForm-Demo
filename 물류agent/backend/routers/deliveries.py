from datetime import date
import os
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Delivery, Driver, Vehicle
from schemas import DeliveryCreate, DeliveryOut
from services.dispatch_logic import calc_pickup_date, check_round_trip, get_travel_hours, get_travel_label
from services.platform_channel import log_completion_report, log_dispatch_confirmed, log_round_trip_result
from services.platform_sync import sync_drivers_to_platform

router = APIRouter()

PLATFORM_API_URL = os.getenv("PLATFORM_API_URL", "http://localhost:8000")


def _enrich(delivery: Delivery) -> DeliveryOut:
    out = DeliveryOut.from_orm(delivery)
    if delivery.driver:
        out.driver_name = delivery.driver.name
    if delivery.vehicle:
        out.vehicle_plate = delivery.vehicle.plate_no
    return out


@router.get("/", response_model=List[DeliveryOut])
def get_deliveries(db: Session = Depends(get_db)):
    deliveries = db.query(Delivery).order_by(Delivery.due_date).all()
    return [_enrich(delivery) for delivery in deliveries]


@router.post("/", response_model=DeliveryOut)
def create_delivery(data: DeliveryCreate, db: Session = Depends(get_db)):
    delivery = Delivery(**data.dict())
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return _enrich(delivery)


@router.post("/{delivery_id}/complete")
def complete_delivery(delivery_id: int, db: Session = Depends(get_db)):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="배송 건을 찾을 수 없습니다")

    delivery.status = "완료"
    delivery.complete_date = date.today()

    if delivery.driver:
        delivery.driver.status = "가용"
        delivery.driver.location_si = _destination_to_si(delivery.destination)

    db.commit()
    db.refresh(delivery)

    delivered_to_platform = _notify_platform_complete(delivery)
    log_completion_report(db, delivery, delivered_to_platform)
    sync_drivers_to_platform(db)

    return {"message": "배송 완료 처리됨", "delivery_id": delivery_id}


def _destination_to_si(destination: str) -> str:
    mapping = {
        "인천항": "인천시",
        "부산항": "부산시",
    }
    return mapping.get(destination, "")


def _notify_platform_complete(delivery: Delivery) -> bool:
    try:
        payload = {
            "delivery_id": delivery.id,
            "company_id": delivery.company_id,
            "destination": delivery.destination,
            "complete_date": str(delivery.complete_date),
            "status": "완료",
        }
        with httpx.Client(timeout=5) as client:
            response = client.post(f"{PLATFORM_API_URL}/api/logistics/complete", json=payload)
            response.raise_for_status()
        return True
    except Exception:
        return False


@router.put("/{delivery_id}/assign")
def assign_driver(
    delivery_id: int,
    driver_id: int,
    vehicle_id: int | None = None,
    vehicle_plate: str | None = None,
    pickup_date: date | None = None,
    empty_return: str | None = None,
    db: Session = Depends(get_db),
):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="배송 건을 찾을 수 없습니다")

    previous_driver = delivery.driver if delivery.driver_id and delivery.driver_id != driver_id else None

    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다")
    if not delivery.due_date and not pickup_date:
        raise HTTPException(status_code=400, detail="납기일 또는 픽업일이 필요합니다")

    resolved_pickup_date = pickup_date or calc_pickup_date(
        delivery.due_date,
        delivery.destination,
        delivery.origin_si,
    )
    same_day_assignment = (
        db.query(Delivery)
        .filter(
            Delivery.id != delivery.id,
            Delivery.driver_id == driver.id,
            Delivery.pickup_date == resolved_pickup_date,
            Delivery.status != "완료",
        )
        .first()
    )
    if same_day_assignment:
        raise HTTPException(status_code=400, detail="같은 픽업일에 이미 배정된 기사입니다")
    if driver.status == "휴무":
        raise HTTPException(status_code=400, detail="휴무 상태 기사는 배정할 수 없습니다")
    if driver.status != "가용" and delivery.driver_id != driver.id and resolved_pickup_date <= date.today():
        raise HTTPException(status_code=400, detail="가용 상태 기사만 배정할 수 있습니다")

    vehicle = None
    if vehicle_id is not None:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    elif vehicle_plate:
        vehicle = db.query(Vehicle).filter(Vehicle.plate_no == vehicle_plate).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="차량을 찾을 수 없습니다")
    if vehicle.driver_id != driver.id:
        raise HTTPException(status_code=400, detail="선택한 기사와 차량이 연결되어 있지 않습니다")
    if empty_return:
        round_trip = empty_return
    else:
        all_deliveries = db.query(Delivery).all()
        round_trip = check_round_trip(delivery, all_deliveries)
    travel_label = get_travel_label(get_travel_hours(delivery.origin_si, delivery.destination))

    if previous_driver:
        previous_driver.status = "가용"

    delivery.driver_id = driver_id
    delivery.vehicle_id = vehicle.id
    delivery.pickup_date = resolved_pickup_date
    delivery.status = "배차대기"
    delivery.empty_return = round_trip
    driver.status = "운행중" if resolved_pickup_date <= date.today() else "가용"

    db.commit()
    db.refresh(delivery)
    log_dispatch_confirmed(db, delivery, driver, vehicle, resolved_pickup_date, travel_label)
    log_round_trip_result(db, delivery)
    sync_drivers_to_platform(db)
    return _enrich(delivery)
