"""
케어라벨 생산 판단 로직
생산규칙.txt + AI_로직.txt 기준 구현
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from services.label_validator import parse_label_code, validate_label_code
from services.production_config import (
    DAILY_HOURS,
    MACHINE_COUNT,
    MAX_DAILY,
    SPEED_PER_PRINTER,
    TOTAL_FACTORY_SPEED_PER_HOUR,
    add_work_hours,
    machine_name,
)
from services.weight_logic import (
    calculate_fabric_m_for_release,
    calculate_fabric_weight_kg_for_release,
    calculate_ink_units_for_release,
    calculate_ink_weight_kg_for_release,
    calculate_label_weight_kg,
    calculate_stock_weight_kg,
)

SAFE_FABRIC_M = 500
SAFE_INK_CAN = 5

# TODO: 주문 1건을 여러 기계에 동시에 분할 투입하는 규칙은 로직 문서에 없음.
# 현재는 "한 시점에 기계 1대 = 주문 1건" 기준으로 기계별 순차 큐를 greedy 배정한다.
SCHEDULING_STRATEGY = "single_order_per_machine_greedy_with_queue"

STATUS_SEVERITY = {
    "납기가능": 0,
    "납기위험": 1,
    "납기불가": 2,
    "오류": 3,
}


def calculate_material_requirements(release_qty: int) -> tuple[int, int]:
    return (
        calculate_fabric_m_for_release(release_qty),
        calculate_ink_units_for_release(release_qty),
    )


def calculate_required_hours(release_qty: int, printers: int = MACHINE_COUNT) -> float:
    total_speed = max(printers, 1) * SPEED_PER_PRINTER
    return release_qty / total_speed


def calculate_required_days(required_hours: float) -> int:
    return math.ceil(required_hours / DAILY_HOURS)


def get_status_severity(status: str | None) -> int:
    if status is None:
        return -1
    return STATUS_SEVERITY.get(status, -1)


def get_more_severe_status(*statuses: str | None) -> str:
    valid_statuses = [status for status in statuses if status]
    if not valid_statuses:
        return "오류"
    return max(valid_statuses, key=get_status_severity)


def calculate_rule_based_deadline_status(required_days: int, due_date: date, today: date) -> tuple[str, int]:
    days_remaining = (due_date - today).days
    if days_remaining >= required_days + 1:
        return "납기가능", days_remaining
    if days_remaining >= required_days:
        return "납기위험", days_remaining
    return "납기불가", days_remaining


def calculate_schedule_deadline_status(estimated_completion_at: datetime, due_date: date) -> str:
    completion_date = estimated_completion_at.date()
    if completion_date > due_date:
        return "납기불가"
    if completion_date >= due_date - timedelta(days=1):
        return "납기위험"
    return "납기가능"


def _summarize_deadline_status(
    deadline_status: str,
    due_date: date,
    estimated_completion_at: datetime,
    required_days: int,
    days_remaining: int,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    instructions: list[str] = []

    completion_text = estimated_completion_at.strftime("%Y-%m-%d %H:%M")
    if deadline_status == "납기불가":
        warnings.append(
            f"납기 불가: 완료예정 {completion_text}, 납기 {due_date.isoformat()} "
            f"(필요 {required_days}일 / 남은 {days_remaining}일)"
        )
        instructions.append("납기일 조정 또는 긴급 생산 검토 필요")
    elif deadline_status == "납기위험":
        warnings.append(
            f"납기 위험: 완료예정 {completion_text}, 납기 {due_date.isoformat()} "
            f"(필요 {required_days}일 / 남은 {days_remaining}일)"
        )
        instructions.append("오늘 우선 생산으로 배정하세요")

    return warnings, instructions


def calculate_agent_result(
    label_code: str,
    release_qty: int,
    due_date: date,
    fabric_stock: float,
    ink_stock: float,
    today: date | None = None,
    now: datetime | None = None,
    estimated_start_at: datetime | None = None,
    priority_rank: int | None = None,
    printers: int = MACHINE_COUNT,
) -> dict:
    today = today or date.today()
    now = now or datetime.now()
    estimated_start_at = estimated_start_at or now

    warnings: list[str] = []
    instructions: list[str] = []

    is_valid, msg = validate_label_code(label_code)
    if not is_valid:
        return {
            "label_code": label_code,
            "is_valid": False,
            "parsed_info": None,
            "required_hours": 0,
            "required_days": 0,
            "rule_based_status": "오류",
            "schedule_status": "오류",
            "deadline_status": "오류",
            "days_remaining": 0,
            "required_fabric_m": 0,
            "required_ink_count": 0,
            "product_weight_kg": 0,
            "required_fabric_weight_kg": 0,
            "required_ink_weight_kg": 0,
            "required_material_weight_kg": 0,
            "fabric_stock": fabric_stock,
            "ink_stock": ink_stock,
            "available_fabric_after_m": fabric_stock,
            "available_ink_after_count": ink_stock,
            "stock_ok": False,
            "estimated_start_at": estimated_start_at.isoformat(timespec="minutes"),
            "estimated_completion_at": None,
            "warnings": [f"라벨코드 오류: {msg}"],
            "instructions": ["라벨코드를 확인하고 다시 입력하세요"],
            "status_basis": ["라벨코드 유효성 검증 실패"],
            "priority_rank": priority_rank,
        }

    parsed_info = parse_label_code(label_code)
    required_hours = calculate_required_hours(release_qty, printers)
    required_days = calculate_required_days(required_hours)
    required_fabric_m, required_ink_count = calculate_material_requirements(release_qty)
    product_weight_kg = calculate_label_weight_kg(release_qty)
    required_fabric_weight_kg = calculate_fabric_weight_kg_for_release(release_qty)
    required_ink_weight_kg = calculate_ink_weight_kg_for_release(release_qty)
    estimated_completion_at = add_work_hours(estimated_start_at, required_hours)

    rule_based_status, days_remaining = calculate_rule_based_deadline_status(required_days, due_date, today)
    schedule_status = calculate_schedule_deadline_status(estimated_completion_at, due_date)
    deadline_status = get_more_severe_status(rule_based_status, schedule_status)

    status_warnings, status_instructions = _summarize_deadline_status(
        deadline_status=deadline_status,
        due_date=due_date,
        estimated_completion_at=estimated_completion_at,
        required_days=required_days,
        days_remaining=days_remaining,
    )
    warnings.extend(status_warnings)
    instructions.extend(status_instructions)

    fabric_ok = fabric_stock >= required_fabric_m
    ink_ok = ink_stock >= required_ink_count
    stock_ok = fabric_ok and ink_ok

    if not fabric_ok:
        shortage = required_fabric_m - fabric_stock
        warnings.append(
            f"라벨원단 부족: 필요 {required_fabric_m}m, 현재 {fabric_stock}m (부족 {shortage}m)"
        )
        instructions.append(f"라벨원단 {shortage}m 이상 입고 후 생산하세요")

    if not ink_ok:
        shortage = required_ink_count - ink_stock
        warnings.append(
            f"잉크 부족: 필요 {required_ink_count}개, 현재 {ink_stock}개 (부족 {shortage}개)"
        )
        instructions.append(f"잉크 {shortage}개 이상 입고 후 생산하세요")

    if fabric_ok and fabric_stock <= SAFE_FABRIC_M:
        warnings.append(f"라벨원단 안전재고 이하: {fabric_stock}m (기준 {SAFE_FABRIC_M}m)")
        instructions.append("라벨원단 발주 권고")

    if ink_ok and ink_stock <= SAFE_INK_CAN:
        warnings.append(f"잉크 안전재고 이하: {ink_stock}개 (기준 {SAFE_INK_CAN}개)")
        instructions.append("잉크 발주 권고")

    available_fabric_after_m = max(fabric_stock - required_fabric_m, 0)
    available_ink_after_count = max(ink_stock - required_ink_count, 0)

    if stock_ok and deadline_status == "납기가능" and not warnings:
        instructions.append(
            f"정상: {label_code} {release_qty:,}매 생산 가능 "
            f"(완료예정 {estimated_completion_at.strftime('%Y-%m-%d %H:%M')})"
        )

    status_basis = [
        f"문서기준={rule_based_status}",
        f"완료예정기준={schedule_status}",
        f"기계수={printers}대 기준",
    ]
    if rule_based_status != schedule_status:
        status_basis.append("상충 시 더 보수적인 상태를 채택")

    return {
        "label_code": label_code,
        "is_valid": True,
        "parsed_info": parsed_info,
        "required_hours": round(required_hours, 2),
        "required_days": required_days,
        "rule_based_status": rule_based_status,
        "schedule_status": schedule_status,
        "deadline_status": deadline_status,
        "days_remaining": days_remaining,
        "required_fabric_m": float(required_fabric_m),
        "required_ink_count": required_ink_count,
        "product_weight_kg": product_weight_kg,
        "required_fabric_weight_kg": required_fabric_weight_kg,
        "required_ink_weight_kg": required_ink_weight_kg,
        "required_material_weight_kg": round(required_fabric_weight_kg + required_ink_weight_kg, 3),
        "fabric_stock": fabric_stock,
        "ink_stock": ink_stock,
        "available_fabric_after_m": float(available_fabric_after_m),
        "available_ink_after_count": float(available_ink_after_count),
        "stock_ok": stock_ok,
        "estimated_start_at": estimated_start_at.isoformat(timespec="minutes"),
        "estimated_completion_at": estimated_completion_at.isoformat(timespec="minutes"),
        "warnings": warnings,
        "instructions": instructions,
        "status_basis": status_basis,
        "priority_rank": priority_rank,
    }


def _build_stock_item(name: str, current_qty: float, safe_qty: float, unit: str) -> dict:
    if current_qty <= 0:
        status = "재고없음"
    elif current_qty <= safe_qty:
        status = "안전재고이하"
    else:
        status = "정상"

    shortage_to_safe = max(safe_qty - current_qty, 0)
    if status == "재고없음":
        summary = f"{name} 재고가 없습니다. 즉시 발주 필요"
    elif status == "안전재고이하":
        summary = f"{name} {current_qty}{unit}로 안전재고 이하입니다"
    else:
        summary = f"{name} 재고 정상 ({current_qty}{unit})"

    return {
        "material_name": name,
        "current_qty": current_qty,
        "safe_qty": safe_qty,
        "unit": unit,
        "weight_kg": calculate_stock_weight_kg(name, current_qty),
        "status": status,
        "shortage_to_safe": shortage_to_safe,
        "summary": summary,
    }


def _order_priority_key(order: dict) -> tuple[int, date, int, int]:
    return (
        -get_status_severity(order["deadline_status"]),
        order["due_date_obj"],
        order["release_qty"],
        order["id"],
    )


def _build_order_summary(order: dict) -> str:
    d_day = f"D-{order['days_remaining']}" if order["days_remaining"] >= 0 else f"D+{abs(order['days_remaining'])}"
    machine_suffix = f" / 추천 {order['assigned_machine_name']}" if order.get("assigned_machine_name") else ""
    return (
        f"{order['label_code']} {order['release_qty']:,}매, "
        f"라벨원단 {int(order['required_fabric_m'])}m 필요, "
        f"잉크 {int(order['required_ink_count'])}개 필요, "
        f"납기 {d_day}, {order['deadline_status']}{machine_suffix}"
    )


def _fmt_machine_time(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("T", " ")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _to_iso_minutes(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.isoformat(timespec="minutes")


def _estimate_order_completion(start_at: datetime, release_qty: int) -> datetime:
    return add_work_hours(start_at, release_qty / SPEED_PER_PRINTER)


def _build_planned_order(
    machine: dict,
    order: dict,
    start_at: datetime,
    completion_at: datetime,
    source: str,
) -> dict:
    return {
        "release_id": order["id"],
        "label_code": order["label_code"],
        "release_qty": order["release_qty"],
        "estimated_start_at": _to_iso_minutes(start_at),
        "estimated_completion_at": _to_iso_minutes(completion_at),
        "deadline_status": calculate_schedule_deadline_status(completion_at, order["due_date_obj"]),
        "machine_id": machine["id"],
        "machine_name": machine["name"],
        "machine_status": machine["status"],
        "source": source,
    }


def _queue_preview(items: list[dict], limit: int = 3) -> str:
    if not items:
        return ""
    preview = " -> ".join(item["label_code"] for item in items[:limit])
    if len(items) > limit:
        preview += f" 외 {len(items) - limit}건"
    return preview


def _build_default_machine_snapshots() -> list[dict]:
    snapshots = []
    for machine_id in range(1, MACHINE_COUNT + 1):
        snapshots.append({
            "id": machine_id,
            "name": machine_name(machine_id),
            "status": "대기중",
            "release_id": None,
            "label_code": None,
            "total_qty": 0,
            "produced_qty": 0,
            "remaining_qty": 0,
            "started_at": None,
            "running_started_at": None,
            "finished_at": None,
            "estimated_completion_at": None,
            "queue_count": 0,
            "queue_items": [],
        })
    return snapshots


def _build_machine_recommendations(active_orders: list[dict], machine_snapshots: list[dict], now: datetime) -> list[dict]:
    orders_by_id = {order["id"]: order for order in active_orders}
    sorted_orders = sorted(active_orders, key=_order_priority_key)
    reserved_order_ids: set[int] = set()
    machine_plans: list[dict] = []

    for machine in sorted(machine_snapshots, key=lambda item: item["id"]):
        plan = {
            "machine": machine,
            "machine_id": machine["id"],
            "machine_name": machine["name"],
            "machine_status": machine["status"],
            "active_current_release_id": None,
            "completed_current_order": None,
            "planned_orders": [],
            "tracked_orders": [],
            "available_at": now,
            "excluded": machine["status"] == "점검중",
        }

        current_release_id = machine.get("release_id")
        current_order = orders_by_id.get(current_release_id) if current_release_id else None
        remaining_qty = float(machine.get("remaining_qty") or 0)

        if current_release_id and current_order and remaining_qty > 0:
            start_at = _parse_iso_datetime(machine.get("running_started_at") or machine.get("started_at")) or now
            completion_at = (
                _parse_iso_datetime(machine.get("estimated_completion_at"))
                or _estimate_order_completion(now, math.ceil(remaining_qty))
            )
            planned_order = _build_planned_order(machine, current_order, start_at, completion_at, "current")
            plan["active_current_release_id"] = current_release_id
            plan["planned_orders"].append(planned_order)
            plan["tracked_orders"].append(planned_order)
            plan["available_at"] = completion_at
            reserved_order_ids.add(current_release_id)
        elif machine["status"] == "완료" and current_release_id and current_order:
            completion_at = _parse_iso_datetime(machine.get("finished_at")) or now
            start_at = _parse_iso_datetime(machine.get("started_at")) or completion_at
            completed_order = _build_planned_order(machine, current_order, start_at, completion_at, "completed")
            plan["completed_current_order"] = completed_order
            plan["tracked_orders"].append(completed_order)
            reserved_order_ids.add(current_release_id)

        for queue_item in machine.get("queue_items") or []:
            queued_order = orders_by_id.get(queue_item["release_id"])
            if not queued_order:
                continue
            start_at = plan["available_at"]
            completion_at = _estimate_order_completion(start_at, queued_order["release_qty"])
            planned_order = _build_planned_order(machine, queued_order, start_at, completion_at, "queue")
            plan["planned_orders"].append(planned_order)
            plan["tracked_orders"].append(planned_order)
            plan["available_at"] = completion_at
            reserved_order_ids.add(queued_order["id"])

        machine_plans.append(plan)

    pending_orders = [order for order in sorted_orders if order["id"] not in reserved_order_ids]
    assignable_plans = [plan for plan in machine_plans if not plan["excluded"]]

    for order in pending_orders:
        if not assignable_plans:
            break
        target_plan = min(
            assignable_plans,
            key=lambda item: (item["available_at"], item["machine_id"]),
        )
        start_at = target_plan["available_at"]
        completion_at = _estimate_order_completion(start_at, order["release_qty"])
        planned_order = _build_planned_order(target_plan["machine"], order, start_at, completion_at, "recommended")
        target_plan["planned_orders"].append(planned_order)
        target_plan["tracked_orders"].append(planned_order)
        target_plan["available_at"] = completion_at

    recommendations: list[dict] = []

    for plan in machine_plans:
        machine = plan["machine"]
        current_queue_ids = [item["release_id"] for item in machine.get("queue_items") or []]
        tracked_orders = plan["tracked_orders"]
        active_release_id = plan["active_current_release_id"]
        completed_order = plan["completed_current_order"]
        planned_orders = plan["planned_orders"]

        recommendation = {
            "machine_id": machine["id"],
            "machine_name": machine["name"],
            "machine_status": machine["status"],
            "recommended_release_id": None,
            "recommended_label_code": None,
            "estimated_start_at": None,
            "estimated_completion_at": None,
            "deadline_status": None,
            "summary": "",
            "assignment_release_id": None,
            "queue_release_ids": [],
            "apply_release_ids": [],
            "planned_release_ids": [item["release_id"] for item in tracked_orders],
            "planned_orders": tracked_orders,
            "apply_required": False,
        }

        if machine["status"] == "점검중":
            if planned_orders:
                recommendation["summary"] = (
                    f"{machine['name']}: 점검중, 현재 배정 유지 및 신규 배정 제외 "
                    f"({_queue_preview(planned_orders)})"
                )
            elif completed_order:
                recommendation["summary"] = f"{machine['name']}: 점검중, 완료 작업 정리 후 점검 해제 필요"
            else:
                recommendation["summary"] = f"{machine['name']}: 점검중 배정 제외"
            recommendations.append(recommendation)
            continue

        if active_release_id and planned_orders:
            current_order = planned_orders[0]
            queue_orders = planned_orders[1:]
            recommendation.update({
                "recommended_release_id": current_order["release_id"],
                "recommended_label_code": current_order["label_code"],
                "estimated_start_at": current_order["estimated_start_at"],
                "estimated_completion_at": current_order["estimated_completion_at"],
                "deadline_status": current_order["deadline_status"],
                "queue_release_ids": [item["release_id"] for item in queue_orders],
                "apply_release_ids": [current_order["release_id"], *[item["release_id"] for item in queue_orders]],
                "apply_required": current_queue_ids != [item["release_id"] for item in queue_orders],
            })
            summary = (
                f"{machine['name']}: {current_order['label_code']} {machine['status']}, "
                f"예상완료 {_fmt_machine_time(current_order['estimated_completion_at'])}"
            )
            if queue_orders:
                summary += f", 이후 {_queue_preview(queue_orders)} 순차 배정"
            recommendation["summary"] = summary
            recommendations.append(recommendation)
            continue

        if completed_order:
            future_orders = planned_orders
            if future_orders:
                first_future = future_orders[0]
                recommendation.update({
                    "recommended_release_id": first_future["release_id"],
                    "recommended_label_code": first_future["label_code"],
                    "estimated_start_at": first_future["estimated_start_at"],
                    "estimated_completion_at": first_future["estimated_completion_at"],
                    "deadline_status": first_future["deadline_status"],
                    "queue_release_ids": [item["release_id"] for item in future_orders],
                    "apply_release_ids": [item["release_id"] for item in future_orders],
                    "apply_required": current_queue_ids != [item["release_id"] for item in future_orders],
                })
                recommendation["summary"] = (
                    f"{machine['name']}: {completed_order['label_code']} 작업 완료, "
                    f"다음 {_queue_preview(future_orders)} 대기"
                )
            else:
                recommendation.update({
                    "recommended_release_id": completed_order["release_id"],
                    "recommended_label_code": completed_order["label_code"],
                    "estimated_start_at": completed_order["estimated_start_at"],
                    "estimated_completion_at": completed_order["estimated_completion_at"],
                    "deadline_status": completed_order["deadline_status"],
                })
                recommendation["summary"] = (
                    f"{machine['name']}: {completed_order['label_code']} 작업 완료, 완료 처리 후 초기화 권장"
                )
            recommendations.append(recommendation)
            continue

        if planned_orders:
            first_order = planned_orders[0]
            queue_orders = planned_orders[1:]
            recommendation.update({
                "recommended_release_id": first_order["release_id"],
                "recommended_label_code": first_order["label_code"],
                "estimated_start_at": first_order["estimated_start_at"],
                "estimated_completion_at": first_order["estimated_completion_at"],
                "deadline_status": first_order["deadline_status"],
                "assignment_release_id": first_order["release_id"],
                "queue_release_ids": [item["release_id"] for item in queue_orders],
                "apply_release_ids": [first_order["release_id"], *[item["release_id"] for item in queue_orders]],
                "apply_required": (
                    machine.get("release_id") != first_order["release_id"]
                    or current_queue_ids != [item["release_id"] for item in queue_orders]
                ),
            })
            summary = (
                f"{machine['name']}: {first_order['label_code']} {first_order['release_qty']:,}매 우선 배정, "
                f"예상완료 {_fmt_machine_time(first_order['estimated_completion_at'])}"
            )
            if queue_orders:
                summary += f", 이후 {_queue_preview(queue_orders)} 순차 배정"
            recommendation["summary"] = summary
        else:
            recommendation["summary"] = f"{machine['name']}: 배정 가능한 신규 작업 없음"

        recommendations.append(recommendation)

    return recommendations


def build_agent_status_snapshot(
    active_releases: list,
    stock_map: dict[str, float],
    platform_report_status: dict | None = None,
    machine_snapshots: list[dict] | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> dict:
    today = today or date.today()
    now = now or datetime.now()
    machine_snapshots = machine_snapshots or _build_default_machine_snapshots()

    fabric_qty = float(stock_map.get("라벨원단", 0.0))
    ink_qty = float(stock_map.get("잉크", 0.0))

    stock_summary = {
        "fabric": _build_stock_item("라벨원단", fabric_qty, SAFE_FABRIC_M, "m"),
        "ink": _build_stock_item("잉크", ink_qty, SAFE_INK_CAN, "개"),
    }
    stock_summary["warnings"] = [
        item["summary"]
        for item in (stock_summary["fabric"], stock_summary["ink"])
        if item["status"] != "정상"
    ]
    stock_summary["all_materials_ok"] = not stock_summary["warnings"]

    active_orders: list[dict] = []
    for release in active_releases:
        analysis = calculate_agent_result(
            label_code=release.label_code,
            release_qty=release.release_qty,
            due_date=release.due_date,
            fabric_stock=fabric_qty,
            ink_stock=ink_qty,
            today=today,
            now=now,
            printers=MACHINE_COUNT,
        )
        analysis.update({
            "id": release.id,
            "release_qty": release.release_qty,
            "due_date": release.due_date.isoformat(),
            "due_date_obj": release.due_date,
            "created_at": release.created_at.isoformat(timespec="minutes") if release.created_at else None,
            "started_at_recorded": release.started_at.isoformat(timespec="minutes") if release.started_at else None,
            "finished_at_recorded": release.finished_at.isoformat(timespec="minutes") if release.finished_at else None,
            "status": release.status,
            "assigned_machine_id": None,
            "assigned_machine_name": None,
            "machine_status": None,
            "machine_estimated_start_at": None,
            "machine_estimated_completion_at": None,
        })
        active_orders.append(analysis)

    machine_recommendations = _build_machine_recommendations(active_orders, machine_snapshots, now)
    recommendations_by_release: dict[int, dict] = {}
    for recommendation in machine_recommendations:
        for planned_order in recommendation.get("planned_orders", []):
            recommendations_by_release[planned_order["release_id"]] = planned_order

    for order in active_orders:
        planned_order = recommendations_by_release.get(order["id"])
        if not planned_order:
            continue
        order["assigned_machine_id"] = planned_order["machine_id"]
        order["assigned_machine_name"] = planned_order["machine_name"]
        order["machine_status"] = planned_order["machine_status"]
        order["machine_estimated_start_at"] = planned_order["estimated_start_at"]
        order["machine_estimated_completion_at"] = planned_order["estimated_completion_at"]
        if planned_order.get("deadline_status"):
            order["deadline_status"] = get_more_severe_status(
                order["deadline_status"],
                planned_order["deadline_status"],
            )

    final_orders = sorted(active_orders, key=_order_priority_key)

    remaining_fabric = fabric_qty
    remaining_ink = ink_qty
    schedule_recommendations: list[dict] = []
    risk_items: list[dict] = []
    material_shortages: list[dict] = []
    next_actions: list[str] = []

    for index, order in enumerate(final_orders, start=1):
        order["priority_rank"] = index
        order["summary"] = _build_order_summary(order)

        if remaining_fabric < order["required_fabric_m"]:
            shortage_qty = round(order["required_fabric_m"] - remaining_fabric, 2)
            material_shortages.append({
                "label_code": order["label_code"],
                "material_name": "라벨원단",
                "required_qty": order["required_fabric_m"],
                "available_qty": round(remaining_fabric, 2),
                "shortage_qty": shortage_qty,
                "unit": "m",
                "summary": f"{order['label_code']} 생산 전 라벨원단 {shortage_qty}m 추가 필요",
            })

        if remaining_ink < order["required_ink_count"]:
            shortage_qty = round(order["required_ink_count"] - remaining_ink, 2)
            material_shortages.append({
                "label_code": order["label_code"],
                "material_name": "잉크",
                "required_qty": order["required_ink_count"],
                "available_qty": round(remaining_ink, 2),
                "shortage_qty": shortage_qty,
                "unit": "개",
                "summary": f"{order['label_code']} 생산 전 잉크 {shortage_qty}개 추가 필요",
            })

        remaining_fabric = max(remaining_fabric - order["required_fabric_m"], 0)
        remaining_ink = max(remaining_ink - order["required_ink_count"], 0)

        schedule_recommendations.append({
            "priority_rank": index,
            "label_code": order["label_code"],
            "deadline_status": order["deadline_status"],
            "estimated_start_at": order.get("machine_estimated_start_at") or order["estimated_start_at"],
            "estimated_completion_at": order.get("machine_estimated_completion_at") or order["estimated_completion_at"],
            "summary": order["summary"],
        })

        if order["deadline_status"] != "납기가능":
            risk_items.append({
                "id": order["id"],
                "label_code": order["label_code"],
                "deadline_status": order["deadline_status"],
                "due_date": order["due_date"],
                "estimated_completion_at": order.get("machine_estimated_completion_at") or order["estimated_completion_at"],
                "summary": order["summary"],
            })

    if final_orders:
        top_order = final_orders[0]
        machine_text = top_order["assigned_machine_name"] or "배정기계 미정"
        next_actions.append(
            f"1순위 {top_order['label_code']} {top_order['release_qty']:,}매를 먼저 처리하세요 "
            f"({top_order['deadline_status']} / {machine_text})"
        )
    else:
        next_actions.append("진행중 생산 주문이 없습니다. 신규 생산 등록과 원자재 재고만 모니터링하세요")

    for recommendation in machine_recommendations[:3]:
        next_actions.append(recommendation["summary"])

    for warning in stock_summary["warnings"]:
        next_actions.append(warning)

    for shortage in material_shortages[:3]:
        next_actions.append(shortage["summary"])

    machine_summary = {
        "total": len(machine_snapshots),
        "running": sum(1 for machine in machine_snapshots if machine["status"] == "가동중"),
        "standby": sum(1 for machine in machine_snapshots if machine["status"] == "대기중"),
        "repair": sum(1 for machine in machine_snapshots if machine["status"] == "점검중"),
        "done": sum(1 for machine in machine_snapshots if machine["status"] == "완료"),
    }

    logic_notes = [
        f"라벨 인쇄기 {MACHINE_COUNT}대, 총 {TOTAL_FACTORY_SPEED_PER_HOUR:,}매/h, 최대 일일 {MAX_DAILY:,}매 기준으로 계산",
        "기계별 배정 추천은 납기 우선 + 가장 빨리 비는 기계 우선의 단순 greedy 방식 사용",
        "주문 1건을 여러 기계에 동시에 분할 투입하는 규칙은 문서에 없음",
        "현재는 한 시점에 기계 1대당 주문 1건만 처리하고, 뒤 작업은 같은 기계 큐에 순차 배정",
    ]

    return {
        "stock_summary": stock_summary,
        "active_orders": [
            {key: value for key, value in order.items() if key != "due_date_obj"}
            for order in final_orders
        ],
        "schedule_recommendations": schedule_recommendations,
        "risk_items": risk_items,
        "material_shortages": material_shortages,
        "next_actions": next_actions,
        "machine_recommendations": machine_recommendations,
        "machine_summary": machine_summary,
        "machine_statuses": machine_snapshots,
        "platform_report_status": platform_report_status or {
            "summary": "최근 플랫폼 보고 없음",
            "recent_reports": [],
            "waiting_count": 0,
            "success_count": 0,
        },
        "logic_notes": logic_notes,
        "scheduling_strategy": SCHEDULING_STRATEGY,
    }
