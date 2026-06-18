from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import ZipperStock
from schemas import StockOut

router = APIRouter(prefix="/stock", tags=["재고"])


@router.get("/", response_model=list[StockOut])
def get_stock(db: Session = Depends(get_db)):
    return db.query(ZipperStock).order_by(ZipperStock.id).all()


@router.delete("/bulk")
def delete_stock_bulk(ids: list[int], db: Session = Depends(get_db)):
    rows = db.query(ZipperStock).filter(ZipperStock.id.in_(ids)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="삭제할 항목이 없습니다")
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": len(rows)}
