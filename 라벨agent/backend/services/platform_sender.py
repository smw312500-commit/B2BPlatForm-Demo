"""
출고완료 보고를 플랫폼으로 전송한다.
플랫폼은 이 payload를 그대로 물류 전송 묶음으로 활용할 수 있다.
"""
from __future__ import annotations

import os
from datetime import date

import httpx

from services.label_validator import parse_label_code
from services.platform_report_state import finish_report, start_report

PLATFORM_API_URL = os.getenv("PLATFORM_API_URL", "http://localhost:8000/api/collected-release")
COMPANY_ID_RAW = os.getenv("COMPANY_ID", "2")
COMPANY_NAME = os.getenv("COMPANY_NAME", "케어라벨사")
COMPANY_LOCATION = os.getenv("COMPANY_LOCATION", "케어라벨사 공장")
EXPORT_PORT = os.getenv("EXPORT_PORT", "부산항")


def _resolve_company_id() -> int | None:
    raw = str(COMPANY_ID_RAW).strip()
    if raw.isdigit():
        return int(raw)
    return None


async def send_release_to_platform(
    label_code: str,
    release_qty: int,
    due_date: date,
    release_date: date,
    product_weight_kg: float,
    fabric_weight_kg: float,
    ink_weight_kg: float,
    material_weight_kg: float,
    box_count: int,
    box_count_rule: str,
    shipment_box_count_total: int,
    shipment_total_weight_kg: float,
    completed_release_list: list[dict],
    completed_release_count: int,
    completed_release_qty_total: int,
    completed_release_total_weight_kg: float,
    material_order_snapshot: list[dict],
    pending_material_order_snapshot: list[dict],
    pending_material_order_count: int,
    bl_material_orders: list[dict],
    bl_material_order_count: int,
    stock_snapshot: list[dict],
    report_batch_due_date: str,
    ai_report: dict,
    packing_list: dict,
) -> dict:
    parsed = parse_label_code(label_code)
    company_id = _resolve_company_id()
    item_name = parsed.get("item_name") or label_code
    payload = {
        "label_code": label_code,
        "item_name": item_name,
        "quantity": release_qty,
        "release_qty": release_qty,
        "qty": release_qty,
        "unit": "장",
        "due_date": due_date.isoformat(),
        "release_date": release_date.isoformat(),
        "status": "출고완료",
        "product_weight_kg": product_weight_kg,
        "shipping_weight_kg": product_weight_kg,
        "fabric_weight_kg": fabric_weight_kg,
        "ink_weight_kg": ink_weight_kg,
        "material_weight_kg": material_weight_kg,
        "box_count": box_count,
        "box_count_rule": box_count_rule,
        "shipment_box_count_total": shipment_box_count_total,
        "shipment_total_weight_kg": shipment_total_weight_kg,
        "completed_release_list": completed_release_list,
        "completed_release_count": completed_release_count,
        "completed_release_qty_total": completed_release_qty_total,
        "completed_release_total_weight_kg": completed_release_total_weight_kg,
        "material_order_snapshot": material_order_snapshot,
        "pending_material_order_snapshot": pending_material_order_snapshot,
        "pending_material_order_count": pending_material_order_count,
        "bl_material_orders": bl_material_orders,
        "bl_material_order_count": bl_material_order_count,
        "stock_snapshot": stock_snapshot,
        "report_batch_due_date": report_batch_due_date,
        "ai_report": ai_report,
        "packing_list": packing_list,
        "company_id": company_id,
        "company_name": COMPANY_NAME,
        "pickup_company": COMPANY_NAME,
        "pickup_location": COMPANY_LOCATION,
        "export_port": EXPORT_PORT,
        "trade_flow": "export",
        "company_type": COMPANY_NAME,
        "parsed_info": parsed,
    }
    event_id, _report_id = start_report("release", label_code, "/collected-release", payload)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(PLATFORM_API_URL, json=payload)
            response.raise_for_status()
            try:
                response_payload = response.json()
            except ValueError:
                response_payload = None
            finish_report(event_id, True, "출고완료 보고 전송 완료", response_payload)
            return {"success": True, "response": response_payload}
    except httpx.ConnectError:
        finish_report(event_id, False, "출고완료 보고 전송 대기")
        return {"success": False, "error": "플랫폼 서버에 연결할 수 없습니다"}
    except httpx.HTTPStatusError as exc:
        finish_report(event_id, False, "출고완료 보고 전송 대기")
        return {"success": False, "error": f"플랫폼 응답 오류: {exc.response.status_code}"}
    except Exception as exc:
        finish_report(event_id, False, "출고완료 보고 전송 대기")
        return {"success": False, "error": str(exc)}
