"""
플랫폼 AI 보고 서비스 (옷감사)
raw 데이터가 아닌 AI가 판단한 요약 정보만 전송
보고 실패는 사일런트 무시 — 플랫폼 장애가 옷감 업무를 막지 않음
표준 규격: 옷감agent/지시이력.txt [2026-06-11 16:00] 플랫폼agent 연결 표준 규격 참고
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta

import httpx

from services.ai_status import build_release_ai_report
from services.platform_report_state import finish_report, start_report
from services.production_rules import FABRIC_NAMES, MACHINES, PRODUCTION_SPEED

PLATFORM_BASE = os.getenv("PLATFORM_BASE_URL", "http://localhost:8000/api")
COMPANY_LOCATION = os.getenv("COMPANY_LOCATION", "옷감사 공장")

# 플랫폼은 collected-release에서 company_id를 정수로만 받는다(COMPANY_TYPE_MAP: 옷감사=1).
# .env의 COMPANY_ID가 회사명("옷감사")이면 정수 코드로 변환하고, 회사명은 company_type으로 보낸다.
_COMPANY_CODE_MAP = {"옷감사": 1}
_COMPANY_ID_RAW = os.getenv("COMPANY_ID", "옷감사").strip()
COMPANY_TYPE = os.getenv("COMPANY_NAME", "옷감사" if not _COMPANY_ID_RAW.isdigit() else "옷감사")
COMPANY_ID = int(_COMPANY_ID_RAW) if _COMPANY_ID_RAW.isdigit() else _COMPANY_CODE_MAP.get(_COMPANY_ID_RAW)


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


async def report_schedule(fabric_code: str, color_code: str, qty: float, due_date) -> None:
    """생산 등록 시 → 플랫폼 /api/agent-report/schedule"""
    speed = PRODUCTION_SPEED.get(fabric_code.upper(), 8)
    estimated_h = qty / (speed * MACHINES)
    est_completion = datetime.now() + timedelta(hours=estimated_h)
    item = f"{fabric_code.upper()}-{color_code.upper()}"
    await _post("/agent-report/schedule", {
        "company_id":           COMPANY_ID,
        "company_name":         "옷감사",
        "item":                 item,
        "qty":                  float(qty),
        "start_at":             datetime.now().isoformat(),
        "estimated_completion": est_completion.isoformat(),
        "due_date":             due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date),
        "status":               "생산등록",
    }, "schedule", item)


async def report_reschedule(production_id: int, reason: str, new_estimated_completion=None) -> None:
    """돌발상황 발생 시 → 플랫폼 /api/agent-report/reschedule"""
    await _post("/agent-report/reschedule", {
        "company_id":               COMPANY_ID,
        "company_name":             "옷감사",
        "report_id_ref":            f"production-{production_id}",
        "label_code":               str(production_id),
        "item":                     str(production_id),
        "reason":                   reason,
        "new_estimated_completion": (
            new_estimated_completion.isoformat()
            if isinstance(new_estimated_completion, datetime)
            else (new_estimated_completion or datetime.now().isoformat())
        ),
    }, "reschedule", str(production_id))


def extract_bl_number(text: str | None) -> str | None:
    """발주 note에서 BL 번호 추출 — 라벨agent 표준(shipment_logic.extract_bl_number)과 동일"""
    if not text:
        return None
    match = re.search(r"\b(BL-[A-Z0-9-]+|MOCK-BL-[A-Z0-9-]+)\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\bBL\s+([A-Z0-9-]+)\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_note_token(text: str | None, token: str) -> str | None:
    if not text:
        return None
    pattern = rf"(?:^|/)\s*{re.escape(token)}\s+([^/]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def extract_port_of_loading(text: str | None) -> str | None:
    return _extract_note_token(text, "POL")


def extract_port_of_discharge(text: str | None) -> str | None:
    return _extract_note_token(text, "POD")


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
    """원자재 입고 보고 → 플랫폼 /api/agent-report/import (라벨agent 표준 시그니처)

    status="입고완료": 발주 입고완료 처리 시 실제 입고 보고.
    status="입고예정": BL 정보가 있는 발주 등록 시점에 보내는 입고예정(선적) 통지."""
    await _post("/agent-report/import", {
        "company_id":   COMPANY_ID,
        "company_name": "옷감사",
        "material":     material,
        "item_name":    material,
        "qty":          float(qty),
        "unit":         "kg",
        "weight_kg":    float(qty),
        "status":       status,
        "arrival_date": arrival_date.isoformat() if hasattr(arrival_date, "isoformat") else str(arrival_date),
        "bl_number":    bl_number or "",
        "supplier":          supplier,
        "supplier_company":  supplier,
        "port_of_loading":   port_of_loading,
        "port_of_discharge": port_of_discharge,
        "receiving_port":    port_of_discharge,
        "due_date": (
            due_date.isoformat() if hasattr(due_date, "isoformat")
            else str(due_date) if due_date
            else None
        ),
        "note": note,
        "receiving_company":          COMPANY_ID,
        "receiving_company_location": COMPANY_LOCATION,
    }, "import", material)


async def report_release(release) -> None:
    """출고완료 시 → 플랫폼 /api/collected-release (report_id 추적 포함)
    ai_report: 라벨agent 표준의 'AI/DB 판단 보고' 카드(analysis_type=db_rule_based,
    uses_openai=False)와 동일한 형식으로 규칙기반 요약을 함께 보낸다."""
    item_name = f"{FABRIC_NAMES.get(release.fabric_code, release.fabric_code)}_{release.color_code}"
    await _post("/collected-release", {
        "company_id":   COMPANY_ID,
        "company_name": COMPANY_TYPE,
        "company_type": COMPANY_TYPE,
        "item_name":    item_name,
        "item_ref":     f"{release.fabric_code}-{release.color_code}",
        "quantity":     float(release.release_qty),
        "release_qty":  float(release.release_qty),
        "unit":         "야드",
        "due_date":     str(release.due_date),
        "release_date": str(release.release_date) if release.release_date else None,
        "status":       "출고완료",
        "label_code":   release.label_code,
        "fabric_code":  release.fabric_code,
        "color_code":   release.color_code,
        "pickup_company":  "옷감사",
        "pickup_location": COMPANY_LOCATION,
        "ai_report":    build_release_ai_report(release),
    }, "release", item_name)


KG_PER_YARD = 0.3  # routers/release.py 패킹리스트와 동일한 야드→kg 환산 기준


async def report_release_batch(
    releases,
    destination: str,
    report_batch_due_date,
    box_count: int,
    export_port: str = "부산항",
) -> None:
    """주차 단위 출고묶음을 하나의 /collected-release 보고로 전송 (플랫폼/물류 매칭 시연용).

    건별 report_release와 별개로, 같은 납기(report_batch_due_date)의 출고건을 묶어
    플랫폼 표준 물류 필드(shipment_total_weight_kg, shipment_box_count_total, destination,
    completed_release_list)를 포함한 묶음 보고를 만든다. 5주차 중복보고 시연을 위해
    동일 source_report_id를 부여한다."""
    total_qty = sum(float(r.release_qty) for r in releases)
    total_weight = round(total_qty * KG_PER_YARD, 1)
    first = releases[0]
    bundle_name = ", ".join(
        f"{FABRIC_NAMES.get(r.fabric_code, r.fabric_code)}_{r.color_code}" for r in releases
    )
    batch_key = (
        report_batch_due_date.isoformat()
        if hasattr(report_batch_due_date, "isoformat")
        else str(report_batch_due_date)
    )
    completed_release_list = [
        {
            "label_code":  r.label_code,
            "fabric_code": r.fabric_code,
            "color_code":  r.color_code,
            "item_ref":    f"{r.fabric_code}-{r.color_code}",
            "release_qty": float(r.release_qty),
            "weight_kg":   round(float(r.release_qty) * KG_PER_YARD, 1),
        }
        for r in releases
    ]
    item_ref = f"batch-{batch_key}"
    await _post("/collected-release", {
        "company_id":   COMPANY_ID,
        "company_name": COMPANY_TYPE,
        "company_type": COMPANY_TYPE,
        "item_name":    bundle_name,
        "item_ref":     item_ref,
        "quantity":     total_qty,
        "release_qty":  total_qty,
        "unit":         "야드",
        "due_date":     batch_key,
        "report_batch_due_date": batch_key,
        "release_date": str(first.release_date) if first.release_date else None,
        "status":       "출고완료",
        "label_code":   first.label_code,
        "completed_release_list":   completed_release_list,
        "shipment_total_weight_kg": total_weight,
        "shipment_box_count_total": box_count,
        "destination":     destination,
        "export_port":     export_port,
        "pickup_company":  "옷감사",
        "pickup_location": COMPANY_LOCATION,
        "source_report_id": f"fabric-batch-{batch_key}",
        "ai_report":       build_release_ai_report(first),
    }, "release", item_ref)
