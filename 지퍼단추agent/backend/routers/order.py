from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import ZipperOrder, ZipperStock
from schemas import OrderCreate, OrderOut
from services.platform_reporter import report_import

router = APIRouter(prefix="/orders", tags=["발주"])


@router.get("/", response_model=list[OrderOut])
def get_orders(db: Session = Depends(get_db)):
    return db.query(ZipperOrder).order_by(ZipperOrder.order_date.desc()).all()


@router.post("/", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    order = ZipperOrder(**body.model_dump())
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(ZipperOrder).filter(ZipperOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="발주를 찾을 수 없습니다")
    if order.status != "대기중":
        raise HTTPException(status_code=400, detail=f"취소 불가 상태: {order.status}")
    order.status = "취소"
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}/receive", response_model=OrderOut)
async def receive_order(
    order_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """재고도착 버튼: 발주량을 원자재 재고에 더하고 입고완료 처리"""
    order = db.query(ZipperOrder).filter(ZipperOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="발주를 찾을 수 없습니다")
    if order.status != "대기중":
        raise HTTPException(status_code=400, detail=f"입고 처리 불가 상태: {order.status}")

    stock = db.query(ZipperStock).filter(
        ZipperStock.material_name == order.material_name
    ).first()

    if stock:
        stock.stock_qty = float(stock.stock_qty) + float(order.order_qty)
    else:
        new_stock = ZipperStock(
            material_name=order.material_name,
            unit=order.unit,
            stock_qty=order.order_qty,
        )
        db.add(new_stock)

    order.status = "입고완료"
    db.commit()
    db.refresh(order)

    background_tasks.add_task(
        report_import,
        order.material_name,
        float(order.order_qty),
        date.today(),
        None,
    )
    return order
