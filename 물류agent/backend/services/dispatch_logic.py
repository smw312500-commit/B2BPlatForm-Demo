from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from models import Delivery, Driver

# 출발지(시) → 도착지(항) 이동시간 매트릭스 (단위: 시간)
TRAVEL_HOURS = {
    "부산시": {"부산항": 1, "인천항": 6},
    "서울시": {"인천항": 1, "부산항": 5},
    "인천시": {"인천항": 0.5, "부산항": 5},
}
DEFAULT_TRAVEL_HOURS = 24


def get_travel_hours(origin_si: str | None, destination: str | None) -> float:
    if not origin_si or not destination:
        return DEFAULT_TRAVEL_HOURS
    return TRAVEL_HOURS.get(origin_si, {}).get(destination, DEFAULT_TRAVEL_HOURS)


def get_travel_label(hours: float) -> str:
    if hours < 1:
        return f"약 {int(hours * 60)}분 소요"
    if hours == int(hours):
        return f"약 {int(hours)}시간 소요"
    return f"약 {hours}시간 소요"


def calc_pickup_date(due_date: date, destination: str | None, origin_si: str | None) -> date:
    hours = get_travel_hours(origin_si, destination)
    buffer = 1 if hours < 3 else 2
    return due_date - timedelta(days=buffer)


def select_best_driver(delivery: Delivery, drivers: list[Driver]) -> Optional[Driver]:
    available = [driver for driver in drivers if driver.status == "가용"]
    if not available:
        return None

    same_si = [driver for driver in available if driver.location_si == delivery.origin_si]
    if same_si:
        return same_si[0]

    return available[0]


def check_round_trip(delivery: Delivery, deliveries: list[Delivery]) -> str:
    if delivery.destination == "인천항":
        return_origin_si, return_dest = "인천시", "부산항"
    else:
        return_origin_si, return_dest = "부산시", "인천항"

    for candidate in deliveries:
        if (
            candidate.id != delivery.id
            and candidate.status == "배차대기"
            and candidate.destination == return_dest
            and candidate.origin_si == return_origin_si
            and candidate.due_date
            and delivery.due_date
            and candidate.due_date >= delivery.due_date
        ):
            return f"연결완료 (귀환 시 {candidate.origin_si} 픽업 가능)"

    return "빈차 귀환"
