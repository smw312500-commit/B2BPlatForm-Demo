from __future__ import annotations

from datetime import date, datetime
from math import floor

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import LabelRelease, LabelStock
from services.shipment_logic import build_export_shipment_payload
from services.weight_logic import calculate_fabric_m_for_release, calculate_ink_units_for_release


def _normalize_completed_qty(release: LabelRelease, completed_qty: int | float | None) -> int:
    total_qty = int(release.release_qty or 0)
    if total_qty <= 0:
        raise HTTPException(status_code=400, detail="완료 처리할 생산 수량이 없습니다")

    if completed_qty is None:
        return total_qty

    qty = int(floor(float(completed_qty)))
    if qty <= 0:
        raise HTTPException(status_code=400, detail="완료 처리할 생산 수량이 0장입니다")
    return min(qty, total_qty)


def finalize_release_record(
    db: Session,
    release: LabelRelease,
    *,
    completed_qty: int | float | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    release_date: date | None = None,
) -> tuple[LabelRelease, dict]:
    if release.status == "출고완료":
        raise HTTPException(status_code=400, detail="이미 출고완료된 항목입니다")

    final_qty = _normalize_completed_qty(release, completed_qty)
    used_fabric = calculate_fabric_m_for_release(final_qty)
    used_ink = calculate_ink_units_for_release(final_qty)

    fabric = db.query(LabelStock).filter(LabelStock.material_name == "라벨원단").first()
    ink = db.query(LabelStock).filter(LabelStock.material_name == "잉크").first()

    if fabric and float(fabric.stock_qty) < used_fabric:
        raise HTTPException(
            status_code=400,
            detail=f"라벨원단 재고 부족 (필요 {used_fabric}m, 현재 {fabric.stock_qty}m)",
        )
    if ink and float(ink.stock_qty) < used_ink:
        raise HTTPException(
            status_code=400,
            detail=f"잉크 재고 부족 (필요 {used_ink}통, 현재 {ink.stock_qty}통)",
        )

    if fabric:
        fabric.stock_qty = float(fabric.stock_qty) - used_fabric
    if ink:
        ink.stock_qty = float(ink.stock_qty) - used_ink

    release.release_qty = final_qty
    release.status = "출고완료"
    release.release_date = release_date or date.today()
    release.started_at = started_at or release.started_at
    release.finished_at = finished_at or release.finished_at or datetime.now()

    db.commit()
    db.refresh(release)

    export_payload = build_export_shipment_payload(db, release)
    return release, export_payload


def build_release_platform_send_kwargs(release: LabelRelease, export_payload: dict) -> dict:
    return {
        "label_code": release.label_code,
        "release_qty": release.release_qty,
        "due_date": release.due_date,
        "release_date": release.release_date,
        "product_weight_kg": release.product_weight_kg,
        "fabric_weight_kg": release.fabric_weight_kg,
        "ink_weight_kg": release.ink_weight_kg,
        "material_weight_kg": release.material_weight_kg,
        "box_count": export_payload["box_count"],
        "box_count_rule": export_payload["box_count_rule"],
        "shipment_box_count_total": export_payload["shipment_box_count_total"],
        "shipment_total_weight_kg": export_payload["shipment_total_weight_kg"],
        "completed_release_list": export_payload["completed_release_list"],
        "completed_release_count": export_payload["completed_release_count"],
        "completed_release_qty_total": export_payload["completed_release_qty_total"],
        "completed_release_total_weight_kg": export_payload["completed_release_total_weight_kg"],
        "material_order_snapshot": export_payload["material_order_snapshot"],
        "pending_material_order_snapshot": export_payload["pending_material_order_snapshot"],
        "pending_material_order_count": export_payload["pending_material_order_count"],
        "bl_material_orders": export_payload["bl_material_orders"],
        "bl_material_order_count": export_payload["bl_material_order_count"],
        "stock_snapshot": export_payload["stock_snapshot"],
        "report_batch_due_date": export_payload["report_batch_due_date"],
        "ai_report": export_payload["ai_report"],
        "packing_list": export_payload["packing_list"],
    }
