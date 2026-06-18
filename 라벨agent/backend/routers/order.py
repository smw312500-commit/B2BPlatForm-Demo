from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import LabelOrder, LabelStock
from schemas import LabelOrderCreate, LabelOrderOut
from services.material_names import normalize_material_name
from services.platform_reporter import report_import
from services.shipment_logic import extract_bl_number, extract_port_of_discharge, extract_port_of_loading

router = APIRouter(prefix="/orders", tags=["발주"])


@router.get("/", response_model=list[LabelOrderOut])
def get_orders(db: Session = Depends(get_db)):
    return db.query(LabelOrder).order_by(LabelOrder.order_date.desc()).all()


@router.post("/", response_model=LabelOrderOut)
def create_order(body: LabelOrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    order = LabelOrder(
        material_name=body.material_name,
        order_qty=body.order_qty,
        supplier=body.supplier,
        order_date=body.order_date,
        due_date=body.due_date,
        note=body.note,
        status="대기중",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

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


@router.patch("/{order_id}/receive", response_model=LabelOrderOut)
def receive_order(order_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """입고 완료 처리: 발주 수량을 재고에 반영하고 플랫폼에 BL 포함 입고 보고."""
    order = db.query(LabelOrder).filter(LabelOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="발주를 찾을 수 없습니다")
    if order.status != "대기중":
        raise HTTPException(status_code=400, detail=f"'{order.status}' 상태는 입고 처리할 수 없습니다")

    stock_material_name = normalize_material_name(order.material_name)
    stock = db.query(LabelStock).filter(LabelStock.material_name == stock_material_name).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"'{order.material_name}' 재고 항목을 찾을 수 없습니다")

    stock.stock_qty = float(stock.stock_qty) + float(order.order_qty)
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


@router.patch("/{order_id}/cancel", response_model=LabelOrderOut)
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(LabelOrder).filter(LabelOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="발주를 찾을 수 없습니다")
    if order.status not in ("대기중",):
        raise HTTPException(status_code=400, detail=f"'{order.status}' 상태는 취소할 수 없습니다")
    order.status = "취소"
    db.commit()
    db.refresh(order)
    return order
