import io
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from models import ZipperRelease, ZipperStock
from schemas import ReleaseCreate, ReleaseComplete, ReleaseOut, IncidentReport
from services.platform_sender import send_release_to_platform
from services.platform_reporter import report_schedule, report_reschedule
from services.ai_agent import get_item_type, RAW_MATERIAL_MAP

# 품목코드 → 영문명 / HS Code
_TYPE_INFO = {
    "WOOD":    ("WOODEN BUTTON",  "9606.21"),
    "PLASTIC": ("PLASTIC BUTTON", "9606.21"),
    "METAL":   ("METAL BUTTON",   "9606.21"),
    "ZIPPER":  ("ZIPPER",         "9607.11"),
}
_COLOR_MAP = {
    "BR": "BROWN", "BK": "BLACK", "WH": "WHITE",
    "SV": "SILVER", "GD": "GOLD",
    "S": "SMALL", "M": "MEDIUM", "L": "LARGE",
}

def _english_name(item_code: str):
    parts = item_code.upper().split("_")
    base, color = parts[0], parts[1] if len(parts) > 1 else ""
    name, hs = _TYPE_INFO.get(base, (item_code, "0000.00"))
    suffix = _COLOR_MAP.get(color, color)
    return (f"{name} ({suffix})" if suffix else name), hs

router = APIRouter(prefix="/releases", tags=["출고"])


@router.get("/", response_model=list[ReleaseOut])
def get_releases(db: Session = Depends(get_db)):
    return db.query(ZipperRelease).order_by(ZipperRelease.created_at.desc()).all()


@router.post("/", response_model=ReleaseOut, status_code=201)
async def create_release(
    body: ReleaseCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    release = ZipperRelease(**body.model_dump(), status="생산중")
    db.add(release)
    db.commit()
    db.refresh(release)
    background_tasks.add_task(report_schedule, body.item_name, body.release_qty, body.due_date)
    return release


@router.delete("/bulk")
def delete_releases_bulk(ids: list[int], db: Session = Depends(get_db)):
    rows = db.query(ZipperRelease).filter(ZipperRelease.id.in_(ids)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="삭제할 항목이 없습니다")
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": len(rows)}


@router.post("/report-batch")
async def report_batch(
    due_date: date = Query(...),
    db: Session = Depends(get_db),
):
    """이미 출고완료 처리된 납기일 묶음을 플랫폼에 보고 (재전송/누락분 보고용)"""
    rows = (
        db.query(ZipperRelease)
        .filter(ZipperRelease.status == "출고완료", ZipperRelease.due_date == due_date)
        .order_by(ZipperRelease.id)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="해당 납기일의 출고완료 건이 없습니다")

    anchor = rows[0]
    result = await send_release_to_platform(
        db,
        item_name=anchor.item_name,
        release_qty=anchor.release_qty,
        due_date=anchor.due_date,
        release_date=anchor.release_date or date.today(),
        label_code=anchor.label_code,
    )
    return {"due_date": str(due_date), "item_count": len(rows), "result": result}


@router.get("/packing-list")
def get_packing_list(
    from_date: date = Query(..., alias="from"),
    to_date:   date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    """날짜 범위 기준 출고완료 건 합산 패킹리스트 PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    rows = db.query(ZipperRelease).filter(
        ZipperRelease.status == "출고완료",
        ZipperRelease.release_date >= from_date,
        ZipperRelease.release_date <= to_date,
    ).all()

    if not rows:
        raise HTTPException(status_code=404, detail="해당 기간 출고완료 건이 없습니다")

    # 품목별 합산
    agg: dict[str, int] = {}
    for r in rows:
        agg[r.item_name] = agg.get(r.item_name, 0) + r.release_qty

    total_qty = sum(agg.values())
    total_kg  = total_qty * 5 / 1000

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    title_style = ParagraphStyle("pl_title", parent=styles["Heading1"],
                                 alignment=1, fontSize=22, spaceAfter=6)
    story.append(Paragraph("PACKING LIST", title_style))
    story.append(Spacer(1, 0.4*cm))

    meta = [
        ["Date:", date.today().strftime("%Y-%m-%d"), "Period:", f"{from_date} ~ {to_date}"],
        ["Exporter:", "ZIPPER & BUTTON CO., LTD.", "Total Items:", f"{len(agg)} kinds"],
    ]
    meta_tbl = Table(meta, colWidths=[3*cm, 8*cm, 3*cm, 4*cm])
    meta_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 0.8*cm))

    header = [["DESCRIPTION", "HS CODE", "QTY (PCS)", "UNIT WT.", "TOTAL WT."]]
    body_rows = []
    for item_name, qty in sorted(agg.items()):
        eng, hs = _english_name(item_name)
        wt = qty * 5 / 1000
        body_rows.append([eng, hs, f"{qty:,}", "5 g", f"{wt:.2f} kg"])

    main_tbl = Table(header + body_rows, colWidths=[8*cm, 3*cm, 3*cm, 2*cm, 2*cm])
    row_bg = [colors.HexColor("#f5f8fc"), colors.white]
    main_styles = [
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",        (0, 1), (0, -1), "LEFT"),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING",   (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
    ]
    for i in range(len(body_rows)):
        main_styles.append(("BACKGROUND", (0, i+1), (-1, i+1), row_bg[i % 2]))
    main_tbl.setStyle(TableStyle(main_styles))
    story.append(main_tbl)
    story.append(Spacer(1, 0.2*cm))

    total_row = [["TOTAL", "", f"{total_qty:,} PCS", "", f"{total_kg:.2f} KG"]]
    total_tbl = Table(total_row, colWidths=[8*cm, 3*cm, 3*cm, 2*cm, 2*cm])
    total_tbl.setStyle(TableStyle([
        ("FONTNAME",     (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 11),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#d0e4f7")),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]))
    story.append(total_tbl)
    story.append(Spacer(1, 1*cm))

    note_style = ParagraphStyle("note", parent=styles["Normal"], fontSize=8,
                                textColor=colors.grey)
    story.append(Paragraph("* Unit weight estimated at 5g per piece.", note_style))
    story.append(Paragraph(f"* Covers {len(rows)} shipment record(s) from {from_date} to {to_date}.", note_style))

    doc.build(story)
    buf.seek(0)
    filename = f"packing_list_{from_date}_{to_date}.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/{release_id}/incident")
async def report_incident(
    release_id: int,
    body: IncidentReport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """돌발상황 보고 → 플랫폼 reschedule 전송"""
    release = db.query(ZipperRelease).filter(ZipperRelease.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail="출고 항목을 찾을 수 없습니다")
    background_tasks.add_task(
        report_reschedule, release_id, body.reason, body.new_estimated_completion
    )
    return {"ok": True, "release_id": release_id, "reason": body.reason}


@router.post("/{release_id}/complete", response_model=ReleaseOut)
async def complete_release(
    release_id: int,
    body: ReleaseComplete = ReleaseComplete(),
    db: Session = Depends(get_db),
):
    release = db.query(ZipperRelease).filter(ZipperRelease.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail="출고 항목을 찾을 수 없습니다")
    if release.status == "출고완료":
        raise HTTPException(status_code=400, detail="이미 출고완료된 항목입니다")

    # 원자재 재고 차감
    item_type = get_item_type(release.item_name)
    raw_info  = RAW_MATERIAL_MAP.get(item_type)

    if raw_info:
        raw_needed = release.release_qty / raw_info["rate"]
        stock = db.query(ZipperStock).filter(
            ZipperStock.material_name == raw_info["name"]
        ).first()
        if stock:
            new_qty = float(stock.stock_qty) - raw_needed
            if new_qty < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"{raw_info['name']} 재고 부족 (필요 {raw_needed:.1f}{raw_info['unit']}, 현재 {stock.stock_qty}{raw_info['unit']})"
                )
            stock.stock_qty = new_qty

    release.status       = "출고완료"
    release.release_date = date.today()
    release.started_at   = body.started_at
    release.finished_at  = body.finished_at
    db.commit()
    db.refresh(release)

    await send_release_to_platform(
        db,
        item_name=release.item_name,
        release_qty=release.release_qty,
        due_date=release.due_date,
        release_date=release.release_date,
        label_code=release.label_code,
    )

    return release
