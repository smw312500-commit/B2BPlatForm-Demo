from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
import os
from database import get_db
from models import Delivery, Driver, Vehicle
from schemas import AIDispatchResult
from services.dispatch_logic import (
    calc_pickup_date,
    check_round_trip,
    get_travel_hours,
    get_travel_label,
    select_best_driver,
)
from services.platform_channel import (
    log_dispatch_confirmed,
    log_dispatch_review,
    log_round_trip_result,
)
from services.platform_sync import sync_drivers_to_platform

router = APIRouter()


def get_openai_client():
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key)


@router.post("/dispatch/{delivery_id}", response_model=AIDispatchResult)
def auto_dispatch(delivery_id: int, db: Session = Depends(get_db)):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="배송 건을 찾을 수 없습니다")

    if not delivery.due_date:
        raise HTTPException(status_code=400, detail="납기일이 없는 배송 건은 자동 배차할 수 없습니다")

    drivers       = db.query(Driver).all()
    all_deliveries = db.query(Delivery).all()

    pickup_date  = calc_pickup_date(delivery.due_date, delivery.destination, delivery.origin_si)
    best_driver  = select_best_driver(delivery, drivers)
    round_trip   = check_round_trip(delivery, all_deliveries)
    hours        = get_travel_hours(delivery.origin_si, delivery.destination)
    travel_label = get_travel_label(hours)
    log_dispatch_review(db, delivery, pickup_date, travel_label)

    if best_driver:
        vehicle = db.query(Vehicle).filter(Vehicle.driver_id == best_driver.id).first()
        delivery.driver_id    = best_driver.id
        delivery.vehicle_id   = vehicle.id if vehicle else None
        delivery.pickup_date  = pickup_date
        delivery.empty_return = round_trip
        delivery.status       = "배차대기"
        best_driver.status    = "운행중"
        db.commit()
        db.refresh(delivery)
        log_dispatch_confirmed(db, delivery, best_driver, vehicle, pickup_date, travel_label)
        log_round_trip_result(db, delivery)
        sync_drivers_to_platform(db)

        return AIDispatchResult(
            delivery_id = delivery.id,
            driver_id   = best_driver.id,
            driver_name = best_driver.name,
            pickup_date = pickup_date,
            round_trip  = round_trip,
            message     = f"{best_driver.name} 배차 완료. 픽업일: {pickup_date} ({travel_label})",
        )

    return AIDispatchResult(
        delivery_id = delivery.id,
        driver_id   = None,
        driver_name = None,
        pickup_date = pickup_date,
        round_trip  = round_trip,
        message     = "가용 기사 없음. 수동 배차 필요.",
    )


@router.get("/panel")
def get_ai_panel(db: Session = Depends(get_db)):
    today      = date.today()
    deliveries = db.query(Delivery).filter(Delivery.status != "완료").all()

    messages = []

    for d in deliveries:
        if d.due_date and (d.due_date - today).days < 0:
            messages.append({
                "type": "error", "icon": "❌",
                "text": f"납기 불가 [{d.company_name or ''}] {d.destination} 납기일 초과",
            })

    for d in deliveries:
        if d.due_date and (d.due_date - today).days == 1:
            messages.append({
                "type": "warning", "icon": "⚠",
                "text": f"납기 D-1 [{d.company_name or ''}] {d.destination} 즉시 배차 필요",
            })

    for d in [x for x in deliveries if x.pickup_date == today]:
        driver_name  = d.driver.name if d.driver else "미배차"
        travel_label = get_travel_label(get_travel_hours(d.origin_si, d.destination))
        messages.append({
            "type": "info", "icon": "▶",
            "text": f"오늘 배차 {driver_name} → {d.origin_si} 픽업 → {d.destination} ({travel_label})",
        })

    for d in [x for x in deliveries if x.empty_return and "연결완료" in x.empty_return]:
        messages.append({
            "type": "success", "icon": "🔄",
            "text": f"왕복 연결 {d.empty_return}",
        })

    if not messages:
        messages.append({
            "type": "success", "icon": "✅",
            "text": "정상 운행 중. 특이사항 없음.",
        })

    drivers = db.query(Driver).all()
    driver_panels = []
    for driver in drivers:
        driver_deliveries = [d for d in deliveries if d.driver_id == driver.id]
        driver_panels.append({
            "driver_id":   driver.id,
            "driver_name": driver.name,
            "status":      driver.status,
            "today_jobs": [
                {
                    "id":          d.id,
                    "destination": d.destination,
                    "pickup_date": str(d.pickup_date) if d.pickup_date else None,
                    "due_date":    str(d.due_date)    if d.due_date    else None,
                    "status":      d.status,
                    "travel":      get_travel_label(get_travel_hours(d.origin_si, d.destination)),
                }
                for d in driver_deliveries
            ],
        })

    return {"messages": messages, "driver_panels": driver_panels}
