"""
출고완료 보고를 플랫폼으로 전송한다.
[2026-06-11 16:00] 표준 규격: POST /api/collected-release, report_id 기반 재시도/dedupe.
같은 납기일 묶음의 완료 출고 건을 모아 패킹리스트(CSV)를 함께 전송한다.
"""
from __future__ import annotations

import os
from datetime import date

import httpx
from sqlalchemy.orm import Session

from services.ai_agent import get_item_type
from services.platform_report_state import enrich_release_payload, finish_report, start_report

PLATFORM_API_URL = os.getenv("PLATFORM_API_URL", "http://localhost:8000/api/collected-release")
COMPANY_ID_RAW   = os.getenv("COMPANY_ID", "3")
COMPANY_NAME     = os.getenv("COMPANY_NAME", "지퍼단추사")
COMPANY_LOCATION = os.getenv("COMPANY_LOCATION", "지퍼단추사 공장")
EXPORT_PORT      = os.getenv("EXPORT_PORT", "부산항")


def _resolve_company_id() -> int | None:
    raw = str(COMPANY_ID_RAW).strip()
    if raw.isdigit():
        return int(raw)
    return None


async def send_release_to_platform(
    db: Session,
    item_name: str,
    release_qty: int,
    due_date: date,
    release_date: date,
    label_code: str | None = None,
    trend_signal: str | None = None,
) -> dict:
    company_id = _resolve_company_id()
    shipping_weight_kg = round(int(release_qty) * 5 / 1000, 3)
    payload = {
        "item_name":       item_name,
        "quantity":        release_qty,
        "release_qty":     release_qty,
        "qty":             release_qty,
        "unit":            "개",
        "due_date":        due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date),
        "release_date":    release_date.isoformat() if hasattr(release_date, "isoformat") else str(release_date),
        "report_batch_due_date": due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date),
        "status":          "출고완료",
        "label_code":      label_code,
        "trend_signal":    trend_signal,
        "shipping_weight_kg": shipping_weight_kg,
        "company_id":      company_id,
        "company_name":    COMPANY_NAME,
        "company_type":    COMPANY_NAME,
        "pickup_company":  COMPANY_NAME,
        "pickup_location": COMPANY_LOCATION,
        "export_port":     EXPORT_PORT,
        "trade_flow":      "export",
        "parsed_info":     {"item_name": item_name, "item_type": get_item_type(item_name)},
    }
    payload = enrich_release_payload(db, payload)

    event_id, _report_id = start_report("release", item_name, "/collected-release", payload)

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
