from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from io import BytesIO
from database import get_db
from models import FabricRelease, FabricStock
from schemas import FabricReleaseCreate, FabricReleaseOut
from services.platform_reporter import report_release

router = APIRouter(prefix="/release", tags=["release"])

VALID_LABEL_CODE_BRANDS = {"W"}
VALID_SEASONS = {"1", "2", "3", "4"}
VALID_GENDERS = {"W", "M"}
VALID_ITEMS = {"T", "P", "J", "D"}
VALID_FABRICS = {"C", "P", "L", "W", "M"}
VALID_COLORS = {"BK", "WH", "NV", "GY", "BE", "RD"}


def validate_label_code(code: str) -> bool:
    if len(code) != 9:
        return False
    if code[0] not in VALID_LABEL_CODE_BRANDS:
        return False
    if code[1] not in VALID_SEASONS:
        return False
    if code[2] not in VALID_GENDERS:
        return False
    if code[3] not in VALID_ITEMS:
        return False
    if code[4] not in VALID_FABRICS:
        return False
    if not code[5:7].isdigit():
        return False
    if code[7:9] not in VALID_COLORS:
        return False
    return True


@router.get("/", response_model=List[FabricReleaseOut])
def get_all_releases(db: Session = Depends(get_db)):
    return db.query(FabricRelease).order_by(FabricRelease.created_at.desc()).all()


@router.get("/active", response_model=List[FabricReleaseOut])
def get_active_releases(db: Session = Depends(get_db)):
    return db.query(FabricRelease).filter(FabricRelease.status == "생산중").all()


@router.post("/", response_model=FabricReleaseOut, status_code=201)
def create_release(data: FabricReleaseCreate, db: Session = Depends(get_db)):
    if not validate_label_code(data.label_code):
        raise HTTPException(status_code=400, detail=f"유효하지 않은 라벨코드: {data.label_code}")

    release = FabricRelease(**data.model_dump(), status="생산중")
    db.add(release)
    db.commit()
    db.refresh(release)
    return release


@router.patch("/{release_id}/complete", response_model=FabricReleaseOut)
def complete_release(release_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    release = db.query(FabricRelease).filter(FabricRelease.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail="출고 내역을 찾을 수 없습니다.")
    if release.status == "출고완료":
        raise HTTPException(status_code=400, detail="이미 출고완료된 건입니다.")

    # 재고 차감
    stock = db.query(FabricStock).filter(
        FabricStock.fabric_code == release.fabric_code,
        FabricStock.color_code == release.color_code
    ).first()
    if not stock:
        raise HTTPException(status_code=400, detail="해당 원단 재고 정보가 없습니다.")
    if stock.stock_qty < release.release_qty:
        raise HTTPException(status_code=400, detail="재고 부족으로 출고 완료 처리 불가합니다.")

    stock.stock_qty = float(stock.stock_qty) - float(release.release_qty)
    release.status = "출고완료"
    release.release_date = date.today()
    db.commit()
    db.refresh(release)

    # 플랫폼으로 출고완료 보고 (report_id 추적, 실패 시 "플랫폼 보고 대기"로 재시도)
    background_tasks.add_task(report_release, release)

    return release


# ── 패킹리스트 PDF (날짜 범위 기준 일괄) ──────────────────────────
FABRIC_EN = {"C": "COTTON FABRIC", "P": "POLYESTER FABRIC",
             "L": "LINEN FABRIC",  "W": "WOOL FABRIC", "M": "MIXED FABRIC"}
COLOR_EN  = {"BK": "BLACK", "WH": "WHITE", "NV": "NAVY",
             "GY": "GRAY",  "BE": "BEIGE", "RD": "RED"}
HS_CODES  = {"C": "5208.11", "P": "5513.11", "L": "5309.11",
             "W": "5111.11", "M": "5513.21"}
KG_PER_YARD = 0.3


@router.get("/packing-list")
def download_packing_list(
    from_date: date = Query(..., alias="from"),
    to_date:   date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    """날짜 범위 내 출고완료 건 합산 패킹리스트 PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    releases = (
        db.query(FabricRelease)
        .filter(
            FabricRelease.status == "출고완료",
            FabricRelease.release_date >= from_date,
            FabricRelease.release_date <= to_date,
        )
        .all()
    )
    if not releases:
        raise HTTPException(status_code=404, detail="해당 기간에 출고완료 건이 없습니다.")

    # 품목별 합산
    totals: dict[tuple, float] = {}
    for r in releases:
        key = (r.fabric_code, r.color_code)
        totals[key] = totals.get(key, 0) + float(r.release_qty)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>PACKING LIST</b>", styles["Title"]))
    story.append(Spacer(1, 0.4*cm))

    hdr_data = [
        ["Shipper:",       "YEONG FABRIC CO., LTD.",   "Issue Date:", str(date.today())],
        ["Period:",        f"{from_date} ~ {to_date}", "Items:",      f"{len(totals)} types"],
    ]
    hdr_tbl = Table(hdr_data, colWidths=[2.5*cm, 7.5*cm, 3*cm, 4.3*cm])
    hdr_tbl.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 0.6*cm))

    rows = [["No.", "DESCRIPTION", "HS CODE", "QTY (Yards)", "WEIGHT (KG)"]]
    total_yards = 0.0
    total_kg    = 0.0
    for i, ((fc, cc), qty) in enumerate(sorted(totals.items()), 1):
        desc   = f"{FABRIC_EN.get(fc, fc)} – {COLOR_EN.get(cc, cc)}"
        hs     = HS_CODES.get(fc, "5208.11")
        weight = round(qty * KG_PER_YARD, 1)
        rows.append([str(i), desc, hs, f"{qty:,.0f}", f"{weight:,.1f}"])
        total_yards += qty
        total_kg    += weight

    rows.append(["", "TOTAL", "", f"{total_yards:,.0f}", f"{total_kg:,.1f}"])

    col_w = [1*cm, 7.5*cm, 2.8*cm, 3*cm, 3*cm]
    tbl = Table(rows, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
        ("FONTNAME",      (1,-1), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("BACKGROUND",    (0,-1), (-1,-1), colors.lightgrey),
        ("ALIGN",         (3,0), (4,-1),  "RIGHT"),
        ("GRID",          (0,0), (-1,-2), 0.5, colors.grey),
        ("LINEABOVE",     (0,-1), (-1,-1), 1, colors.HexColor("#1e3a5f")),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS",(0,1),(-1,-2), [colors.white, colors.HexColor("#f0f4ff")]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        "This packing list is computer-generated. Weight estimated at 0.3 kg/yard.",
        styles["Normal"]
    ))

    doc.build(story)
    buf.seek(0)

    fname = f"packing_list_{from_date}_{to_date}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
