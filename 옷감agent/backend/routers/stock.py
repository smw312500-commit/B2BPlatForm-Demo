from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import FabricStock
from schemas import FabricStockCreate, FabricStockOut, FabricStockUpdate

router = APIRouter(prefix="/stock", tags=["stock"])

VALID_FABRIC_CODES = {"C", "P", "L", "W", "M"}
VALID_COLOR_CODES = {"BK", "WH", "NV", "GY", "BE", "RD"}


@router.get("/", response_model=List[FabricStockOut])
def get_all_stock(db: Session = Depends(get_db)):
    return db.query(FabricStock).all()


@router.get("/{fabric_code}/{color_code}", response_model=FabricStockOut)
def get_stock(fabric_code: str, color_code: str, db: Session = Depends(get_db)):
    item = db.query(FabricStock).filter(
        FabricStock.fabric_code == fabric_code.upper(),
        FabricStock.color_code == color_code.upper()
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="재고 항목을 찾을 수 없습니다.")
    return item


@router.post("/", response_model=FabricStockOut, status_code=201)
def create_stock(data: FabricStockCreate, db: Session = Depends(get_db)):
    if data.fabric_code.upper() not in VALID_FABRIC_CODES:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 원단코드: {data.fabric_code}")
    if data.color_code.upper() not in VALID_COLOR_CODES:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 컬러코드: {data.color_code}")

    exists = db.query(FabricStock).filter(
        FabricStock.fabric_code == data.fabric_code.upper(),
        FabricStock.color_code == data.color_code.upper()
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="이미 존재하는 재고 항목입니다.")

    item = FabricStock(
        fabric_code=data.fabric_code.upper(),
        color_code=data.color_code.upper(),
        stock_qty=data.stock_qty
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{stock_id}", response_model=FabricStockOut)
def update_stock(stock_id: int, data: FabricStockUpdate, db: Session = Depends(get_db)):
    item = db.query(FabricStock).filter(FabricStock.id == stock_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="재고 항목을 찾을 수 없습니다.")
    item.stock_qty = data.stock_qty
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{stock_id}", status_code=204)
def delete_stock(stock_id: int, db: Session = Depends(get_db)):
    item = db.query(FabricStock).filter(FabricStock.id == stock_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="재고 항목을 찾을 수 없습니다.")
    db.delete(item)
    db.commit()
