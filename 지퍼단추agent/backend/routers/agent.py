from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import ZipperStock, ZipperRelease
from schemas import AgentRequest, AgentResponse, PlatformReportReply
from services.ai_agent import calculate_agent_result, build_agent_status
from services.platform_report_state import get_report_status_snapshot, record_platform_reply
from services.validator import validate_item_code

router = APIRouter(prefix="/agent", tags=["AI Agent"])


@router.post("/analyze", response_model=AgentResponse)
def analyze(body: AgentRequest, db: Session = Depends(get_db)):
    raw_stocks = {s.material_name: float(s.stock_qty) for s in db.query(ZipperStock).all()}
    result = calculate_agent_result(
        item_name=body.item_name,
        release_qty=body.release_qty,
        due_date=body.due_date,
        raw_stocks=raw_stocks,
    )
    return result


@router.get("/validate/{item_name:path}")
def validate(item_name: str):
    ok, msg = validate_item_code(item_name)
    return {"item_name": item_name, "valid": ok, "message": msg}


@router.get("/status")
def agent_status(db: Session = Depends(get_db)):
    """지퍼단추사 AI Agent 현재상황 종합 판단

    재고/원자재/진행주문/납기/트렌드를 규칙 기반으로 판단해 반환한다.
    플랫폼은 이 요약 결과만 받고 자사 raw DB를 직접 조회하지 않는다.
    """
    stocks = db.query(ZipperStock).all()
    raw_stocks = {s.material_name: float(s.stock_qty) for s in stocks}
    active_releases = (
        db.query(ZipperRelease)
        .filter(ZipperRelease.status == "생산중")
        .order_by(ZipperRelease.due_date)
        .all()
    )
    status = build_agent_status(db, raw_stocks, active_releases)
    status["platform_report_status"] = get_report_status_snapshot()
    return status


@router.post("/report-reply")
def report_reply(body: PlatformReportReply):
    """플랫폼agent가 보낸 수신확인/오류/추가 지시를 보고 채널에 기록"""
    message = record_platform_reply(
        report_type=body.report_type,
        item_ref=body.item_ref,
        status=body.status,
        message=body.message,
        payload=body.payload,
    )
    return {"received": True, "message": message}
