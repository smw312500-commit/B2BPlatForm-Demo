from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from models import CollectedRelease, CompanyInfo, Dispatch, ReportMessage
from services.logistics_bridge import register_and_match_dispatch
from services.report_message import serialize_payload

PRODUCER_IDS = {1, 2, 3}
DEFAULT_EXPORT_PORT = "부산항"
COMPANY_ID_BY_NAME = {
    "옷감사": 1,
    "옷감": 1,
    "케어라벨사": 2,
    "케어라벨": 2,
    "라벨사": 2,
    "라벨": 2,
    "지퍼단추사": 3,
    "지퍼단추": 3,
    "지퍼": 3,
}


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


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_quantity(value: Any, unit: str) -> str | None:
    quantity = _to_float(value)
    clean_unit = str(unit or "").strip()
    if quantity is None or not clean_unit:
        return None
    if quantity.is_integer():
        return f"{int(quantity):,}{clean_unit}"
    return f"{quantity:,.1f}".rstrip("0").rstrip(".") + clean_unit


def _resolve_company_id_from_text(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    for key, company_id in COMPANY_ID_BY_NAME.items():
        if key in text:
            return company_id
    return None


def _completed_company_ids(payload: dict[str, Any]) -> set[int]:
    completed = set()
    payload_company_id = _resolve_company_id_from_text(payload.get("company_id"))
    if payload_company_id:
        completed.add(payload_company_id)

    for item in payload.get("completed_release_list") or []:
        if not isinstance(item, dict):
            continue
        company_id = (
            _resolve_company_id_from_text(item.get("company_id"))
            or _resolve_company_id_from_text(item.get("company_name"))
            or _resolve_company_id_from_text(item.get("company_type"))
        )
        if company_id:
            completed.add(company_id)

    return completed


def _resolve_export_port(db: Session, label_code: str | None) -> str:
    if not label_code:
        return DEFAULT_EXPORT_PORT

    messages = (
        db.query(ReportMessage)
        .filter(ReportMessage.event_type == "collected_release")
        .order_by(ReportMessage.created_at.desc())
        .all()
    )
    for message in messages:
        payload = serialize_payload(message.payload_json)
        if not isinstance(payload, dict):
            continue
        if str(payload.get("label_code") or "").strip() != label_code:
            continue
        export_port = _normalize_port(payload.get("export_port"))
        if export_port:
            return export_port
    return DEFAULT_EXPORT_PORT


async def create_export_dispatch_from_release_payload(
    db: Session,
    *,
    payload: dict[str, Any],
    source_report_id: str | None,
) -> list[Dispatch]:
    label_code = str(payload.get("label_code") or "").strip()
    due_date = _to_date(
        payload.get("due_date")
        or payload.get("report_batch_due_date")
        or payload.get("release_date")
    )
    if not label_code or not due_date:
        return []

    completed_companies = _completed_company_ids(payload)
    completed_count = _to_float(payload.get("completed_release_count")) or 0
    if not PRODUCER_IDS.issubset(completed_companies) and completed_count < len(PRODUCER_IDS):
        return []

    release_items = [
        item for item in (payload.get("completed_release_list") or [])
        if isinstance(item, dict)
    ]
    if not release_items:
        release_items = [payload]

    created_or_existing: list[Dispatch] = []
    export_port = _normalize_port(payload.get("export_port")) or _resolve_export_port(db, label_code)
    item_name = str(payload.get("item_name") or "").strip()

    for item in release_items:
        company_id = (
            _resolve_company_id_from_text(item.get("company_id"))
            or _resolve_company_id_from_text(item.get("company_name"))
            or _resolve_company_id_from_text(item.get("company_type"))
            or _resolve_company_id_from_text(payload.get("company_id"))
            or 2
        )
        if company_id not in PRODUCER_IDS:
            continue

        item_due_date = _to_date(item.get("due_date")) or due_date
        company_report_id = f"{source_report_id}:export:{company_id}" if source_report_id else None
        existing = None
        if company_report_id:
            existing = (
                db.query(Dispatch)
                .filter(
                    Dispatch.dispatch_type == "export",
                    Dispatch.source_report_id == company_report_id,
                )
                .first()
            )
        if not existing:
            existing = (
                db.query(Dispatch)
                .filter(
                    Dispatch.dispatch_type == "export",
                    Dispatch.label_code == label_code,
                    Dispatch.due_date == item_due_date,
                    Dispatch.company_id == company_id,
                )
                .first()
            )
        if existing:
            created_or_existing.append(existing)
            continue

        company_name = str(item.get("company_name") or "").strip()
        quantity = _to_float(
            item.get("release_qty")
            or item.get("quantity")
            or payload.get("completed_release_qty_total")
            or payload.get("quantity")
        )
        unit = str(item.get("unit") or payload.get("unit") or "").strip()
        quantity_text = _format_quantity(quantity, unit)
        qty_text = f" / {quantity_text}" if quantity_text else ""
        cargo_detail = f"{label_code} {company_name or item_name or '출고품'}{qty_text}".strip()[:200]
        weight_kg = _to_float(
            item.get("weight_kg")
            or item.get("product_weight_kg")
            or (
                payload.get("label_weight_kg")
                if company_id == 2
                else payload.get("fabric_weight_kg")
                if company_id == 1
                else payload.get("zipper_button_weight_kg")
            )
            or payload.get("shipment_total_weight_kg")
            or (payload.get("packing_list") or {}).get("total_weight_kg")
        )

        dispatch = Dispatch(
            label_code=label_code,
            company_id=company_id,
            dispatch_type="export",
            source_report_id=company_report_id,
            destination=export_port,
            cargo_detail=cargo_detail,
            weight_kg=weight_kg,
            due_date=item_due_date,
            pickup_date=item_due_date,
            status="대기",
        )
        db.add(dispatch)
        db.commit()
        db.refresh(dispatch)

        await register_and_match_dispatch(db, dispatch)
        created_or_existing.append(dispatch)

    return created_or_existing


async def check_and_create_dispatch(db: Session, label_code: str, due_date: date | None):
    records = (
        db.query(CollectedRelease)
        .filter(
            CollectedRelease.label_code == label_code,
            CollectedRelease.status == "출고완료",
        )
        .all()
    )

    completed_companies = {record.company_id for record in records}
    if not PRODUCER_IDS.issubset(completed_companies):
        return

    existing = (
        db.query(Dispatch)
        .filter(
            Dispatch.dispatch_type == "export",
            Dispatch.label_code == label_code,
        )
        .first()
    )
    if existing:
        return

    pickup_date = due_date - timedelta(days=2) if due_date else None
    export_port = _resolve_export_port(db, label_code)

    dispatch = Dispatch(
        label_code=label_code,
        company_id=2,
        dispatch_type="export",
        destination=export_port,
        cargo_detail=label_code,
        due_date=due_date,
        pickup_date=pickup_date,
        status="대기",
    )
    db.add(dispatch)
    db.commit()
    db.refresh(dispatch)

    await register_and_match_dispatch(db, dispatch)


async def create_import_dispatch_from_report(
    db: Session,
    *,
    company_id: int,
    payload: dict[str, Any],
    source_report_id: str | None,
) -> Dispatch | None:
    if company_id not in PRODUCER_IDS:
        return None

    company = db.query(CompanyInfo).filter(CompanyInfo.id == company_id).first()
    arrival_date = _to_date(payload.get("arrival_date") or payload.get("due_date"))
    if not arrival_date:
        return None

    cargo_detail = str(
        payload.get("material_display_name")
        or payload.get("material")
        or payload.get("bl_number")
        or "수입품"
    ).strip()
    origin_port = _normalize_port(
        payload.get("port_of_discharge")
        or payload.get("receiving_port")
        or payload.get("final_place_of_delivery")
    )
    destination = str(
        payload.get("receiving_company_location")
        or (company.company_name if company else payload.get("company_name"))
        or "공장"
    ).strip()[:20]
    weight_kg = payload.get("weight_kg")

    if source_report_id:
        existing = (
            db.query(Dispatch)
            .filter(
                Dispatch.dispatch_type == "import",
                Dispatch.source_report_id == source_report_id,
            )
            .first()
        )
        if existing:
            return existing

    existing = (
        db.query(Dispatch)
        .filter(
            Dispatch.dispatch_type == "import",
            Dispatch.company_id == company_id,
            Dispatch.due_date == arrival_date,
            Dispatch.destination == destination,
            Dispatch.cargo_detail == cargo_detail,
            Dispatch.origin_port == origin_port,
        )
        .first()
    )
    if existing:
        return existing

    dispatch = Dispatch(
        company_id=company_id,
        dispatch_type="import",
        source_report_id=source_report_id,
        origin_port=origin_port,
        destination=destination,
        cargo_detail=cargo_detail,
        weight_kg=weight_kg,
        due_date=arrival_date,
        pickup_date=arrival_date,
        status="대기",
    )
    db.add(dispatch)
    db.commit()
    db.refresh(dispatch)

    await register_and_match_dispatch(db, dispatch)
    return dispatch
