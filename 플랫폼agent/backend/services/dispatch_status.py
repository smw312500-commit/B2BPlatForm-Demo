from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from models import Dispatch

COMPLETED_DISPATCH_STATUSES = {"배송완료", "완료"}


def sync_elapsed_dispatch_statuses(db: Session, today: date | None = None) -> int:
    """Mark dispatches whose due date has passed as delivered."""
    reference_date = today or date.today()
    records = (
        db.query(Dispatch)
        .filter(
            Dispatch.due_date < reference_date,
            ~Dispatch.status.in_(COMPLETED_DISPATCH_STATUSES),
        )
        .all()
    )
    for record in records:
        record.status = "배송완료"
    if records:
        db.commit()
    return len(records)
