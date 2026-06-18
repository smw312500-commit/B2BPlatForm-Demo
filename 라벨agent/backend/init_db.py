"""
DB 초기 데이터 삽입 스크립트
python init_db.py 실행 시 label_stock / label_machine 기본 데이터 삽입
"""
from database import SessionLocal, engine, Base
from models import LabelMachine, LabelStock
from services.production_config import MACHINE_COUNT, machine_name

Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    try:
        if db.query(LabelStock).count() == 0:
            db.add_all([
                LabelStock(material_name="라벨원단", unit="m",  stock_qty=1000),
                LabelStock(material_name="잉크",     unit="통", stock_qty=10),
            ])
            db.commit()
            print("초기 재고 데이터 삽입 완료")
        else:
            print("이미 재고 데이터가 존재합니다")

        if db.query(LabelMachine).count() == 0:
            db.add_all([
                LabelMachine(id=i, name=machine_name(i), status="대기중")
                for i in range(1, MACHINE_COUNT + 1)
            ])
            db.commit()
            print("기계 데이터 삽입 완료")
        else:
            print("이미 기계 데이터가 존재합니다")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
