"""
Platform report state and chat-style report channel store.
This store is persisted in the label-agent DB and survives process restart.
"""
from __future__ import annotations

import json
from datetime import date
from datetime import datetime
from threading import Lock
from typing import Any

from database import SessionLocal
from models import LabelPlatformReportEvent, LabelPlatformReportMessage, LabelRelease
from services.material_names import display_material_name, material_unit
from services.shipment_logic import box_count_rule_text, calculate_box_count

_LOCK = Lock()
_MAX_REPORTS = 30
_MAX_CHANNEL_MESSAGES = 80
_VISIBLE_REPORT_TYPES = ("import", "release")


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
        "import": "수입 보고",
        "release": "수출 보고",
        "deadline_check": "납기 체크",
    }.get(report_type, report_type)


def _material_unit(material_name: str | None) -> str:
    return material_unit(material_name) or ""


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
    raw = payload.get("report_batch_due_date") or payload.get("due_date") or payload.get("label_code")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _build_release_ai_summary(ai_report: dict[str, Any], payload: dict[str, Any]) -> str:
    batch_label = (
        ai_report.get("report_batch_label")
        or (f"납기 {payload['report_batch_due_date']} 묶음" if payload.get("report_batch_due_date") else None)
        or payload.get("label_code")
        or "수출 묶음"
    )
    parts = [
        (
            f"라벨회사 DB 판단: {batch_label} 완료 "
            f"{_format_number(ai_report.get('completed_release_count') or payload.get('completed_release_count') or 0)}건 "
            f"{_format_number(ai_report.get('completed_release_qty_total') or payload.get('completed_release_qty_total') or 0)}장"
        )
    ]

    if ai_report.get("on_time_count") is not None or ai_report.get("delayed_count") is not None:
        parts.append(
            f"납기준수 {_format_number(ai_report.get('on_time_count') or 0)}건 / "
            f"지연 {_format_number(ai_report.get('delayed_count') or 0)}건"
        )
    if ai_report.get("stock_summary_text"):
        parts.append(f"현재 재고 {ai_report['stock_summary_text']}")
    if ai_report.get("pending_order_summary_text"):
        parts.append(f"대기 발주 {ai_report['pending_order_summary_text']}")
    elif ai_report.get("pending_material_order_count") is not None:
        pending_count = int(ai_report.get("pending_material_order_count") or 0)
        parts.append(f"대기 발주 {pending_count}건" if pending_count else "대기 발주 없음")

    total_weight = ai_report.get("shipment_total_weight_kg") or payload.get("shipment_total_weight_kg")
    total_boxes = ai_report.get("shipment_box_count_total") or payload.get("shipment_box_count_total")
    if total_weight is not None or total_boxes is not None:
        parts.append(
            f"수출 묶음 {_format_weight(total_weight) if total_weight is not None else '-'} / "
            f"{_format_number(total_boxes or 0)}박스"
        )

    if ai_report.get("decision_level") and ai_report.get("decision"):
        parts.append(f"판정 {ai_report['decision_level']}: {ai_report['decision']}")

    return ". ".join(parts)


def _enrich_release_payload(db, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return payload

    batch_due_date = _parse_iso_date(payload.get("report_batch_due_date") or payload.get("due_date"))
    if not batch_due_date:
        return payload

    rows = (
        db.query(LabelRelease)
        .filter(
            LabelRelease.status == "출고완료",
            LabelRelease.due_date == batch_due_date,
        )
        .order_by(LabelRelease.label_code, LabelRelease.id)
        .all()
    )
    if not rows:
        return payload

    completed_release_list = []
    completed_release_qty_total = 0
    shipment_total_weight_kg = 0.0
    shipment_box_count_total = 0

    for release in rows:
        product_weight_kg = float(release.product_weight_kg or 0)
        box_count = calculate_box_count(product_weight_kg)
        completed_release_list.append(
            {
                "id": release.id,
                "label_code": release.label_code,
                "release_qty": release.release_qty,
                "release_date": release.release_date.isoformat() if release.release_date else None,
                "due_date": release.due_date.isoformat() if release.due_date else None,
                "product_weight_kg": product_weight_kg,
                "box_count": box_count,
                "box_count_rule": box_count_rule_text(),
            }
        )
        completed_release_qty_total += int(release.release_qty or 0)
        shipment_total_weight_kg += product_weight_kg
        shipment_box_count_total += box_count

    merged_payload = dict(payload)
    merged_payload["report_batch_due_date"] = batch_due_date.isoformat()
    merged_payload["completed_release_list"] = completed_release_list
    merged_payload["completed_release_count"] = len(completed_release_list)
    merged_payload["completed_release_qty_total"] = completed_release_qty_total
    merged_payload["shipment_total_weight_kg"] = round(shipment_total_weight_kg, 3)
    merged_payload["completed_release_total_weight_kg"] = round(shipment_total_weight_kg, 3)
    merged_payload["shipment_box_count_total"] = shipment_box_count_total

    packing_list = dict(merged_payload.get("packing_list") or {})
    packing_list["filename"] = f"packing_list_{batch_due_date}_{batch_due_date}.csv"
    packing_list["period_from"] = batch_due_date.isoformat()
    packing_list["period_to"] = batch_due_date.isoformat()
    packing_list["total_qty"] = completed_release_qty_total
    packing_list["total_weight_kg"] = round(shipment_total_weight_kg, 3)
    packing_list["label_code_count"] = len({item["label_code"] for item in completed_release_list})
    merged_payload["packing_list"] = packing_list

    ai_report = dict(merged_payload.get("ai_report") or {})
    ai_report["report_batch_type"] = "due_date"
    ai_report["report_batch_due_date"] = batch_due_date.isoformat()
    ai_report["report_batch_label"] = f"납기 {batch_due_date.isoformat()} 묶음"
    ai_report["completed_release_count"] = len(completed_release_list)
    ai_report["completed_release_qty_total"] = completed_release_qty_total
    ai_report["shipment_total_weight_kg"] = round(shipment_total_weight_kg, 3)
    ai_report["shipment_box_count_total"] = shipment_box_count_total
    ai_report["packing_list_filename"] = packing_list["filename"]
    ai_report["summary"] = _build_release_ai_summary(ai_report, merged_payload)
    merged_payload["ai_report"] = ai_report

    return merged_payload


def _build_outbound_summary(report_type: str, item_ref: str, payload: dict[str, Any] | None) -> str:
    payload = payload or {}

    if report_type == "import":
        material = payload.get("material_display_name") or display_material_name(payload.get("material")) or item_ref
        qty = _format_number(payload.get("qty"))
        unit = _material_unit(payload.get("material") or material)
        status = payload.get("status") or "입고완료"
        if status == "입고완료":
            action_label = "수입 입고 보고"
            date_label = "입고일"
        else:
            action_label = f"수입 {status} 통지"
            date_label = f"{status}일"
        parts = [f"{material} {qty}{unit} {action_label}"]

        if payload.get("bl_number"):
            parts.append(f"BL {payload['bl_number']}")
        if payload.get("port_of_loading"):
            parts.append(f"선적항 {payload['port_of_loading']}")
        if payload.get("port_of_discharge") or payload.get("receiving_port"):
            parts.append(f"도착항 {payload.get('port_of_discharge') or payload.get('receiving_port')}")
        if payload.get("supplier_company") or payload.get("supplier"):
            parts.append(f"공급사 {payload.get('supplier_company') or payload.get('supplier')}")
        if payload.get("receiving_company_location"):
            parts.append(f"입고처 {payload['receiving_company_location']}")
        if payload.get("arrival_date"):
            parts.append(f"{date_label} {payload['arrival_date']}")
        if payload.get("weight_kg") is not None:
            parts.append(f"중량 {_format_weight(payload['weight_kg'])}")

        return ". ".join(parts)

    if report_type == "release":
        ai_report = payload.get("ai_report") or {}
        ai_summary = ai_report.get("summary")
        if ai_summary:
            return ai_summary

        completed_release_list = payload.get("completed_release_list") or []
        completed_release_count = payload.get("completed_release_count")
        completed_release_qty_total = payload.get("completed_release_qty_total")
        if completed_release_qty_total is None and completed_release_list:
            completed_release_qty_total = sum(int(item.get("release_qty") or 0) for item in completed_release_list)

        shipment_total_weight_kg = (
            payload.get("shipment_total_weight_kg")
            or payload.get("completed_release_total_weight_kg")
            or (payload.get("packing_list") or {}).get("total_weight_kg")
        )
        shipment_box_count_total = payload.get("shipment_box_count_total")
        if shipment_box_count_total is None and completed_release_list:
            shipment_box_count_total = sum(int(item.get("box_count") or 0) for item in completed_release_list)

        if completed_release_count or completed_release_qty_total or shipment_total_weight_kg is not None:
            parts = [
                (
                    f"완료 {_format_number(completed_release_count or len(completed_release_list) or 1)}건 "
                    f"{_format_number(completed_release_qty_total or payload.get('release_qty') or payload.get('qty'))}장 "
                    "수출 보고"
                )
            ]
            if item_ref:
                parts.append(f"기준 품목 {item_ref}")
        else:
            qty = _format_number(payload.get("release_qty") or payload.get("qty"))
            parts = [f"{item_ref} {qty}장 수출 완료 보고"]

        if payload.get("export_port"):
            parts.append(f"출항항구 {payload['export_port']}")
        if shipment_total_weight_kg is not None:
            parts.append(f"총중량 {_format_weight(shipment_total_weight_kg)}")
        elif payload.get("shipping_weight_kg") is not None:
            parts.append(f"수출중량 {_format_weight(payload['shipping_weight_kg'])}")
        if shipment_box_count_total is not None:
            parts.append(f"총 박스 {shipment_box_count_total}개")
        elif payload.get("box_count") is not None:
            parts.append(f"박스 {payload['box_count']}개")
        packing_list = payload.get("packing_list") or {}
        if packing_list.get("filename"):
            parts.append(f"{packing_list['filename']} 포함")

        return ". ".join(parts)

    if report_type == "deadline_check":
        trigger_detail = payload.get("trigger_detail", item_ref)
        overall = payload.get("overall_status", "-")
        assessments = payload.get("assessments") or []

        lines = [f"{trigger_detail} → 납기체크 [{overall}]"]
        for a in assessments[:4]:
            mat = (
                "자재OK"
                if a.get("stock_ok")
                else f"자재부족(입고예정 {a.get('material_arrival_date') or '미정'})"
            )
            completion = (a.get("estimated_completion_at") or "")[:16]
            lines.append(
                f"  {a.get('label_code', '-')} {_format_number(a.get('release_qty'))}장:"
                f" {mat}, 완료예상 {completion},"
                f" 납기 {a.get('due_date', '-')}, {a.get('deadline_status', '-')}"
            )
        if len(assessments) > 4:
            lines.append(f"  외 {len(assessments) - 4}건")
        return "\n".join(lines)

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
        for row in db.query(LabelPlatformReportEvent.id)
        .order_by(LabelPlatformReportEvent.id.desc())
        .offset(_MAX_REPORTS)
        .all()
    ]
    if event_ids:
        db.query(LabelPlatformReportMessage).filter(LabelPlatformReportMessage.event_id.in_(event_ids)).delete(
            synchronize_session=False
        )
        db.query(LabelPlatformReportEvent).filter(LabelPlatformReportEvent.id.in_(event_ids)).delete(
            synchronize_session=False
        )

    message_ids = [
        row.id
        for row in db.query(LabelPlatformReportMessage.id)
        .order_by(LabelPlatformReportMessage.id.desc())
        .offset(_MAX_CHANNEL_MESSAGES)
        .all()
    ]
    if message_ids:
        db.query(LabelPlatformReportMessage).filter(LabelPlatformReportMessage.id.in_(message_ids)).delete(
            synchronize_session=False
        )


def _dedupe_report_rows(rows: list[LabelPlatformReportEvent], db) -> list[LabelPlatformReportEvent]:
    deduped: list[LabelPlatformReportEvent] = []
    seen_release_batches: set[str] = set()

    for row in rows:
        if row.report_type != "release":
            deduped.append(row)
            continue

        payload = _enrich_release_payload(db, _deserialize_payload(row.payload_json))
        batch_key = _release_batch_key(payload)
        if batch_key and batch_key in seen_release_batches:
            continue
        if batch_key:
            seen_release_batches.add(batch_key)
        deduped.append(row)

    return deduped


def _dedupe_message_rows(rows: list[LabelPlatformReportMessage], db) -> list[LabelPlatformReportMessage]:
    deduped: list[LabelPlatformReportMessage] = []
    seen_release_batches: set[tuple[str, str]] = set()

    for row in rows:
        if row.report_type != "release":
            deduped.append(row)
            continue

        payload = _deserialize_payload(row.payload_json)
        if row.direction == "outbound":
            payload = _enrich_release_payload(db, payload)

        batch_key = _release_batch_key(payload)
        dedupe_key = (row.direction, batch_key) if batch_key else None
        if dedupe_key and dedupe_key in seen_release_batches:
            continue
        if dedupe_key:
            seen_release_batches.add(dedupe_key)
        deduped.append(row)

    return deduped


def _row_to_message(row: LabelPlatformReportMessage, db=None) -> dict[str, Any]:
    payload = _deserialize_payload(row.payload_json)
    if db and row.report_type == "release" and row.direction == "outbound":
        payload = _enrich_release_payload(db, payload)
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


def _row_to_report(row: LabelPlatformReportEvent, db=None) -> dict[str, Any]:
    payload = _deserialize_payload(row.payload_json)
    if db and row.report_type == "release":
        payload = _enrich_release_payload(db, payload)
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
    """Create a report event/message row and return (event_id, report_id).

    The given ``payload`` dict is mutated in place to inject ``report_id`` so the
    caller's payload (already in hand) is sent to the platform with report_id included.
    """
    summary = _build_outbound_summary(report_type, item_ref, payload)
    report_type_label = _report_type_label(report_type)
    now = _now()

    with _LOCK:
        db = SessionLocal()
        try:
            event = LabelPlatformReportEvent(
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

            report_id = f"label-{event.id}"
            if payload is not None:
                payload["report_id"] = report_id

            event.report_id = report_id
            event.payload_json = _serialize_payload(payload)

            message = LabelPlatformReportMessage(
                event_id=event.id,
                direction="outbound",
                sender="라벨agent",
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
            event = db.query(LabelPlatformReportEvent).filter(LabelPlatformReportEvent.id == event_id).first()
            if not event:
                return

            event.status = "전송완료" if success else "플랫폼 보고 대기"
            event.message = message or ("플랫폼 보고 완료" if success else "플랫폼 보고 대기")
            event.updated_at = _now()

            if event.channel_message_id:
                outbound_message = (
                    db.query(LabelPlatformReportMessage)
                    .filter(LabelPlatformReportMessage.id == event.channel_message_id)
                    .first()
                )
                if outbound_message:
                    outbound_message.status = event.status
                    outbound_message.updated_at = event.updated_at

            if success:
                inbound_message = LabelPlatformReportMessage(
                    event_id=event.id,
                    direction="inbound",
                    sender="플랫폼agent",
                    receiver="라벨agent",
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
            row = LabelPlatformReportMessage(
                event_id=None,
                direction="inbound",
                sender="플랫폼agent",
                receiver="라벨agent",
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
                db.query(LabelPlatformReportEvent)
                .filter(LabelPlatformReportEvent.report_type.in_(_VISIBLE_REPORT_TYPES))
                .order_by(LabelPlatformReportEvent.id.desc())
                .limit(_MAX_REPORTS)
                .all()
            )
            raw_message_rows = (
                db.query(LabelPlatformReportMessage)
                .filter(LabelPlatformReportMessage.report_type.in_(_VISIBLE_REPORT_TYPES))
                .order_by(LabelPlatformReportMessage.id.desc())
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
        summary = "최근 수입/수출 보고 없음"
    elif waiting_count:
        summary = f"최근 {len(statuses)}건 중 전송완료 {success_count}건 / 대기 {waiting_count}건"
    else:
        summary = f"최근 {len(statuses)}건 모두 수입/수출 보고 완료"

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
