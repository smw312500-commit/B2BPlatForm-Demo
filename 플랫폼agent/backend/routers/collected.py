import base64
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, datetime
from database import get_db
from models import CollectedRelease, CompanyInfo, PackingList
from schemas import CollectedReleaseIn, CollectedReleaseOut
from services.packing_list_payload import normalize_packing_list_payload
from services.dispatch_auto import check_and_create_dispatch, create_export_dispatch_from_release_payload
from services.report_message import (
    find_message_by_report_id,
    record_channel_message,
    resolve_channel,
    serialize_payload,
)

router = APIRouter()

COMPANY_TYPE_MAP = {
    "옷감사": 1,
    "케어라벨사": 2,
    "라벨사": 2,
    "지퍼단추사": 3,
    "지퍼사": 3,
    "물류사": 4,
}


def _resolve_company_id(data: CollectedReleaseIn) -> int:
    if data.company_id:
        return data.company_id
    if data.company_type:
        return COMPANY_TYPE_MAP.get(data.company_type, 0)
    return 0


def _is_broken_text(value: Optional[str]) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    return set(text) == {"?"}


def _default_unit(company_id: int) -> Optional[str]:
    if company_id == 1:
        return "yard"
    if company_id == 2:
        return "장"
    if company_id == 3:
        return "개"
    return None


def _normalize_status(value: Optional[str]) -> str:
    if _is_broken_text(value):
        return "출고완료"
    return str(value).strip()


def _normalize_unit(company_id: int, value: Optional[str]) -> Optional[str]:
    if _is_broken_text(value):
        return _default_unit(company_id)
    return str(value).strip()


def _resolve_item_name(body: CollectedReleaseIn, company_name: Optional[str]) -> Optional[str]:
    if not _is_broken_text(body.item_name):
        return str(body.item_name).strip()

    parsed_info = body.parsed_info if isinstance(body.parsed_info, dict) else {}
    parsed_item_name = parsed_info.get("item_name")
    if not _is_broken_text(parsed_item_name):
        return str(parsed_item_name).strip()

    if body.label_code and company_name == "케어라벨사":
        return body.label_code
    return body.label_code


def _format_number(value) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def _format_weight(value) -> str:
    return f"{_format_number(value)}kg"


def _build_release_summary(
    body: CollectedReleaseIn,
    company_name: str,
    item_name: Optional[str],
    qty_text: str,
    due_text: str,
) -> str:
    ai_report = body.ai_report if isinstance(body.ai_report, dict) else None
    if ai_report and ai_report.get("summary"):
        return str(ai_report["summary"])

    completed_count = body.completed_release_count
    completed_qty_total = body.completed_release_qty_total
    if completed_qty_total is None and isinstance(body.completed_release_list, list):
        completed_qty_total = sum(
            int(item.get("release_qty") or 0)
            for item in body.completed_release_list
            if isinstance(item, dict)
        )

    total_weight = body.shipment_total_weight_kg
    if total_weight is None:
        total_weight = body.completed_release_total_weight_kg
    total_boxes = body.shipment_box_count_total

    if not (completed_count or completed_qty_total or total_weight is not None or total_boxes is not None):
        return f"{company_name} 출고 보고 수신. 품목 {item_name or '미기재'}, 수량 {qty_text}, 납기 {due_text}"

    parts = [f"수출 묶음 {_format_number(completed_count or 1)}건 {_format_number(completed_qty_total)}장"]
    details = []
    if total_weight is not None:
        details.append(_format_weight(total_weight))
    if total_boxes is not None:
        details.append(f"{_format_number(total_boxes)}박스")
    if details:
        parts[0] += f" ({', '.join(details)})"
    parts.append(f"대표 품목 {item_name or '미기재'}({body.label_code or '-'})")
    return ". ".join(parts)


def _parse_date(value) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _save_packing_list(
    db: Session,
    body: CollectedReleaseIn,
    record: CollectedRelease,
    company_id: int,
) -> Optional[PackingList]:
    packing_list = normalize_packing_list_payload(body.packing_list)
    if not packing_list:
        return None

    csv_base64 = packing_list.get("csv_base64")
    if not csv_base64:
        return None

    content_type = packing_list.get("content_type")
    try:
        stored_content = base64.b64decode(csv_base64).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return None
    content_type = content_type or "text/csv"

    batch_due_date = _parse_date(body.report_batch_due_date) or _parse_date(body.due_date)

    query = db.query(PackingList).filter(PackingList.company_id == company_id)
    if batch_due_date:
        query = query.filter(PackingList.report_batch_due_date == batch_due_date)
    else:
        query = query.filter(PackingList.label_code == body.label_code)
    entry = query.order_by(PackingList.id.desc()).first()

    if not entry:
        entry = PackingList(company_id=company_id)
        db.add(entry)

    entry.collected_release_id = record.id
    entry.label_code = body.label_code
    entry.report_batch_due_date = batch_due_date
    entry.filename = packing_list.get("filename")
    entry.content_type = content_type
    entry.period_from = _parse_date(packing_list.get("period_from"))
    entry.period_to = _parse_date(packing_list.get("period_to"))
    entry.total_qty = packing_list.get("total_qty")
    entry.total_weight_kg = packing_list.get("total_weight_kg")
    entry.label_code_count = packing_list.get("label_code_count")
    entry.csv_content = stored_content

    db.commit()
    db.refresh(entry)
    return entry


def _attach_packing_list_metadata(payload: dict, packing_list_entry: Optional[PackingList]) -> dict:
    packing_list = normalize_packing_list_payload(payload.get("packing_list"))
    if not isinstance(packing_list, dict):
        return payload

    packing_list_payload = dict(packing_list)
    packing_list_payload.pop("csv_base64", None)
    packing_list_payload.pop("pdf_base64", None)

    if packing_list_entry:
        packing_list_payload["packing_list_id"] = packing_list_entry.id
        packing_list_payload["download_url"] = f"/api/packing-lists/{packing_list_entry.id}/download"

    payload["packing_list"] = packing_list_payload
    if packing_list_entry:
        payload["packing_list_id"] = packing_list_entry.id
        payload["packing_list_download_url"] = f"/api/packing-lists/{packing_list_entry.id}/download"
    return payload


def _enrich(record: CollectedRelease) -> CollectedReleaseOut:
    out = CollectedReleaseOut.from_orm(record)
    if record.company:
        out.company_name = record.company.company_name
    if out.quantity is None:
        out.quantity = None
    return out


@router.post("/collected-release", response_model=CollectedReleaseOut)
@router.post("/release", response_model=CollectedReleaseOut, include_in_schema=False)
async def receive_release(body: CollectedReleaseIn, db: Session = Depends(get_db)):
    if body.report_id:
        existing_message = find_message_by_report_id(db, body.report_id)
        if existing_message:
            existing_payload = serialize_payload(existing_message.payload_json)
            existing_record_id = (
                existing_payload.get("_collected_release_id") if isinstance(existing_payload, dict) else None
            )
            existing_record = (
                db.query(CollectedRelease).filter(CollectedRelease.id == existing_record_id).first()
                if existing_record_id
                else None
            )
            if existing_record:
                out = _enrich(existing_record)
                out.report_id = body.report_id
                out.received = True
                return out

    company_id = _resolve_company_id(body)
    company = db.query(CompanyInfo).filter(CompanyInfo.id == company_id).first()
    company_name = (
        company.company_name
        if company
        else body.company_name
        or body.company_type
        or f"company_{company_id}"
    )

    qty = body.quantity if body.quantity is not None else body.release_qty
    due = body.due_date if body.due_date is not None else body.release_date
    item_name = _resolve_item_name(body, company_name)
    unit = _normalize_unit(company_id, body.unit)
    status = _normalize_status(body.status)

    record = CollectedRelease(
        company_id=company_id,
        item_name=item_name,
        quantity=qty,
        unit=unit,
        due_date=due,
        status=status,
        label_code=body.label_code,
        collected_at=datetime.now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    packing_list_entry = _save_packing_list(db, body, record, company_id)

    related_code = body.label_code or item_name
    qty_text = f"{qty} {unit or ''}".strip() if qty is not None else "수량미상"
    due_text = str(due) if due else "납기미정"
    payload = body.model_dump(mode="json") if hasattr(body, "model_dump") else body.dict()
    payload.update(
        {
            "company_id": company_id,
            "company_name": company_name,
            "company_type": company_name,
            "item_name": item_name,
            "quantity": qty,
            "unit": unit,
            "due_date": str(due) if due else None,
            "status": status,
            "_collected_release_id": record.id,
        }
    )
    payload = _attach_packing_list_metadata(payload, packing_list_entry)
    record_channel_message(
        db,
        channel=resolve_channel(company_id=company_id, company_name=company_name),
        direction="inbound",
        source_agent=company_name,
        target_agent="플랫폼",
        event_type="collected_release",
        title="출고완료 보고 수신",
        summary=_build_release_summary(body, company_name, item_name, qty_text, due_text),
        related_code=related_code,
        payload=payload,
        status=status,
        source_report_id=body.report_id,
    )

    # 3사 통합 완료 보고 또는 3사 개별 완료 체크 → 자동 배차
    if body.label_code:
        dispatch = await create_export_dispatch_from_release_payload(
            db,
            payload=payload,
            source_report_id=body.report_id,
        )
        if not dispatch:
            await check_and_create_dispatch(db, body.label_code, due)

    out = _enrich(record)
    out.report_id = body.report_id
    out.received = True
    return out


@router.get("/collected-release", response_model=List[CollectedReleaseOut])
def list_releases(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    q = db.query(CollectedRelease).order_by(CollectedRelease.collected_at.desc())
    if from_date:
        q = q.filter(CollectedRelease.collected_at >= from_date)
    if to_date:
        q = q.filter(CollectedRelease.collected_at <= to_date + " 23:59:59")
    records = q.all()
    return [_enrich(r) for r in records]
