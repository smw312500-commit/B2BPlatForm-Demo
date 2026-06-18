from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from database import get_db
from models import FabricProduction
from schemas import FabricProductionCreate, FabricProductionOut, FabricProductionStageUpdate, IncidentReport
from services.platform_reporter import report_schedule, report_reschedule

router = APIRouter(prefix="/production", tags=["production"])

VALID_FABRIC_CODES = {"C", "P", "L", "W", "M"}
VALID_COLOR_CODES = {"BK", "WH", "NV", "GY", "BE", "RD"}
STAGES = ["원사입고", "정경·제직", "염색", "가공", "검품", "완성"]


@router.get("/", response_model=List[FabricProductionOut])
def get_all(db: Session = Depends(get_db)):
    return db.query(FabricProduction).order_by(FabricProduction.target_date).all()


@router.post("/", response_model=FabricProductionOut, status_code=201)
def create(data: FabricProductionCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if data.fabric_code.upper() not in VALID_FABRIC_CODES:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 원단코드: {data.fabric_code}")
    if data.color_code.upper() not in VALID_COLOR_CODES:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 컬러코드: {data.color_code}")
    item = FabricProduction(
        fabric_code=data.fabric_code.upper(),
        color_code=data.color_code.upper(),
        quantity=data.quantity,
        stage=data.stage if data.stage in STAGES else "원사입고",
        target_date=data.target_date,
        worker=data.worker,
        note=data.note,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    background_tasks.add_task(
        report_schedule,
        item.fabric_code, item.color_code, float(item.quantity), item.target_date,
    )
    return item


@router.patch("/{prod_id}/stage", response_model=FabricProductionOut)
def advance_stage(prod_id: int, data: FabricProductionStageUpdate, db: Session = Depends(get_db)):
    item = db.query(FabricProduction).filter(FabricProduction.id == prod_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="생산 항목을 찾을 수 없습니다.")
    if data.stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 단계: {data.stage}")
    item.stage = data.stage
    if data.stage == "완성":
        try:
            item.completed_at = datetime.now()
        except Exception:
            pass
    db.commit()
    db.refresh(item)
    return item


@router.post("/{prod_id}/incident")
def report_incident(prod_id: int, body: IncidentReport, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """돌발상황(기계고장/불량 등) 발생 시 플랫폼에 재스케줄 보고"""
    item = db.query(FabricProduction).filter(FabricProduction.id == prod_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="생산 항목을 찾을 수 없습니다.")
    background_tasks.add_task(
        report_reschedule,
        prod_id,
        body.reason,
        body.new_estimated_completion,
    )
    return {"reported": True, "production_id": prod_id, "reason": body.reason}


@router.get("/completed", response_model=List[FabricProductionOut])
def get_completed(db: Session = Depends(get_db)):
    return (
        db.query(FabricProduction)
        .filter(FabricProduction.stage == "완성")
        .order_by(FabricProduction.updated_at.desc())
        .all()
    )


@router.delete("/{prod_id}", status_code=204)
def delete(prod_id: int, db: Session = Depends(get_db)):
    item = db.query(FabricProduction).filter(FabricProduction.id == prod_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="생산 항목을 찾을 수 없습니다.")
    db.delete(item)
    db.commit()
