"""
플랫폼 보고 상태 + 채팅형 보고 채널 저장소.
[2026-06-11 16:00] 표준 규격 / [2026-06-04 13:53] 채널 UI 지시 기준으로
지퍼단추agent DB(company_zipper)에 영속 저장한다.
"""
from __future__ import annotations

import base64
import csv
import io
import json
from datetime import date, datetime
from threading import Lock
from typing import Any

from database import SessionLocal
from models import ZipperPlatformReportEvent, ZipperPlatformReportMessage, ZipperRelease, ZipperStock
from services.ai_agent import MATERIAL_UNIT, build_raw_material_summary, get_item_type

_LOCK = Lock()
_MAX_REPORTS = 30
_MAX_CHANNEL_MESSAGES = 80
# [2026-06-04 13:53] 지시: 생산일정/재조정/원자재입고/출고완료 보고를 모두 채널에 표시
_VISIBLE_REPORT_TYPES = ("schedule", "reschedule", "import", "release")


def _now() -> datetime:
    return datetime.now()


def _now_text() -> str:
    return _now().isoformat(timespec="seconds")


def _format_number(value: Any) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.3f}".rstrip("0").rstrip(".")


def _format_weight(value: Any) -> str | None:
    if value is None:
        return None
    return f"{_format_number(value)}kg"


def _report_type_label(report_type: str) -> str:
    return {
        "schedule": "생산일정 보고",
        "reschedule": "일정변경 보고",
        "import": "원자재 입고 보고",
        "release": "출고완료 보고",
    }.get(report_type, report_type)


def _material_unit(material_name: str | None) -> str:
    return MATERIAL_UNIT.get(material_name or "", "")


def _serialize_payload(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False, default=str)


def _deserialize_payload(payload_json: str | None) -> dict[str, Any]:
    if not payload_json:
        return {}
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _release_batch_key(payload: dict[str, Any] | None) -> str | None:
    payload = payload or {}
    raw = payload.get("report_batch_due_date") or payload.get("due_date")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _build_packing_list_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["item_name", "item_type", "release_qty", "weight_kg", "due_date", "release_date", "label_code"])
    for r in rows:
        writer.writerow([
            r["item_name"], r["item_type"], r["release_qty"], r["weight_kg"],
            r["due_date"], r["release_date"], r.get("label_code") or "",
        ])
    return buf.getvalue()


def _build_release_ai_summary(ai_report: dict[str, Any], payload: dict[str, Any]) -> str:
    batch_label = ai_report.get("report_batch_label") or "출고 묶음"
    parts = [
        (
            f"지퍼단추사 DB 판단: {batch_label} 완료 "
            f"{_format_number(ai_report.get('completed_release_count') or 0)}건 "
            f"{_format_number(ai_report.get('completed_release_qty_total') or 0)}개"
        )
    ]

    total_weight = ai_report.get("shipment_total_weight_kg")
    if total_weight is not None:
        parts.append(f"총중량 {_format_weight(total_weight)}")

    if ai_report.get("stock_summary_text"):
        parts.append(f"현재 원자재 재고 {ai_report['stock_summary_text']}")

    if ai_report.get("decision_level") and ai_report.get("decision"):
        parts.append(f"판정 {ai_report['decision_level']}: {ai_report['decision']}")

    return ". ".join(parts)


def enrich_release_payload(db, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return payload

    batch_due_date = _parse_iso_date(payload.get("report_batch_due_date") or payload.get("due_date"))
    if not batch_due_date:
        return payload

    rows = (
        db.query(ZipperRelease)
        .filter(
            ZipperRelease.status == "출고완료",
            ZipperRelease.due_date == batch_due_date,
        )
        .order_by(ZipperRelease.item_name, ZipperRelease.id)
        .all()
    )
    if not rows:
        return payload

    completed_release_list = []
    completed_release_qty_total = 0
    shipment_total_weight_kg = 0.0
    item_codes: set[str] = set()

    for release in rows:
        weight_kg = round(int(release.release_qty or 0) * 5 / 1000, 3)
        completed_release_list.append(
            {
                "id": release.id,
                "item_name": release.item_name,
                "item_type": get_item_type(release.item_name),
                "label_code": release.label_code,
                "release_qty": release.release_qty,
                "release_date": release.release_date.isoformat() if release.release_date else None,
                "due_date": release.due_date.isoformat() if release.due_date else None,
                "weight_kg": weight_kg,
            }
        )
        completed_release_qty_total += int(release.release_qty or 0)
        shipment_total_weight_kg += weight_kg
        item_codes.add(release.item_name)

    merged_payload = dict(payload)
    merged_payload["report_batch_due_date"] = batch_due_date.isoformat()
    merged_payload["completed_release_list"] = completed_release_list
    merged_payload["completed_release_count"] = len(completed_release_list)
    merged_payload["completed_release_qty_total"] = completed_release_qty_total
    merged_payload["shipment_total_weight_kg"] = round(shipment_total_weight_kg, 3)
    merged_payload["completed_release_total_weight_kg"] = round(shipment_total_weight_kg, 3)

    csv_text = _build_packing_list_csv(completed_release_list)
    packing_list = dict(merged_payload.get("packing_list") or {})
    packing_list["filename"] = f"packing_list_{batch_due_date}_{batch_due_date}.csv"
    packing_list["content_type"] = "text/csv"
    packing_list["period_from"] = batch_due_date.isoformat()
    packing_list["period_to"] = batch_due_date.isoformat()
    packing_list["total_qty"] = completed_release_qty_total
    packing_list["total_weight_kg"] = round(shipment_total_weight_kg, 3)
    packing_list["label_code_count"] = len(item_codes)
    packing_list["csv_base64"] = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")
    packing_list["csv_size_bytes"] = len(csv_text.encode("utf-8"))
    merged_payload["packing_list"] = packing_list

    raw_stocks = {s.material_name: float(s.stock_qty) for s in db.query(ZipperStock).all()}
    raw_summary = build_raw_material_summary(raw_stocks)

    ai_report = dict(merged_payload.get("ai_report") or {})
    ai_report["report_batch_type"] = "due_date"
    ai_report["report_batch_due_date"] = batch_due_date.isoformat()
    ai_report["report_batch_label"] = f"납기 {batch_due_date.isoformat()} 묶음"
    ai_report["completed_release_count"] = len(completed_release_list)
    ai_report["completed_release_qty_total"] = completed_release_qty_total
    ai_report["shipment_total_weight_kg"] = round(shipment_total_weight_kg, 3)
    ai_report["packing_list_filename"] = packing_list["filename"]
    ai_report["stock_snapshot"] = raw_summary
    ai_report["stock_summary_text"] = ", ".join(
        f"{m['material_name']} {_format_number(m['current_qty'])}{m['unit']}({m['level']})" for m in raw_summary
    )
    ai_report["summary"] = _build_release_ai_summary(ai_report, merged_payload)
    merged_payload["ai_report"] = ai_report

    return merged_payload


def _build_outbound_summary(report_type: str, item_ref: str, payload: dict[str, Any] | None) -> str:
    payload = payload or {}

    if report_type == "schedule":
        qty = _format_number(payload.get("qty"))
        parts = [f"{item_ref} {qty}개 생산일정 보고"]
        if payload.get("due_date"):
            parts.append(f"납기 {payload['due_date']}")
        if payload.get("estimated_completion"):
            parts.append(f"예상완료 {str(payload['estimated_completion'])[:16].replace('T', ' ')}")
        if payload.get("status"):
            parts.append(f"상태 {payload['status']}")
        return ". ".join(parts)

    if report_type == "reschedule":
        parts = [f"{item_ref} 일정변경/돌발상황 보고"]
        if payload.get("reason"):
            parts.append(f"사유: {payload['reason']}")
        if payload.get("new_estimated_completion"):
            parts.append(f"새 예상완료 {str(payload['new_estimated_completion'])[:16].replace('T', ' ')}")
        return ". ".join(parts)

    if report_type == "import":
        material = payload.get("material_display_name") or payload.get("material") or item_ref
        qty = _format_number(payload.get("qty"))
        unit = payload.get("unit") or _material_unit(payload.get("material"))
        status = payload.get("status") or "입고완료"
        action_label = "원자재 입고 보고" if status == "입고완료" else f"입고 {status} 통지"
        parts = [f"{material} {qty}{unit} {action_label}"]

        if payload.get("bl_number"):
            parts.append(f"BL {payload['bl_number']}")
        if payload.get("port_of_loading"):
            parts.append(f"선적항 {payload['port_of_loading']}")
        if payload.get("port_of_discharge") or payload.get("receiving_port"):
            parts.append(f"도착항 {payload.get('port_of_discharge') or payload.get('receiving_port')}")
        if payload.get("supplier_company") or payload.get("supplier"):
            parts.append(f"공급사 {payload.get('supplier_company') or payload.get('supplier')}")
        if payload.get("arrival_date"):
            parts.append(f"입고일 {payload['arrival_date']}")
        if payload.get("weight_kg") is not None:
            parts.append(f"중량 {_format_weight(payload['weight_kg'])}")

        return ". ".join(parts)

    if report_type == "release":
        ai_report = payload.get("ai_report") or {}
        ai_summary = ai_report.get("summary")
        if ai_summary:
            parts = [ai_summary]
        else:
            qty = _format_number(payload.get("release_qty") or payload.get("quantity") or payload.get("qty"))
            parts = [f"{item_ref} {qty}개 출고완료 보고"]

        if payload.get("label_code"):
            parts.append(f"{payload['label_code']} 연동")
        if payload.get("export_port"):
            parts.append(f"출항항구 {payload['export_port']}")
        packing_list = payload.get("packing_list") or {}
        if packing_list.get("filename"):
            parts.append(f"{packing_list['filename']} 포함")

        return ". ".join(parts)

    return f"{_report_type_label(report_type)}: {item_ref}"


def _build_inbound_summary(report_type: str, item_ref: str, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    instruction = payload.get("instruction") or payload.get("message")
    summary = f"플랫폼agent가 {_report_type_label(report_type)}를 수신확인했습니다. 대상: {item_ref}"
    if instruction:
        summary += f" / 메모: {instruction}"
    return summary


def _prune_old_rows(db) -> None:
    event_ids = [
        row.id
        for row in db.query(ZipperPlatformReportEvent.id)
        .order_by(ZipperPlatformReportEvent.id.desc())
        .offset(_MAX_REPORTS)
        .all()
    ]
    if event_ids:
        db.query(ZipperPlatformReportMessage).filter(ZipperPlatformReportMessage.event_id.in_(event_ids)).delete(
            synchronize_session=False
        )
        db.query(ZipperPlatformReportEvent).filter(ZipperPlatformReportEvent.id.in_(event_ids)).delete(
            synchronize_session=False
        )

    message_ids = [
        row.id
        for row in db.query(ZipperPlatformReportMessage.id)
        .order_by(ZipperPlatformReportMessage.id.desc())
        .offset(_MAX_CHANNEL_MESSAGES)
        .all()
    ]
    if message_ids:
        db.query(ZipperPlatformReportMessage).filter(ZipperPlatformReportMessage.id.in_(message_ids)).delete(
            synchronize_session=False
        )


def _dedupe_report_rows(rows: list[ZipperPlatformReportEvent], db) -> list[ZipperPlatformReportEvent]:
    deduped: list[ZipperPlatformReportEvent] = []
    seen_release_batches: set[str] = set()

    for row in rows:
        if row.report_type != "release":
            deduped.append(row)
            continue

        payload = enrich_release_payload(db, _deserialize_payload(row.payload_json))
        batch_key = _release_batch_key(payload)
        if batch_key and batch_key in seen_release_batches:
            continue
        if batch_key:
            seen_release_batches.add(batch_key)
        deduped.append(row)

    return deduped


def _dedupe_message_rows(rows: list[ZipperPlatformReportMessage], db) -> list[ZipperPlatformReportMessage]:
    deduped: list[ZipperPlatformReportMessage] = []
    seen_release_batches: set[tuple[str, str]] = set()

    for row in rows:
        if row.report_type != "release":
            deduped.append(row)
            continue

        payload = _deserialize_payload(row.payload_json)
        if row.direction == "outbound":
            payload = enrich_release_payload(db, payload)

        batch_key = _release_batch_key(payload)
        dedupe_key = (row.direction, batch_key) if batch_key else None
        if dedupe_key and dedupe_key in seen_release_batches:
            continue
        if dedupe_key:
            seen_release_batches.add(dedupe_key)
        deduped.append(row)

    return deduped


def _row_to_message(row: ZipperPlatformReportMessage, db=None) -> dict[str, Any]:
    payload = _deserialize_payload(row.payload_json)
    if db and row.report_type == "release" and row.direction == "outbound":
        payload = enrich_release_payload(db, payload)
    summary = row.summary
    if row.direction == "outbound":
        summary = _build_outbound_summary(row.report_type, row.item_ref, payload)

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
        "summary": summary,
        "payload": payload,
        "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
        "updated_at": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
    }


def _row_to_report(row: ZipperPlatformReportEvent, db=None) -> dict[str, Any]:
    payload = _deserialize_payload(row.payload_json)
    if db and row.report_type == "release":
        payload = enrich_release_payload(db, payload)
    return {
        "id": row.id,
        "report_type": row.report_type,
        "report_type_label": row.report_type_label,
        "item_ref": row.item_ref,
        "path": row.path,
        "status": row.status,
        "message": _build_outbound_summary(row.report_type, row.item_ref, payload),
        "payload": payload,
        "updated_at": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
    }


def start_report(report_type: str, item_ref: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, str]:
    """보고 이벤트/메시지 row를 생성하고 (event_id, report_id)를 반환한다.

    전달된 ``payload`` dict는 in-place로 ``report_id``가 주입된다.
    """
    summary = _build_outbound_summary(report_type, item_ref, payload)
    report_type_label = _report_type_label(report_type)
    now = _now()

    with _LOCK:
        db = SessionLocal()
        try:
            event = ZipperPlatformReportEvent(
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

            report_id = f"zipper-{event.id}"
            if payload is not None:
                payload["report_id"] = report_id

            event.report_id = report_id
            event.payload_json = _serialize_payload(payload)

            message = ZipperPlatformReportMessage(
                event_id=event.id,
                direction="outbound",
                sender="지퍼단추agent",
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


def finish_report(
    event_id: int,
    success: bool,
    message: str | None = None,
    response_payload: dict[str, Any] | None = None,
) -> None:
    with _LOCK:
        db = SessionLocal()
        try:
            event = db.query(ZipperPlatformReportEvent).filter(ZipperPlatformReportEvent.id == event_id).first()
            if not event:
                return

            event.status = "전송완료" if success else "플랫폼 보고 대기"
            event.message = message or ("플랫폼 보고 완료" if success else "플랫폼 보고 대기")
            event.updated_at = _now()

            if event.channel_message_id:
                outbound_message = (
                    db.query(ZipperPlatformReportMessage)
                    .filter(ZipperPlatformReportMessage.id == event.channel_message_id)
                    .first()
                )
                if outbound_message:
                    outbound_message.status = event.status
                    outbound_message.updated_at = event.updated_at

            if success:
                inbound_message = ZipperPlatformReportMessage(
                    event_id=event.id,
                    direction="inbound",
                    sender="플랫폼agent",
                    receiver="지퍼단추agent",
                    report_type=event.report_type,
                    report_type_label=event.report_type_label,
                    item_ref=event.item_ref,
                    path=event.path,
                    status="수신확인",
                    summary=_build_inbound_summary(event.report_type, event.item_ref, response_payload),
                    payload_json=_serialize_payload(response_payload),
                    created_at=_now(),
                    updated_at=_now(),
                )
                db.add(inbound_message)

            _prune_old_rows(db)
            db.commit()
        finally:
            db.close()


def record_platform_reply(
    report_type: str,
    item_ref: str,
    status: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_type_label = _report_type_label(report_type)
    now = _now()

    with _LOCK:
        db = SessionLocal()
        try:
            row = ZipperPlatformReportMessage(
                event_id=None,
                direction="inbound",
                sender="플랫폼agent",
                receiver="지퍼단추agent",
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
    with _LOCK:
        db = SessionLocal()
        try:
            raw_report_rows = (
                db.query(ZipperPlatformReportEvent)
                .filter(ZipperPlatformReportEvent.report_type.in_(_VISIBLE_REPORT_TYPES))
                .order_by(ZipperPlatformReportEvent.id.desc())
                .limit(_MAX_REPORTS)
                .all()
            )
            raw_message_rows = (
                db.query(ZipperPlatformReportMessage)
                .filter(ZipperPlatformReportMessage.report_type.in_(_VISIBLE_REPORT_TYPES))
                .order_by(ZipperPlatformReportMessage.id.desc())
                .limit(_MAX_CHANNEL_MESSAGES)
                .all()
            )
            deduped_report_rows = _dedupe_report_rows(raw_report_rows, db)
            deduped_message_rows = _dedupe_message_rows(raw_message_rows, db)

            report_rows = deduped_report_rows[:8]
            message_rows = deduped_message_rows[:20]
            reports = [_row_to_report(row, db) for row in report_rows]
            channel_messages = [_row_to_message(row, db) for row in message_rows]
            statuses = [row.status for row in deduped_report_rows]
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
