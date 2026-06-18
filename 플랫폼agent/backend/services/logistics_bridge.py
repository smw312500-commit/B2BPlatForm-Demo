from __future__ import annotations

import os
from datetime import date
from typing import Any

import httpx
from sqlalchemy.orm import Session

from models import CompanyInfo, Dispatch
from services.dispatch_planner import PORT_CITY_MAP, build_dispatch_plan, get_logistics_availability_from_cache
from services.report_message import record_channel_message

LOGISTICS_API_URL = os.getenv("LOGISTICS_API_URL", "http://localhost:8004")


def _date_from_text(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dispatch_ref(dispatch: Dispatch, company: CompanyInfo | None) -> str:
    return dispatch.cargo_detail or dispatch.label_code or (company.company_name if company else f"dispatch_{dispatch.id}")


def _build_signal_payload(db: Session, dispatch: Dispatch, company: CompanyInfo | None) -> dict[str, Any]:
    cargo_detail = _dispatch_ref(dispatch, company)

    if dispatch.dispatch_type == "import":
        origin_port = dispatch.origin_port
        origin_si = PORT_CITY_MAP.get(origin_port or "") or (company.address_si if company else None)
        return {
            "company_id": dispatch.company_id,
            "company_name": company.company_name if company else f"company_{dispatch.company_id}",
            "origin_si": origin_si,
            "origin_gu": None,
            "destination": dispatch.destination or (company.company_name if company else "공장"),
            "cargo_detail": cargo_detail,
            "weight_kg": _to_float(dispatch.weight_kg),
            "due_date": str(dispatch.due_date) if dispatch.due_date else None,
            "pickup_date": str(dispatch.pickup_date) if dispatch.pickup_date else None,
            "label_code": dispatch.label_code,
            "signal_type": "dispatch",
            "item": cargo_detail,
        }

    return {
        "company_id": dispatch.company_id,
        "company_name": company.company_name if company else f"company_{dispatch.company_id}",
        "origin_si": company.address_si if company else None,
        "origin_gu": company.address_gu if company else None,
        "destination": dispatch.destination or "부산항",
        "cargo_detail": cargo_detail,
        "weight_kg": _to_float(dispatch.weight_kg),
        "due_date": str(dispatch.due_date) if dispatch.due_date else None,
        "pickup_date": str(dispatch.pickup_date) if dispatch.pickup_date else None,
        "label_code": dispatch.label_code,
        "signal_type": "dispatch",
        "item": cargo_detail,
    }


async def _ensure_logistics_delivery(
    db: Session,
    dispatch: Dispatch,
    signal_payload: dict[str, Any],
    dispatch_ref: str,
) -> tuple[int | None, str | None]:
    related_code = dispatch.label_code or dispatch.source_report_id or dispatch_ref

    if dispatch.logistics_delivery_id is not None:
        record_channel_message(
            db,
            channel="logistics",
            direction="outbound",
            source_agent="플랫폼",
            target_agent="물류",
            event_type="dispatch_rematch",
            title="배차 재매칭 요청",
            summary=f"배차 #{dispatch.id} / 기존 물류건 #{dispatch.logistics_delivery_id} 재매칭 요청",
            related_code=related_code,
            payload={"delivery_id": dispatch.logistics_delivery_id, "dispatch_id": dispatch.id},
            status="전송완료",
        )
        return dispatch.logistics_delivery_id, None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(f"{LOGISTICS_API_URL}/api/platform/signal", json=signal_payload)
            response.raise_for_status()
            signal_result = response.json()
    except Exception as exc:
        record_channel_message(
            db,
            channel="logistics",
            direction="outbound",
            source_agent="플랫폼",
            target_agent="물류",
            event_type="platform_signal",
            title="배차 요청",
            summary=f"배차 #{dispatch.id} / 화물 {dispatch_ref} 물류 전송 실패",
            related_code=related_code,
            payload=signal_payload,
            status="전송실패",
        )
        return None, f"물류 등록 실패: {exc}"

    logistics_delivery_id = signal_result.get("delivery_id")
    record_channel_message(
        db,
        channel="logistics",
        direction="outbound",
        source_agent="플랫폼",
        target_agent="물류",
        event_type="platform_signal",
        title="배차 요청",
        summary=f"배차 #{dispatch.id} / 화물 {dispatch_ref} 생성 요청 전송",
        related_code=related_code,
        payload=signal_payload,
        status="전송완료",
    )
    return logistics_delivery_id, None


async def _assign_dispatch_to_logistics(
    logistics_delivery_id: int,
    *,
    driver_id: int,
    vehicle_id: int | None,
    vehicle_plate: str | None,
    pickup_date: date | None,
    empty_return: str | None,
) -> dict[str, Any]:
    params = {"driver_id": driver_id}
    if vehicle_id:
        params["vehicle_id"] = vehicle_id
    if vehicle_plate:
        params["vehicle_plate"] = vehicle_plate
    if pickup_date:
        params["pickup_date"] = str(pickup_date)
    if empty_return:
        params["empty_return"] = empty_return

    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.put(
            f"{LOGISTICS_API_URL}/api/deliveries/{logistics_delivery_id}/assign",
            params=params,
        )
        response.raise_for_status()
        return response.json()


async def register_and_match_dispatch(db: Session, dispatch: Dispatch) -> Dispatch:
    company = dispatch.company or db.query(CompanyInfo).filter(CompanyInfo.id == dispatch.company_id).first()
    dispatch_ref = _dispatch_ref(dispatch, company)
    signal_payload = _build_signal_payload(db, dispatch, company)

    logistics_delivery_id, delivery_error = await _ensure_logistics_delivery(
        db,
        dispatch,
        signal_payload,
        dispatch_ref,
    )
    if not logistics_delivery_id:
        plan = build_dispatch_plan(db, dispatch)
        dispatch.pickup_date = plan.pickup_date or dispatch.pickup_date
        dispatch.empty_return = plan.empty_return
        dispatch.logistics_message = (
            f"{plan.message or '플랫폼 배차 판단 완료'} / "
            f"{delivery_error or '물류 등록 실패'}"
        )
        if plan.driver_id and (plan.vehicle_id or plan.vehicle_plate):
            dispatch.logistics_driver_id = plan.driver_id
            dispatch.driver_name = plan.driver_name
            dispatch.logistics_vehicle_id = plan.vehicle_id
            dispatch.vehicle_plate = plan.vehicle_plate
            dispatch.status = "배차완료"
        else:
            dispatch.logistics_driver_id = None
            dispatch.driver_name = None
            dispatch.logistics_vehicle_id = None
            dispatch.vehicle_plate = plan.vehicle_plate
            dispatch.status = "대기"
        db.commit()
        db.refresh(dispatch)

        record_channel_message(
            db,
            channel="logistics",
            direction="outbound",
            source_agent="플랫폼",
            target_agent="물류",
            event_type="dispatch_planned",
            title="배차 판단 결과",
            summary=dispatch.logistics_message,
            related_code=dispatch.label_code or dispatch.source_report_id or dispatch_ref,
            payload={
                "dispatch_id": dispatch.id,
                "logistics_delivery_id": None,
                "logistics_delivery_error": delivery_error,
                **plan.to_payload(),
            },
            status="전송대기" if dispatch.status == "배차완료" else "검토필요",
        )

        if dispatch.dispatch_type == "export" and dispatch.empty_return:
            record_channel_message(
                db,
                channel="logistics",
                direction="inbound",
                source_agent="물류",
                target_agent="플랫폼",
                event_type="round_trip_result",
                title="공차/귀로 연결 결과 수신",
                summary=dispatch.empty_return,
                related_code=dispatch.label_code or dispatch.source_report_id or dispatch_ref,
                payload={
                    "delivery_id": None,
                    "empty_return": dispatch.empty_return,
                    "logistics_delivery_error": delivery_error,
                },
                status="연결완료" if "연결완료" in dispatch.empty_return else "검토",
            )
        return dispatch

    dispatch.logistics_delivery_id = logistics_delivery_id
    db.commit()

    plan = build_dispatch_plan(db, dispatch)
    dispatch.pickup_date = plan.pickup_date or dispatch.pickup_date
    dispatch.empty_return = plan.empty_return
    dispatch.logistics_message = plan.message

    related_code = dispatch.label_code or dispatch.source_report_id or dispatch_ref
    record_channel_message(
        db,
        channel="logistics",
        direction="outbound",
        source_agent="플랫폼",
        target_agent="물류",
        event_type="dispatch_planned",
        title="배차 판단 결과",
        summary=plan.message or "배차 판단 결과 없음",
        related_code=related_code,
        payload={
            "dispatch_id": dispatch.id,
            "logistics_delivery_id": logistics_delivery_id,
            **plan.to_payload(),
        },
        status="판단완료" if plan.driver_id and (plan.vehicle_id or plan.vehicle_plate) else "검토필요",
    )

    if not (plan.driver_id and (plan.vehicle_id or plan.vehicle_plate)):
        dispatch.logistics_driver_id = None
        dispatch.driver_name = None
        dispatch.logistics_vehicle_id = None
        dispatch.vehicle_plate = plan.vehicle_plate
        dispatch.status = "대기"
        db.commit()
        db.refresh(dispatch)
        return dispatch

    try:
        dispatch_result = await _assign_dispatch_to_logistics(
            logistics_delivery_id,
            driver_id=plan.driver_id,
            vehicle_id=plan.vehicle_id,
            vehicle_plate=plan.vehicle_plate,
            pickup_date=plan.pickup_date,
            empty_return=plan.empty_return,
        )
    except Exception as exc:
        dispatch.logistics_driver_id = None
        dispatch.driver_name = None
        dispatch.logistics_vehicle_id = None
        dispatch.vehicle_plate = None
        dispatch.status = "대기"
        dispatch.logistics_message = f"{plan.message or '플랫폼 배차 판단 완료'} / 물류 배정 반영 실패: {exc}"
        db.commit()
        db.refresh(dispatch)
        return dispatch

    dispatch.pickup_date = _date_from_text(dispatch_result.get("pickup_date")) or plan.pickup_date or dispatch.pickup_date
    dispatch.empty_return = dispatch_result.get("empty_return") or plan.empty_return
    dispatch.logistics_message = plan.message
    dispatch.logistics_driver_id = dispatch_result.get("driver_id") or plan.driver_id
    dispatch.driver_name = dispatch_result.get("driver_name") or plan.driver_name
    dispatch.logistics_vehicle_id = dispatch_result.get("vehicle_id") or plan.vehicle_id
    dispatch.vehicle_plate = dispatch_result.get("vehicle_plate") or plan.vehicle_plate
    dispatch.status = "배차완료"

    db.commit()
    db.refresh(dispatch)

    record_channel_message(
        db,
        channel="logistics",
        direction="inbound",
        source_agent="물류",
        target_agent="플랫폼",
        event_type="dispatch_confirmed",
        title="배차 확정 정보 수신",
        summary=f"{dispatch.driver_name} / {dispatch.vehicle_plate or '차량미상'} 배차 확정",
        related_code=related_code,
        payload=dispatch_result,
        status="배차완료",
    )

    if dispatch.dispatch_type == "export" and dispatch.empty_return:
        record_channel_message(
            db,
            channel="logistics",
            direction="inbound",
            source_agent="물류",
            target_agent="플랫폼",
            event_type="round_trip_result",
            title="공차/귀로 연결 결과 수신",
            summary=dispatch.empty_return,
            related_code=related_code,
            payload={
                "delivery_id": dispatch.logistics_delivery_id,
                "empty_return": dispatch.empty_return,
            },
            status="연결완료" if "연결완료" in dispatch.empty_return else "검토",
        )

    return dispatch


def get_logistics_availability(db: Session) -> dict[str, Any]:
    return get_logistics_availability_from_cache(db)
