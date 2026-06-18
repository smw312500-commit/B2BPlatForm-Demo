from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from database import get_db
from models import FabricOrder
from schemas import FabricOrderCreate, FabricOrderOut
from services.platform_reporter import (
    extract_bl_number,
    extract_port_of_discharge,
    extract_port_of_loading,
    report_import,
)

router = APIRouter(prefix="/order", tags=["order"])


@router.get("/", response_model=List[FabricOrderOut])
def get_all_orders(db: Session = Depends(get_db)):
    return db.query(FabricOrder).order_by(FabricOrder.order_date.desc()).all()


@router.get("/active", response_model=List[FabricOrderOut])
def get_active_orders(db: Session = Depends(get_db)):
    return db.query(FabricOrder).filter(FabricOrder.status == "대기중").all()


@router.post("/", response_model=FabricOrderOut, status_code=201)
def create_order(data: FabricOrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    order = FabricOrder(**data.model_dump(), status="대기중")
    db.add(order)
    db.commit()
    db.refresh(order)

    # 라벨agent 표준: BL 기반 발주 등록 시점에 '입고예정' 통지를 플랫폼 보고 채널로 전송
    bl_number = extract_bl_number(order.note)
    if bl_number:
        background_tasks.add_task(
            report_import,
            order.material_name,
            float(order.order_qty),
            order.due_date,
            bl_number,
            order.supplier,
            order.due_date,
            order.note,
            extract_port_of_loading(order.note),
            extract_port_of_discharge(order.note),
            status="입고예정",
        )

    return order


@router.patch("/{order_id}/complete", response_model=FabricOrderOut)
def complete_order(order_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    order = db.query(FabricOrder).filter(FabricOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="발주 내역을 찾을 수 없습니다.")
    if order.status != "대기중":
        raise HTTPException(status_code=400, detail="대기중 상태의 발주만 완료 처리 가능합니다.")
    order.status = "입고완료"
    db.commit()
    db.refresh(order)
    background_tasks.add_task(
        report_import,
        order.material_name,
        float(order.order_qty),
        date.today(),
        extract_bl_number(order.note),
        order.supplier,
        order.due_date,
        order.note,
        extract_port_of_loading(order.note),
        extract_port_of_discharge(order.note),
    )
    return order


@router.patch("/{order_id}/cancel", response_model=FabricOrderOut)
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(FabricOrder).filter(FabricOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="발주 내역을 찾을 수 없습니다.")
    if order.status != "대기중":
        raise HTTPException(status_code=400, detail="대기중 상태의 발주만 취소 가능합니다.")
    order.status = "취소"
    db.commit()
    db.refresh(order)
    return order
