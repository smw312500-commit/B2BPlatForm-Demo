from __future__ import annotations

import math

from services.material_names import normalize_material_name

LABEL_PCS_PER_KG = 1_000
FABRIC_PCS_PER_KG = 1_000
INK_UNITS_PER_KG = 10

FABRIC_PCS_PER_METER = 25
INK_PCS_PER_CAN = 10_000


def round_weight_kg(value: float) -> float:
    return round(float(value), 3)


def calculate_label_weight_kg(release_qty: int | float) -> float:
    return round_weight_kg(float(release_qty) / LABEL_PCS_PER_KG)


def calculate_fabric_m_for_release(release_qty: int | float) -> int:
    return math.ceil(float(release_qty) / FABRIC_PCS_PER_METER)


def calculate_ink_units_for_release(release_qty: int | float) -> int:
    return math.ceil(float(release_qty) / INK_PCS_PER_CAN)


def calculate_fabric_weight_kg_for_release(release_qty: int | float) -> float:
    return round_weight_kg(float(release_qty) / FABRIC_PCS_PER_KG)


def calculate_ink_weight_kg_from_units(units: int | float) -> float:
    return round_weight_kg(float(units) / INK_UNITS_PER_KG)


def calculate_ink_weight_kg_for_release(release_qty: int | float) -> float:
    return calculate_ink_weight_kg_from_units(calculate_ink_units_for_release(release_qty))


def calculate_material_weight_kg_for_release(release_qty: int | float) -> float:
    return round_weight_kg(
        calculate_fabric_weight_kg_for_release(release_qty)
        + calculate_ink_weight_kg_for_release(release_qty)
    )


def calculate_stock_weight_kg(material_name: str, stock_qty: int | float) -> float | None:
    qty = float(stock_qty)
    normalized = normalize_material_name(material_name)
    if normalized == "라벨원단":
        return round_weight_kg((qty * FABRIC_PCS_PER_METER) / FABRIC_PCS_PER_KG)
    if normalized == "잉크":
        return calculate_ink_weight_kg_from_units(qty)
    return None


def calculate_order_weight_kg(material_name: str, order_qty: int | float) -> float | None:
    qty = float(order_qty)
    normalized = normalize_material_name(material_name)
    if normalized == "라벨원단":
        return round_weight_kg((qty * FABRIC_PCS_PER_METER) / FABRIC_PCS_PER_KG)
    if normalized == "잉크":
        return calculate_ink_weight_kg_from_units(qty)
    return None
