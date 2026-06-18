from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from models import LabelMachine, LabelMachineQueue, LabelRelease
from services.production_config import (
    MACHINE_COUNT,
    MACHINE_SPEED_PER_SECOND,
    SPEED_PER_PRINTER,
    add_work_hours,
    machine_name,
)


def ensure_machine_rows(db: Session) -> list[LabelMachine]:
    existing = {machine.id: machine for machine in db.query(LabelMachine).all()}
    created = False

    for machine_id in range(1, MACHINE_COUNT + 1):
        if machine_id in existing:
            continue
        db.add(LabelMachine(id=machine_id, name=machine_name(machine_id), status="대기중"))
        created = True

    if created:
        db.commit()

    return db.query(LabelMachine).order_by(LabelMachine.id).all()


def compute_live_produced(machine: LabelMachine, now: datetime | None = None) -> float:
    now = now or datetime.now()
    produced = float(machine.produced_qty or 0)
    total = int(machine.total_qty or 0)

    if machine.status == "가동중" and machine.running_started_at and total > 0:
        elapsed = max((now - machine.running_started_at).total_seconds(), 0)
        produced = min(total, produced + elapsed * MACHINE_SPEED_PER_SECOND)
    elif machine.status == "완료":
        produced = float(total)

    return round(produced, 2)


def get_machine_queue_rows(db: Session, machine_id: int | None = None) -> list[LabelMachineQueue]:
    query = db.query(LabelMachineQueue)
    if machine_id is not None:
        query = query.filter(LabelMachineQueue.machine_id == machine_id)
    return query.order_by(LabelMachineQueue.machine_id, LabelMachineQueue.sequence, LabelMachineQueue.id).all()


def normalize_machine_queue(db: Session, machine_id: int) -> list[LabelMachineQueue]:
    rows = get_machine_queue_rows(db, machine_id)
    for index, row in enumerate(rows, start=1):
        row.sequence = index
    return rows


def assign_release_to_machine(machine: LabelMachine, release: LabelRelease | None) -> None:
    if release is None:
        machine.release_id = None
        machine.label_code = None
        machine.total_qty = 0
        machine.produced_qty = 0
        machine.started_at = None
        machine.running_started_at = None
        machine.finished_at = None
        if machine.status != "점검중":
            machine.status = "대기중"
        return

    machine.release_id = release.id
    machine.label_code = release.label_code
    machine.total_qty = release.release_qty
    machine.produced_qty = 0
    machine.started_at = None
    machine.running_started_at = None
    machine.finished_at = None
    if machine.status == "완료":
        machine.status = "대기중"


def pop_next_queue_release(db: Session, machine: LabelMachine) -> LabelRelease | None:
    next_row = (
        db.query(LabelMachineQueue)
        .filter(LabelMachineQueue.machine_id == machine.id)
        .order_by(LabelMachineQueue.sequence, LabelMachineQueue.id)
        .first()
    )
    if not next_row:
        return None

    release = db.query(LabelRelease).filter(LabelRelease.id == next_row.release_id).first()
    db.delete(next_row)
    normalize_machine_queue(db, machine.id)
    return release


def promote_next_queue_release(db: Session, machine: LabelMachine) -> LabelRelease | None:
    assign_release_to_machine(machine, None)
    next_release = pop_next_queue_release(db, machine)
    if next_release:
        assign_release_to_machine(machine, next_release)
    return next_release


def sync_machine_progress(db: Session, now: datetime | None = None) -> list[LabelMachine]:
    now = now or datetime.now()
    machines = ensure_machine_rows(db)
    changed = False

    for machine in machines:
        if machine.release_id:
            release = db.query(LabelRelease).filter(LabelRelease.id == machine.release_id).first()
            if not release or release.status != "생산중":
                promote_next_queue_release(db, machine)
                changed = True
                continue

        total = int(machine.total_qty or 0)
        if machine.status != "가동중" or not machine.running_started_at or total <= 0:
            continue

        live_produced = compute_live_produced(machine, now)
        if live_produced < total:
            continue

        machine.produced_qty = total
        machine.status = "완료"
        machine.running_started_at = None
        if not machine.finished_at:
            machine.finished_at = now

        if machine.release_id:
            release = db.query(LabelRelease).filter(LabelRelease.id == machine.release_id).first()
            if release:
                if not release.started_at and machine.started_at:
                    release.started_at = machine.started_at
                if not release.finished_at:
                    release.finished_at = machine.finished_at
        changed = True

    if changed:
        db.commit()
        machines = ensure_machine_rows(db)

    return machines


def _build_queue_item_map(db: Session) -> dict[int, list[dict]]:
    queue_rows = get_machine_queue_rows(db)
    if not queue_rows:
        return {}

    release_ids = [row.release_id for row in queue_rows]
    release_map = {
        release.id: release
        for release in db.query(LabelRelease).filter(LabelRelease.id.in_(release_ids)).all()
    }

    queue_map: dict[int, list[dict]] = {}
    for row in queue_rows:
        release = release_map.get(row.release_id)
        if not release:
            continue
        queue_map.setdefault(row.machine_id, []).append({
            "release_id": release.id,
            "label_code": release.label_code,
            "release_qty": release.release_qty,
            "due_date": release.due_date.isoformat(),
            "sequence": row.sequence,
        })

    return queue_map


def build_machine_snapshot(
    machine: LabelMachine,
    now: datetime | None = None,
    queue_items: list[dict] | None = None,
) -> dict:
    now = now or datetime.now()
    queue_items = queue_items or []
    total = int(machine.total_qty or 0)
    produced = compute_live_produced(machine, now)
    remaining = max(total - produced, 0)

    estimated_completion_at = None
    if machine.status == "가동중" and remaining > 0:
        estimated_completion_at = add_work_hours(now, remaining / SPEED_PER_PRINTER).isoformat(timespec="minutes")
    elif machine.status == "대기중" and machine.label_code and remaining > 0:
        estimated_completion_at = add_work_hours(now, remaining / SPEED_PER_PRINTER).isoformat(timespec="minutes")
    elif machine.status == "완료":
        estimated_completion_at = machine.finished_at.isoformat(timespec="minutes") if machine.finished_at else None

    return {
        "id": machine.id,
        "name": machine.name,
        "status": machine.status,
        "release_id": machine.release_id,
        "label_code": machine.label_code,
        "total_qty": total,
        "produced_qty": produced,
        "remaining_qty": round(remaining, 2),
        "started_at": machine.started_at.isoformat(timespec="minutes") if machine.started_at else None,
        "running_started_at": machine.running_started_at.isoformat(timespec="minutes") if machine.running_started_at else None,
        "finished_at": machine.finished_at.isoformat(timespec="minutes") if machine.finished_at else None,
        "estimated_completion_at": estimated_completion_at,
        "queue_count": len(queue_items),
        "queue_items": queue_items,
    }


def get_machine_snapshots(db: Session, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    machines = sync_machine_progress(db, now)
    queue_map = _build_queue_item_map(db)
    return [
        build_machine_snapshot(machine, now, queue_map.get(machine.id, []))
        for machine in machines
    ]
