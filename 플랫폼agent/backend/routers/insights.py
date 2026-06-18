import csv
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import os
from database import get_db
from models import InsightLog
from schemas import InsightOut
from services.ai_insight import generate_insights
from services.insight_query import query_insight

router = APIRouter()


DEMO_DATA_DIR = Path(__file__).resolve().parents[3] / "demo_data" / "four_year_supply_chain"


def _coerce_demo_value(value: str):
    if value == "":
      return None
    text = str(value)
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return value


def _read_demo_csv(filename: str) -> list[dict]:
    path = DEMO_DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"데모 데이터 파일이 없습니다: {filename}")

    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        return [
            {key: _coerce_demo_value(value) for key, value in row.items()}
            for row in reader
        ]


def _read_demo_summary() -> dict:
    path = DEMO_DATA_DIR / "dataset_summary.json"
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


@router.get("/insights", response_model=List[InsightOut])
def list_insights(db: Session = Depends(get_db)):
    records = db.query(InsightLog).order_by(InsightLog.created_at.desc()).all()
    return records


@router.get("/insights/demo-supply-chain")
def get_demo_supply_chain_insight_seed():
    if not DEMO_DATA_DIR.exists():
        raise HTTPException(status_code=404, detail="4년치 공급망 데모 데이터가 없습니다")

    return {
        "dataset": "four_year_supply_chain_demo",
        "demo_seed": True,
        "notice": (
            "UI 검증용 시드 데이터입니다. 플랫폼이 원본 DB를 직접 소유한다는 의미가 아니며, "
            "운영 구조에서는 각 회사 agent가 자기 DB를 읽고 요약 보고를 플랫폼에 전송합니다."
        ),
        "summary": _read_demo_summary(),
        "material_receipts": _read_demo_csv("material_receipts.csv"),
        "production_batches": _read_demo_csv("production_batches.csv"),
        "finished_shipments": _read_demo_csv("finished_shipments.csv"),
        "logistics_performance": _read_demo_csv("logistics_performance.csv"),
    }


@router.post("/insights/analyze", response_model=List[InsightOut])
async def analyze_insights(db: Session = Depends(get_db)):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "your_openai_key":
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY가 설정되지 않았습니다")

    results = await generate_insights(db)

    saved = []
    for item in results:
        log = InsightLog(
            insight_type=item.get("type"),
            content=item.get("content"),
            related_code=item.get("related_code"),
        )
        db.add(log)
        db.flush()
        saved.append(log)
    db.commit()
    for s in saved:
        db.refresh(s)

    return saved


@router.post("/insights/query")
async def query_insight_endpoint(body: dict, db: Session = Depends(get_db)):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "your_openai_key":
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY가 설정되지 않았습니다")
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question이 필요합니다")
    return await query_insight(db, question)
