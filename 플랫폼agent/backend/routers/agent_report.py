"""
생산사 AI 보고 수신
- POST /api/agent-report/schedule
- POST /api/agent-report/reschedule
- POST /api/agent-report/import
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AgentReport, CompanyInfo
from services.dispatch_auto import create_import_dispatch_from_report
from services.report_message import find_message_by_report_id, record_channel_message, resolve_channel

router = APIRouter(prefix="/agent-report", tags=["에이전트 보고"])

LOGISTICS_API_URL = os.getenv("LOGISTICS_API_URL", "http://localhost:8004")

COMPANY_ID_BY_NAME = {
    "옷감사": 1,
    "옷감": 1,
    "케어라벨사": 2,
    "케어라벨": 2,
    "라벨사": 2,
    "라벨": 2,
    "라벨agent": 2,
    "지퍼단추사": 3,
    "지퍼단추": 3,
    "물류사": 4,
    "물류": 4,
}

COMPANY_NAME_BY_ID = {
    1: "옷감사",
    2: "케어라벨사",
    3: "지퍼단추사",
    4: "물류사",
}


class ScheduleReport(BaseModel):
    company_id: int | str
    company_name: Optional[str] = None
    item: str
    qty: int | float
    start_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = "진행중"
    product_weight_kg: Optional[float] = None
    shipping_weight_kg: Optional[float] = None
    fabric_weight_kg: Optional[float] = None
    ink_weight_kg: Optional[float] = None
    material_weight_kg: Optional[float] = None
    reported_at: Optional[str] = None
    trigger_event: Optional[str] = None
    trigger_detail: Optional[str] = None
    overall_status: Optional[str] = None
    assessment_count: Optional[int] = None
    assessments: Optional[list] = None
    report_id: Optional[str] = None


class RescheduleReport(BaseModel):
    company_id: int | str
    company_name: Optional[str] = None
    label_code: Optional[str] = None
    reason: str
    new_estimated_completion: Optional[str] = None
    reported_at: Optional[str] = None
    report_id: Optional[str] = None


class ImportReport(BaseModel):
    company_id: int | str
    company_name: Optional[str] = None
    material: str
    qty: int | float
    unit: Optional[str] = None
    weight_kg: Optional[float] = None
    arrival_date: str
    bl_number: Optional[str] = None
    material_display_name: Optional[str] = None
    supplier: Optional[str] = None
    supplier_company: Optional[str] = None
    receiving_company: Optional[str] = None
    receiving_company_location: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    receiving_port: Optional[str] = None
    final_place_of_delivery: Optional[str] = None
    due_date: Optional[str] = None
    note: Optional[str] = None
    reported_at: Optional[str] = None
    report_id: Optional[str] = None


async def _send_logistics_signal(
    db: Session,
    payload: dict,
    *,
    title: str,
    summary: str,
    related_code: Optional[str] = None,
):
    delivered = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{LOGISTICS_API_URL}/api/platform/signal", json=payload)
            delivered = True
    except Exception:
        delivered = False

    record_channel_message(
        db,
        channel="logistics",
        direction="outbound",
        source_agent="플랫폼",
        target_agent="물류",
        event_type=payload.get("signal_type", "platform_signal"),
        title=title,
        summary=summary,
        related_code=related_code,
        payload=payload,
        status="전송완료" if delivered else "전송실패",
    )


def _first_date_text(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value:
            return str(value)
    return None


def _date_only(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def _normalize_qty_for_storage(value: int | float | None) -> Optional[int]:
    if value is None:
        return None
    numeric = float(value)
    if numeric.is_integer():
        return int(numeric)
    return None


def _format_number(value: int | float | None) -> str:
    if value is None:
        return "-"
    numeric = float(value)
    if numeric.is_integer():
        return f"{int(numeric):,}"
    return f"{numeric:,.3f}".rstrip("0").rstrip(".")


def _format_weight(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{_format_number(value)}kg"


def _build_import_summary(company_name: str, body: ImportReport) -> str:
    material_text = body.material_display_name or body.material
    qty_text = f"{_format_number(body.qty)}{body.unit or ''}"
    parts = [f"{company_name} 원자재 {material_text} {qty_text} 수입 입고 보고"]

    if body.bl_number:
        parts.append(f"BL {body.bl_number}")
    if body.port_of_loading:
        parts.append(f"선적항 {body.port_of_loading}")
    if body.port_of_discharge or body.receiving_port:
        parts.append(f"도착항 {body.port_of_discharge or body.receiving_port}")
    if body.final_place_of_delivery:
        parts.append(f"최종도착지 {body.final_place_of_delivery}")
    if body.supplier_company or body.supplier:
        parts.append(f"공급사 {body.supplier_company or body.supplier}")
    if body.receiving_company_location:
        parts.append(f"수령위치 {body.receiving_company_location}")
    if body.arrival_date:
        parts.append(f"입고일 {body.arrival_date}")
    if body.weight_kg is not None:
        parts.append(f"중량 {_format_weight(body.weight_kg)}")

    return ". ".join(parts)


def _resolve_company_identity(
    db: Session,
    company_id_raw: int | str | None,
    company_name_raw: Optional[str],
) -> tuple[int, str]:
    resolved_id = None
    resolved_name = company_name_raw.strip() if isinstance(company_name_raw, str) and company_name_raw.strip() else None

    if isinstance(company_id_raw, int):
        resolved_id = company_id_raw
    elif isinstance(company_id_raw, str):
        stripped = company_id_raw.strip()
        if stripped.isdigit():
            resolved_id = int(stripped)
        elif stripped:
            for name_key, mapped_id in COMPANY_ID_BY_NAME.items():
                if name_key in stripped:
                    resolved_id = mapped_id
                    break
            if resolved_name is None:
                resolved_name = stripped

    if resolved_id is None and resolved_name:
        for name_key, mapped_id in COMPANY_ID_BY_NAME.items():
            if name_key in resolved_name:
                resolved_id = mapped_id
                break

    if resolved_id is not None:
        company = db.query(CompanyInfo).filter(CompanyInfo.id == resolved_id).first()
        if company:
            return company.id, company.company_name
        return resolved_id, resolved_name or COMPANY_NAME_BY_ID.get(resolved_id, f"company_{resolved_id}")

    raise HTTPException(status_code=422, detail="company_id 또는 company_name으로 회사를 식별할 수 없습니다.")


def _calc_pickup(completion_str: str, destination: str = "인천항") -> str:
    try:
        completion = datetime.fromisoformat(completion_str)
        buffer_days = 2 if destination == "부산항" else 1
        pickup = completion.date() + timedelta(days=buffer_days)
        return str(pickup)
    except Exception:
        return completion_str[:10]


@router.post("/schedule")
async def report_schedule(body: ScheduleReport, db: Session = Depends(get_db)):
    if body.report_id and find_message_by_report_id(db, body.report_id):
        return {"message": "생산 일정 보고 수신 완료", "report_id": body.report_id, "received": True}

    company_id, company_name = _resolve_company_identity(db, body.company_id, body.company_name)
    completion_basis = _first_date_text(body.estimated_completion, body.due_date, body.reported_at)

    report = AgentReport(
        company_id=company_id,
        company_name=company_name,
        report_type="schedule",
        item=body.item,
        qty=_normalize_qty_for_storage(body.qty),
        start_at=body.start_at,
        estimated_completion=completion_basis,
        status=body.status,
    )
    db.add(report)
    db.commit()

    payload = body.model_dump(mode="json") if hasattr(body, "model_dump") else body.dict()

    if body.trigger_event:
        detail = body.trigger_detail or body.item
        overall = body.overall_status or body.status or "-"
        count = body.assessment_count or len(body.assessments or [])
        event_type = "deadline_check"
        title = f"납기 체크 수신 ({body.trigger_event})"
        summary = f"{company_name} {detail} / {count}건 납기 체크 / 전체상태 {overall}"
    else:
        event_type = "agent_report_schedule"
        title = "생산 일정 보고 수신"
        summary = f"{company_name}가 {body.item} {body.qty} 생산 일정을 보고"

    record_channel_message(
        db,
        channel=resolve_channel(company_id=company_id, company_name=company_name),
        direction="inbound",
        source_agent=company_name,
        target_agent="플랫폼",
        event_type=event_type,
        title=title,
        summary=summary,
        related_code=body.item,
        payload=payload,
        status=body.overall_status or body.status,
        source_report_id=body.report_id,
    )

    pickup = _calc_pickup(completion_basis) if completion_basis else None
    if completion_basis and pickup:
        logistics_payload = {
            "company_id": company_id,
            "company_name": company_name,
            "destination": "인천항",
            "due_date": _date_only(completion_basis),
            "pickup_date": pickup,
            "signal_type": "schedule",
            "item": body.item,
            "qty": body.qty,
        }
        await _send_logistics_signal(
            db,
            logistics_payload,
            title="픽업 필요 보고",
            summary=f"{company_name} 생산 완료 예정 화물 {body.item} 픽업 필요",
            related_code=body.item,
        )

    return {"message": "생산 일정 보고 수신 완료", "pickup_date": pickup, "report_id": body.report_id, "received": True}


@router.post("/reschedule")
async def report_reschedule(body: RescheduleReport, db: Session = Depends(get_db)):
    if body.report_id and find_message_by_report_id(db, body.report_id):
        return {"message": "일정 변경 보고 수신 완료", "report_id": body.report_id, "received": True}

    company_id, company_name = _resolve_company_identity(db, body.company_id, body.company_name)

    report = AgentReport(
        company_id=company_id,
        company_name=company_name,
        report_type="reschedule",
        reason=body.reason,
        estimated_completion=body.new_estimated_completion,
        status="조정",
    )
    db.add(report)
    db.commit()

    payload = body.model_dump(mode="json") if hasattr(body, "model_dump") else body.dict()
    record_channel_message(
        db,
        channel=resolve_channel(company_id=company_id, company_name=company_name),
        direction="inbound",
        source_agent=company_name,
        target_agent="플랫폼",
        event_type="agent_report_reschedule",
        title="생산 일정 조정 보고 수신",
        summary=f"사유 {body.reason} / 완료예정 {body.new_estimated_completion}",
        related_code=body.label_code,
        payload=payload,
        status="조정",
        source_report_id=body.report_id,
    )

    pickup = _calc_pickup(body.new_estimated_completion) if body.new_estimated_completion else None
    if body.new_estimated_completion and pickup:
        logistics_payload = {
            "company_id": company_id,
            "company_name": company_name,
            "destination": "인천항",
            "due_date": _date_only(body.new_estimated_completion),
            "pickup_date": pickup,
            "signal_type": "reschedule",
            "reason": body.reason,
            "label_code": body.label_code,
        }
        await _send_logistics_signal(
            db,
            logistics_payload,
            title="배차 변경 요청",
            summary=f"{company_name} 일정 조정 / {body.reason}",
            related_code=body.label_code,
        )

    return {"message": "일정 변경 보고 수신 완료", "new_pickup_date": pickup, "report_id": body.report_id, "received": True}


@router.post("/import")
async def report_import(body: ImportReport, db: Session = Depends(get_db)):
    if body.report_id and find_message_by_report_id(db, body.report_id):
        return {"message": "BL 입고 보고 수신 완료", "bl_number": body.bl_number, "report_id": body.report_id, "received": True}

    company_id, company_name = _resolve_company_identity(db, body.company_id, body.company_name)

    report = AgentReport(
        company_id=company_id,
        company_name=company_name,
        report_type="import",
        material=body.material,
        qty=_normalize_qty_for_storage(body.qty),
        arrival_date=body.arrival_date,
        bl_number=body.bl_number,
        status="입고완료",
    )
    db.add(report)
    db.commit()

    payload = body.model_dump(mode="json") if hasattr(body, "model_dump") else body.dict()
    payload["company_id"] = company_id
    payload["company_name"] = company_name
    summary = _build_import_summary(company_name, body)

    record_channel_message(
        db,
        channel=resolve_channel(company_id=company_id, company_name=company_name),
        direction="inbound",
        source_agent=company_name,
        target_agent="플랫폼",
        event_type="agent_report_import",
        title="BL 입고 보고 수신",
        summary=summary,
        related_code=body.bl_number or body.material,
        payload=payload,
        status="입고완료",
        source_report_id=body.report_id,
    )

    await create_import_dispatch_from_report(
        db,
        company_id=company_id,
        payload=payload,
        source_report_id=body.report_id,
    )

    return {"message": "BL 입고 보고 수신 완료", "bl_number": body.bl_number, "report_id": body.report_id, "received": True}


@router.get("/")
def list_reports(db: Session = Depends(get_db)):
    return db.query(AgentReport).order_by(AgentReport.created_at.desc()).limit(50).all()
