"""
옷감회사 AI Agent 현재상황 판단 로직
[2026-06-02 13:27] 지시: AI Agent 현재상황 판단 고도화

AI_로직.txt / 생산규칙.txt / 옷감코드_규칙.txt 에 정의된 규칙만 사용한다.
문서에 명시되지 않은 계산은 함수별 주석에 "로직 문서에 없음 — 보조계산"으로 표기한다.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from database import SessionLocal
from models import FabricProduction, FabricStock
from services.production_rules import (
    FABRIC_NAMES,
    PRODUCTION_SPEED,
    SAFE_STOCK,
    calc_deadline_status,
    calc_required_days,
    calc_required_hours,
)

STAGES = ["원사입고", "정경·제직", "염색", "가공", "검품", "완성"]

# AI_로직.txt 3순위(느린 원단 W,L 먼저 착수)를 생산속도 오름차순(느린 순)으로 일반화한 정렬 키.
# 문서에는 W,L만 명시되어 있고 C/M/P 사이의 순서는 로직 문서에 없음 — PRODUCTION_SPEED 값을 그대로 사용해 보완.
_SEVERITY_ORDER = {"납기불가": 0, "납기위험": 1, "납기가능": 2}


def _build_stock_item(fabric_code: str, color_code: str, stock_qty: float) -> dict:
    safe = SAFE_STOCK.get(fabric_code, 0)
    name = f"{FABRIC_NAMES.get(fabric_code, fabric_code)}_{color_code}"

    if stock_qty <= 0:
        status = "재고없음"
        summary = f"{name} 재고 없음 — 긴급 발주 필요"
    elif stock_qty <= safe:
        status = "안전재고이하"
        summary = f"{name} {stock_qty:,.0f}야드 — 안전재고({safe:,}야드) 이하, 발주 권고"
    else:
        status = "정상"
        summary = f"{name} 재고 정상 ({stock_qty:,.0f}야드)"

    return {
        "fabric_code": fabric_code,
        "color_code": color_code,
        "material_name": name,
        "current_qty": stock_qty,
        "safe_qty": safe,
        "unit": "야드",
        "status": status,
        "shortage_to_safe": max(safe - stock_qty, 0),
        "summary": summary,
    }


def build_stock_summary(all_stocks) -> dict:
    """AI_로직.txt 2. 재고 모니터링 로직"""
    items = [_build_stock_item(s.fabric_code, s.color_code, float(s.stock_qty)) for s in all_stocks]
    warnings = [item["summary"] for item in items if item["status"] != "정상"]
    return {
        "items": items,
        "warnings": warnings,
        "all_materials_ok": not warnings,
    }


def _production_priority_key(item: dict) -> tuple:
    """AI_로직.txt 3. 우선순위 결정 로직
    1순위: 납기위험(불가 포함) 먼저, 남은 일수 적은 순
    2순위: 동일 납기일이면 주문량(생산량) 적은 것 먼저
    3순위: 느린 원단(W,L) 먼저 착수 → PRODUCTION_SPEED 오름차순으로 일반화
    """
    return (
        _SEVERITY_ORDER.get(item["deadline_status"], 2),
        item["days_remaining"],
        float(item["quantity"]),
        PRODUCTION_SPEED.get(item["fabric_code"], 8),
    )


def build_active_productions(productions, today: date | None = None) -> list[dict]:
    today = today or date.today()
    items = []
    for p in productions:
        qty = float(p.quantity)
        required_days = calc_required_days(p.fabric_code, qty)
        required_hours = calc_required_hours(p.fabric_code, qty)
        days_remaining = (p.target_date - today).days
        deadline_status = calc_deadline_status(days_remaining, required_days)
        item_name = f"{p.fabric_code}-{p.color_code}"

        # 예상완료일 = 오늘 + ceil(필요일수) — AI_로직.txt에 별도 정의 없는 보조계산(달력일 환산)
        estimated_completion = (today + timedelta(days=math.ceil(required_days))).isoformat()

        items.append({
            "id": p.id,
            "item_name": item_name,
            "fabric_code": p.fabric_code,
            "color_code": p.color_code,
            "quantity": qty,
            "stage": p.stage,
            "target_date": p.target_date.isoformat(),
            "days_remaining": days_remaining,
            "required_days": required_days,
            "required_hours": required_hours,
            "estimated_completion": estimated_completion,
            "deadline_status": deadline_status,
            "worker": p.worker,
        })

    items.sort(key=_production_priority_key)
    for idx, item in enumerate(items, start=1):
        d_day = f"D-{item['days_remaining']}" if item["days_remaining"] >= 0 else f"D+{abs(item['days_remaining'])}"
        item["priority_rank"] = idx
        item["summary"] = (
            f"{item['item_name']} {item['quantity']:,.0f}야드: {item['stage']} 단계, "
            f"예상완료 {item['estimated_completion']}, 납기 {d_day}, {item['deadline_status']}"
        )
    return items


def build_stage_summary(all_productions) -> list[dict]:
    """생산규칙.txt 생산 단계: 원사입고 → 정경·제직 → 염색 → 가공 → 검품 → 완성
    stage='완성'은 출고 가능 상태."""
    counts = {stage: 0 for stage in STAGES}
    for p in all_productions:
        if p.stage in counts:
            counts[p.stage] += 1
    return [
        {"stage": stage, "count": count, "ready_for_release": stage == "완성"}
        for stage, count in counts.items()
    ]


def build_agent_status_snapshot(
    all_stocks,
    active_productions_raw,
    all_productions,
    platform_report_status: dict | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()

    stock_summary = build_stock_summary(all_stocks)
    active_productions = build_active_productions(active_productions_raw, today)
    stage_summary = build_stage_summary(all_productions)

    schedule_recommendations = [
        {
            "priority_rank": item["priority_rank"],
            "item_name": item["item_name"],
            "stage": item["stage"],
            "deadline_status": item["deadline_status"],
            "due_date": item["target_date"],
            "estimated_completion": item["estimated_completion"],
            "summary": item["summary"],
        }
        for item in active_productions
    ]

    risk_items = [
        {
            "id": item["id"],
            "item_name": item["item_name"],
            "stage": item["stage"],
            "deadline_status": item["deadline_status"],
            "due_date": item["target_date"],
            "days_remaining": item["days_remaining"],
            "summary": item["summary"],
        }
        for item in active_productions
        if item["deadline_status"] != "납기가능"
    ]

    # AI_로직.txt 5. AI Agent 패널 표시 규칙(지시사항 표시 우선순위)
    next_actions: list[str] = []
    for risk in risk_items:
        if risk["deadline_status"] == "납기불가":
            next_actions.append(f"❌ {risk['item_name']} 납기 불가 — 긴급 외주 또는 납기 조정 필요 ({risk['summary']})")
    for risk in risk_items:
        if risk["deadline_status"] == "납기위험":
            next_actions.append(f"⚠ {risk['item_name']} 납기 위험 — 오늘 최우선 착수 ({risk['summary']})")

    next_actions.extend(stock_summary["warnings"])

    if active_productions:
        top = active_productions[0]
        if top["deadline_status"] == "납기가능":
            next_actions.append(f"✅ 오늘 우선 작업: {top['summary']}")
    else:
        next_actions.append("✅ 진행중인 생산 항목이 없습니다 — 신규 생산 등록 및 재고 모니터링만 진행하세요")

    return {
        "stock_summary": stock_summary,
        "active_productions": active_productions,
        "stage_summary": stage_summary,
        "schedule_recommendations": schedule_recommendations,
        "risk_items": risk_items,
        "next_actions": next_actions,
        "platform_report_status": platform_report_status or {
            "summary": "최근 플랫폼 보고 없음",
            "recent_reports": [],
            "channel_messages": [],
            "waiting_count": 0,
            "success_count": 0,
        },
    }


def build_release_ai_report(release) -> dict:
    """출고완료 보고용 'AI/DB 판단 보고' 요약 — 라벨agent 표준(analysis_type=db_rule_based,
    uses_openai=False)을 그대로 적용한다. GPT 미사용, 규칙기반 요약만 생성한다."""
    item_name = f"{FABRIC_NAMES.get(release.fabric_code, release.fabric_code)}_{release.color_code}"
    release_qty = float(release.release_qty)
    due_date = release.due_date
    release_date = release.release_date or date.today()
    delay_days = (release_date - due_date).days if due_date else 0
    due_result = "납기준수" if delay_days <= 0 else "납기지연"

    db = SessionLocal()
    try:
        all_stocks = db.query(FabricStock).all()
        stock_summary = build_stock_summary(all_stocks)

        active_raw = db.query(FabricProduction).filter(FabricProduction.stage != "완성").all()
        active_productions = build_active_productions(active_raw)
    finally:
        db.close()

    stock_summary_text = ", ".join(stock_summary["warnings"]) if stock_summary["warnings"] else "전체 안전재고 이상 정상"
    risk_items = [p for p in active_productions if p["deadline_status"] != "납기가능"]

    has_shortage = any(i["status"] == "재고없음" for i in stock_summary["items"])
    has_low_stock = any(i["status"] == "안전재고이하" for i in stock_summary["items"])
    has_unfeasible = any(p["deadline_status"] == "납기불가" for p in risk_items)
    has_at_risk = any(p["deadline_status"] == "납기위험" for p in risk_items)

    if delay_days > 0:
        decision_level = "긴급"
        decision = "출고가 납기보다 지연되어 완료되었습니다. 플랫폼은 지연 사유 확인 및 후속 일정 조율이 필요합니다."
    elif has_shortage or has_unfeasible:
        decision_level = "주의"
        decision = "출고는 납기 내 완료됐지만 원단 재고 부족 또는 납기불가 생산 건이 있어 후속 생산 일정을 함께 점검해야 합니다."
    elif has_low_stock or has_at_risk:
        decision_level = "주의"
        decision = "출고는 정상 완료됐지만 일부 원단 재고가 안전재고 이하이거나 납기 위험 생산 건이 있어 모니터링이 필요합니다."
    else:
        decision_level = "정상"
        decision = "출고 완료 및 원단 재고·진행중 생산 모두 안정 범위입니다."

    summary = ". ".join([
        f"옷감회사 DB 판단: {item_name} {release_qty:,.0f}야드 출고완료 ({due_result})",
        f"현재 재고 {stock_summary_text}",
        f"진행중 생산 위험 {len(risk_items)}건" if risk_items else "진행중 생산 위험 없음",
        f"판정 {decision_level}: {decision}",
    ])

    return {
        "analysis_type": "db_rule_based",
        "uses_openai": False,
        "decision_level": decision_level,
        "decision": decision,
        "summary": summary,
        "item_ref": f"{release.fabric_code}-{release.color_code}",
        "release_qty": release_qty,
        "due_date": due_date.isoformat() if due_date else None,
        "release_date": release_date.isoformat() if release_date else None,
        "due_result": due_result,
        "delay_days": max(delay_days, 0),
        "stock_summary_text": stock_summary_text,
        "risk_item_count": len(risk_items),
    }
