import base64
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models import PackingList, ReportMessage
from schemas import PackingListOut
from services.packing_list_payload import normalize_packing_list_payload
from services.report_message import serialize_payload

router = APIRouter(prefix="/packing-lists", tags=["패킹리스트"])


def _upgrade_legacy_packing_list_entry(db: Session, entry: PackingList) -> PackingList:
    if (entry.content_type or "").startswith("text/"):
        return entry

    records = (
        db.query(ReportMessage)
        .filter(ReportMessage.event_type == "collected_release")
        .order_by(ReportMessage.id.desc())
        .all()
    )

    for record in records:
        payload = serialize_payload(record.payload_json)
        if not isinstance(payload, dict):
            continue

        packing_list = payload.get("packing_list")
        packing_list_id = payload.get("packing_list_id")
        if isinstance(packing_list, dict) and not packing_list_id:
            packing_list_id = packing_list.get("packing_list_id")
        if packing_list_id != entry.id:
            continue

        normalized = normalize_packing_list_payload(packing_list)
        csv_base64 = normalized.get("csv_base64") if isinstance(normalized, dict) else None
        if not csv_base64:
            continue

        try:
            entry.csv_content = base64.b64decode(csv_base64).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            continue

        entry.filename = normalized.get("filename") or entry.filename
        entry.content_type = normalized.get("content_type") or "text/csv"
        db.commit()
        db.refresh(entry)
        return entry

    return entry


@router.get("/", response_model=list[PackingListOut])
def list_packing_lists(
    label_code: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(PackingList)
    if label_code:
        query = query.filter(PackingList.label_code == label_code)
    if company_id:
        query = query.filter(PackingList.company_id == company_id)
    return query.order_by(PackingList.id.desc()).all()


@router.get("/{packing_list_id}/download")
def download_packing_list(packing_list_id: int, db: Session = Depends(get_db)):
    entry = db.query(PackingList).filter(PackingList.id == packing_list_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="패킹리스트를 찾을 수 없습니다.")

    entry = _upgrade_legacy_packing_list_entry(db, entry)

    filename = entry.filename or f"packing_list_{packing_list_id}.csv"
    if (entry.content_type or "").startswith("text/"):
        file_bytes = entry.csv_content.encode("utf-8")
    else:
        try:
            file_bytes = base64.b64decode(entry.csv_content)
        except (ValueError, TypeError):
            raise HTTPException(status_code=500, detail="패킹리스트 원문 복원에 실패했습니다.")

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=entry.content_type or "text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
