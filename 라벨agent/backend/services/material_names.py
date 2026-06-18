from __future__ import annotations

CANONICAL_MATERIALS = {
    "라벨원단": "라벨원단",
    "라벨 원단": "라벨원단",
    "label_fabric": "라벨원단",
    "LABEL_FABRIC": "라벨원단",
    "잉크": "잉크",
    "print_ink": "잉크",
    "PRINT_INK": "잉크",
}

DISPLAY_MATERIALS = {
    "라벨원단": "라벨 원단",
    "잉크": "잉크",
}

MATERIAL_UNITS = {
    "라벨원단": "m",
    "잉크": "통",
}


def normalize_material_name(material_name: str | None) -> str | None:
    if material_name is None:
        return None
    raw = str(material_name).strip()
    return CANONICAL_MATERIALS.get(raw, raw)


def display_material_name(material_name: str | None) -> str | None:
    normalized = normalize_material_name(material_name)
    if normalized is None:
        return None
    return DISPLAY_MATERIALS.get(normalized, normalized)


def material_unit(material_name: str | None) -> str | None:
    normalized = normalize_material_name(material_name)
    if normalized is None:
        return None
    return MATERIAL_UNITS.get(normalized)

