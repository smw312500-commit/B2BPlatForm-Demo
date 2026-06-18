import os
import math
from datetime import date

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import FabricProduction, FabricRelease, FabricStock
from schemas import PlatformReportReply
from services.ai_status import build_agent_status_snapshot
from services.platform_report_state import get_report_status_snapshot, record_platform_reply
from services.production_rules import (
    FABRIC_NAMES,
    SAFE_STOCK,
    YARN_RATIO,
    calc_required_days,
    calc_required_hours,
)

router = APIRouter(prefix="/agent", tags=["agent"])


# ── Agent Status ─────────────────────────────────────────────
@router.get("/status")
def get_agent_status(db: Session = Depends(get_db)):
    today = date.today()

    # 원자재 재고 전체
    all_stocks = db.query(FabricStock).order_by(FabricStock.fabric_code, FabricStock.color_code).all()
    stocks_list = [
        {
            "material_name": f"{FABRIC_NAMES.get(s.fabric_code, s.fabric_code)}_{s.color_code}",
            "fabric_code": s.fabric_code,
            "color_code": s.color_code,
            "stock_qty": float(s.stock_qty),
            "unit": "야드",
        }
        for s in all_stocks
    ]

    # 진행 중인 출고 건
    active_releases = db.query(FabricRelease).filter(FabricRelease.status == "생산중").all()

    active_orders = []
    for r in active_releases:
        days_left = (r.due_date - today).days
        req_days  = calc_required_days(r.fabric_code, float(r.release_qty))
        req_hours = calc_required_hours(r.fabric_code, float(r.release_qty))

        if days_left < req_days:
            flag = "DANGER"
        elif days_left < req_days + 1:
            flag = "WARNING"
        else:
            flag = "OK"

        active_orders.append({
            "id": r.id,
            "item_name": f"{r.fabric_code}_{r.color_code}",
            "label_code": r.label_code,
            "fabric_code": r.fabric_code,
            "color_code": r.color_code,
            "release_qty": float(r.release_qty),
            "due_date": str(r.due_date),
            "days_remaining": days_left,
            "required_days": req_days,
            "required_hours": req_hours,
            "status_flag": flag,
        })

    priority = {"DANGER": 0, "WARNING": 1, "OK": 2}
    active_orders.sort(key=lambda x: (priority[x["status_flag"]], x["days_remaining"]))

    # 재고 경고
    stock_warnings = []
    for s in all_stocks:
        safe = SAFE_STOCK.get(s.fabric_code, 0)
        qty  = float(s.stock_qty)
        if qty <= safe:
            item = f"{FABRIC_NAMES.get(s.fabric_code, s.fabric_code)}_{s.color_code}"
            if qty == 0:
                stock_warnings.append(f"❌ 긴급 발주: [{item}] 재고 없음")
            else:
                stock_warnings.append(f"⚠ 발주 권고: [{item}] {qty:.0f}야드 (안전재고 {safe}야드)")

    # [2026-06-02 13:27] AI Agent 현재상황 판단 고도화
    active_productions_raw = db.query(FabricProduction).filter(FabricProduction.stage != "완성").all()
    all_productions = db.query(FabricProduction).all()
    snapshot = build_agent_status_snapshot(
        all_stocks=all_stocks,
        active_productions_raw=active_productions_raw,
        all_productions=all_productions,
        platform_report_status=get_report_status_snapshot(),
        today=today,
    )

    return {
        "stocks": stocks_list,
        "active_orders": active_orders,
        "stock_warnings": stock_warnings,
        **snapshot,
    }


# ── 플랫폼 보고 응답/추가지시 수신 ────────────────────────────────
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


# ── Validate ─────────────────────────────────────────────────
VALID_FABRIC_CODES = {"C", "P", "L", "W", "M"}

@router.get("/validate/{fabric_code}")
def validate_fabric(fabric_code: str):
    code = fabric_code.upper()
    if code not in VALID_FABRIC_CODES:
        return {"valid": False, "message": f"유효하지 않은 원단코드: {code}"}
    name = FABRIC_NAMES.get(code, code)
    return {"valid": True, "message": f"✅ {code} ({name}) — 유효한 원단코드"}


# ── Analyze ──────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    fabric_code: str
    color_code: str
    release_qty: float
    due_date: str


@router.post("/analyze")
def analyze_order(body: AnalyzeRequest, db: Session = Depends(get_db)):
    code = body.fabric_code.upper()
    if code not in VALID_FABRIC_CODES:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 원단코드: {code}")

    today        = date.today()
    due          = date.fromisoformat(body.due_date)
    days_left    = (due - today).days
    req_hours    = calc_required_hours(code, body.release_qty)
    req_days     = calc_required_days(code, body.release_qty)
    yarn_ratio   = YARN_RATIO.get(code, 3.0)
    yarn_needed  = math.ceil(body.release_qty / yarn_ratio * 10) / 10

    stock = db.query(FabricStock).filter(
        FabricStock.fabric_code == code,
        FabricStock.color_code  == body.color_code.upper()
    ).first()

    stock_qty = float(stock.stock_qty) if stock else 0
    stock_ok  = stock_qty >= body.release_qty

    if days_left < req_days:
        deadline_status = "납기불가"
    elif days_left < req_days + 1:
        deadline_status = "납기위험"
    else:
        deadline_status = "납기가능"

    warnings = []
    instructions = []
    if not stock_ok:
        warnings.append(f"⚠ 재고 부족: 현재 {stock_qty:.0f}야드, 필요 {body.release_qty:.0f}야드")
    if deadline_status == "납기불가":
        warnings.append(f"❌ 납기 불가: {req_days:.1f}일 필요, {days_left}일 남음")
        instructions.append("긴급 외주 또는 납기 조정 필요")
    elif deadline_status == "납기위험":
        instructions.append("즉시 착수 권고 — 여유 없음")
    else:
        instructions.append(f"정상 납기 가능 — 착수 시작일 조율 가능")

    return {
        "fabric_code": code,
        "color_code": body.color_code.upper(),
        "release_qty": body.release_qty,
        "due_date": body.due_date,
        "days_remaining": days_left,
        "required_hours": req_hours,
        "required_days": req_days,
        "raw_material": f"원사({FABRIC_NAMES.get(code, code)})",
        "raw_needed": yarn_needed,
        "raw_unit": "kg",
        "stock_qty": stock_qty,
        "stock_ok": stock_ok,
        "deadline_status": deadline_status,
        "is_valid": True,
        "warnings": warnings,
        "instructions": instructions,
    }


# ── BL 파싱 (포트 8010 파서 서비스로 프록시) ──────────────────────
@router.post("/parse-bl")
async def parse_bl(file: UploadFile = File(...)):
    bl_parser_url = os.getenv("BL_PARSER_URL", "http://localhost:8010/parse-bl")
    content = await file.read()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                bl_parser_url,
                files={"file": (file.filename, content, file.content_type or "application/octet-stream")},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="BL 파서 서비스에 연결할 수 없습니다 (포트 8010 확인)")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"BL 파서 오류: {e.response.text}")
