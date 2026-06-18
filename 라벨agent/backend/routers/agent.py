from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models import LabelRelease, LabelStock
from schemas import AgentRequest, AgentResponse, PlatformReportReply
from services.ai_agent import build_agent_status_snapshot, calculate_agent_result
from services.bl_parser import parse_bl_document
from services.label_validator import validate_label_code
from services.machine_state import get_machine_snapshots
from services.platform_report_state import get_report_status_snapshot, record_platform_reply

router = APIRouter(prefix="/agent", tags=["AI Agent"])


@router.post("/analyze", response_model=AgentResponse)
def analyze(body: AgentRequest, db: Session = Depends(get_db)):
    fabric = db.query(LabelStock).filter(LabelStock.material_name == "라벨원단").first()
    ink = db.query(LabelStock).filter(LabelStock.material_name == "잉크").first()

    fabric_qty = float(fabric.stock_qty) if fabric else 0.0
    ink_qty = float(ink.stock_qty) if ink else 0.0

    return calculate_agent_result(
        label_code=body.label_code,
        release_qty=body.release_qty,
        due_date=body.due_date,
        fabric_stock=fabric_qty,
        ink_stock=ink_qty,
    )


@router.get("/validate/{label_code}")
def validate(label_code: str):
    ok, msg = validate_label_code(label_code)
    return {"label_code": label_code, "valid": ok, "message": msg}


@router.get("/status")
def agent_status(db: Session = Depends(get_db)):
    stocks = db.query(LabelStock).all()
    active_releases = (
        db.query(LabelRelease)
        .filter(LabelRelease.status == "생산중")
        .order_by(LabelRelease.created_at, LabelRelease.id)
        .all()
    )

    stock_map = {stock.material_name: float(stock.stock_qty) for stock in stocks}
    return build_agent_status_snapshot(
        active_releases=active_releases,
        stock_map=stock_map,
        platform_report_status=get_report_status_snapshot(),
        machine_snapshots=get_machine_snapshots(db),
    )


@router.post("/report-reply")
def report_reply(body: PlatformReportReply):
    message = record_platform_reply(
        report_type=body.report_type,
        item_ref=body.item_ref,
        status=body.status,
        message=body.message,
        payload=body.payload,
    )
    return {"received": True, "message": message}


@router.post("/parse-bl")
async def parse_bl(file: UploadFile = File(...)):
    content = await file.read()
    try:
        return parse_bl_document(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
