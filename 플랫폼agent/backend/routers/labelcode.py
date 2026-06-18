from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import CollectedRelease
from schemas import LabelCodeStatus, CompanyStatus

router = APIRouter()

COMPANY_MAP = {1: "옷감사", 2: "라벨사", 3: "지퍼단추사"}


@router.get("/labelcode/{label_code}/status", response_model=LabelCodeStatus)
def get_label_status(label_code: str, db: Session = Depends(get_db)):
    records = (
        db.query(CollectedRelease)
        .filter(CollectedRelease.label_code == label_code)
        .order_by(CollectedRelease.collected_at.desc())
        .all()
    )

    # 각 회사별 가장 최신 레코드 추출
    company_latest: dict[int, CollectedRelease] = {}
    for r in records:
        if r.company_id not in company_latest:
            company_latest[r.company_id] = r

    def make_status(cid: int) -> CompanyStatus:
        r = company_latest.get(cid)
        if r is None:
            return CompanyStatus(status=None, item_name=None, qty=None)
        return CompanyStatus(
            status=r.status,
            item_name=r.item_name,
            qty=float(r.quantity) if r.quantity is not None else None,
        )

    s1 = make_status(1)
    s2 = make_status(2)
    s3 = make_status(3)

    all_complete = (
        s1.status == "출고완료"
        and s2.status == "출고완료"
        and s3.status == "출고완료"
    )

    return LabelCodeStatus(
        label_code=label_code,
        옷감사=s1,
        라벨사=s2,
        지퍼단추사=s3,
        all_complete=all_complete,
    )


@router.get("/company-info")
def get_company_info(db: Session = Depends(get_db)):
    from models import CompanyInfo
    return db.query(CompanyInfo).all()
