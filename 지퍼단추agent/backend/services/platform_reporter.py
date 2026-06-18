"""
플랫폼 AI 보고 서비스 — 지퍼단추사
[2026-06-11 16:00] 표준 규격: 모든 payload에 report_id 포함, 실패 시 업무는 계속 진행하고
내부 상태는 "플랫폼 보고 대기"로 남겨 동일 report_id로 재시도 가능하게 한다.
"""
import os
from datetime import datetime, timedelta

import httpx

from services.ai_agent import MATERIAL_UNIT
from services.platform_report_state import finish_report, start_report

PLATFORM_BASE = os.getenv("PLATFORM_BASE_URL", "http://localhost:8000/api")
COMPANY_ID    = os.getenv("COMPANY_ID", "지퍼단추사")

# 품목유형별 총 생산속도 (기계 2대 기준, 개/h)
_SPEED_MAP = {
    "원목단추":     20  * 2,   # 40개/h
    "플라스틱단추": 300 * 2,   # 600개/h
    "금속단추":     150 * 2,   # 300개/h
    "지퍼":         200 * 2,   # 400개/h
}

def _get_item_type(item_name: str) -> str:
    p = item_name.upper().split("_")[0]
    return {"WOOD": "원목단추", "PLASTIC": "플라스틱단추", "METAL": "금속단추"}.get(p, "지퍼")


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


async def report_schedule(item: str, qty: int, due_date) -> None:
    """생산 등록 시 → 플랫폼 /api/agent-report/schedule"""
    item_type   = _get_item_type(item)
    speed       = _SPEED_MAP.get(item_type, 100)
    est_h       = qty / speed
    est_done    = datetime.now() + timedelta(hours=est_h)
    payload = {
        "company_id":           COMPANY_ID,
        "item":                 item,
        "qty":                  qty,
        "start_at":             None,
        "estimated_completion": est_done.isoformat(),
        "due_date":             due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date),
        "status":               "생산등록",
        "reported_at":          datetime.now().isoformat(timespec="seconds"),
    }
    await _post("/agent-report/schedule", payload, "schedule", item)


async def report_reschedule(release_id: int, reason: str, new_estimated_completion=None) -> None:
    """돌발상황 발생 시 → 플랫폼 /api/agent-report/reschedule"""
    payload = {
        "company_id":               COMPANY_ID,
        "release_id":               release_id,
        "reason":                   reason,
        "new_estimated_completion": (
            new_estimated_completion.isoformat()
            if isinstance(new_estimated_completion, datetime)
            else new_estimated_completion
        ),
        "status":                   "돌발상황",
        "reported_at":              datetime.now().isoformat(timespec="seconds"),
    }
    await _post("/agent-report/reschedule", payload, "reschedule", f"release#{release_id}")


async def report_import(material: str, qty: float, arrival_date, bl_number: str = None) -> None:
    """입고 확정 시 → 플랫폼 /api/agent-report/import"""
    unit = MATERIAL_UNIT.get(material, "")
    weight_kg = float(qty) if unit == "kg" else None
    payload = {
        "company_id":          COMPANY_ID,
        "material":            material,
        "material_display_name": material,
        "qty":                 qty,
        "unit":                unit,
        "weight_kg":           weight_kg,
        "status":              "입고완료",
        "arrival_date":        arrival_date.isoformat() if hasattr(arrival_date, "isoformat") else str(arrival_date),
        "bl_number":           bl_number,
        "receiving_company":   COMPANY_ID,
        "reported_at":         datetime.now().isoformat(timespec="seconds"),
    }
    await _post("/agent-report/import", payload, "import", material)
