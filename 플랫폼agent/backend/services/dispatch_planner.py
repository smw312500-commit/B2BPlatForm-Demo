from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import CompanyInfo, Dispatch, LogisticsDriverCache, ReportMessage
from services.report_message import serialize_payload

TRAVEL_HOURS = {
    "부산시": {"부산항": 1, "인천항": 6},
    "서울시": {"인천항": 1, "부산항": 5},
    "인천시": {"인천항": 0.5, "부산항": 5},
}
DEFAULT_TRAVEL_HOURS = 24.0
FREE_PORT_STORAGE_DAYS = 2
PORT_CITY_MAP = {
    "부산항": "부산시",
    "인천항": "인천시",
}
PORT_BASE_REGION_MAP = {
    "부산항": "부산권",
    "인천항": "수도권",
}


@dataclass
class DispatchPlan:
    status: str
    pickup_date: date | None
    driver_id: int | None = None
    driver_name: str | None = None
    vehicle_id: int | None = None
    vehicle_plate: str | None = None
    empty_return: str | None = None
    message: str | None = None
    available_driver_count: int = 0
    available_vehicle_count: int = 0
    matched_by: str = "platform_dispatch_planner"

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "pickup_date": str(self.pickup_date) if self.pickup_date else None,
            "driver_id": self.driver_id,
            "driver_name": self.driver_name,
            "vehicle_id": self.vehicle_id,
            "vehicle_plate": self.vehicle_plate,
            "empty_return": self.empty_return,
            "message": self.message,
            "available_driver_count": self.available_driver_count,
            "available_vehicle_count": self.available_vehicle_count,
            "matched_by": self.matched_by,
        }


@dataclass
class RoundTripCandidate:
    summary: str
    payload: dict[str, Any] | None = None
    arrival_date: date | None = None
    free_storage_until: date | None = None
    destination_port: str | None = None
    preferred_origin_si: str | None = None
    preferred_base_region: str | None = None
    active: bool = False


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> date | None:
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


def _normalize_port(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if "부산" in text or "busan" in lowered or "pusan" in lowered:
        return "부산항"
    if "인천" in text or "incheon" in lowered:
        return "인천항"
    return text


def _company_matches(payload: dict[str, Any], dispatch_company_id: int, dispatch_company_name: str | None) -> bool:
    payload_company_id = _to_int(payload.get("company_id"))
    if payload_company_id is not None:
        return payload_company_id == dispatch_company_id

    company_name = str(
        payload.get("company_name")
        or payload.get("receiving_company")
        or payload.get("company_id")
        or ""
    ).strip()
    if not company_name or not dispatch_company_name:
        return False
    return dispatch_company_name in company_name or company_name in dispatch_company_name


def _capacity_rank(driver: LogisticsDriverCache, required_weight: float | None) -> tuple[int, float]:
    if required_weight is None:
        return (2, 0.0)
    max_weight = _to_float(driver.vehicle_max_weight)
    if max_weight is None:
        return (1, 999999.0)
    if max_weight < required_weight:
        return (0, 999999.0)
    return (2, max_weight - required_weight)


def _travel_hours(origin_si: str | None, destination: str | None) -> float:
    if not origin_si or not destination:
        return DEFAULT_TRAVEL_HOURS
    return TRAVEL_HOURS.get(origin_si, {}).get(destination, DEFAULT_TRAVEL_HOURS)


def calc_pickup_date(due_date: date | None, origin_si: str | None, destination: str | None) -> date | None:
    if not due_date:
        return None
    hours = _travel_hours(origin_si, destination)
    buffer_days = 1 if hours < 3 else 2
    return due_date - timedelta(days=buffer_days)


def get_logistics_availability_from_cache(db: Session) -> dict[str, Any]:
    records = db.query(LogisticsDriverCache).order_by(LogisticsDriverCache.driver_id.asc()).all()

    available_drivers = []
    available_vehicles = []
    last_synced_at = None

    for record in records:
        if record.last_synced_at and (last_synced_at is None or record.last_synced_at > last_synced_at):
            last_synced_at = record.last_synced_at

        if record.status != "가용":
            continue

        available_drivers.append(
            {
                "id": record.driver_id,
                "name": record.name or f"기사#{record.driver_id}",
                "phone": record.phone,
                "location_si": record.location_si,
                "location_gu": record.location_gu,
                "base_region": record.base_region,
                "status": record.status,
                "vehicle_id": record.vehicle_id,
                "vehicle_plate": record.vehicle_plate,
                "vehicle_type": record.vehicle_type,
                "vehicle_max_weight": _to_float(record.vehicle_max_weight),
                "current_delivery_id": record.current_delivery_id,
                "current_destination": record.current_destination,
                "estimated_arrival": record.estimated_arrival,
                "last_synced_at": record.last_synced_at,
            }
        )

        if record.vehicle_id or record.vehicle_plate:
            available_vehicles.append(
                {
                    "id": record.vehicle_id,
                    "driver_id": record.driver_id,
                    "driver_name": record.name,
                    "plate_no": record.vehicle_plate,
                    "max_weight": _to_float(record.vehicle_max_weight),
                    "vehicle_type": record.vehicle_type,
                }
            )

    return {
        "total_driver_count": len(records),
        "available_driver_count": len(available_drivers),
        "available_vehicle_count": len(available_vehicles),
        "drivers": available_drivers,
        "vehicles": available_vehicles,
        "last_synced_at": last_synced_at,
    }


def _find_round_trip_candidate(db: Session, dispatch: Dispatch, company: CompanyInfo | None) -> RoundTripCandidate:
    destination_port = _normalize_port(dispatch.destination)
    if not destination_port:
        return RoundTripCandidate(summary="빈차귀환 - 항구 정보 없음")

    messages = (
        db.query(ReportMessage)
        .filter(ReportMessage.event_type == "agent_report_import")
        .order_by(ReportMessage.created_at.desc())
        .all()
    )

    candidates: list[RoundTripCandidate] = []
    company_name = company.company_name if company else None

    for message in messages:
        payload = serialize_payload(message.payload_json)
        if not isinstance(payload, dict):
            continue
        if not _company_matches(payload, dispatch.company_id, company_name):
            continue

        import_port = _normalize_port(
            payload.get("port_of_discharge")
            or payload.get("receiving_port")
            or payload.get("final_place_of_delivery")
        )
        if import_port != destination_port:
            continue

        arrival_date = _to_date(payload.get("arrival_date") or payload.get("due_date"))
        if dispatch.due_date and arrival_date and arrival_date > dispatch.due_date:
            continue

        free_storage_until = arrival_date + timedelta(days=FREE_PORT_STORAGE_DAYS) if arrival_date else None
        active = bool(
            dispatch.due_date
            and arrival_date
            and free_storage_until
            and dispatch.due_date <= free_storage_until
        )

        bl_number = payload.get("bl_number") or "-"
        arrival_text = str(arrival_date) if arrival_date else "도착일 미확인"
        due_text = str(dispatch.due_date) if dispatch.due_date else "수출일 미확인"

        if active:
            summary = f"연결완료 - {arrival_text} {destination_port} 수입 BL {bl_number} + {due_text} 수출건"
        elif free_storage_until:
            summary = f"연결보류 - {arrival_text} {destination_port} 수입 BL {bl_number} 무료보관 {free_storage_until} 까지"
        else:
            summary = f"연결보류 - {destination_port} 수입 BL {bl_number} 도착일 미확인"

        candidates.append(
            RoundTripCandidate(
                summary=summary,
                payload=payload,
                arrival_date=arrival_date,
                free_storage_until=free_storage_until,
                destination_port=destination_port,
                preferred_origin_si=PORT_CITY_MAP.get(destination_port),
                preferred_base_region=PORT_BASE_REGION_MAP.get(destination_port),
                active=active,
            )
        )

    active_candidates = [candidate for candidate in candidates if candidate.active]
    if not active_candidates:
        return RoundTripCandidate(
            summary=f"빈차귀환 - {destination_port} 기준 무료보관 내 수입 회수건 없음",
            destination_port=destination_port,
        )

    def _sort_key(candidate: RoundTripCandidate) -> tuple[int, int, int]:
        active_rank = 0 if candidate.active else 1
        if dispatch.due_date and candidate.arrival_date:
            date_gap = abs((dispatch.due_date - candidate.arrival_date).days)
            arrival_rank = -candidate.arrival_date.toordinal()
        else:
            date_gap = 999999
            arrival_rank = 0
        return (active_rank, date_gap, arrival_rank)

    return sorted(active_candidates, key=_sort_key)[0]


def _list_available_candidates(
    db: Session,
    dispatch: Dispatch,
    company: CompanyInfo | None,
    *,
    preferred_origin_si: str | None = None,
    preferred_base_region: str | None = None,
    target_pickup_date: date | None = None,
) -> list[LogisticsDriverCache]:
    required_weight = _to_float(dispatch.weight_kg)
    keep_current_driver = dispatch.status == "배차완료" and dispatch.logistics_driver_id is not None
    status_filter = LogisticsDriverCache.status == "가용"
    if keep_current_driver:
        status_filter = or_(
            LogisticsDriverCache.status == "가용",
            LogisticsDriverCache.driver_id == dispatch.logistics_driver_id,
        )

    candidates = (
        db.query(LogisticsDriverCache)
        .filter(status_filter)
        .order_by(LogisticsDriverCache.driver_id.asc())
        .all()
    )

    candidates = [driver for driver in candidates if driver.vehicle_id or driver.vehicle_plate]
    if target_pickup_date:
        busy_driver_ids = {
            driver_id
            for (driver_id,) in (
                db.query(Dispatch.logistics_driver_id)
                .filter(
                    Dispatch.id != dispatch.id,
                    Dispatch.logistics_driver_id.isnot(None),
                    Dispatch.pickup_date == target_pickup_date,
                    Dispatch.status.in_(["배차완료", "운행중"]),
                )
                .all()
            )
        }
        candidates = [
            driver
            for driver in candidates
            if driver.driver_id not in busy_driver_ids or driver.driver_id == dispatch.logistics_driver_id
        ]
    if not candidates:
        return []

    def _sort_key(driver: LogisticsDriverCache) -> tuple[int, int, int, int, int, float, int]:
        capacity_rank, over_capacity = _capacity_rank(driver, required_weight)
        current_assigned = 1 if dispatch.logistics_driver_id == driver.driver_id else 0
        same_company_si = 1 if company and company.address_si and driver.location_si == company.address_si else 0
        same_company_gu = 1 if company and company.address_gu and driver.location_gu == company.address_gu else 0
        same_company_base = 1 if company and company.address_gu and driver.base_region == company.address_gu else 0

        if preferred_origin_si:
            same_port_si = 1 if driver.location_si == preferred_origin_si else 0
            same_port_base = 1 if preferred_base_region and driver.base_region == preferred_base_region else 0
            return (
                -current_assigned,
                -capacity_rank,
                -same_port_si,
                -same_port_base,
                -same_company_si,
                over_capacity,
                driver.driver_id,
            )

        return (
            -current_assigned,
            -capacity_rank,
            -same_company_si,
            -same_company_gu,
            -same_company_base,
            over_capacity,
            driver.driver_id,
        )

    ranked = sorted(candidates, key=_sort_key)
    best_capacity_rank = _capacity_rank(ranked[0], required_weight)[0] if ranked else 0
    if best_capacity_rank == 0:
        return []
    return ranked


def _company_destination_label(company: CompanyInfo | None, dispatch: Dispatch) -> str:
    if company:
        region = " ".join(part for part in [company.address_si, company.address_gu] if part)
        return f"{company.company_name}({region})" if region else company.company_name
    return dispatch.destination or f"company_{dispatch.company_id}"


def _driver_header(driver: LogisticsDriverCache) -> str:
    name = driver.name or f"기사#{driver.driver_id}"
    phone = driver.phone or "전화번호 미등록"
    return f"{name} 기사 / {phone} / ID {driver.driver_id}"


def _build_export_message(
    selected: LogisticsDriverCache,
    dispatch: Dispatch,
    company: CompanyInfo | None,
    pickup_date: date | None,
    round_trip: RoundTripCandidate,
) -> str:
    company_label = _company_destination_label(company, dispatch)
    pickup_text = str(pickup_date) if pickup_date else "일정 미확정"
    due_text = str(dispatch.due_date) if dispatch.due_date else pickup_text
    destination_port = round_trip.destination_port or dispatch.destination or "항구 미확인"

    lines = [_driver_header(selected)]

    if round_trip.active:
        lines.append(f"{pickup_text} {destination_port} 출발 수입품 회수")
        lines.append(f"{pickup_text} {company_label} 도착")
        lines.append(f"{due_text} 수출물건 {destination_port} 입고")
        return "\n".join(lines)

    origin_label = " ".join(part for part in [selected.location_si, selected.location_gu] if part) or "기사 현재 위치"
    lines.append(f"{pickup_text} {origin_label} 출발")
    lines.append(f"{pickup_text} {company_label} 집하")
    lines.append(f"{due_text} 수출물건 {dispatch.destination or '도착지 미확인'} 입고")
    return "\n".join(lines)


def _build_import_message(
    selected: LogisticsDriverCache,
    dispatch: Dispatch,
    company: CompanyInfo | None,
    pickup_date: date | None,
) -> str:
    company_label = _company_destination_label(company, dispatch)
    pickup_text = str(pickup_date) if pickup_date else "일정 미확정"
    lines = [_driver_header(selected)]
    if dispatch.origin_port:
        lines.append(f"{pickup_text} {dispatch.origin_port} 출발 수입품 회수")
    else:
        lines.append(f"{pickup_text} 수입품 회수")
    lines.append(f"{pickup_text} {company_label} 도착")
    return "\n".join(lines)


def _build_import_summary(dispatch: Dispatch, company: CompanyInfo | None, pickup_date: date | None) -> str:
    pickup_text = str(pickup_date) if pickup_date else "일정 미확정"
    company_label = _company_destination_label(company, dispatch)
    if dispatch.origin_port:
        return f"수입회수 - {pickup_text} {dispatch.origin_port} -> {company_label}"
    return f"수입회수 - {pickup_text} {company_label} 입고 예정"


def _build_import_plan(db: Session, dispatch: Dispatch, company: CompanyInfo | None) -> DispatchPlan:
    pickup_date = dispatch.pickup_date or dispatch.due_date
    preferred_origin_si = PORT_CITY_MAP.get(dispatch.origin_port or "")
    preferred_base_region = PORT_BASE_REGION_MAP.get(dispatch.origin_port or "")

    availability = get_logistics_availability_from_cache(db)
    available_candidates = _list_available_candidates(
        db,
        dispatch,
        company,
        preferred_origin_si=preferred_origin_si,
        preferred_base_region=preferred_base_region,
        target_pickup_date=pickup_date,
    )

    if not available_candidates:
        if dispatch.origin_port:
            message = f"{dispatch.origin_port} 기준 가용 기사 또는 적재 가능 차량이 없음"
        else:
            message = "수입 회수 출발지 정보가 부족하거나 가용 기사가 없음"
        return DispatchPlan(
            status="대기",
            pickup_date=pickup_date,
            empty_return=_build_import_summary(dispatch, company, pickup_date),
            message=message,
            available_driver_count=availability["available_driver_count"],
            available_vehicle_count=availability["available_vehicle_count"],
        )

    selected = available_candidates[0]
    return DispatchPlan(
        status="배차완료",
        pickup_date=pickup_date,
        driver_id=selected.driver_id,
        driver_name=selected.name,
        vehicle_id=selected.vehicle_id,
        vehicle_plate=selected.vehicle_plate,
        empty_return=_build_import_summary(dispatch, company, pickup_date),
        message=_build_import_message(selected, dispatch, company, pickup_date),
        available_driver_count=availability["available_driver_count"],
        available_vehicle_count=availability["available_vehicle_count"],
    )


def _build_export_plan(db: Session, dispatch: Dispatch, company: CompanyInfo | None) -> DispatchPlan:
    round_trip = _find_round_trip_candidate(db, dispatch, company)
    if round_trip.active and dispatch.due_date:
        pickup_date = dispatch.due_date
    elif dispatch.pickup_date and not dispatch.due_date:
        pickup_date = dispatch.pickup_date
    else:
        pickup_date = calc_pickup_date(
            dispatch.due_date,
            company.address_si if company else None,
            dispatch.destination,
        )

    availability = get_logistics_availability_from_cache(db)
    available_candidates = _list_available_candidates(
        db,
        dispatch,
        company,
        preferred_origin_si=round_trip.preferred_origin_si if round_trip.active else None,
        preferred_base_region=round_trip.preferred_base_region if round_trip.active else None,
        target_pickup_date=pickup_date,
    )

    if not available_candidates:
        if round_trip.active and round_trip.preferred_origin_si:
            message = f"{round_trip.destination_port or '항구'} 회수 연계는 가능하지만 {round_trip.preferred_origin_si} 기준 가용 기사 없음"
        elif availability["available_driver_count"] > 0 and availability["available_vehicle_count"] == 0:
            message = "가용 기사 정보는 있으나 차량 정보가 없어 배차를 확정할 수 없음"
        else:
            message = "가용 기사 또는 적재 가능한 차량이 없어 배차를 확정할 수 없음"
        return DispatchPlan(
            status="대기",
            pickup_date=pickup_date,
            empty_return=round_trip.summary,
            message=message,
            available_driver_count=availability["available_driver_count"],
            available_vehicle_count=availability["available_vehicle_count"],
        )

    selected = available_candidates[0]
    return DispatchPlan(
        status="배차완료",
        pickup_date=pickup_date,
        driver_id=selected.driver_id,
        driver_name=selected.name,
        vehicle_id=selected.vehicle_id,
        vehicle_plate=selected.vehicle_plate,
        empty_return=round_trip.summary,
        message=_build_export_message(selected, dispatch, company, pickup_date, round_trip),
        available_driver_count=availability["available_driver_count"],
        available_vehicle_count=availability["available_vehicle_count"],
    )


def build_dispatch_plan(db: Session, dispatch: Dispatch) -> DispatchPlan:
    company = dispatch.company or db.query(CompanyInfo).filter(CompanyInfo.id == dispatch.company_id).first()
    if dispatch.dispatch_type == "import":
        return _build_import_plan(db, dispatch, company)
    return _build_export_plan(db, dispatch, company)
