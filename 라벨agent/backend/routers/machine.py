from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import LabelMachine, LabelMachineQueue, LabelRelease
from schemas import LabelMachineAction, LabelMachineOut
from services.machine_state import (
    assign_release_to_machine,
    compute_live_produced,
    get_machine_queue_rows,
    get_machine_snapshots,
    normalize_machine_queue,
    pop_next_queue_release,
    promote_next_queue_release,
    sync_machine_progress,
)
from services.platform_sender import send_release_to_platform
from services.release_completion import build_release_platform_send_kwargs, finalize_release_record

router = APIRouter(prefix="/machines", tags=["기계"])


def _get_machine(db: Session, machine_id: int) -> LabelMachine:
    machine = db.query(LabelMachine).filter(LabelMachine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="기계를 찾을 수 없습니다")
    return machine


def _load_release_map(db: Session, release_ids: list[int]) -> dict[int, LabelRelease]:
    rows = db.query(LabelRelease).filter(LabelRelease.id.in_(release_ids)).all()
    return {row.id: row for row in rows}


def _ensure_release_assignable(
    db: Session,
    machine_id: int,
    release_ids: list[int],
    now: datetime,
) -> dict[int, LabelRelease]:
    unique_release_ids = list(dict.fromkeys(release_ids))
    release_map = _load_release_map(db, unique_release_ids)

    for release_id in unique_release_ids:
        release = release_map.get(release_id)
        if not release:
            raise HTTPException(status_code=404, detail="배정할 생산 주문을 찾을 수 없습니다")
        if release.status != "생산중":
            raise HTTPException(status_code=400, detail="생산중 주문만 기계에 배정할 수 있습니다")

    occupied_elsewhere = {
        machine.release_id
        for machine in db.query(LabelMachine).filter(LabelMachine.id != machine_id).all()
        if machine.release_id
    }
    occupied_elsewhere.update(
        row.release_id
        for row in db.query(LabelMachineQueue).filter(LabelMachineQueue.machine_id != machine_id).all()
    )

    for release_id in unique_release_ids:
        if release_id in occupied_elsewhere:
            release = release_map[release_id]
            raise HTTPException(
                status_code=400,
                detail=f"{release.label_code} 작업은 이미 다른 기계에 배정되어 있습니다",
            )

    machine = _get_machine(db, machine_id)
    if machine.status == "점검중":
        raise HTTPException(status_code=400, detail="점검중 기계에는 작업을 배정할 수 없습니다")

    if machine.release_id and machine.release_id in unique_release_ids:
        # 현재 작업은 같은 기계에 유지되는 상태라 허용한다.
        pass

    return release_map


def _set_machine_queue(db: Session, machine: LabelMachine, release_ids: list[int]) -> None:
    existing_rows = get_machine_queue_rows(db, machine.id)
    for row in existing_rows:
        db.delete(row)
    db.flush()

    for sequence, release_id in enumerate(release_ids, start=1):
        db.add(LabelMachineQueue(machine_id=machine.id, release_id=release_id, sequence=sequence))


def _has_unfinished_current_work(machine: LabelMachine, now: datetime) -> bool:
    if not machine.release_id or int(machine.total_qty or 0) <= 0:
        return False
    return compute_live_produced(machine, now) < int(machine.total_qty or 0)


@router.get("/", response_model=list[LabelMachineOut])
def get_machines(db: Session = Depends(get_db)):
    return get_machine_snapshots(db)


@router.post("/{machine_id}/action", response_model=LabelMachineOut)
def apply_machine_action(
    machine_id: int,
    body: LabelMachineAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    now = datetime.now()
    sync_machine_progress(db, now)

    machine = _get_machine(db, machine_id)
    action = body.action

    if action == "assign":
        if body.release_id is None:
            _set_machine_queue(db, machine, [])
            assign_release_to_machine(machine, None)
        else:
            release_map = _ensure_release_assignable(db, machine_id, [body.release_id], now)
            release = release_map[body.release_id]

            if _has_unfinished_current_work(machine, now):
                if machine.release_id == release.id:
                    raise HTTPException(status_code=400, detail="이미 같은 작업이 현재 기계에 배정되어 있습니다")
                existing_queue_ids = [row.release_id for row in get_machine_queue_rows(db, machine.id)]
                if release.id in existing_queue_ids:
                    raise HTTPException(status_code=400, detail="이미 같은 작업이 이 기계 대기열에 있습니다")
                db.add(
                    LabelMachineQueue(
                        machine_id=machine.id,
                        release_id=release.id,
                        sequence=len(existing_queue_ids) + 1,
                    )
                )
            elif machine.status == "완료" and machine.release_id:
                existing_queue_ids = [row.release_id for row in get_machine_queue_rows(db, machine.id)]
                if release.id == machine.release_id or release.id in existing_queue_ids:
                    raise HTTPException(status_code=400, detail="이미 같은 작업이 이 기계에 있습니다")
                db.add(
                    LabelMachineQueue(
                        machine_id=machine.id,
                        release_id=release.id,
                        sequence=len(existing_queue_ids) + 1,
                    )
                )
            else:
                assign_release_to_machine(machine, release)

    elif action == "apply_plan":
        release_ids = list(dict.fromkeys(body.release_ids or []))
        release_map = _ensure_release_assignable(db, machine_id, release_ids, now)

        if _has_unfinished_current_work(machine, now):
            if release_ids and release_ids[0] != machine.release_id:
                raise HTTPException(status_code=400, detail="가동중/대기중 현재 작업은 유지한 채 뒤 작업만 재배정할 수 있습니다")
            queue_release_ids = release_ids[1:]
            _set_machine_queue(db, machine, queue_release_ids)
        elif machine.status == "완료" and machine.release_id:
            _set_machine_queue(db, machine, release_ids)
        else:
            if not release_ids:
                _set_machine_queue(db, machine, [])
                assign_release_to_machine(machine, None)
            else:
                assign_release_to_machine(machine, release_map[release_ids[0]])
                _set_machine_queue(db, machine, release_ids[1:])

    elif action == "start":
        if not machine.release_id or not machine.label_code or int(machine.total_qty or 0) <= 0:
            raise HTTPException(status_code=400, detail="작업이 배정된 기계만 시작할 수 있습니다")
        if machine.status == "점검중":
            raise HTTPException(status_code=400, detail="점검중 기계는 시작할 수 없습니다")
        if machine.status != "가동중":
            machine.status = "가동중"
            if not machine.started_at:
                machine.started_at = now
            machine.running_started_at = now
            machine.finished_at = None
            release = db.query(LabelRelease).filter(LabelRelease.id == machine.release_id).first()
            if release and not release.started_at:
                release.started_at = machine.started_at

    elif action == "stop":
        if machine.status == "가동중":
            machine.produced_qty = compute_live_produced(machine, now)
            machine.running_started_at = None
            if float(machine.produced_qty or 0) >= int(machine.total_qty or 0):
                machine.status = "완료"
                machine.finished_at = now
            else:
                machine.status = "대기중"

    elif action == "complete":
        if not machine.release_id:
            raise HTTPException(status_code=400, detail="완료 처리할 현재 작업이 없습니다")

        if machine.status == "가동중":
            machine.produced_qty = compute_live_produced(machine, now)
            machine.running_started_at = None

        current_release = db.query(LabelRelease).filter(LabelRelease.id == machine.release_id).first()
        if not current_release:
            raise HTTPException(status_code=404, detail="완료 처리할 생산 주문을 찾을 수 없습니다")

        completed_qty = int(machine.total_qty or 0)
        live_produced = compute_live_produced(machine, now)
        if 0 < live_produced < int(machine.total_qty or 0):
            completed_qty = max(1, int(live_produced))

        release_started_at = machine.started_at or now
        release_finished_at = now
        completed_release, export_payload = finalize_release_record(
            db,
            current_release,
            completed_qty=completed_qty,
            started_at=release_started_at,
            finished_at=release_finished_at,
        )

        machine.produced_qty = completed_release.release_qty
        machine.finished_at = release_finished_at
        machine.status = "완료"
        background_tasks.add_task(
            send_release_to_platform,
            **build_release_platform_send_kwargs(completed_release, export_payload),
        )
        promote_next_queue_release(db, machine)

    elif action == "status_change":
        if body.status not in {"대기중", "점검중"}:
            raise HTTPException(status_code=400, detail="변경 가능한 상태는 대기중/점검중입니다")
        if machine.status == "가동중":
            machine.produced_qty = compute_live_produced(machine, now)
            machine.running_started_at = None
        machine.status = body.status

    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 기계 액션입니다")

    if machine.release_id:
        release = db.query(LabelRelease).filter(LabelRelease.id == machine.release_id).first()
        if release:
            if machine.started_at and not release.started_at:
                release.started_at = machine.started_at
            if machine.status == "완료" and machine.finished_at:
                release.finished_at = machine.finished_at

    db.commit()
    normalize_machine_queue(db, machine.id)
    db.commit()

    updated = get_machine_snapshots(db, now)
    snapshot = next((item for item in updated if item["id"] == machine_id), None)
    if not snapshot:
        raise HTTPException(status_code=500, detail="기계 상태를 다시 읽을 수 없습니다")
    return snapshot
