from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from models import LabelOrder, LabelRelease, LabelStock
from services.material_names import display_material_name, material_unit, normalize_material_name
from services.packing_list import build_packing_list_package

BOX_MAX_WEIGHT_KG = 10.0
TRACKED_MATERIALS = ("라벨원단", "잉크")
SAFE_STOCK_QTY = {
    "라벨원단": 500.0,
    "잉크": 5.0,
}
PENDING_ORDER_STATUS = "대기중"


def calculate_box_count(product_weight_kg: float) -> int:
    weight = float(product_weight_kg or 0)
    if weight <= 0:
        return 0
    return math.ceil(weight / BOX_MAX_WEIGHT_KG)


def box_count_rule_text() -> str:
    return f"1 box per {BOX_MAX_WEIGHT_KG:.0f}kg, rounded up"


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.3f}".rstrip("0").rstrip(".")


def _format_weight(value: Any) -> str:
    return f"{_format_number(value)}kg"


def extract_bl_number(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"\b(BL-[A-Z0-9-]+|MOCK-BL-[A-Z0-9-]+)\b", text, re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(r"\bBL\s+([A-Z0-9-]+)\b", text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _extract_note_token(text: str | None, token: str) -> str | None:
    if not text:
        return None

    pattern = rf"(?:^|/)\s*{re.escape(token)}\s+([^/]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def extract_port_of_loading(text: str | None) -> str | None:
    return _extract_note_token(text, "POL")


def extract_port_of_discharge(text: str | None) -> str | None:
    return _extract_note_token(text, "POD")


def _build_order_snapshot(order: LabelOrder) -> dict[str, Any] | None:
    normalized_name = normalize_material_name(order.material_name)
    if normalized_name not in TRACKED_MATERIALS:
        return None

    bl_number = extract_bl_number(order.note)
    return {
        "id": order.id,
        "material_name": normalized_name,
        "material_display_name": display_material_name(normalized_name),
        "order_qty": float(order.order_qty or 0),
        "unit": material_unit(normalized_name),
        "weight_kg": order.weight_kg,
        "supplier": order.supplier,
        "order_date": order.order_date.isoformat() if order.order_date else None,
        "due_date": order.due_date.isoformat() if order.due_date else None,
        "status": order.status,
        "bl_number": bl_number,
        "note": order.note,
        "source": "bl_upload" if bl_number else "manual_order",
    }


def build_material_order_snapshot(db, limit: int = 10) -> list[dict]:
    rows = db.query(LabelOrder).order_by(LabelOrder.id.desc()).all()

    normalized_rows = []
    for order in rows:
        snapshot = _build_order_snapshot(order)
        if snapshot:
            normalized_rows.append(snapshot)

    bl_rows = [row for row in normalized_rows if row["bl_number"]]
    snapshot_rows = bl_rows or normalized_rows
    return snapshot_rows[:limit]


def build_pending_material_order_snapshot(db, limit: int = 10) -> list[dict]:
    rows = (
        db.query(LabelOrder)
        .filter(LabelOrder.status == PENDING_ORDER_STATUS)
        .order_by(LabelOrder.due_date, LabelOrder.id)
        .all()
    )

    snapshots = []
    for order in rows:
        snapshot = _build_order_snapshot(order)
        if snapshot:
            snapshots.append(snapshot)
    return snapshots[:limit]


def build_current_stock_snapshot(db) -> list[dict]:
    rows = db.query(LabelStock).all()
    row_map = {normalize_material_name(row.material_name): row for row in rows}
    snapshots: list[dict] = []

    for material_name in TRACKED_MATERIALS:
        row = row_map.get(material_name)
        qty = float(row.stock_qty or 0) if row else 0.0
        weight_kg = row.weight_kg if row else 0.0
        safe_qty = SAFE_STOCK_QTY.get(material_name, 0.0)

        if qty <= 0:
            status = "부족"
        elif qty <= safe_qty:
            status = "주의"
        else:
            status = "정상"

        display_name = display_material_name(material_name) or material_name
        unit = material_unit(material_name) or ""
        snapshots.append(
            {
                "material_name": material_name,
                "material_display_name": display_name,
                "qty": qty,
                "unit": unit,
                "weight_kg": weight_kg,
                "safe_qty": safe_qty,
                "status": status,
                "summary": f"{display_name} {_format_number(qty)}{unit} ({status})",
            }
        )

    return snapshots


def build_completed_release_snapshot(db, release_date: date) -> list[LabelRelease]:
    return (
        db.query(LabelRelease)
        .filter(LabelRelease.release_date == release_date)
        .order_by(LabelRelease.label_code, LabelRelease.id)
        .all()
    )


def build_completed_release_due_batch_snapshot(db, due_date: date) -> list[LabelRelease]:
    return (
        db.query(LabelRelease)
        .filter(
            LabelRelease.status == "출고완료",
            LabelRelease.due_date == due_date,
        )
        .order_by(LabelRelease.label_code, LabelRelease.id)
        .all()
    )


def build_completed_release_list(releases: list[LabelRelease]) -> list[dict]:
    items = []
    for release in releases:
        items.append(
            {
                "id": release.id,
                "label_code": release.label_code,
                "release_qty": release.release_qty,
                "release_date": release.release_date.isoformat() if release.release_date else None,
                "due_date": release.due_date.isoformat() if release.due_date else None,
                "product_weight_kg": release.product_weight_kg,
                "box_count": calculate_box_count(release.product_weight_kg),
                "box_count_rule": box_count_rule_text(),
            }
        )
    return items


def _build_completed_due_snapshot(release: LabelRelease) -> dict[str, Any]:
    if release.release_date:
        completed_on = release.release_date
    elif release.finished_at:
        completed_on = release.finished_at.date()
    else:
        completed_on = date.today()
    delay_days = (completed_on - release.due_date).days
    is_on_time = delay_days <= 0
    return {
        "label_code": release.label_code,
        "release_qty": int(release.release_qty or 0),
        "due_date": release.due_date.isoformat() if release.due_date else None,
        "release_date": completed_on.isoformat(),
        "status": "납기준수" if is_on_time else "납기지연",
        "delay_days": max(delay_days, 0),
        "product_weight_kg": release.product_weight_kg,
    }


def _build_ai_decision(
    delayed_count: int,
    stock_snapshot: list[dict],
    pending_material_orders: list[dict],
) -> tuple[str, str]:
    has_shortage = any(item["status"] == "부족" for item in stock_snapshot)
    has_low_stock = any(item["status"] == "주의" for item in stock_snapshot)

    if delayed_count > 0:
        return (
            "긴급",
            "완료건에 납기 지연이 포함되어 있어 플랫폼은 우선 출고와 긴급 차량 배차 기준으로 처리하면 됩니다.",
        )
    if has_shortage:
        return (
            "주의",
            "현재 수출은 진행할 수 있어도 후속 생산용 자재 재고가 부족합니다. 대기 발주 입고 일정을 함께 확인해야 합니다.",
        )
    if has_low_stock or pending_material_orders:
        return (
            "주의",
            "오늘 수출은 가능하지만 후속 생산을 위해 재고와 대기 발주 일정을 같이 보면서 운영하는 편이 안전합니다.",
        )
    return (
        "정상",
        "완료된 수출건과 후속 생산용 재고 흐름이 모두 안정 범위입니다.",
    )


def build_export_ai_report(
    release: LabelRelease,
    completed_releases: list[LabelRelease],
    stock_snapshot: list[dict],
    pending_material_orders: list[dict],
    packing_list: dict,
) -> dict[str, Any]:
    batch_due_date = release.due_date.isoformat() if release.due_date else None
    batch_label = f"납기 {batch_due_date} 묶음" if batch_due_date else "납기 미정 묶음"
    completed_snapshot = [_build_completed_due_snapshot(item) for item in completed_releases]
    completed_release_count = len(completed_snapshot)
    completed_release_qty_total = sum(item["release_qty"] for item in completed_snapshot)
    shipment_box_count_total = sum(calculate_box_count(item.product_weight_kg) for item in completed_releases)
    shipment_total_weight_kg = float(packing_list.get("total_weight_kg") or 0)
    on_time_count = sum(1 for item in completed_snapshot if item["status"] == "납기준수")
    delayed_items = [item for item in completed_snapshot if item["status"] == "납기지연"]
    delayed_count = len(delayed_items)
    decision_level, decision = _build_ai_decision(delayed_count, stock_snapshot, pending_material_orders)

    stock_summary_text = ", ".join(item["summary"] for item in stock_snapshot) or "재고 정보 없음"
    if pending_material_orders:
        pending_order_summary_text = ", ".join(
            (
                f"{order['material_display_name']} {_format_number(order['order_qty'])}{order['unit']}"
                f" / 입고예정 {order['due_date'] or '-'}"
            )
            for order in pending_material_orders[:3]
        )
        if len(pending_material_orders) > 3:
            pending_order_summary_text += f" 외 {len(pending_material_orders) - 3}건"
    else:
        pending_order_summary_text = "대기 발주 없음"

    summary = ". ".join(
        [
            (
                f"라벨회사 DB 판단: {batch_label} 완료 {completed_release_count}건 "
                f"{_format_number(completed_release_qty_total)}장"
            ),
            f"납기준수 {on_time_count}건 / 지연 {delayed_count}건",
            f"현재 재고 {stock_summary_text}",
            f"대기 발주 {len(pending_material_orders)}건" if pending_material_orders else "대기 발주 없음",
            (
                f"수출 묶음 {_format_weight(shipment_total_weight_kg)} / "
                f"{_format_number(shipment_box_count_total)}박스"
            ),
            f"판정 {decision_level}: {decision}",
        ]
    )

    return {
        "analysis_type": "db_rule_based",
        "uses_openai": False,
        "report_batch_type": "due_date",
        "report_batch_due_date": batch_due_date,
        "report_batch_label": batch_label,
        "decision_level": decision_level,
        "decision": decision,
        "summary": summary,
        "completed_release_count": completed_release_count,
        "completed_release_qty_total": completed_release_qty_total,
        "completed_release_due_snapshot": completed_snapshot,
        "on_time_count": on_time_count,
        "delayed_count": delayed_count,
        "delayed_label_codes": [item["label_code"] for item in delayed_items],
        "stock_snapshot": stock_snapshot,
        "stock_summary_text": stock_summary_text,
        "pending_material_order_count": len(pending_material_orders),
        "pending_material_orders": pending_material_orders,
        "pending_order_summary_text": pending_order_summary_text,
        "shipment_total_weight_kg": shipment_total_weight_kg,
        "shipment_box_count_total": shipment_box_count_total,
        "packing_list_filename": packing_list.get("filename"),
        "release_reference": {
            "label_code": release.label_code,
            "release_qty": release.release_qty,
            "due_date": release.due_date.isoformat() if release.due_date else None,
            "release_date": release.release_date.isoformat() if release.release_date else None,
        },
    }


def build_export_shipment_payload(db, release: LabelRelease) -> dict:
    release_day = release.release_date or date.today()
    batch_due_date = release.due_date or release_day
    completed_releases = build_completed_release_due_batch_snapshot(db, batch_due_date)
    if not completed_releases:
        completed_releases = build_completed_release_snapshot(db, release_day)
    completed_release_list = build_completed_release_list(completed_releases)
    packing_list = build_packing_list_package(completed_releases, batch_due_date, batch_due_date)
    material_orders = build_material_order_snapshot(db, limit=10)
    pending_material_orders = build_pending_material_order_snapshot(db, limit=10)
    stock_snapshot = build_current_stock_snapshot(db)
    shipment_box_count_total = sum(item["box_count"] for item in completed_release_list)
    completed_release_qty_total = sum(int(item["release_qty"] or 0) for item in completed_release_list)
    ai_report = build_export_ai_report(
        release=release,
        completed_releases=completed_releases,
        stock_snapshot=stock_snapshot,
        pending_material_orders=pending_material_orders,
        packing_list=packing_list,
    )

    return {
        "box_count": calculate_box_count(release.product_weight_kg),
        "box_count_rule": box_count_rule_text(),
        "shipment_box_count_total": shipment_box_count_total,
        "shipment_total_weight_kg": packing_list["total_weight_kg"],
        "completed_release_list": completed_release_list,
        "completed_release_count": len(completed_release_list),
        "completed_release_qty_total": completed_release_qty_total,
        "completed_release_total_weight_kg": packing_list["total_weight_kg"],
        "packing_list": packing_list,
        "material_order_snapshot": material_orders,
        "pending_material_order_snapshot": pending_material_orders,
        "pending_material_order_count": len(pending_material_orders),
        "bl_material_orders": material_orders,
        "bl_material_order_count": len(material_orders),
        "stock_snapshot": stock_snapshot,
        "report_batch_due_date": batch_due_date.isoformat() if hasattr(batch_due_date, "isoformat") else str(batch_due_date),
        "ai_report": ai_report,
    }
