from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models import LabelRelease
from schemas import (
    IncidentReport,
    LabelReleaseComplete,
    LabelReleaseCreate,
    LabelReleaseOut,
    PackingListSelection,
)
from services.packing_list import build_packing_list_csv_bytes, build_packing_list_xlsx_bytes
from services.platform_sender import send_release_to_platform
from services.release_completion import build_release_platform_send_kwargs, finalize_release_record

router = APIRouter(prefix="/releases", tags=["출고"])


def _normalize_packing_list_format(export_format: str) -> str:
    normalized = (export_format or "csv").strip().lower()
    if normalized not in {"csv", "xlsx"}:
        raise HTTPException(status_code=400, detail="패킹리스트 형식은 csv 또는 xlsx만 가능합니다.")
    return normalized


def _stream_packing_list(releases: list[LabelRelease], export_format: str = "csv") -> StreamingResponse:
    if not releases:
        raise HTTPException(status_code=404, detail="패킹리스트를 생성할 출고완료 건이 없습니다.")

    export_format = _normalize_packing_list_format(export_format)
    release_dates = [row.release_date for row in releases if row.release_date]
    if release_dates:
        from_date = min(release_dates)
        to_date = max(release_dates)
    else:
        from_date = date.today()
        to_date = date.today()

    if export_format == "xlsx":
        file_bytes = build_packing_list_xlsx_bytes(releases, from_date, to_date)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        file_bytes = build_packing_list_csv_bytes(releases, from_date, to_date)
        media_type = "text/csv"

    filename = f"packing_list_{from_date}_{to_date}_{len(releases)}items.{export_format}"
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/", response_model=list[LabelReleaseOut])
def get_releases(db: Session = Depends(get_db)):
    return db.query(LabelRelease).order_by(LabelRelease.created_at.desc()).all()


@router.post("/", response_model=LabelReleaseOut)
def create_release(body: LabelReleaseCreate, db: Session = Depends(get_db)):
    release = LabelRelease(
        label_code=body.label_code,
        release_qty=body.release_qty,
        due_date=body.due_date,
        status="생산중",
    )
    db.add(release)
    db.commit()
    db.refresh(release)

    return release


@router.post("/{release_id}/incident")
def report_incident(
    release_id: int,
    body: IncidentReport,
    db: Session = Depends(get_db),
):
    release = db.query(LabelRelease).filter(LabelRelease.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail="출고 건을 찾을 수 없습니다.")

    return {
        "reported": False,
        "platform_report_skipped": True,
        "label_code": release.label_code,
        "reason": body.reason,
    }


@router.delete("/bulk")
def delete_releases_bulk(ids: list[int], db: Session = Depends(get_db)):
    rows = db.query(LabelRelease).filter(LabelRelease.id.in_(ids)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="삭제할 항목이 없습니다.")
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": len(rows)}


@router.post("/{release_id}/complete", response_model=LabelReleaseOut)
async def complete_release(
    release_id: int,
    body: LabelReleaseComplete = LabelReleaseComplete(),
    db: Session = Depends(get_db),
):
    release = db.query(LabelRelease).filter(LabelRelease.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail="출고 건을 찾을 수 없습니다.")
    release, export_payload = finalize_release_record(
        db,
        release,
        started_at=body.started_at,
        finished_at=body.finished_at,
        release_date=date.today(),
    )

    await send_release_to_platform(**build_release_platform_send_kwargs(release, export_payload))

    return release


@router.get("/packing-list")
def get_packing_list_range(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    export_format: str = Query("csv", alias="format"),
    db: Session = Depends(get_db),
):
    releases = (
        db.query(LabelRelease)
        .filter(
            LabelRelease.status == "출고완료",
            LabelRelease.release_date >= from_date,
            LabelRelease.release_date <= to_date,
        )
        .order_by(LabelRelease.label_code)
        .all()
    )
    if not releases:
        raise HTTPException(status_code=404, detail=f"{from_date} ~ {to_date} 기간 출고완료 건이 없습니다.")

    return _stream_packing_list(releases, export_format)


@router.post("/packing-list/selected")
def get_selected_packing_list(
    body: PackingListSelection,
    export_format: str = Query("csv", alias="format"),
    db: Session = Depends(get_db),
):
    release_ids = list(dict.fromkeys(body.release_ids))
    if not release_ids:
        raise HTTPException(status_code=400, detail="패킹리스트로 추출할 완료 항목을 먼저 체크하세요.")

    releases = (
        db.query(LabelRelease)
        .filter(
            LabelRelease.id.in_(release_ids),
            LabelRelease.status == "출고완료",
        )
        .order_by(LabelRelease.release_date, LabelRelease.label_code, LabelRelease.id)
        .all()
    )

    if not releases:
        raise HTTPException(status_code=404, detail="선택한 출고완료 항목을 찾을 수 없습니다.")
    if len(releases) != len(release_ids):
        raise HTTPException(status_code=400, detail="선택 항목 중 출고완료가 아닌 건이 포함되어 있습니다.")

    return _stream_packing_list(releases, export_format)
