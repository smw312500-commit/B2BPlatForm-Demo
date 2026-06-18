from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import PackingList, ReportMessage
from schemas import ReportChannelOut, ReportMessageOut
from services.packing_list_payload import normalize_packing_list_payload
from services.report_message import (
    apply_completed_channel_filter,
    dedupe_release_channel_messages,
    get_channel_catalog,
    is_valid_channel,
    serialize_payload,
)

router = APIRouter(prefix="/report-channels", tags=["보고 채널"])


def _enrich_packing_list_payload(db: Session, payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload

    packing_list = normalize_packing_list_payload(payload.get("packing_list"))
    if not isinstance(packing_list, dict):
        return payload

    enriched = dict(payload)
    packing_list_id = enriched.get("packing_list_id") or packing_list.get("packing_list_id")
    if packing_list_id:
        entry = db.query(PackingList).filter(PackingList.id == packing_list_id).first()
        if entry:
            packing_list["packing_list_id"] = entry.id
            packing_list["download_url"] = f"/api/packing-lists/{entry.id}/download"
            packing_list["filename"] = entry.filename or packing_list.get("filename")
            packing_list["content_type"] = entry.content_type or packing_list.get("content_type")
            enriched["packing_list_id"] = entry.id
            enriched["packing_list_download_url"] = f"/api/packing-lists/{entry.id}/download"

    enriched["packing_list"] = packing_list
    return enriched


@router.get("/", response_model=list[ReportChannelOut])
def list_report_channels(
    completed_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    result = []

    for info in get_channel_catalog():
        channel = info["channel"]
        channel_query = db.query(ReportMessage).filter(ReportMessage.channel == channel)
        if completed_only:
            channel_query = apply_completed_channel_filter(channel_query)

        last_message = channel_query.order_by(ReportMessage.created_at.desc(), ReportMessage.id.desc()).first()
        message_count = channel_query.count()

        result.append(
            ReportChannelOut(
                channel=channel,
                label=info["label"],
                counterparty=info["counterparty"],
                message_count=message_count,
                last_message_at=last_message.created_at if last_message else None,
                last_summary=last_message.summary if last_message else None,
                last_direction=last_message.direction if last_message else None,
                last_status=last_message.status if last_message else None,
            )
        )

    return result


@router.get("/{channel}/messages", response_model=list[ReportMessageOut])
def list_report_channel_messages(
    channel: str,
    limit: int = Query(100, ge=1, le=300),
    completed_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    if not is_valid_channel(channel):
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    query = db.query(ReportMessage).filter(ReportMessage.channel == channel)
    if completed_only:
        query = apply_completed_channel_filter(query)

    records = query.order_by(ReportMessage.created_at.desc(), ReportMessage.id.desc()).limit(limit).all()
    records = dedupe_release_channel_messages(records)

    response_items = []
    for record in records:
        payload = serialize_payload(record.payload_json)
        if record.event_type == "collected_release":
            payload = _enrich_packing_list_payload(db, payload)

        response_items.append(
            ReportMessageOut(
                id=record.id,
                channel=record.channel,
                direction=record.direction,
                source_agent=record.source_agent,
                target_agent=record.target_agent,
                event_type=record.event_type,
                related_code=record.related_code,
                title=record.title,
                summary=record.summary,
                payload_json=payload,
                status=record.status,
                created_at=record.created_at,
            )
        )

    return response_items
