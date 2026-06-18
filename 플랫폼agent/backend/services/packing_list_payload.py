from __future__ import annotations

import base64
import csv
from io import StringIO
from pathlib import Path
from typing import Any


def _normalize_filename(filename: str | None, extension: str) -> str:
    if filename:
        path = Path(str(filename))
        stem = path.stem or "packing_list"
    else:
        stem = "packing_list"
    return f"{stem}.{extension}"


def build_packing_list_csv_text(packing_list: dict[str, Any]) -> str | None:
    items = packing_list.get("items")
    if not isinstance(items, list) or not items:
        return None

    period_from = packing_list.get("period_from") or "-"
    period_to = packing_list.get("period_to") or "-"
    label_code_count = packing_list.get("label_code_count") or len(items)
    total_qty = packing_list.get("total_qty") or 0
    total_weight_kg = packing_list.get("total_weight_kg") or 0

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Shipper", "CARE LABEL CO., LTD."])
    writer.writerow(["Issue Date", period_to if period_to != "-" else ""])
    writer.writerow(["Period", f"{period_from} ~ {period_to}"])
    writer.writerow(["Items", f"{label_code_count} label code(s)"])
    writer.writerow([])
    writer.writerow(["No.", "Label Code", "Description", "Fabric/Color/Style", "Qty(pcs)", "Weight(kg)"])

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        writer.writerow(
            [
                item.get("no") or index,
                item.get("label_code") or "",
                item.get("description") or "",
                item.get("detail") or "",
                item.get("qty") or 0,
                item.get("weight_kg") or 0,
            ]
        )

    writer.writerow(["", "", "", "TOTAL", total_qty, total_weight_kg])
    return buffer.getvalue()


def normalize_packing_list_payload(packing_list: Any) -> dict[str, Any] | None:
    if not isinstance(packing_list, dict):
        return None

    normalized = dict(packing_list)
    filename = str(normalized.get("filename") or "")
    content_type = str(normalized.get("content_type") or "").strip().lower()
    csv_base64 = normalized.get("csv_base64")

    if csv_base64:
        normalized["content_type"] = content_type or "text/csv"
        normalized["filename"] = _normalize_filename(filename, "csv")
        if "csv_size_bytes" not in normalized:
            try:
                normalized["csv_size_bytes"] = len(base64.b64decode(csv_base64))
            except (ValueError, TypeError):
                pass
        normalized.pop("pdf_base64", None)
        normalized.pop("pdf_size_bytes", None)
        return normalized

    looks_like_pdf = (
        content_type == "application/pdf"
        or filename.lower().endswith(".pdf")
        or "pdf_base64" in normalized
        or "pdf_size_bytes" in normalized
    )
    if not looks_like_pdf:
        return normalized

    csv_text = build_packing_list_csv_text(normalized)
    if not csv_text:
        return normalized

    csv_bytes = csv_text.encode("utf-8")
    normalized["filename"] = _normalize_filename(filename, "csv")
    normalized["content_type"] = "text/csv"
    normalized["csv_base64"] = base64.b64encode(csv_bytes).decode("ascii")
    normalized["csv_size_bytes"] = len(csv_bytes)
    normalized.pop("pdf_base64", None)
    normalized.pop("pdf_size_bytes", None)
    return normalized
