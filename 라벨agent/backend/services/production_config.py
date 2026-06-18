from __future__ import annotations

from datetime import datetime, timedelta

MACHINE_COUNT = 6
SPEED_PER_PRINTER = 800
DAILY_HOURS = 9
WORKDAY_START_HOUR = 9
WORKDAY_END_HOUR = 18

TOTAL_FACTORY_SPEED_PER_HOUR = MACHINE_COUNT * SPEED_PER_PRINTER
MAX_DAILY = TOTAL_FACTORY_SPEED_PER_HOUR * DAILY_HOURS
MACHINE_SPEED_PER_SECOND = SPEED_PER_PRINTER / 3600


def machine_name(machine_id: int) -> str:
    return f"인쇄기 {machine_id}호"


def align_to_work_start(dt: datetime) -> datetime:
    work_start = dt.replace(hour=WORKDAY_START_HOUR, minute=0, second=0, microsecond=0)
    work_end = dt.replace(hour=WORKDAY_END_HOUR, minute=0, second=0, microsecond=0)

    if dt < work_start:
        return work_start
    if dt >= work_end:
        return work_start + timedelta(days=1)
    return dt.replace(second=0, microsecond=0)


def add_work_hours(start_at: datetime, hours: float) -> datetime:
    current = align_to_work_start(start_at)
    remaining = hours

    while remaining > 1e-9:
        work_end = current.replace(hour=WORKDAY_END_HOUR, minute=0, second=0, microsecond=0)
        available_hours = max((work_end - current).total_seconds() / 3600, 0)

        if remaining <= available_hours + 1e-9:
            return current + timedelta(hours=remaining)

        remaining -= available_hours
        current = (current + timedelta(days=1)).replace(
            hour=WORKDAY_START_HOUR,
            minute=0,
            second=0,
            microsecond=0,
        )

    return current
