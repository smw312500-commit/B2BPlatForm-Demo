"""
Periodically resend platform reports stuck in '플랫폼 보고 대기' status.
Uses the report_id + payload_json saved by platform_report_state.start_report,
so retries are identifiable by the platform as the same report.
Retries are best-effort only and must not block label-agent workflows.
"""
from __future__ import annotations

import asyncio
import json
import os

import httpx

from database import SessionLocal
from models import LabelPlatformReportEvent
from services.platform_report_state import finish_report

PLATFORM_BASE = os.getenv("PLATFORM_BASE_URL", "http://localhost:8000/api")
RETRY_INTERVAL_SECONDS = int(os.getenv("PLATFORM_RETRY_INTERVAL_SECONDS", "150"))
WAITING_STATUS = "플랫폼 보고 대기"


def _load_pending() -> list[tuple[int, str, str]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(LabelPlatformReportEvent)
            .filter(LabelPlatformReportEvent.status == WAITING_STATUS)
            .all()
        )
        return [(row.id, row.path, row.payload_json) for row in rows if row.path and row.payload_json]
    finally:
        db.close()


async def _retry_once() -> None:
    for event_id, path, payload_json in _load_pending():
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            continue

        url = PLATFORM_BASE + path
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            try:
                response_payload = response.json()
            except ValueError:
                response_payload = None
            finish_report(event_id, True, "플랫폼 보고 완료(재시도)", response_payload)
        except Exception:
            continue


async def run_platform_retry_loop() -> None:
    while True:
        try:
            await _retry_once()
        except Exception:
            pass
        await asyncio.sleep(RETRY_INTERVAL_SECONDS)
