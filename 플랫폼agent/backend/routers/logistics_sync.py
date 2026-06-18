"""
물류agent → 플랫폼 기사 목록 동기화
- POST /api/logistics/drivers/sync
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import LogisticsDriverCache
from schemas import LogisticsDriverSyncIn

router = APIRouter()


def _to_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@router.post("/logistics/drivers/sync")
def sync_drivers(body: LogisticsDriverSyncIn, db: Session = Depends(get_db)):
    for item in body.drivers:
        record = (
            db.query(LogisticsDriverCache)
            .filter(LogisticsDriverCache.driver_id == item.driver_id)
            .first()
        )
        if not record:
            record = LogisticsDriverCache(driver_id=item.driver_id)
            db.add(record)

        record.name = item.name
        record.phone = item.phone
        record.location_si = item.location_si
        record.location_gu = item.location_gu
        record.base_region = item.base_region
        record.vehicle_type = item.vehicle_type
        record.vehicle_id = item.vehicle_id
        record.vehicle_plate = item.vehicle_plate
        record.vehicle_max_weight = item.vehicle_max_weight
        record.status = item.status
        record.current_delivery_id = item.current_delivery_id
        record.current_destination = item.current_destination
        record.estimated_arrival = _to_date(item.estimated_arrival)
        record.last_synced_at = datetime.now()

    db.commit()
    return {"message": "기사 목록 동기화 완료", "count": len(body.drivers)}
