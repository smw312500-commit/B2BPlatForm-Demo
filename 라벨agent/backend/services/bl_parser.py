from __future__ import annotations

import io
import re
from datetime import date
from datetime import datetime

import pdfplumber

LABEL_MATERIAL_CODES = {
    "LABEL_FABRIC": "라벨 원단",
    "PRINT_INK": "잉크",
}

CODE_NAMES = {
    "C-BK": "면(Cotton) / 블랙(BK)",
    "C-WH": "면(Cotton) / 화이트(WH)",
    "C-NV": "면(Cotton) / 네이비(NV)",
    "C-GY": "면(Cotton) / 그레이(GY)",
    "C-BE": "면(Cotton) / 베이지(BE)",
    "C-RD": "면(Cotton) / 레드(RD)",
    "P-BK": "폴리에스터 / 블랙(BK)",
    "P-WH": "폴리에스터 / 화이트(WH)",
    "P-NV": "폴리에스터 / 네이비(NV)",
    "P-GY": "폴리에스터 / 그레이(GY)",
    "P-BE": "폴리에스터 / 베이지(BE)",
    "P-RD": "폴리에스터 / 레드(RD)",
    "L-BK": "린넨 / 블랙(BK)",
    "L-WH": "린넨 / 화이트(WH)",
    "L-NV": "린넨 / 네이비(NV)",
    "L-GY": "린넨 / 그레이(GY)",
    "L-BE": "린넨 / 베이지(BE)",
    "L-RD": "린넨 / 레드(RD)",
    "W-BK": "울(Wool) / 블랙(BK)",
    "W-WH": "울(Wool) / 화이트(WH)",
    "W-NV": "울(Wool) / 네이비(NV)",
    "W-GY": "울(Wool) / 그레이(GY)",
    "W-BE": "울(Wool) / 베이지(BE)",
    "W-RD": "울(Wool) / 레드(RD)",
    "M-BK": "혼방(Mixed) / 블랙(BK)",
    "M-WH": "혼방(Mixed) / 화이트(WH)",
    "M-NV": "혼방(Mixed) / 네이비(NV)",
    "M-GY": "혼방(Mixed) / 그레이(GY)",
    "M-BE": "혼방(Mixed) / 베이지(BE)",
    "M-RD": "혼방(Mixed) / 레드(RD)",
    "LABEL_FABRIC": "라벨 원단",
    "PRINT_INK": "잉크",
    "RAW_WOOD": "원목",
    "RAW_PLASTIC": "플라스틱원료",
    "RAW_METAL": "금속원료",
    "ZIPPER_TAPE": "지퍼테이프",
    "COTTON_YARN": "면사",
    "POLY_YARN": "폴리에스터사",
    "LINEN_YARN": "린넨사",
    "WOOL_YARN": "울사",
    "MIXED_YARN": "혼방사",
}


def _normalize_unit(unit: str) -> str:
    normalized = unit.lower()
    if normalized in ("yards", "yard"):
        return "yards"
    if normalized in ("m", "meter", "meters"):
        return "m"
    if normalized in ("cans", "can"):
        return "cans"
    if normalized in ("kg",):
        return "kg"
    if normalized in ("ea", "pcs", "pc"):
        return "EA"
    return unit


def _to_iso_date(value: str | None) -> str | None:
    if not value:
        return None

    raw = value.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def _extract_text_from_pdf(content: bytes) -> str:
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)


def _group_words_by_line(words: list[dict], tolerance: float = 2.0) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not lines or abs(word["top"] - lines[-1][0]["top"]) > tolerance:
            lines.append([word])
            continue
        lines[-1].append(word)
    return lines


def _join_words(words: list[dict]) -> str:
    return " ".join(word["text"] for word in sorted(words, key=lambda item: item["x0"])).strip()


def _find_phrase_start(words: list[dict], phrase_tokens: list[str]) -> float | None:
    tokens = [str(word["text"]).strip().lower() for word in words]
    phrase = [token.lower() for token in phrase_tokens]
    width = len(phrase)
    for index in range(len(tokens) - width + 1):
        if tokens[index : index + width] == phrase:
            return float(words[index]["x0"])
    return None


def _extract_port_columns_from_pdf(content: bytes) -> dict[str, str | None]:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue

            lines = _group_words_by_line(words)
            for index, header_words in enumerate(lines[:-1]):
                header_text = _join_words(header_words).lower()
                if (
                    "port of loading" not in header_text
                    or "port of discharge" not in header_text
                    or "final place of delivery" not in header_text
                ):
                    continue

                values_words = lines[index + 1]
                loading_start = _find_phrase_start(header_words, ["Port", "of", "Loading"])
                discharge_start = _find_phrase_start(header_words, ["Port", "of", "Discharge"])
                delivery_start = _find_phrase_start(header_words, ["Final", "Place", "of", "Delivery"])
                if loading_start is None or discharge_start is None or delivery_start is None:
                    continue

                loading_words = [word for word in values_words if float(word["x0"]) < discharge_start]
                discharge_words = [
                    word
                    for word in values_words
                    if discharge_start <= float(word["x0"]) < delivery_start
                ]
                delivery_words = [word for word in values_words if float(word["x0"]) >= delivery_start]

                return {
                    "port_of_loading": _join_words(loading_words) or None,
                    "port_of_discharge": _join_words(discharge_words) or None,
                    "final_place_of_delivery": _join_words(delivery_words) or None,
                }

    return {
        "port_of_loading": None,
        "port_of_discharge": None,
        "final_place_of_delivery": None,
    }


def _parse_bl_text(text: str) -> dict:
    result = {
        "bl_number": None,
        "bl_date": None,
        "shipper": None,
        "port_of_loading": None,
        "port_of_discharge": None,
        "final_place_of_delivery": None,
        "vessel": None,
        "eta": None,
        "items": [],
    }

    patterns = {
        "bl_number": [
            r"BL\s*No\.?\s*:?\s*(BL-[\w-]+)",
            r"\b(MOCK-BL-[A-Z0-9-]+)\b",
        ],
        "bl_date": [
            r"DATE\s*:?\s*(\d{4}[-/]\d{2}[-/]\d{2})",
            r"Place and Date of Issue.+?-\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
            r"Shipped On Board.+?-\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        ],
        "shipper": [
            r"SHIPPER\s*:?\s*([^\n]+)",
            r"SHIPPER\s+([^\n]+)",
        ],
        "port_of_loading": [
            r"PORT OF LOADING\s*:?\s*(.+)",
            r"Port of Loading.+?\n([^\n]+?)\s+Busan",
        ],
        "port_of_discharge": [
            r"PORT OF DISCHARGE\s*:?\s*(.+)",
            r"Port of Loading.+?\n[^\n]+?\s+(Busan,\s+Republic of Korea|Busan)",
        ],
        "eta": [
            r"ETA\s*:?\s*(\d{4}[-/]\d{2}[-/]\d{2})",
            r"Expected Arrival.+?-\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
            r"Estimated Date of Arrival\s*\n([0-9]{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        ],
        "vessel": [
            r"VESSEL\s*:?\s*(.+)",
            r"Pre-Carriage By Place of Receipt Vessel\s*\n.+?\s+(.+)",
        ],
    }

    for key, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if not match:
                continue
            value = " ".join(match.group(1).strip().split())
            result[key] = _to_iso_date(value) if key in ("bl_date", "eta") else value
            break

    item_pattern = re.compile(
        r"\[([A-Z][A-Z0-9_\-]*)\].*?([\d,]+(?:\.\d+)?)\s+(Yards|yards|m|EA|ea|KG|kg|cans?|pcs?)\b",
        re.IGNORECASE,
    )

    for match in item_pattern.finditer(text):
        code = match.group(1).upper()
        qty = float(match.group(2).replace(",", ""))
        unit = _normalize_unit(match.group(3))
        result["items"].append(
            {
                "code": code,
                "name": CODE_NAMES.get(code, code),
                "qty": qty,
                "unit": unit,
            }
        )

    if not result["items"]:
        total_quantity = re.search(
            r"TOTAL QUANTITY\s+LABEL FABRIC:\s*([\d,]+(?:\.\d+)?)\s*M\s*/\s*PRINTING INK:\s*([\d,]+(?:\.\d+)?)\s*CANS",
            text,
            re.IGNORECASE,
        )
        if total_quantity:
            result["items"].extend(
                [
                    {
                        "code": "LABEL_FABRIC",
                        "name": CODE_NAMES["LABEL_FABRIC"],
                        "qty": float(total_quantity.group(1).replace(",", "")),
                        "unit": "m",
                    },
                    {
                        "code": "PRINT_INK",
                        "name": CODE_NAMES["PRINT_INK"],
                        "qty": float(total_quantity.group(2).replace(",", "")),
                        "unit": "cans",
                    },
                ]
            )

    if not result["items"]:
        label_fabric_match = re.search(
            r"LABEL FABRIC\s+.*?=\s*([\d,]+(?:\.\d+)?)\s*M",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        printing_ink_match = re.search(
            r"PRINTING INK\s+([\d,]+(?:\.\d+)?)\s*CANS",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if label_fabric_match:
            result["items"].append(
                {
                    "code": "LABEL_FABRIC",
                    "name": CODE_NAMES["LABEL_FABRIC"],
                    "qty": float(label_fabric_match.group(1).replace(",", "")),
                    "unit": "m",
                }
            )
        if printing_ink_match:
            result["items"].append(
                {
                    "code": "PRINT_INK",
                    "name": CODE_NAMES["PRINT_INK"],
                    "qty": float(printing_ink_match.group(1).replace(",", "")),
                    "unit": "cans",
                }
            )

    return result


def _convert_to_order_item(item: dict) -> dict | None:
    material_name = LABEL_MATERIAL_CODES.get(item["code"])
    if not material_name:
        return None

    qty = float(item["qty"])
    original_unit = item["unit"]

    if material_name == "라벨 원단":
        if original_unit == "yards":
            qty = round(qty * 0.9144, 1)
        elif original_unit != "m":
            return None
        unit = "m"
    elif material_name == "잉크":
        if original_unit != "cans":
            return None
        qty = round(qty, 1)
        unit = "통"
    else:
        return None

    return {
        "material_name": material_name,
        "order_qty": qty,
        "unit": unit,
        "source_code": item["code"],
        "original_qty": item["qty"],
        "original_unit": original_unit,
    }


def parse_bl_document(filename: str, content: bytes) -> dict:
    if not filename.lower().endswith(".pdf"):
        raise ValueError("PDF 파일만 업로드할 수 있습니다.")

    try:
        full_text = _extract_text_from_pdf(content)
    except Exception as exc:
        raise ValueError(f"PDF 텍스트 추출 실패: {exc}") from exc

    if not full_text.strip():
        raise ValueError("PDF에서 텍스트를 추출할 수 없습니다.")

    parsed = _parse_bl_text(full_text)
    parsed.update(_extract_port_columns_from_pdf(content))
    if not parsed["items"]:
        raise ValueError("BL에서 품목을 찾을 수 없습니다. 지정 형식의 PDF인지 확인하세요.")

    order_items = [item for item in (_convert_to_order_item(raw) for raw in parsed["items"]) if item]
    if not order_items:
        raise ValueError("라벨agent에서 처리할 수 있는 원자재 품목이 BL에 없습니다.")

    primary_order = order_items[0]
    extra_orders = order_items[1:]
    note_parts = []

    if parsed["bl_number"]:
        note_parts.append(f"BL {parsed['bl_number']}")
    if extra_orders:
        extra_summary = ", ".join(
            f"{item['material_name']} {item['order_qty']}{item['unit']}" for item in extra_orders
        )
        note_parts.append(f"추가 품목: {extra_summary}")

    return {
        **parsed,
        "orders": order_items,
        "material_name": primary_order["material_name"],
        "order_qty": primary_order["order_qty"],
        "supplier": parsed["shipper"] or "",
        "order_date": parsed["bl_date"] or date.today().isoformat(),
        "due_date": parsed["eta"] or "",
        "note": " / ".join(note_parts),
    }
