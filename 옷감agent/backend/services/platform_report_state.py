"""
플랫폼 보고 채널 상태 저장소 (옷감agent)

- FabricPlatformReportEvent: 보고 1건당 1행 (전송중/전송완료/플랫폼 보고 대기)
- FabricPlatformReportMessage: 채팅형 타임라인 (옷감agent→플랫폼 / 플랫폼→옷감agent)

DB에 영속 저장되므로 프로세스 재시작에도 유지된다.
report_id는 f"fabric-{event.id}" 형식이며, 재시도 시에도 동일 값을 유지한다.
"""
from __future__ import annotations

import json
from datetime import datetime
from threading import Lock
from typing import Any

from database import SessionLocal
from models import FabricPlatformReportEvent, FabricPlatformReportMessage

_LOCK = Lock()
_MAX_REPORTS = 30
_MAX_CHANNEL_MESSAGES = 80


def _now() -> datetime:
    return datetime.now()


def _now_text() -> str:
    return _now().isoformat(timespec="seconds")


def _serialize_payload(payload: dict | None) -> str | None:
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False, default=str)


def _deserialize_payload(payload_json: str | None) -> dict:
    if not payload_json:
        return {}
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _format_number(value) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}"


def _report_type_label(report_type: str) -> str:
    return {
        "schedule": "생산일정 보고",
        "reschedule": "일정변경 보고",
        "import": "원자재 입고 보고",
        "release": "출고완료 보고",
    }.get(report_type, report_type)


def _build_outbound_summary(report_type: str, item_ref: str, payload: dict | None) -> str:
    payload = payload or {}

    if report_type == "schedule":
        qty = _format_number(payload.get("qty"))
        completion = (payload.get("estimated_completion") or "")[:16].replace("T", " ")
        due = payload.get("due_date", "-")
        status = payload.get("status", "생산등록")
        return f"{item_ref} {qty}야드 생산등록. 완료예정 {completion or '-'}, 납기 {due}, {status}"

    if report_type == "reschedule":
        reason = payload.get("reason", "-")
        new_completion = (payload.get("new_estimated_completion") or "")[:16].replace("T", " ")
        text = f"생산 #{item_ref} 일정변경: {reason}"
        if new_completion:
            text += f" → 새 완료예정 {new_completion}"
        return text

    if report_type == "import":
        material = payload.get("material") or item_ref
        qty = _format_number(payload.get("qty"))
        unit = payload.get("unit", "kg")
        arrival = payload.get("arrival_date", "-")
        if payload.get("status") == "입고예정":
            parts = [f"{material} {qty}{unit} 입고예정 통지 (도착예정 {arrival})"]
        else:
            parts = [f"{material} {qty}{unit} 입고 보고 (입고일 {arrival})"]
        if payload.get("bl_number"):
            parts.append(f"BL {payload['bl_number']}")
        if payload.get("supplier"):
            parts.append(f"공급사 {payload['supplier']}")
        return ". ".join(parts)

    if report_type == "release":
        qty = _format_number(payload.get("quantity"))
        item_name = payload.get("item_name", item_ref)
        due = payload.get("due_date", "-")
        release_date = payload.get("release_date", "-")
        text = f"{item_name} {qty}야드 출고완료 보고. 납기 {due}, 출고일 {release_date}"
        if payload.get("label_code"):
            text += f", 연동 라벨 {payload['label_code']}"
        return text

    return f"{_report_type_label(report_type)}: {item_ref}"


def _build_inbound_summary(report_type: str, item_ref: str, payload: dict | None = None) -> str:
    payload = payload or {}
    instruction = payload.get("instruction") or payload.get("message")
    summary = f"플랫폼agent가 {_report_type_label(report_type)}를 수신확인했습니다. 대상: {item_ref}"
    if instruction:
        summary += f" / 메모: {instruction}"
    return summary


def _prune_old_rows(db) -> None:
    event_ids = [
        row.id
        for row in db.query(FabricPlatformReportEvent.id)
        .order_by(FabricPlatformReportEvent.id.desc())
        .offset(_MAX_REPORTS)
        .all()
    ]
    if event_ids:
        db.query(FabricPlatformReportMessage).filter(
            FabricPlatformReportMessage.event_id.in_(event_ids)
        ).delete(synchronize_session=False)
        db.query(FabricPlatformReportEvent).filter(
            FabricPlatformReportEvent.id.in_(event_ids)
        ).delete(synchronize_session=False)

    message_ids = [
        row.id
        for row in db.query(FabricPlatformReportMessage.id)
        .order_by(FabricPlatformReportMessage.id.desc())
        .offset(_MAX_CHANNEL_MESSAGES)
        .all()
    ]
    if message_ids:
        db.query(FabricPlatformReportMessage).filter(
            FabricPlatformReportMessage.id.in_(message_ids)
        ).delete(synchronize_session=False)


def _row_to_message(row: FabricPlatformReportMessage) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_id": row.event_id,
        "direction": row.direction,
        "sender": row.sender,
        "receiver": row.receiver,
        "report_type": row.report_type,
        "report_type_label": row.report_type_label,
        "item_ref": row.item_ref,
        "path": row.path,
        "status": row.status,
        "summary": row.summary,
        "payload": _deserialize_payload(row.payload_json),
        "report_id": row.report_id,
        "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
        "updated_at": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
    }


def _row_to_report(row: FabricPlatformReportEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "report_type": row.report_type,
        "report_type_label": row.report_type_label,
        "item_ref": row.item_ref,
        "path": row.path,
        "status": row.status,
        "message": row.message,
        "payload": _deserialize_payload(row.payload_json),
        "report_id": row.report_id,
        "updated_at": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
    }


def start_report(report_type: str, item_ref: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, str]:
    """보고 이벤트 + 채팅 메시지(outbound) row 생성. (event_id, report_id) 반환.

    payload는 in-place로 report_id가 주입되어 재시도 시에도 동일 ID가 유지된다.
    """
    summary = _build_outbound_summary(report_type, item_ref, payload)
    report_type_label = _report_type_label(report_type)
    now = _now()

    with _LOCK:
        db = SessionLocal()
        try:
            event = FabricPlatformReportEvent(
                report_type=report_type,
                report_type_label=report_type_label,
                item_ref=item_ref,
                path=path,
                status="전송중",
                message=summary,
                created_at=now,
                updated_at=now,
            )
            db.add(event)
            db.flush()

            report_id = f"fabric-{event.id}"
            if payload is not None:
                payload["report_id"] = report_id

            event.report_id = report_id
            event.payload_json = _serialize_payload(payload)

            message = FabricPlatformReportMessage(
                event_id=event.id,
                direction="outbound",
                sender="옷감agent",
                receiver="플랫폼agent",
                report_type=report_type,
                report_type_label=report_type_label,
                item_ref=item_ref,
                path=path,
                status="전송중",
                summary=summary,
                payload_json=_serialize_payload(payload),
                report_id=report_id,
                created_at=now,
                updated_at=now,
            )
            db.add(message)
            db.flush()

            event.channel_message_id = message.id
            _prune_old_rows(db)
            db.commit()
            return event.id, report_id
        finally:
            db.close()


def finish_report(event_id: int, success: bool, message: str | None = None, response_payload: dict | None = None) -> None:
    """보고 결과 반영. 성공 시 플랫폼 응답(inbound) 메시지를 채널에 추가한다."""
    with _LOCK:
        db = SessionLocal()
        try:
            event = db.query(FabricPlatformReportEvent).filter(FabricPlatformReportEvent.id == event_id).first()
            if not event:
                return

            event.status = "전송완료" if success else "플랫폼 보고 대기"
            event.message = message or ("플랫폼 보고 완료" if success else "플랫폼 보고 대기")
            event.updated_at = _now()

            if event.channel_message_id:
                outbound = db.query(FabricPlatformReportMessage).filter(
                    FabricPlatformReportMessage.id == event.channel_message_id
                ).first()
                if outbound:
                    outbound.status = event.status
                    outbound.updated_at = event.updated_at

            if success:
                inbound = FabricPlatformReportMessage(
                    event_id=event.id,
                    direction="inbound",
                    sender="플랫폼agent",
                    receiver="옷감agent",
                    report_type=event.report_type,
                    report_type_label=event.report_type_label,
                    item_ref=event.item_ref,
                    path=event.path,
                    status="수신확인",
                    summary=_build_inbound_summary(event.report_type, event.item_ref, response_payload),
                    payload_json=_serialize_payload(response_payload),
                    report_id=event.report_id,
                    created_at=_now(),
                    updated_at=_now(),
                )
                db.add(inbound)

            _prune_old_rows(db)
            db.commit()
        finally:
            db.close()


def record_platform_reply(report_type: str, item_ref: str, status: str, message: str, payload: dict | None = None) -> dict[str, Any]:
    """플랫폼이 능동적으로 보내는 응답/추가지시를 채널에 기록한다 (POST /agent/report-reply)."""
    report_type_label = _report_type_label(report_type)
    now = _now()

    with _LOCK:
        db = SessionLocal()
        try:
            row = FabricPlatformReportMessage(
                event_id=None,
                direction="inbound",
                sender="플랫폼agent",
                receiver="옷감agent",
                report_type=report_type,
                report_type_label=report_type_label,
                item_ref=item_ref,
                path=None,
                status=status,
                summary=message,
                payload_json=_serialize_payload(payload),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            _prune_old_rows(db)
            db.commit()
            db.refresh(row)
            return _row_to_message(row)
        finally:
            db.close()


def get_report_status_snapshot() -> dict[str, Any]:
    """AI Agent /status 응답에 포함되는 '플랫폼 보고 상태' 요약."""
    with _LOCK:
        db = SessionLocal()
        try:
            report_rows = (
                db.query(FabricPlatformReportEvent)
                .order_by(FabricPlatformReportEvent.id.desc())
                .limit(8)
                .all()
            )
            message_rows = (
                db.query(FabricPlatformReportMessage)
                .order_by(FabricPlatformReportMessage.id.desc())
                .limit(_MAX_CHANNEL_MESSAGES)
                .all()
            )
            reports = [_row_to_report(row) for row in report_rows]
            channel_messages = [_row_to_message(row) for row in message_rows]
            statuses = [row.status for row in report_rows]
        finally:
            db.close()

    success_count = sum(1 for status in statuses if status == "전송완료")
    waiting_count = sum(1 for status in statuses if status != "전송완료")

    if not statuses:
        summary = "최근 플랫폼 보고 없음"
    elif waiting_count:
        summary = f"최근 {len(statuses)}건 중 전송완료 {success_count}건 / 대기 {waiting_count}건"
    else:
        summary = f"최근 {len(statuses)}건 모두 플랫폼 보고 완료"

    channel_messages.reverse()  # 오래된 순 → 최신 순

    return {
        "summary": summary,
        "success_count": success_count,
        "waiting_count": waiting_count,
        "recent_reports": reports,
        "channel_messages": channel_messages,
        "storage": "database",
        "persistent": True,
        "last_synced_at": _now_text(),
    }
