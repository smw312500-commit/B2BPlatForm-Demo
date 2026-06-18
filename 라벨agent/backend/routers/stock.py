from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import LabelStock
from schemas import LabelStockOut

router = APIRouter(prefix="/stock", tags=["재고"])


@router.get("/", response_model=list[LabelStockOut])
def get_all_stock(db: Session = Depends(get_db)):
    return db.query(LabelStock).all()


@router.delete("/bulk")
def delete_stock_bulk(ids: List[int], db: Session = Depends(get_db)):
    deleted = db.query(LabelStock).filter(LabelStock.id.in_(ids)).all()
    if not deleted:
        raise HTTPException(status_code=404, detail="삭제할 항목이 없습니다")
    for item in deleted:
        db.delete(item)
    db.commit()
    return {"deleted": len(deleted)}
