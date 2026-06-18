from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from models import Delivery, Driver, PlatformChannelMessage, Vehicle

CHANNEL_NAME = "물류 - 플랫폼"

SIGNAL_TITLES = {
    "schedule": "픽업 요청 수신",
    "reschedule": "납기 위험 화물 알림",
    "dispatch": "배차 요청 수신",
    "round_trip": "귀로배정 후보 요청",
}


def _model_to_payload(model: Any) -> Any:
    if model is None:
        return None
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", exclude_none=True)
    if hasattr(model, "dict"):
        return model.dict(exclude_none=True)
    return model


def _serialize_payload(payload_json: str | None) -> Any:
    if not payload_json:
        return None
    try:
        return json.loads(payload_json)
    except Exception:
        return payload_json


def _join_parts(*parts: str | None) -> str:
    return " / ".join(part for part in parts if part)


def _company_name(company_name: str | None, company_id: int | None = None) -> str:
    if company_name:
        return company_name
    if company_id is not None:
        return f"업체 #{company_id}"
    return "업체 미상"


def _route_text(origin_si: str | None, destination: str | None) -> str:
    if origin_si and destination:
        return f"{origin_si} -> {destination}"
    return destination or origin_si or "경로 미정"


def _delivery_name(delivery: Delivery) -> str:
    return delivery.company_name or f"화물 #{delivery.id}"


def _record_message(
    db: Session,
    *,
    direction: str,
    event_type: str,
    title: str,
    summary: str,
    status: str,
    related_delivery_id: int | None = None,
    payload: Any = None,
) -> dict[str, Any] | None:
    payload_data = _model_to_payload(payload)
    payload_json = None
    if payload_data is not None:
        payload_json = json.dumps(payload_data, ensure_ascii=False, default=str)

    message = PlatformChannelMessage(
        direction=direction,
        event_type=event_type,
        title=title,
        summary=summary,
        status=status,
        related_delivery_id=related_delivery_id,
        payload_json=payload_json,
    )

    try:
        db.add(message)
        db.commit()
        db.refresh(message)
        return serialize_message(message)
    except Exception:
        db.rollback()
        return None


def serialize_message(message: PlatformChannelMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "direction": message.direction,
        "event_type": message.event_type,
        "title": message.title,
        "summary": message.summary,
        "status": message.status,
        "related_delivery_id": message.related_delivery_id,
        "payload": _serialize_payload(message.payload_json),
        "created_at": message.created_at.isoformat(sep=" ", timespec="seconds") if message.created_at else None,
    }


def list_channel_messages(db: Session, limit: int = 30) -> list[dict[str, Any]]:
    records = (
        db.query(PlatformChannelMessage)
        .filter(PlatformChannelMessage.event_type != "driver_sync")
        .order_by(PlatformChannelMessage.created_at.desc(), PlatformChannelMessage.id.desc())
        .limit(limit)
        .all()
    )
    records.reverse()
    return [serialize_message(record) for record in records]


def log_signal_received(db: Session, signal: Any, delivery_id: int | None = None) -> dict[str, Any] | None:
    payload = _model_to_payload(signal) or {}
    signal_type = payload.get("signal_type") or "platform_signal"
    title = SIGNAL_TITLES.get(signal_type, "플랫폼 신호 수신")

    detail = payload.get("cargo_detail") or payload.get("item") or payload.get("label_code")
    qty = payload.get("qty")
    qty_text = f"수량 {qty}" if qty is not None else None

    summary = _join_parts(
        f"{_company_name(payload.get('company_name'), payload.get('company_id'))} {title}",
        _route_text(payload.get("origin_si"), payload.get("destination")),
        f"납기 {payload.get('due_date')}" if payload.get("due_date") else None,
        f"픽업 {payload.get('pickup_date')}" if payload.get("pickup_date") else None,
        f"화물 {detail}" if detail else None,
        qty_text,
        f"사유 {payload.get('reason')}" if payload.get("reason") else None,
    )

    return _record_message(
        db,
        direction="inbound",
        event_type=signal_type,
        title=title,
        summary=summary,
        status="수신완료",
        related_delivery_id=delivery_id,
        payload=payload,
    )


def log_dispatch_review(
    db: Session,
    delivery: Delivery,
    pickup_date: Any,
    travel_label: str,
) -> dict[str, Any] | None:
    summary = _join_parts(
        f"{_delivery_name(delivery)} 배차 검토중",
        _route_text(delivery.origin_si, delivery.destination),
        f"목표 픽업 {pickup_date}" if pickup_date else None,
        travel_label,
        "가용 기사 없음",
    )
    return _record_message(
        db,
        direction="outbound",
        event_type="dispatch_review",
        title="배차 검토 보고",
        summary=summary,
        status="배차검토중",
        related_delivery_id=delivery.id,
        payload={
            "delivery_id": delivery.id,
            "pickup_date": str(pickup_date) if pickup_date else None,
            "travel": travel_label,
        },
    )


def log_dispatch_confirmed(
    db: Session,
    delivery: Delivery,
    driver: Driver,
    vehicle: Vehicle | None,
    pickup_date: Any,
    travel_label: str,
) -> dict[str, Any] | None:
    vehicle_label = vehicle.plate_no if vehicle else "차량 미지정"
    summary = _join_parts(
        f"{driver.name} / {vehicle_label} 배차 확정",
        _route_text(delivery.origin_si, delivery.destination),
        f"픽업 {pickup_date}" if pickup_date else None,
        travel_label,
    )
    return _record_message(
        db,
        direction="outbound",
        event_type="dispatch_confirmed",
        title="배차 확정 보고",
        summary=summary,
        status="배차완료",
        related_delivery_id=delivery.id,
        payload={
            "delivery_id": delivery.id,
            "driver_id": driver.id,
            "driver_name": driver.name,
            "vehicle_id": vehicle.id if vehicle else None,
            "vehicle_plate": vehicle.plate_no if vehicle else None,
            "pickup_date": str(pickup_date) if pickup_date else None,
            "travel": travel_label,
        },
    )


def log_round_trip_result(db: Session, delivery: Delivery) -> dict[str, Any] | None:
    connected = bool(delivery.empty_return and "연결완료" in delivery.empty_return)
    summary = _join_parts(
        f"{_delivery_name(delivery)} 귀로 판단",
        _route_text(delivery.origin_si, delivery.destination),
        delivery.empty_return or "미정",
    )
    return _record_message(
        db,
        direction="outbound",
        event_type="round_trip_result",
        title="귀로 배정 판단",
        summary=summary,
        status="귀로배정 연결완료" if connected else "빈차귀환",
        related_delivery_id=delivery.id,
        payload={
            "delivery_id": delivery.id,
            "empty_return": delivery.empty_return,
        },
    )


def log_completion_report(
    db: Session,
    delivery: Delivery,
    delivered_to_platform: bool,
) -> dict[str, Any] | None:
    summary = _join_parts(
        f"{_delivery_name(delivery)} 배송 완료 보고",
        delivery.destination,
        f"완료일 {delivery.complete_date}" if delivery.complete_date else None,
        None if delivered_to_platform else "플랫폼 완료 API 재전송 필요",
    )
    return _record_message(
        db,
        direction="outbound",
        event_type="delivery_complete",
        title="배송 완료 보고",
        summary=summary,
        status="배송완료" if delivered_to_platform else "플랫폼 보고 대기",
        related_delivery_id=delivery.id,
        payload={
            "delivery_id": delivery.id,
            "company_id": delivery.company_id,
            "destination": delivery.destination,
            "complete_date": str(delivery.complete_date) if delivery.complete_date else None,
            "status": "완료",
        },
    )
