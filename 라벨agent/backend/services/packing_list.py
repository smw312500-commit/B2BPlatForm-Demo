from __future__ import annotations

import base64
import csv
from collections import defaultdict
from datetime import date
from io import BytesIO, StringIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from services.weight_logic import calculate_label_weight_kg

_SEASON_EN = {"1": "SS", "2": "FW", "3": "SP", "4": "SU"}
_GENDER_EN = {"W": "Women", "M": "Men"}
_ITEM_EN = {"T": "T-Shirt", "P": "Pants", "J": "Jacket", "D": "Dress"}
_FABRIC_EN = {"C": "Cotton", "P": "Polyester", "L": "Linen", "W": "Wool", "M": "Mixed"}
_COLOR_EN = {"WH": "White", "BK": "Black", "NV": "Navy", "GY": "Gray", "BE": "Beige", "RD": "Red"}


def _label_en(code: str) -> tuple[str, str]:
    if len(code) != 9:
        return code, ""
    desc = f"{_ITEM_EN.get(code[3], code[3])} Care Label / {_SEASON_EN.get(code[1], code[1])} {_GENDER_EN.get(code[2], code[2])}"
    sub_desc = (
        f"Fabric: {_FABRIC_EN.get(code[4], code[4])}  |  "
        f"Color: {_COLOR_EN.get(code[7:9], code[7:9])}  |  Style No: {code[5:7]}"
    )
    return desc, sub_desc


def build_packing_list_items(releases: list) -> dict:
    aggregated: dict[str, int] = defaultdict(int)
    for release in releases:
        aggregated[release.label_code] += int(release.release_qty)

    items = []
    total_qty = 0
    total_weight_kg = 0.0

    for index, (code, qty) in enumerate(sorted(aggregated.items()), 1):
        desc, sub_desc = _label_en(code)
        weight_kg = calculate_label_weight_kg(qty)
        items.append(
            {
                "no": index,
                "label_code": code,
                "description": desc,
                "detail": sub_desc,
                "qty": qty,
                "weight_kg": weight_kg,
            }
        )
        total_qty += qty
        total_weight_kg += weight_kg

    return {
        "items": items,
        "total_qty": total_qty,
        "total_weight_kg": round(total_weight_kg, 3),
        "label_code_count": len(items),
    }


def build_packing_list_rows(
    releases: list,
    from_date: date,
    to_date: date,
    issue_date: date | None = None,
) -> tuple[dict, list[list[str | int]]]:
    summary = build_packing_list_items(releases)
    issue_date = issue_date or date.today()

    rows: list[list[str | int]] = [
        ["Shipper", "CARE LABEL CO., LTD."],
        ["Issue Date", issue_date.isoformat()],
        ["Period", f"{from_date} ~ {to_date}"],
        ["Items", f"{summary['label_code_count']} label code(s)"],
        [],
        ["No.", "Label Code", "Description", "Fabric/Color/Style", "Qty(pcs)", "Weight(kg)"],
    ]
    for item in summary["items"]:
        rows.append(
            [
                item["no"],
                item["label_code"],
                item["description"],
                item["detail"],
                item["qty"],
                f"{item['weight_kg']:.3f}",
            ]
        )
    rows.append(["", "", "", "TOTAL", summary["total_qty"], f"{summary['total_weight_kg']:.3f}"])
    return summary, rows


def build_packing_list_csv_bytes(releases: list, from_date: date, to_date: date, issue_date: date | None = None) -> bytes:
    _summary, rows = build_packing_list_rows(releases, from_date, to_date, issue_date)

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerows(rows)

    return buffer.getvalue().encode("utf-8")


def _column_letter(index: int) -> str:
    value = index + 1
    letters = []
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def _xlsx_inline_string_cell(cell_ref: str, value: str) -> str:
    return (
        f'<c r="{cell_ref}" t="inlineStr">'
        f"<is><t xml:space=\"preserve\">{escape(value)}</t></is>"
        "</c>"
    )


def _build_xlsx_sheet_xml(rows: list[list[str | int]]) -> str:
    row_xml_parts: list[str] = []
    max_column_index = 0

    for row_index, row in enumerate(rows, start=1):
        cells: list[str] = []
        for column_index, value in enumerate(row, start=1):
            if value in (None, ""):
                continue
            max_column_index = max(max_column_index, column_index)
            cell_ref = f"{_column_letter(column_index - 1)}{row_index}"
            cells.append(_xlsx_inline_string_cell(cell_ref, str(value)))

        if cells:
            row_xml_parts.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        else:
            row_xml_parts.append(f'<row r="{row_index}"/>')

    dimension_end = f"{_column_letter(max(max_column_index, 1) - 1)}{max(len(rows), 1)}"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{dimension_end}"/>'
        "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
        "<sheetFormatPr defaultRowHeight=\"15\"/>"
        "<sheetData>"
        f'{"".join(row_xml_parts)}'
        "</sheetData>"
        "</worksheet>"
    )


def build_packing_list_xlsx_bytes(
    releases: list,
    from_date: date,
    to_date: date,
    issue_date: date | None = None,
) -> bytes:
    _summary, rows = build_packing_list_rows(releases, from_date, to_date, issue_date)
    sheet_xml = _build_xlsx_sheet_xml(rows)
    buffer = BytesIO()

    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '<Override PartName="/xl/styles.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                "</Types>"
            ),
        )
        archive.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="xl/workbook.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                "<sheets>"
                '<sheet name="Packing List" sheetId="1" r:id="rId1"/>'
                "</sheets>"
                "</workbook>"
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/>'
                '<Relationship Id="rId2" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                'Target="styles.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/styles.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<fonts count="1"><font><sz val="11"/><name val="Calibri"/><family val="2"/></font></fonts>'
                '<fills count="2"><fill><patternFill patternType="none"/></fill>'
                '<fill><patternFill patternType="gray125"/></fill></fills>'
                '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
                '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
                "</styleSheet>"
            ),
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    return buffer.getvalue()


def build_packing_list_package(releases: list, from_date: date, to_date: date, issue_date: date | None = None) -> dict:
    summary = build_packing_list_items(releases)
    csv_bytes = build_packing_list_csv_bytes(releases, from_date, to_date, issue_date)
    filename = f"packing_list_{from_date}_{to_date}.csv"

    return {
        "filename": filename,
        "period_from": from_date.isoformat(),
        "period_to": to_date.isoformat(),
        "items": summary["items"],
        "total_qty": summary["total_qty"],
        "total_weight_kg": summary["total_weight_kg"],
        "label_code_count": summary["label_code_count"],
        "content_type": "text/csv",
        "csv_base64": base64.b64encode(csv_bytes).decode("ascii"),
        "csv_size_bytes": len(csv_bytes),
    }
