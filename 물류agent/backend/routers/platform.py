from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Delivery
from schemas import PlatformChannelOut, PlatformSignal
from services.platform_channel import CHANNEL_NAME, list_channel_messages, log_signal_received
from services.platform_sync import sync_drivers_to_platform

router = APIRouter()


@router.post("/signal")
def receive_signal(signal: PlatformSignal, db: Session = Depends(get_db)):
    """플랫폼 → 물류: 플랫폼 신호 수신 → delivery 자동 생성"""
    delivery = Delivery(
        company_id   = signal.company_id,
        company_name = signal.company_name,
        origin_si    = signal.origin_si,
        origin_gu    = signal.origin_gu,
        destination  = signal.destination or "인천항",
        cargo_detail = signal.cargo_detail or signal.item or signal.label_code,
        weight_kg    = signal.weight_kg,
        due_date     = signal.due_date,
        pickup_date  = signal.pickup_date,
        status       = "배차대기",
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    log_signal_received(db, signal, delivery.id)
    return {"message": "화물 등록 완료", "delivery_id": delivery.id}


@router.get("/status")
def dispatch_status(db: Session = Depends(get_db)):
    """물류 → 플랫폼: 현재 배차 현황 제공"""
    deliveries = db.query(Delivery).all()
    return [
        {
            "delivery_id":   d.id,
            "company_id":    d.company_id,
            "destination":   d.destination,
            "status":        d.status,
            "pickup_date":   str(d.pickup_date)   if d.pickup_date   else None,
            "complete_date": str(d.complete_date) if d.complete_date else None,
        }
        for d in deliveries
    ]


@router.get("/channel", response_model=PlatformChannelOut)
def platform_channel(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    return {
        "channel": CHANNEL_NAME,
        "messages": list_channel_messages(db, limit=limit),
    }


@router.post("/drivers/sync")
def sync_driver_channel(db: Session = Depends(get_db)):
    return sync_drivers_to_platform(db)
