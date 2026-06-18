"""
Deadline check: aligns material arrival date with production due dates.
Pure computation — no DB access. Designed for use in background tasks.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from services.ai_agent import calculate_agent_result


def build_assessments_snapshot(
    release_snapshots: list[dict],
    stock_map: dict[str, float],
    material_arrivals: dict[str, date] | None = None,
) -> list[dict]:
    """
    For each active production release, compute whether current stock covers it
    and estimate the completion time relative to the due date.

    release_snapshots: [{label_code, release_qty, due_date (date | str)}]
    stock_map:         {"라벨원단": float, "잉크": float, ...}
    material_arrivals: {"라벨원단": earliest_pending_due_date, "잉크": ..., ...}

    Stock is consumed sequentially in snapshot order so later releases reflect
    reduced availability from earlier ones.
    """
    fabric_qty = float(stock_map.get("라벨원단", 0.0))
    ink_qty = float(stock_map.get("잉크", 0.0))
    arrivals: dict[str, date] = material_arrivals or {}

    today = date.today()
    now = datetime.now()
    assessments: list[dict] = []

    for snap in release_snapshots:
        due_date = snap["due_date"]
        if isinstance(due_date, str):
            due_date = date.fromisoformat(due_date)

        analysis = calculate_agent_result(
            label_code=snap["label_code"],
            release_qty=snap["release_qty"],
            due_date=due_date,
            fabric_stock=fabric_qty,
            ink_stock=ink_qty,
            today=today,
            now=now,
        )

        fabric_need = float(analysis.get("required_fabric_m") or 0)
        ink_need = float(analysis.get("required_ink_count") or 0)
        fabric_ok = fabric_qty >= fabric_need
        ink_ok = ink_qty >= ink_need

        # If material is short, find the latest required arrival date
        # (both materials must be ready before production can start)
        arrival_dates: list[date] = []
        if not fabric_ok:
            d = arrivals.get("라벨원단")
            if d:
                arrival_dates.append(d)
        if not ink_ok:
            d = arrivals.get("잉크")
            if d:
                arrival_dates.append(d)
        material_arrival: Optional[date] = max(arrival_dates) if arrival_dates else None

        assessments.append({
            "label_code": snap["label_code"],
            "release_qty": snap["release_qty"],
            "due_date": due_date.isoformat(),
            "deadline_status": analysis["deadline_status"],
            "estimated_completion_at": analysis["estimated_completion_at"],
            "stock_ok": analysis["stock_ok"],
            "fabric_ok": fabric_ok,
            "ink_ok": ink_ok,
            "material_arrival_date": material_arrival.isoformat() if material_arrival else None,
        })

        # Consume stock for subsequent releases (sequential production)
        fabric_qty = max(fabric_qty - fabric_need, 0.0)
        ink_qty = max(ink_qty - ink_need, 0.0)

    return assessments
