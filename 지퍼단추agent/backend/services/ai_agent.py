import math
from datetime import date, datetime, timedelta

# 기계 1대당 시간당 생산량
PRODUCTION_RATE = {
    "원목단추":     20,
    "플라스틱단추": 300,
    "금속단추":     150,
    "지퍼":         200,
}

MACHINES_PER_TYPE = 2
DAILY_HOURS = 9

# 원자재 변환비율
RAW_MATERIAL_MAP = {
    "원목단추":     {"name": "원목",        "unit": "kg", "rate": 50},
    "플라스틱단추": {"name": "플라스틱원료", "unit": "kg", "rate": 200},
    "금속단추":     {"name": "금속원료",     "unit": "kg", "rate": 150},
    "지퍼":         {"name": "지퍼테이프",   "unit": "m",  "rate": 1},
}

# 안전재고
SAFE_STOCK = {
    "원목":        50,
    "플라스틱원료": 100,
    "금속원료":    80,
    "지퍼테이프":  200,
}

# 원자재 단위
MATERIAL_UNIT = {
    "원목":        "kg",
    "플라스틱원료": "kg",
    "금속원료":    "kg",
    "지퍼테이프":  "m",
}

# TODO: 트렌드 신호 임계값 — AI_로직.txt에는 "원목단추 출고 +20% 이상"만 수치가 명시됨.
# 나머지 3개 패턴(지퍼+D, J+금속단추, 플라스틱단추 급감)은 임계값 미정 → 동일 20% 적용.
TREND_THRESHOLD = 0.20

# 납기 상태 표시용 한글 라벨 (AgentPanel 메시지용)
DEADLINE_LABEL = {
    "납기가능": "정상",
    "납기위험": "주의",
    "납기불가": "긴급",
}

# 라벨코드 품목코드 → 필요 부자재
ITEM_CODE_MAP = {
    "T": {"label": "티셔츠", "parts": ["플라스틱단추"]},
    "P": {"label": "바지",   "parts": ["금속단추"]},
    "J": {"label": "재킷",   "parts": ["지퍼", "금속단추"]},
    "D": {"label": "다운",   "parts": ["지퍼"]},
}


def get_item_type(item_name: str) -> str:
    parts = item_name.upper().split("_")
    if parts[0] == "ZIPPER":
        return "지퍼"
    map_ = {"WOOD": "원목단추", "PLASTIC": "플라스틱단추", "METAL": "금속단추"}
    return map_.get(parts[0], item_name)


def calc_hours(item_type: str, qty: int) -> float:
    rate = PRODUCTION_RATE.get(item_type, 100)
    return qty / (MACHINES_PER_TYPE * rate)


def calc_days(hours: float) -> int:
    return math.ceil(hours / DAILY_HOURS)


def calc_raw_needed(item_type: str, qty: int) -> float:
    info = RAW_MATERIAL_MAP.get(item_type)
    if not info:
        return 0
    return math.ceil(qty / info["rate"] * 10) / 10


def calculate_agent_result(
    item_name: str,
    release_qty: int,
    due_date: date,
    raw_stocks: dict,   # {원자재명: qty}
) -> dict:
    item_type = get_item_type(item_name)
    today = date.today()
    days_remaining = (due_date - today).days

    hours = calc_hours(item_type, release_qty)
    days_needed = calc_days(hours)

    raw_info = RAW_MATERIAL_MAP.get(item_type, {})
    raw_needed = calc_raw_needed(item_type, release_qty)
    current_raw = raw_stocks.get(raw_info.get("name", ""), 0)
    stock_ok = current_raw >= raw_needed

    if days_remaining >= days_needed + 1:
        deadline_status = "납기가능"
    elif days_remaining >= days_needed:
        deadline_status = "납기위험"
    else:
        deadline_status = "납기불가"

    warnings = []
    instructions = []

    if not stock_ok:
        shortage = raw_needed - current_raw
        warnings.append(
            f"⚠ {raw_info.get('name','')} 부족: 현재 {current_raw}{raw_info.get('unit','')}, "
            f"필요 {raw_needed}{raw_info.get('unit','')} (부족 {round(shortage,1)})"
        )
        instructions.append(f"{raw_info.get('name','')} {round(shortage+10,1)}{raw_info.get('unit','')} 발주 권고")

    if deadline_status == "납기불가":
        instructions.insert(0, f"❌ 납기 불가: {days_needed}일 필요, {days_remaining}일 남음")
    elif deadline_status == "납기위험":
        instructions.insert(0, "⚠ 납기 위험: 즉시 생산 착수 필요")

    safe = SAFE_STOCK.get(raw_info.get("name", ""), 0)
    if current_raw <= safe and raw_info:
        warnings.append(f"⚠ {raw_info['name']} 안전재고 이하 ({current_raw}{raw_info['unit']})")

    return {
        "item_name":       item_name,
        "item_type":       item_type,
        "release_qty":     release_qty,
        "required_hours":  round(hours, 2),
        "required_days":   days_needed,
        "raw_material":    raw_info.get("name", "-"),
        "raw_needed":      raw_needed,
        "raw_unit":        raw_info.get("unit", ""),
        "stock_ok":        stock_ok,
        "days_remaining":  days_remaining,
        "deadline_status": deadline_status,
        "warnings":        warnings,
        "instructions":    instructions,
        "is_valid":        True,
    }


# ============================================================
# AI Agent 현재상황 종합 판단 (GET /agent/status)
#   - AI_로직.txt / 생산규칙.txt / 지퍼단추코드_규칙.txt 기준
#   - 플랫폼은 raw DB를 보지 않고 이 요약 결과만 보고받음
# ============================================================

def _label_4th(label_code) -> str:
    """라벨코드 4번째 자리(품목코드) 추출. 없으면 빈 문자열."""
    if label_code and len(label_code) >= 4:
        return label_code[3].upper()
    return ""


def build_active_order_judgments(active_releases, raw_stocks: dict) -> list[dict]:
    """진행중(생산중) 주문별 납기/원자재 판정 + 예상완료시각 계산"""
    now = datetime.now()
    judgments = []
    for r in active_releases:
        result = calculate_agent_result(
            item_name=r.item_name,
            release_qty=r.release_qty,
            due_date=r.due_date,
            raw_stocks=raw_stocks,
        )
        # TODO: 09:00~18:00 영업시간 경계 미반영. 현재는 단순 누적시간(now + required_hours)으로 근사.
        estimated_completion_at = now + timedelta(hours=result["required_hours"])
        result.update({
            "id":                      r.id,
            "label_code":              r.label_code,
            "due_date":                r.due_date.isoformat(),
            "estimated_completion_at": estimated_completion_at.isoformat(),
        })
        judgments.append(result)
    return judgments


def build_stock_summary(active_releases) -> list[dict]:
    """완제품 재고 현황 — 별도 완제품 재고 테이블이 없어 생산중 주문 수량 합계로 대체"""
    agg: dict[str, dict] = {}
    for r in active_releases:
        item_type = get_item_type(r.item_name)
        entry = agg.setdefault(r.item_name, {
            "item_name":         r.item_name,
            "item_type":         item_type,
            "in_production_qty": 0,
            "order_count":       0,
        })
        entry["in_production_qty"] += r.release_qty
        entry["order_count"] += 1
    return sorted(agg.values(), key=lambda x: x["item_name"])


def build_raw_material_summary(raw_stocks: dict) -> list[dict]:
    """원자재 재고 현황 (안전재고 대비 정상/경고/긴급)"""
    summary = []
    for name, safe_qty in SAFE_STOCK.items():
        current = raw_stocks.get(name, 0)
        if current == 0:
            level = "긴급"
        elif current <= safe_qty:
            level = "경고"
        else:
            level = "정상"
        summary.append({
            "material_name": name,
            "unit":          MATERIAL_UNIT.get(name, ""),
            "current_qty":   current,
            "safe_qty":      safe_qty,
            "level":         level,
        })
    return summary


def build_material_shortages(raw_stocks: dict) -> list[dict]:
    """안전재고 이하 원자재 → 발주 권고 목록
    발주 권장량 산식은 로직문서에 명시 없음 → 기본값(안전재고 - 현재재고) 사용 (TODO: 확정 필요)
    """
    shortages = []
    for name, safe_qty in SAFE_STOCK.items():
        current = raw_stocks.get(name, 0)
        if current > safe_qty:
            continue
        level = "긴급" if current == 0 else "경고"
        shortages.append({
            "material_name":         name,
            "unit":                  MATERIAL_UNIT.get(name, ""),
            "current_qty":           current,
            "safe_qty":              safe_qty,
            "level":                 level,
            "recommended_order_qty": round(max(safe_qty - current, 0), 1),
        })
    return shortages


def build_schedule_recommendations(judgments: list[dict]) -> list[dict]:
    """오늘 우선 처리 작업 순서

    신규 지시문 기준: 납기불가 > 납기위험 > 납기 가까운 순 > 생산량 적은 순
    AI_로직.txt 4번 기준: 납기위험(남은일수 적은순) > 원목단추 우선 > 주문량 적은 순
    → 두 기준을 결합: (납기상태 등급, 남은일수, 원목단추 우선, 생산량) 순으로 정렬
    """
    status_rank = {"납기불가": 0, "납기위험": 1, "납기가능": 2}

    def sort_key(j):
        wood_first = 0 if j["item_type"] == "원목단추" else 1
        return (status_rank.get(j["deadline_status"], 9), j["days_remaining"], wood_first, j["release_qty"])

    ordered = sorted(judgments, key=sort_key)

    recs = []
    for i, j in enumerate(ordered, start=1):
        if j["deadline_status"] == "납기불가":
            reason = f"❌ 납기 불가 — 즉시 착수 필요 (소요 {j['required_days']}일 / 남은 {j['days_remaining']}일)"
        elif j["deadline_status"] == "납기위험":
            reason = f"⚠ 납기 위험 — 우선 착수 권고 (소요 {j['required_days']}일 / 남은 {j['days_remaining']}일)"
        else:
            reason = f"✅ 정상 — 순서대로 진행 가능 (소요 {j['required_days']}일 / 남은 {j['days_remaining']}일)"
        recs.append({
            "priority":        i,
            "id":              j["id"],
            "item_name":       j["item_name"],
            "item_type":       j["item_type"],
            "release_qty":     j["release_qty"],
            "due_date":        j["due_date"],
            "deadline_status": j["deadline_status"],
            "reason":          reason,
        })
    return recs


def build_risk_items(judgments: list[dict]) -> list[dict]:
    """납기위험/납기불가 주문 — 사람이 읽기 쉬운 요약 문구 포함"""
    status_rank = {"납기불가": 0, "납기위험": 1}
    risky = [j for j in judgments if j["deadline_status"] in status_rank]
    risky.sort(key=lambda j: (status_rank[j["deadline_status"]], j["days_remaining"]))

    items = []
    for j in risky:
        sign = "-" if j["days_remaining"] >= 0 else "+"
        est = j["estimated_completion_at"].replace("T", " ")[:16]
        message = (
            f"{j['item_name']} {j['release_qty']:,}개: {j['raw_material']} {j['raw_needed']}{j['raw_unit']} 필요, "
            f"예상완료 {est}, 납기 D{sign}{abs(j['days_remaining'])}, {DEADLINE_LABEL.get(j['deadline_status'], j['deadline_status'])}"
        )
        items.append({
            "id":                      j["id"],
            "item_name":               j["item_name"],
            "label_code":              j["label_code"],
            "release_qty":             j["release_qty"],
            "due_date":                j["due_date"],
            "days_remaining":          j["days_remaining"],
            "deadline_status":         j["deadline_status"],
            "estimated_completion_at": j["estimated_completion_at"],
            "message":                 message,
        })
    return items


def build_trend_signals(db) -> list[dict]:
    """월간 출고 트렌드 신호 (AI_로직.txt 3번)

    원래는 "월 1회 자동 집계"이지만 패널에서는 이번달(1일~오늘) vs 지난달 동일 기간을 비교해
    실시간으로 보여준다. 원목단추 +20% 이상만 로직문서에 명시되어 있고,
    나머지 3개 패턴은 TREND_THRESHOLD(20%)를 동일하게 적용한다 (TODO: 임계값 확정 필요).
    """
    from models import ZipperRelease

    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    compare_day = min(today.day, last_month_end.day)
    last_month_compare_end = last_month_start.replace(day=compare_day)

    rows = db.query(ZipperRelease).filter(
        ZipperRelease.status == "출고완료",
        ZipperRelease.release_date >= last_month_start,
        ZipperRelease.release_date <= today,
    ).all()

    def sum_qty(predicate, start, end):
        return sum(
            r.release_qty for r in rows
            if r.release_date and start <= r.release_date <= end and predicate(r)
        )

    def pct_change(this_qty, last_qty):
        if last_qty == 0:
            return None
        return (this_qty - last_qty) / last_qty

    signals = []

    # 1) 원목단추 출고 증가 +20% 이상 → 프리미엄 셔츠 라인 수요 증가
    is_wood = lambda r: r.item_name.upper().startswith("WOOD")
    wood_this = sum_qty(is_wood, this_month_start, today)
    wood_last = sum_qty(is_wood, last_month_start, last_month_compare_end)
    chg = pct_change(wood_this, wood_last)
    if chg is not None and chg >= TREND_THRESHOLD:
        signals.append({
            "signal":   "프리미엄 셔츠 라인 수요 증가",
            "category": "원목단추",
            "basis":    f"원목단추 출고 {wood_last}→{wood_this}개 ({chg:+.0%})",
        })

    # 2) 지퍼 + D(다운) 라벨 출고 급증 → 아웃도어 다운 시즌 수요 증가
    is_zip_d = lambda r: r.item_name.upper().startswith("ZIPPER") and _label_4th(r.label_code) == "D"
    zipd_this = sum_qty(is_zip_d, this_month_start, today)
    zipd_last = sum_qty(is_zip_d, last_month_start, last_month_compare_end)
    chg = pct_change(zipd_this, zipd_last)
    if chg is not None and chg >= TREND_THRESHOLD:
        signals.append({
            "signal":   "아웃도어 다운 시즌 수요 증가",
            "category": "지퍼(D라벨)",
            "basis":    f"지퍼+D라벨 출고 {zipd_last}→{zipd_this}개 ({chg:+.0%})",
        })

    # 3) J(재킷) + 금속단추 출고 증가 → 포멀 재킷 라인 수요 증가
    is_jacket_metal = lambda r: r.item_name.upper().startswith("METAL") and _label_4th(r.label_code) == "J"
    jm_this = sum_qty(is_jacket_metal, this_month_start, today)
    jm_last = sum_qty(is_jacket_metal, last_month_start, last_month_compare_end)
    chg = pct_change(jm_this, jm_last)
    if chg is not None and chg >= TREND_THRESHOLD:
        signals.append({
            "signal":   "포멀 재킷 라인 수요 증가",
            "category": "재킷(J라벨)+금속단추",
            "basis":    f"J라벨+금속단추 출고 {jm_last}→{jm_this}개 ({chg:+.0%})",
        })

    # 4) 플라스틱단추 출고 급감 → 캐주얼 라인 수요 감소
    is_plastic = lambda r: r.item_name.upper().startswith("PLASTIC")
    pl_this = sum_qty(is_plastic, this_month_start, today)
    pl_last = sum_qty(is_plastic, last_month_start, last_month_compare_end)
    chg = pct_change(pl_this, pl_last)
    if chg is not None and chg <= -TREND_THRESHOLD:
        signals.append({
            "signal":   "캐주얼 라인 수요 감소",
            "category": "플라스틱단추",
            "basis":    f"플라스틱단추 출고 {pl_last}→{pl_this}개 ({chg:+.0%})",
        })

    return signals


def build_next_actions(schedule_recs, material_shortages, trend_signals) -> list[str]:
    """오늘 우선 처리해야 할 작업 순서 — 사람이 읽는 요약 문구 리스트"""
    actions = []

    for rec in schedule_recs:
        if rec["deadline_status"] in ("납기불가", "납기위험"):
            actions.append(f"[{rec['priority']}순위] {rec['item_name']} {rec['release_qty']:,}개 — {rec['reason']}")

    for m in material_shortages:
        actions.append(
            f"{m['material_name']} {m['recommended_order_qty']}{m['unit']} 발주 권고 "
            f"(현재 {m['current_qty']}{m['unit']} / 안전재고 {m['safe_qty']}{m['unit']}, {m['level']})"
        )

    for t in trend_signals:
        actions.append(f"📈 트렌드 신호: {t['signal']} — {t['basis']} (플랫폼 보고 대상)")

    if not actions:
        if schedule_recs:
            top = schedule_recs[0]
            actions.append(f"오늘 우선 작업: {top['item_name']} {top['release_qty']:,}개 — {top['reason']}")
        else:
            actions.append("진행 중인 생산 주문이 없습니다. 신규 발주 대기 중.")

    return actions


def build_agent_status(db, raw_stocks: dict, active_releases) -> dict:
    """GET /agent/status 종합 응답 — 지퍼단추사 AI의 현재상황 판단 결과"""
    judgments          = build_active_order_judgments(active_releases, raw_stocks)
    schedule_recs      = build_schedule_recommendations(judgments)
    material_shortages = build_material_shortages(raw_stocks)
    trend_signals      = build_trend_signals(db)

    return {
        "generated_at":             datetime.now().isoformat(),
        "stock_summary":            build_stock_summary(active_releases),
        "raw_material_summary":     build_raw_material_summary(raw_stocks),
        "active_orders":            judgments,
        "schedule_recommendations": schedule_recs,
        "risk_items":               build_risk_items(judgments),
        "material_shortages":       material_shortages,
        "trend_signals":            trend_signals,
        "next_actions":             build_next_actions(schedule_recs, material_shortages, trend_signals),
        "notes": [
            "완제품 재고 테이블 없음 → stock_summary는 생산중 주문 수량 합계로 대체 (로직문서에 명시 없음)",
            "예상완료시각(estimated_completion_at)은 09:00~18:00 영업시간 경계 미반영, "
            "단순 누적시간(now + required_hours)으로 근사 (TODO)",
            "발주 권장량 = 안전재고 - 현재재고 (로직문서에 정확한 산식 없음, 기본값 적용)",
            "트렌드 신호 임계값: 원목단추 +20%는 AI_로직.txt 명시값, 나머지 3개 패턴은 동일 20% 적용 (TODO 확정 필요)",
            "우선순위: 신규 지시문(납기불가>납기위험>납기가까운순>생산량적은순)과 "
            "AI_로직.txt 4번(남은일수적은순→원목단추우선→주문량적은순)을 결합하여 적용 — "
            "납기상태 등급 → 남은일수 → 원목단추 우선 → 생산량 적은순",
        ],
    }
