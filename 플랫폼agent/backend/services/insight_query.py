import csv
import json
import os
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

DEMO_DIR = Path(__file__).resolve().parents[3] / "demo_data" / "four_year_supply_chain"
BASE_DATE = date(2026, 6, 16)

COMPANY_KEYWORDS = {
    "케어라벨사": ("케어라벨사", 2),
    "케어라벨": ("케어라벨사", 2),
    "라벨사": ("케어라벨사", 2),
    "라벨": ("케어라벨사", 2),
    "옷감사": ("옷감사", 1),
    "옷감": ("옷감사", 1),
    "지퍼단추사": ("지퍼단추사", 3),
    "지퍼단추": ("지퍼단추사", 3),
    "지퍼": ("지퍼단추사", 3),
    "단추": ("지퍼단추사", 3),
}


def _detect_company(q: str):
    for kw, val in COMPANY_KEYWORDS.items():
        if kw in q:
            return val
    return None, None


def _detect_months(q: str):
    if "6개월" in q or "반기" in q:
        return 6
    if "3개월" in q or "분기" in q:
        return 3
    if "1년" in q or "올해" in q or "2026" in q:
        return 12
    return None  # 전체


def _parse_date_safe(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _period_label(date_str: str) -> str | None:
    d = _parse_date_safe(date_str)
    if not d:
        return None
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def _safe_float(v) -> float | None:
    try:
        return float(v)
    except Exception:
        return None


def _cutoff_date(months: int | None) -> date | None:
    if months is None:
        return None
    m = BASE_DATE.month - months
    y = BASE_DATE.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _read_csv(fn: str) -> list[dict]:
    p = DEMO_DIR / fn
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _filter_rows(rows, date_field: str, cutoff: date | None, company_name: str | None) -> list[dict]:
    result = []
    for row in rows:
        if cutoff:
            d = _parse_date_safe(row.get(date_field))
            if not d or d < cutoff:
                continue
        if company_name and row.get("company_name") != company_name:
            continue
        result.append(row)
    return result


def _agg_production(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        period = _period_label(row.get("production_complete_date", ""))
        if not period:
            continue
        groups[(period, row.get("company_name", "알수없음"))].append(row)

    result = []
    for (period, company), batch in sorted(groups.items()):
        buffers = [_safe_float(r.get("due_buffer_days")) for r in batch]
        buffers = [v for v in buffers if v is not None]
        durations = [_safe_float(r.get("production_duration_days")) for r in batch]
        durations = [v for v in durations if v is not None]
        lates = sum(1 for r in batch if str(r.get("is_late", "")).lower() in ("true", "1"))
        result.append({
            "기간": period,
            "회사": company,
            "평균납기여유일": round(statistics.mean(buffers), 1) if buffers else None,
            "평균생산소요일": round(statistics.mean(durations), 1) if durations else None,
            "지연건수": lates,
            "총건수": len(batch),
        })
    return result


def _agg_material(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        period = _period_label(row.get("actual_receipt_date", ""))
        if not period:
            continue
        groups[(period, row.get("supplier", "기타"))].append(row)

    result = []
    for (period, supplier), batch in sorted(groups.items()):
        delays = [_safe_float(r.get("delay_days")) for r in batch]
        delays = [v for v in delays if v is not None]
        result.append({
            "기간": period,
            "공급사": supplier,
            "평균지연일": round(statistics.mean(delays), 1) if delays else None,
            "지연건수": sum(1 for d in delays if d > 0),
            "총건수": len(batch),
        })
    return result


def _agg_logistics(rows: list[dict]) -> list[dict]:
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        period = _period_label(row.get("pickup_date", ""))
        if not period:
            continue
        groups[period].append(row)

    result = []
    for period, batch in sorted(groups.items()):
        delays = [_safe_float(r.get("delivery_delay_days")) for r in batch]
        delays = [v for v in delays if v is not None]
        hours = [_safe_float(r.get("assignment_hours")) for r in batch]
        hours = [v for v in hours if v is not None]
        result.append({
            "기간": period,
            "평균배송지연일": round(statistics.mean(delays), 1) if delays else None,
            "평균배차소요시간": round(statistics.mean(hours), 1) if hours else None,
            "건수": len(batch),
        })
    return result


async def query_insight(db: Session, question: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    client = AsyncOpenAI(api_key=api_key)

    company_name, company_id = _detect_company(question)
    months = _detect_months(question)
    cutoff = _cutoff_date(months)

    is_prod = any(k in question for k in ["생산성", "납기", "생산", "완료", "소요", "여유"])
    is_mat = any(k in question for k in ["자재", "원자재", "입고", "지연", "리드타임", "공급사"])
    is_log = any(k in question for k in ["물류", "배차", "배송", "운송"])
    if not any([is_prod, is_mat, is_log]):
        is_prod = True

    context_parts = []
    data_sources = []

    if is_prod:
        rows = _filter_rows(_read_csv("production_batches.csv"), "production_complete_date", cutoff, company_name)
        agg = _agg_production(rows)[:60]
        company_label = f" — {company_name}" if company_name else ""
        context_parts.append(f"## 생산 배치 집계{company_label} ({len(agg)}개 기간-회사 조합)\n{json.dumps(agg, ensure_ascii=False)}")
        data_sources.append("production_batches.csv")

    if is_mat:
        rows = _filter_rows(_read_csv("material_receipts.csv"), "actual_receipt_date", cutoff, None)
        if company_name:
            rows = [r for r in rows if r.get("company_name") == company_name]
        agg = _agg_material(rows)[:60]
        context_parts.append(f"## 자재 입고 집계 ({len(agg)}개 기간-공급사 조합)\n{json.dumps(agg, ensure_ascii=False)}")
        data_sources.append("material_receipts.csv")

    if is_log:
        rows = _filter_rows(_read_csv("logistics_performance.csv"), "pickup_date", cutoff, None)
        agg = _agg_logistics(rows)[:30]
        context_parts.append(f"## 물류 성과 집계 ({len(agg)}개 기간)\n{json.dumps(agg, ensure_ascii=False)}")
        data_sources.append("logistics_performance.csv")

    context = "\n\n".join(context_parts)

    system_prompt = """당신은 B2B 의류 부자재 공급망 플랫폼의 AI 분석 어시스턴트입니다.
시뮬레이션 기간: 2023-01~2026-12 (4년치). 현재 기준일: 2026-06-16.
회사: 케어라벨사(라벨), 옷감사(원단), 지퍼단추사(부자재).
시나리오: 1~2년차(2023~2024)는 정상 운영, 3년차(2025)부터 자재 지연 시작, 4년차(2026)에 지연+생산성 저하 가속.

반드시 아래 JSON 형식으로만 응답하세요 (JSON 외 다른 텍스트 금지):
{
  "answer": "구체적 수치를 포함한 2~5문장 한국어 분석",
  "chart": null,
  "data_sources": ["파일명"]
}

chart가 필요한 경우 (시간 추이 또는 카테고리 비교가 유의미할 때):
{
  "type": "line" 또는 "bar",
  "title": "차트 제목",
  "data": [{"name": "2023-Q1", "키A": 8.2, "키B": 3.1}, ...],
  "lines": [{"key": "키A", "color": "#3b82f6"}, {"key": "키B", "color": "#10b981"}],
  "y_label": "단위"
}

규칙:
- answer에 구체적 수치 포함 (예: "평균 8.2일에서 1.4일로 감소")
- chart.data의 name은 기간(연도-분기) 또는 카테고리명
- 숫자는 소수점 1자리
- chart.data 배열 최대 20개 항목
- 단순 사실 질문은 chart=null"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"질문: {question}\n\n{context}"},
        ],
        temperature=0.2,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
        result["question"] = question
        result.setdefault("answer", "분석 결과를 생성할 수 없습니다.")
        result.setdefault("chart", None)
        result.setdefault("data_sources", data_sources)
        return result
    except json.JSONDecodeError:
        return {
            "question": question,
            "answer": f"응답 파싱에 실패했습니다. 다시 시도해 주세요.",
            "chart": None,
            "data_sources": data_sources,
        }
