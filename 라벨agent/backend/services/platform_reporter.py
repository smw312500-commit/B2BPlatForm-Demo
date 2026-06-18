"""
Platform AI report sender.
Reports are best-effort only and must not block label-agent workflows.
"""
from __future__ import annotations

import os
from datetime import datetime

import httpx

from services.ai_agent import STATUS_SEVERITY
from services.material_names import display_material_name, material_unit, normalize_material_name
from services.platform_report_state import finish_report, start_report
from services.weight_logic import calculate_order_weight_kg, round_weight_kg

PLATFORM_BASE = os.getenv("PLATFORM_BASE_URL", "http://localhost:8000/api")
COMPANY_LOCATION = os.getenv("COMPANY_LOCATION", "케어라벨사 공장")
COMPANY_ID = os.getenv("COMPANY_ID", "케어라벨사")


async def _post(path: str, payload: dict, report_type: str, item_ref: str) -> None:
    url = PLATFORM_BASE + path
    event_id, _report_id = start_report(report_type, item_ref, path, payload)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = None
        finish_report(event_id, True, "플랫폼 보고 완료", response_payload)
    except Exception:
        finish_report(event_id, False, "플랫폼 보고 대기")


def _compose_import_note(
    note: str | None,
    bl_number: str | None,
    port_of_loading: str | None,
    port_of_discharge: str | None,
) -> str | None:
    parts = [segment.strip() for segment in str(note or "").split("/") if segment and segment.strip()]
    normalized = {part.upper() for part in parts}

    if bl_number and f"BL {bl_number}".upper() not in normalized:
        parts.insert(0, f"BL {bl_number}")
    if port_of_loading and f"POL {port_of_loading}".upper() not in normalized:
        parts.append(f"POL {port_of_loading}")
    if port_of_discharge and f"POD {port_of_discharge}".upper() not in normalized:
        parts.append(f"POD {port_of_discharge}")

    return " / ".join(parts) if parts else None


async def report_schedule(
    item: str,
    qty: int,
    due_date,
    estimated_completion: str | None = None,
    deadline_status: str | None = None,
    estimated_start_at: str | None = None,
    product_weight_kg: float | None = None,
    fabric_weight_kg: float | None = None,
    ink_weight_kg: float | None = None,
) -> None:
    """Send planned production status to /api/agent-report/schedule."""
    material_weight_kg = None
    if fabric_weight_kg is not None or ink_weight_kg is not None:
        material_weight_kg = round_weight_kg((fabric_weight_kg or 0) + (ink_weight_kg or 0))

    payload = {
        "company_id": COMPANY_ID,
        "item": item,
        "qty": qty,
        "start_at": estimated_start_at,
        "estimated_completion": estimated_completion,
        "due_date": due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date),
        "status": deadline_status or "생산등록",
        "product_weight_kg": product_weight_kg,
        "shipping_weight_kg": product_weight_kg,
        "fabric_weight_kg": fabric_weight_kg,
        "ink_weight_kg": ink_weight_kg,
        "material_weight_kg": material_weight_kg,
        "reported_at": datetime.now().isoformat(timespec="seconds"),
    }
    await _post("/agent-report/schedule", payload, "schedule", item)


async def report_reschedule(label_code: str, reason: str, new_estimated_completion=None) -> None:
    """Send incident/reschedule status to /api/agent-report/reschedule."""
    await _post(
        "/agent-report/reschedule",
        {
            "company_id": COMPANY_ID,
            "label_code": label_code,
            "reason": reason,
            "new_estimated_completion": (
                new_estimated_completion.isoformat()
                if isinstance(new_estimated_completion, datetime)
                else new_estimated_completion
            ),
            "reported_at": datetime.now().isoformat(timespec="seconds"),
        },
        "reschedule",
        label_code,
    )


async def _send_deadline_check(
    trigger_event: str,
    trigger_detail: str,
    assessments: list[dict],
) -> None:
    """Send combined material-arrival × production-deadline assessment to platform."""
    if not assessments:
        return

    statuses = [a.get("deadline_status") for a in assessments if a.get("deadline_status")]
    overall_status = (
        max(statuses, key=lambda s: STATUS_SEVERITY.get(s, 0))
        if statuses
        else "납기가능"
    )

    payload = {
        "company_id": COMPANY_ID,
        "item": trigger_detail,
        "qty": sum(a.get("release_qty", 0) for a in assessments),
        "trigger_event": trigger_event,
        "trigger_detail": trigger_detail,
        "overall_status": overall_status,
        "assessment_count": len(assessments),
        "assessments": [
            {k: v for k, v in a.items() if v is not None or k in ("stock_ok", "fabric_ok", "ink_ok")}
            for a in assessments
        ],
        "status": overall_status,
        "reported_at": datetime.now().isoformat(timespec="seconds"),
    }
    await _post("/agent-report/schedule", payload, "deadline_check", trigger_detail)


async def report_deadline_check_on_import(
    material_name: str,
    material_qty: float,
    arrival_date,
    release_snapshots: list[dict],
    stock_map: dict[str, float],
    material_arrivals: dict | None = None,
) -> None:
    """Send deadline check after raw material is received."""
    if not release_snapshots:
        return
    from services.deadline_check import build_assessments_snapshot

    assessments = build_assessments_snapshot(release_snapshots, stock_map, material_arrivals)
    mat_display = display_material_name(material_name) or material_name
    unit = material_unit(material_name) or ""
    qty_text = f"{int(material_qty):,}" if float(material_qty).is_integer() else f"{material_qty:,.1f}"
    arrival_text = arrival_date.isoformat() if hasattr(arrival_date, "isoformat") else str(arrival_date)
    trigger_detail = f"{mat_display} {qty_text}{unit} 입고 ({arrival_text})"
    await _send_deadline_check("입고완료", trigger_detail, assessments)


async def report_deadline_check_on_production(
    label_code: str,
    release_qty: int,
    due_date,
    stock_map: dict[str, float],
    material_arrivals: dict | None = None,
) -> None:
    """Send deadline check when a new production release is registered."""
    from datetime import date as _date
    from services.deadline_check import build_assessments_snapshot

    if isinstance(due_date, str):
        due_date = _date.fromisoformat(due_date)

    snapshots = [{"label_code": label_code, "release_qty": release_qty, "due_date": due_date}]
    assessments = build_assessments_snapshot(snapshots, stock_map, material_arrivals)
    trigger_detail = f"{label_code} {release_qty:,}장 생산등록"
    await _send_deadline_check("생산등록", trigger_detail, assessments)


async def report_import(
    material: str,
    qty: float,
    arrival_date,
    bl_number: str | None = None,
    supplier: str | None = None,
    due_date=None,
    note: str | None = None,
    port_of_loading: str | None = None,
    port_of_discharge: str | None = None,
    status: str = "입고완료",
) -> None:
    """Send raw material receiving/inbound-shipment status to /api/agent-report/import.

    status="입고완료": 재고 입고 처리(receive_order) 시 실제 입고 보고.
    status="입고예정": BL 정보가 있는 발주 등록 시점에 보내는 입고예정(선적) 통지.
    """
    normalized_material = normalize_material_name(material) or material
    weight_kg = calculate_order_weight_kg(normalized_material, qty)
    note_text = _compose_import_note(note, bl_number, port_of_loading, port_of_discharge)
    await _post(
        "/agent-report/import",
        {
            "company_id": COMPANY_ID,
            "material": normalized_material,
            "material_display_name": display_material_name(normalized_material),
            "qty": qty,
            "unit": material_unit(normalized_material),
            "weight_kg": weight_kg,
            "status": status,
            "arrival_date": arrival_date.isoformat() if hasattr(arrival_date, "isoformat") else str(arrival_date),
            "bl_number": bl_number,
            "supplier": supplier,
            "supplier_company": supplier,
            "receiving_company": COMPANY_ID,
            "receiving_company_location": COMPANY_LOCATION,
            "port_of_loading": port_of_loading,
            "port_of_discharge": port_of_discharge,
            "receiving_port": port_of_discharge,
            "due_date": (
                due_date.isoformat()
                if hasattr(due_date, "isoformat")
                else str(due_date)
                if due_date
                else None
            ),
            "note": note_text,
            "reported_at": datetime.now().isoformat(timespec="seconds"),
        },
        "import",
        normalized_material,
    )
