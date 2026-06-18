from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from random import Random


OUT_DIR = Path(__file__).resolve().parent / "four_year_supply_chain"
TOTAL_GARMENTS = 6_000_000
YEARS = [2023, 2024, 2025, 2026]

COMPANIES = [
    {"id": 1, "name": "옷감사", "channel": "fabric"},
    {"id": 2, "name": "케어라벨사", "channel": "label"},
    {"id": 3, "name": "지퍼단추사", "channel": "zipper"},
]

MATERIALS = {
    "케어라벨사": [
        ("라벨원단", "m", "Apex Label Materials", "Stable Label Backup"),
        ("잉크", "통", "Korea Ink Supply", "Busan Ink Backup"),
    ],
    "옷감사": [
        ("면 원사", "kg", "Qingdao Cotton Trading", "Vietnam Yarn Backup"),
        ("폴리에스터 원사", "kg", "Sino Poly Fiber", "Daegu Poly Backup"),
        ("린넨 원사", "kg", "Linen Mill Partners", "Daegu Linen Backup"),
        ("울 원사", "kg", "Ulaan Wool Trading", "Busan Wool Backup"),
        ("혼방 원사", "kg", "Mixed Yarn Korea", "Daegu Mixed Backup"),
        ("염료", "kg", "Korea Dye Works", "Busan Dye Backup"),
    ],
    "지퍼단추사": [
        ("플라스틱원료", "kg", "Ningbo Resin Parts", "Korea Resin Backup"),
        ("금속원료", "kg", "Qingdao Metal Parts", "Incheon Metal Backup"),
        ("지퍼테이프", "m", "Shenzhen Zipper Tape", "Korea Tape Backup"),
    ],
}

# 각 agent 폴더의 실제 로직 기준 환산값.
LABEL_PCS_PER_KG = 1_000
LABEL_FABRIC_PCS_PER_METER = 25
LABEL_INK_PCS_PER_CAN = 10_000
LABEL_INK_CANS_PER_KG = 10

FABRIC_KG_PER_YARD = 0.3  # 옷감agent/backend/routers/release.py, platform_reporter.py 기준
FABRIC_YARDS_PER_GARMENT = {
    "T": 1.2,
    "P": 1.6,
    "J": 2.1,
    "D": 2.4,
}
YARN_YARDS_PER_KG = {
    "C": 3.0,
    "P": 5.0,
    "L": 2.5,
    "W": 2.0,
    "M": 3.5,
}
FABRIC_MATERIAL_BY_CODE = {
    "C": "면 원사",
    "P": "폴리에스터 원사",
    "L": "린넨 원사",
    "W": "울 원사",
    "M": "혼방 원사",
}

ZIPPER_BUTTON_GRAM_PER_PIECE = 5
ZIPPER_BUTTON_PARTS_BY_ITEM_CODE = {
    "T": ["플라스틱단추"],
    "P": ["금속단추"],
    "J": ["지퍼", "금속단추"],
    "D": ["지퍼"],
}
ZIPPER_BUTTON_RAW_BY_PART = {
    "플라스틱단추": ("플라스틱원료", "kg", 200),
    "금속단추": ("금속원료", "kg", 150),
    "지퍼": ("지퍼테이프", "m", 1),
}

PROBLEM_SUPPLIERS = {
    "Apex Label Materials",
    "Qingdao Cotton Trading",
    "Qingdao Metal Parts",
}

PRODUCT_PROFILES = [
    ("W2MTC08RD", "여름", "남성", "면", "티셔츠", "레드"),
    ("W2WPL07BE", "여름", "여성", "린넨", "바지", "베이지"),
    ("W1MTP05BE", "봄", "남성", "폴리에스터", "티셔츠", "베이지"),
    ("W2WTL06WH", "여름", "여성", "린넨", "티셔츠", "화이트"),
    ("W2MPL09NV", "여름", "남성", "린넨", "바지", "네이비"),
    ("W2WPM10GY", "여름", "여성", "혼방", "바지", "그레이"),
    ("W3MJW01NV", "가을", "남성", "울", "재킷", "네이비"),
    ("W4WDP11BK", "겨울", "여성", "폴리에스터", "다운", "블랙"),
]

CUSTOMERS = [
    "North Peak Apparel",
    "Urban Trail Korea",
    "Daily Cotton Studio",
    "River Outdoor Co.",
    "Mode Basic Partners",
]

DESTINATIONS = ["부산항", "인천항"]
ROUND_TRIP_FREE_STORAGE_DAYS = 2
ROUND_TRIP_TARGETS = {
    "SHP-202607-01": ["케어라벨사", "옷감사"],
    "SHP-202607-02": ["케어라벨사", "지퍼단추사"],
    "SHP-202607-03": ["옷감사", "케어라벨사", "지퍼단추사"],
    "SHP-202607-04": ["케어라벨사"],
    "SHP-202607-05": ["옷감사", "지퍼단추사"],
}
ROUND_TRIP_ARRIVAL_OFFSETS = [2, 1, 0, 2, 1, 0, 2, 1, 0, 2]


@dataclass(frozen=True)
class ShipmentPlan:
    shipment_batch_id: str
    shipment_date: date
    shipment_due_date: date
    garments: int
    profile: tuple[str, str, str, str, str, str]
    customer: str
    destination: str
    scenario_tag: str


def month_ship_days(year: int, month: int) -> list[int]:
    if year == 2026 and month == 7:
        return [3, 10, 17, 24, 31]
    return [7, 15, 23, 28] if month in {2, 5, 8, 11} else [8, 18, 27]


def phase_for_year(year: int) -> str:
    if year <= 2024:
        return "smooth"
    if year == 2025:
        return "supply_crack"
    return "supply_and_production_break"


def supplier_delay_days(year: int, quarter: int, supplier: str, rng: Random) -> int:
    if supplier not in PROBLEM_SUPPLIERS:
        return rng.randint(0, 6)
    if year <= 2024:
        return rng.randint(0, 7)
    if year == 2025:
        base = [12, 17, 22, 27][quarter - 1]
        return max(0, base + rng.randint(-3, 4))
    base = [24, 31, 38, 44][quarter - 1]
    return max(0, base + rng.randint(-4, 5))


def risk_stage_from_delay(delay_days: int) -> str:
    if delay_days >= 21:
        return "supplier_problem_candidate"
    if delay_days >= 15:
        return "material_risk"
    if delay_days >= 8:
        return "watch"
    return "normal_variation"


def item_code(label_code: str) -> str:
    return label_code[3].upper()


def fabric_code(label_code: str) -> str:
    return label_code[4].upper()


def quarter_key(day: date) -> tuple[int, int]:
    return day.year, ((day.month - 1) // 3) + 1


def label_fabric_m_for_qty(label_qty: int) -> int:
    return math.ceil(label_qty / LABEL_FABRIC_PCS_PER_METER)


def label_ink_cans_for_qty(label_qty: int) -> int:
    return math.ceil(label_qty / LABEL_INK_PCS_PER_CAN)


def label_finished_weight_kg(label_qty: int) -> float:
    return round(label_qty / LABEL_PCS_PER_KG, 3)


def label_fabric_weight_kg(fabric_m: float) -> float:
    return round((fabric_m * LABEL_FABRIC_PCS_PER_METER) / LABEL_PCS_PER_KG, 3)


def label_ink_weight_kg(ink_cans: float) -> float:
    return round(ink_cans / LABEL_INK_CANS_PER_KG, 3)


def fabric_yards_for_shipment(label_code: str, garments: int) -> float:
    return round(garments * FABRIC_YARDS_PER_GARMENT.get(item_code(label_code), 1.5), 1)


def fabric_finished_weight_kg(fabric_yards: float) -> float:
    return round(fabric_yards * FABRIC_KG_PER_YARD, 1)


def zipper_button_requirements(label_code: str, garments: int) -> dict[str, int]:
    return {
        part: garments
        for part in ZIPPER_BUTTON_PARTS_BY_ITEM_CODE.get(item_code(label_code), [])
    }


def zipper_button_finished_weight_kg(requirements: dict[str, int]) -> float:
    total_qty = sum(requirements.values())
    return round(total_qty * ZIPPER_BUTTON_GRAM_PER_PIECE / 1000, 3)


def raw_material_weight_kg(material_name: str, qty: float) -> float | None:
    if material_name == "라벨원단":
        return label_fabric_weight_kg(qty)
    if material_name == "잉크":
        return label_ink_weight_kg(qty)
    if material_name.endswith("원사") or material_name in {"염료", "플라스틱원료", "금속원료"}:
        return round(float(qty), 3)
    return None


def production_buffer_days(year: int, company: str, rng: Random) -> int:
    if year <= 2024:
        return rng.randint(18, 31)
    if year == 2025:
        return rng.randint(7, 16)
    if company == "옷감사":
        return rng.randint(-2, 5)
    if company == "케어라벨사":
        return rng.randint(0, 7)
    return rng.randint(-1, 6)


def production_duration_days(year: int, company: str, garments: int, rng: Random) -> int:
    base = {
        "옷감사": 12,
        "케어라벨사": 5,
        "지퍼단추사": 7,
    }[company]
    volume_factor = max(0, int((garments - 30_000) / 18_000))
    year_penalty = 0 if year <= 2024 else (2 if year == 2025 else 5)
    return max(2, base + volume_factor + year_penalty + rng.randint(-1, 2))


def build_shipment_plans(rng: Random) -> list[ShipmentPlan]:
    weighted = []
    for year in YEARS:
        for month in range(1, 13):
            for index, day in enumerate(month_ship_days(year, month), start=1):
                season_weight = 1.0
                if month in {5, 6, 7}:
                    season_weight = 1.18
                elif month in {10, 11, 12}:
                    season_weight = 1.12
                elif month in {1, 2}:
                    season_weight = 0.92

                degradation_weight = 1.0
                if year == 2025:
                    degradation_weight = 0.97
                elif year == 2026:
                    degradation_weight = 0.93

                weight = season_weight * degradation_weight * rng.uniform(0.85, 1.15)
                weighted.append((year, month, day, index, weight))

    total_weight = sum(item[4] for item in weighted)
    raw_counts = [max(16_000, int(TOTAL_GARMENTS * item[4] / total_weight)) for item in weighted]
    diff = TOTAL_GARMENTS - sum(raw_counts)
    raw_counts[-1] += diff

    plans = []
    for seq, ((year, month, day, index, _weight), garments) in enumerate(zip(weighted, raw_counts), start=1):
        profile = PRODUCT_PROFILES[(seq + month + year) % len(PRODUCT_PROFILES)]
        shipment_date = date(year, month, day)
        due_date = shipment_date
        phase = phase_for_year(year)
        tag = phase
        if year == 2026 and month == 7:
            tag = {
                1: "july_normal",
                2: "july_due_day_pressure",
                3: "july_round_trip_candidate",
                4: "july_heavy_load",
                5: "july_duplicate_guard",
            }[index]
        plans.append(
            ShipmentPlan(
                shipment_batch_id=f"SHP-{year}{month:02d}-{index:02d}",
                shipment_date=shipment_date,
                shipment_due_date=due_date,
                garments=garments,
                profile=profile,
                customer=CUSTOMERS[(seq + year) % len(CUSTOMERS)],
                destination=DESTINATIONS[(seq + month) % len(DESTINATIONS)],
                scenario_tag=tag,
            )
        )
    return plans


def build_quarterly_material_needs(plans: list[ShipmentPlan]) -> dict[tuple[int, int, str, str], float]:
    needs: dict[tuple[int, int, str, str], float] = {}

    def add(year: int, quarter: int, company_name: str, material_name: str, qty: float) -> None:
        key = (year, quarter, company_name, material_name)
        needs[key] = needs.get(key, 0.0) + float(qty)

    for plan in plans:
        year, quarter = quarter_key(plan.shipment_date)
        code = plan.profile[0]
        garments = int(plan.garments)

        add(year, quarter, "케어라벨사", "라벨원단", label_fabric_m_for_qty(garments))
        add(year, quarter, "케어라벨사", "잉크", label_ink_cans_for_qty(garments))

        yards = fabric_yards_for_shipment(code, garments)
        fc = fabric_code(code)
        yarn_material = FABRIC_MATERIAL_BY_CODE.get(fc, "혼방 원사")
        yards_per_kg = YARN_YARDS_PER_KG.get(fc, 3.5)
        add(year, quarter, "옷감사", yarn_material, math.ceil(yards / yards_per_kg))
        add(year, quarter, "옷감사", "염료", math.ceil(yards * 0.015))

        for part_name, part_qty in zipper_button_requirements(code, garments).items():
            material_name, _unit, rate = ZIPPER_BUTTON_RAW_BY_PART[part_name]
            add(year, quarter, "지퍼단추사", material_name, math.ceil(part_qty / rate * 10) / 10)

    return needs


def normalize_order_qty(material_name: str, unit: str, raw_qty: float) -> float | int:
    if unit in {"m", "통"}:
        return int(math.ceil(raw_qty))
    if material_name == "지퍼테이프":
        return int(math.ceil(raw_qty))
    return round(float(raw_qty), 1)


def port_of_discharge_for_destination(destination: str) -> str:
    if "인천" in destination:
        return "Incheon, Republic of Korea"
    return "Busan, Republic of Korea"


def company_by_name(company_name: str) -> dict:
    for company in COMPANIES:
        if company["name"] == company_name:
            return company
    raise ValueError(f"Unknown company: {company_name}")


def material_catalog(company_name: str, material_name: str) -> tuple[str, str, str, str]:
    for material in MATERIALS[company_name]:
        if material[0] == material_name:
            return material
    raise ValueError(f"Unknown material for {company_name}: {material_name}")


def round_trip_material_for_company(plan: ShipmentPlan, company_name: str) -> tuple[str, str, str, float]:
    code = plan.profile[0]
    garments = int(plan.garments)

    if company_name == "케어라벨사":
        material_name = "라벨원단"
        unit = "m"
        qty = max(300, math.ceil(label_fabric_m_for_qty(garments) * 0.45))
    elif company_name == "옷감사":
        fc = fabric_code(code)
        material_name = FABRIC_MATERIAL_BY_CODE.get(fc, "혼방 원사")
        unit = "kg"
        yards = fabric_yards_for_shipment(code, garments)
        qty = max(500, math.ceil((yards / YARN_YARDS_PER_KG.get(fc, 3.5)) * 0.3))
    else:
        requirements = zipper_button_requirements(code, garments)
        if requirements:
            part_name, part_qty = next(iter(requirements.items()))
            material_name, unit, rate = ZIPPER_BUTTON_RAW_BY_PART[part_name]
            qty = max(120, math.ceil((part_qty / rate) * 0.5))
        else:
            material_name = "플라스틱원료"
            unit = "kg"
            qty = 120

    _name, _unit, primary_supplier, backup_supplier = material_catalog(company_name, material_name)
    supplier = backup_supplier if primary_supplier in PROBLEM_SUPPLIERS else primary_supplier
    return material_name, unit, supplier, normalize_order_qty(material_name, unit, qty)


def build_material_receipts(plans: list[ShipmentPlan], rng: Random) -> list[dict]:
    rows = []
    receipt_id = 1
    material_needs = build_quarterly_material_needs(plans)
    for year in YEARS:
        for quarter in range(1, 5):
            q_start_month = (quarter - 1) * 3 + 1
            promised_date = date(year, q_start_month, 1) - timedelta(days=10)
            order_date = promised_date - timedelta(days=45)
            for company in COMPANIES:
                for material_name, unit, primary_supplier, backup_supplier in MATERIALS[company["name"]]:
                    required_qty = material_needs.get((year, quarter, company["name"], material_name), 0.0)
                    if required_qty <= 0:
                        continue
                    use_backup = year == 2026 and quarter == 4 and primary_supplier in PROBLEM_SUPPLIERS
                    supplier = backup_supplier if use_backup else primary_supplier
                    delay = supplier_delay_days(year, quarter, supplier, rng)
                    actual_date = promised_date + timedelta(days=delay)
                    qty = normalize_order_qty(material_name, unit, required_qty * rng.uniform(1.06, 1.18))
                    weight_kg = raw_material_weight_kg(material_name, qty)
                    rows.append(
                        {
                            "receipt_id": f"MAT-{receipt_id:04d}",
                            "year": year,
                            "quarter": f"Q{quarter}",
                            "company_id": company["id"],
                            "company_name": company["name"],
                            "material_name": material_name,
                            "supplier": supplier,
                            "order_date": order_date.isoformat(),
                            "promised_date": promised_date.isoformat(),
                            "actual_receipt_date": actual_date.isoformat(),
                            "delay_days": delay,
                            "ordered_qty": qty,
                            "unit": unit,
                            "weight_kg": weight_kg if weight_kg is not None else "",
                            "quantity_basis": "agent_logic_required_qty_plus_buffer",
                            "port_of_discharge": "Busan, Republic of Korea",
                            "round_trip_candidate": "N",
                            "round_trip_target_shipment_id": "",
                            "free_storage_until": "",
                            "risk_stage": risk_stage_from_delay(delay),
                            "note": "대체 공급사 테스트" if use_backup else "",
                        }
                    )
                    receipt_id += 1

    target_index = 0
    plans_by_id = {plan.shipment_batch_id: plan for plan in plans}
    for shipment_id, target_companies in ROUND_TRIP_TARGETS.items():
        plan = plans_by_id.get(shipment_id)
        if not plan:
            continue
        for company_name in target_companies:
            company = company_by_name(company_name)
            material_name, unit, supplier, qty = round_trip_material_for_company(plan, company_name)
            arrival_offset = ROUND_TRIP_ARRIVAL_OFFSETS[target_index % len(ROUND_TRIP_ARRIVAL_OFFSETS)]
            actual_date = plan.shipment_due_date - timedelta(days=arrival_offset)
            promised_date = actual_date
            order_date = promised_date - timedelta(days=45)
            weight_kg = raw_material_weight_kg(material_name, qty)
            free_storage_until = actual_date + timedelta(days=ROUND_TRIP_FREE_STORAGE_DAYS)
            rows.append(
                {
                    "receipt_id": f"MAT-{receipt_id:04d}",
                    "year": plan.shipment_due_date.year,
                    "quarter": f"Q{((plan.shipment_due_date.month - 1) // 3) + 1}",
                    "company_id": company["id"],
                    "company_name": company["name"],
                    "material_name": material_name,
                    "supplier": supplier,
                    "order_date": order_date.isoformat(),
                    "promised_date": promised_date.isoformat(),
                    "actual_receipt_date": actual_date.isoformat(),
                    "delay_days": 0,
                    "ordered_qty": qty,
                    "unit": unit,
                    "weight_kg": weight_kg if weight_kg is not None else "",
                    "quantity_basis": "round_trip_demo_partial_bl_under_free_port_storage",
                    "port_of_discharge": port_of_discharge_for_destination(plan.destination),
                    "round_trip_candidate": "Y",
                    "round_trip_target_shipment_id": shipment_id,
                    "free_storage_until": free_storage_until.isoformat(),
                    "risk_stage": "round_trip_candidate",
                    "note": "귀로매칭 시연용: 항구 무료보관 2일 내 수출건과 연결",
                }
            )
            receipt_id += 1
            target_index += 1
    return rows


def build_finished_shipments(plans: list[ShipmentPlan]) -> list[dict]:
    rows = []
    for plan in plans:
        code, season, gender, fabric, garment_type, color = plan.profile
        fabric_yards = fabric_yards_for_shipment(code, plan.garments)
        label_weight_kg = label_finished_weight_kg(plan.garments)
        fabric_weight_kg = fabric_finished_weight_kg(fabric_yards)
        zipper_button_req = zipper_button_requirements(code, plan.garments)
        zipper_button_qty = sum(zipper_button_req.values())
        zipper_button_weight_kg = zipper_button_finished_weight_kg(zipper_button_req)
        rows.append(
            {
                "shipment_batch_id": plan.shipment_batch_id,
                "shipment_date": plan.shipment_date.isoformat(),
                "shipment_due_date": plan.shipment_due_date.isoformat(),
                "production_year": plan.shipment_date.year,
                "target_retail_year": plan.shipment_date.year + 1,
                "customer": plan.customer,
                "destination": plan.destination,
                "label_code": code,
                "season": season,
                "gender": gender,
                "fabric": fabric,
                "garment_type": garment_type,
                "color": color,
                "garment_units": plan.garments,
                "label_qty": plan.garments,
                "fabric_yards": fabric_yards,
                "zipper_button_qty": zipper_button_qty,
                "label_weight_kg": label_weight_kg,
                "fabric_weight_kg": fabric_weight_kg,
                "zipper_button_weight_kg": zipper_button_weight_kg,
                "total_weight_kg": label_weight_kg,
                "box_count": max(1, math.ceil(label_weight_kg / 10)),
                "weight_basis": "label_agent: 1000pcs=1kg; fabric_agent: 0.3kg/yard; zipper_agent: 5g/pcs",
                "scenario_tag": plan.scenario_tag,
            }
        )
    return rows


def build_production_batches(plans: list[ShipmentPlan], rng: Random) -> list[dict]:
    rows = []
    production_id = 1
    for plan in plans:
        code, season, gender, fabric, garment_type, color = plan.profile
        fabric_yards = fabric_yards_for_shipment(code, plan.garments)
        zipper_button_qty = sum(zipper_button_requirements(code, plan.garments).values())
        company_quantity = {
            "옷감사": (fabric_yards, "야드", fabric_finished_weight_kg(fabric_yards)),
            "케어라벨사": (plan.garments, "장", label_finished_weight_kg(plan.garments)),
            "지퍼단추사": (zipper_button_qty, "개", zipper_button_finished_weight_kg(zipper_button_requirements(code, plan.garments))),
        }
        for company in COMPANIES:
            buffer_days = production_buffer_days(plan.shipment_date.year, company["name"], rng)
            complete_date = plan.shipment_due_date - timedelta(days=buffer_days)
            duration = production_duration_days(plan.shipment_date.year, company["name"], plan.garments, rng)
            start_date = complete_date - timedelta(days=duration)
            is_late = complete_date > plan.shipment_due_date
            production_qty, production_unit, shipment_weight_kg = company_quantity[company["name"]]
            rows.append(
                {
                    "production_id": f"PRD-{production_id:05d}",
                    "shipment_batch_id": plan.shipment_batch_id,
                    "company_id": company["id"],
                    "company_name": company["name"],
                    "label_code": code,
                    "season": season,
                    "gender": gender,
                    "fabric": fabric,
                    "garment_type": garment_type,
                    "color": color,
                    "garment_units": plan.garments,
                    "production_qty": production_qty,
                    "production_unit": production_unit,
                    "shipment_weight_kg": shipment_weight_kg,
                    "production_start_date": start_date.isoformat(),
                    "production_complete_date": complete_date.isoformat(),
                    "production_due_date": plan.shipment_due_date.isoformat(),
                    "production_duration_days": duration,
                    "due_buffer_days": buffer_days,
                    "is_late": "Y" if is_late else "N",
                    "line_or_machine": f"{company['channel']}-line-{(production_id % 6) + 1}",
                    "risk_stage": "late" if is_late else ("tight" if buffer_days <= 5 else "normal"),
                    "scenario_tag": plan.scenario_tag,
                }
            )
            production_id += 1
    return rows


def build_logistics_performance(plans: list[ShipmentPlan], rng: Random) -> list[dict]:
    rows = []
    carriers = ["플랫폼연동물류", "기존계약물류A", "기존계약물류B"]
    for index, plan in enumerate(plans, start=1):
        year = plan.shipment_date.year
        carrier = carriers[index % len(carriers)]
        request_at = datetime.combine(plan.shipment_date - timedelta(days=2), datetime.min.time()).replace(hour=10)
        assign_hours = rng.randint(2, 10)
        if carrier != "플랫폼연동물류":
            assign_hours += 8 if year >= 2025 else 3
        if year == 2026:
            assign_hours += rng.randint(4, 18)
        assigned_at = request_at + timedelta(hours=assign_hours)
        pickup_date = plan.shipment_date - timedelta(days=1 if assign_hours < 24 else 0)
        delivery_delay = 0
        if year == 2026 and carrier != "플랫폼연동물류":
            delivery_delay = rng.choice([0, 1, 1, 2])
        rows.append(
            {
                "dispatch_id": f"DSP-{index:05d}",
                "shipment_batch_id": plan.shipment_batch_id,
                "carrier": carrier,
                "destination": plan.destination,
                "request_at": request_at.isoformat(timespec="minutes"),
                "assigned_at": assigned_at.isoformat(timespec="minutes"),
                "assignment_hours": assign_hours,
                "pickup_date": pickup_date.isoformat(),
                "delivery_due_date": plan.shipment_due_date.isoformat(),
                "actual_delivery_date": (plan.shipment_due_date + timedelta(days=delivery_delay)).isoformat(),
                "delivery_delay_days": delivery_delay,
                "status": "지연" if delivery_delay else "정상",
                "scenario_tag": plan.scenario_tag,
            }
        )
    return rows


def build_logistics_snapshots(rng: Random) -> list[dict]:
    drivers = [
        ("김도현", "부산시", "강서구", "5톤 트럭", 5000),
        ("신동엽", "서울시", "구로구", "1톤 트럭", 1000),
        ("이하늘", "인천시", "중구", "3.5톤 트럭", 3500),
        ("박민수", "대구시", "달서구", "5톤 트럭", 5000),
        ("최서윤", "부산시", "해운대구", "11톤 트럭", 11000),
        ("정우진", "광주시", "북구", "2.5톤 트럭", 2500),
        ("한지훈", "인천시", "연수구", "5톤 트럭", 5000),
        ("문소라", "서울시", "성동구", "1톤 트럭", 1000),
    ]
    rows = []
    snapshot_id = 1
    for year in YEARS:
        for month in range(1, 13):
            snapshot_date = date(year, month, 5)
            for driver_index, (name, si, gu, vehicle_type, max_weight) in enumerate(drivers, start=1):
                stale = year == 2026 and month in {6, 7, 8} and driver_index in {2, 8}
                last_synced = datetime.combine(snapshot_date, datetime.min.time()).replace(hour=9)
                if stale:
                    last_synced -= timedelta(days=5)
                status = rng.choice(["가용", "가용", "가용", "운행중", "휴무"])
                rows.append(
                    {
                        "snapshot_id": f"LOG-SNP-{snapshot_id:05d}",
                        "snapshot_date": snapshot_date.isoformat(),
                        "driver_id": driver_index,
                        "vehicle_id": driver_index,
                        "driver_name": name,
                        "location_si": si,
                        "location_gu": gu,
                        "vehicle_type": vehicle_type,
                        "vehicle_plate": f"{10 + driver_index}가 {1000 + driver_index * 137}",
                        "vehicle_max_weight_kg": max_weight,
                        "status": status,
                        "current_destination": rng.choice(["부산항", "인천항", "서울", "대구", ""]),
                        "estimated_arrival": (snapshot_date + timedelta(days=rng.randint(0, 3))).isoformat(),
                        "last_synced_at": last_synced.isoformat(timespec="minutes"),
                        "is_stale": "Y" if stale else "N",
                    }
                )
                snapshot_id += 1
    return rows


def build_platform_report_messages(
    material_rows: list[dict],
    production_rows: list[dict],
    shipment_rows: list[dict],
) -> list[dict]:
    rows: list[dict] = []
    message_id = 1
    channel_by_company = {"옷감사": "fabric", "케어라벨사": "label", "지퍼단추사": "zipper"}

    for row in material_rows:
        channel = channel_by_company[row["company_name"]]
        payload = {
            "company_id": int(row["company_id"]),
            "company_name": row["company_name"],
            "material": row["material_name"],
            "material_display_name": row["material_name"],
            "qty": float(row["ordered_qty"]),
            "unit": row["unit"],
            "weight_kg": float(row["weight_kg"]) if row.get("weight_kg") not in ("", None) else None,
            "quantity_basis": row.get("quantity_basis"),
            "supplier": row["supplier"],
            "supplier_company": row["supplier"],
            "arrival_date": row["actual_receipt_date"],
            "due_date": row["promised_date"],
            "order_date": row["order_date"],
            "delay_days": int(row["delay_days"]),
            "bl_number": f"BL-{row['receipt_id']}",
            "port_of_loading": "Shanghai" if "Qingdao" in row["supplier"] or "Ningbo" in row["supplier"] else "Busan",
            "port_of_discharge": row.get("port_of_discharge") or "Busan, Republic of Korea",
            "receiving_company_location": f"{row['company_name']} 공장",
            "round_trip_candidate": row.get("round_trip_candidate") == "Y",
            "round_trip_target_shipment_id": row.get("round_trip_target_shipment_id") or None,
            "free_storage_until": row.get("free_storage_until") or None,
            "risk_stage": row["risk_stage"],
            "report_id": f"demo-{row['receipt_id']}",
        }
        rows.append(
            {
                "id": message_id,
                "channel": channel,
                "direction": "inbound",
                "source_agent": row["company_name"],
                "target_agent": "플랫폼",
                "event_type": "agent_report_import",
                "related_code": row["material_name"],
                "title": "원자재 입고 보고",
                "summary": (
                    f"{row['company_name']} {row['material_name']} 입고. "
                    f"공급사 {row['supplier']}. 납기 {row['promised_date']} / 실제 {row['actual_receipt_date']} "
                    f"/ 지연 {row['delay_days']}일"
                ),
                "payload_json": payload,
                "status": "수신완료",
                "created_at": row["actual_receipt_date"] + "T09:00:00",
            }
        )
        message_id += 1

    production_by_shipment: dict[str, list[dict]] = {}
    for row in production_rows:
        production_by_shipment.setdefault(row["shipment_batch_id"], []).append(row)

    for row in shipment_rows:
        related_production = production_by_shipment.get(row["shipment_batch_id"], [])
        completed_list = []
        for item in related_production:
            completed_list.append(
                {
                    "company_name": item["company_name"],
                    "label_code": item["label_code"],
                    "release_qty": float(item["production_qty"]),
                    "unit": item["production_unit"],
                    "weight_kg": float(item["shipment_weight_kg"]),
                    "due_date": item["production_due_date"],
                    "release_date": item["production_complete_date"],
                    "started_at": item["production_start_date"],
                    "finished_at": item["production_complete_date"],
                    "due_buffer_days": int(item["due_buffer_days"]),
                    "is_late": item["is_late"],
                }
            )

        payload = {
            "company_id": 2,
            "company_name": "케어라벨사",
            "item_name": row["garment_type"],
            "label_code": row["label_code"],
            "quantity": int(row["garment_units"]),
            "unit": "장",
            "due_date": row["shipment_due_date"],
            "release_date": row["shipment_date"],
            "report_batch_due_date": row["shipment_due_date"],
            "completed_release_count": len(completed_list),
            "completed_release_qty_total": int(row["garment_units"]),
            "shipment_total_weight_kg": float(row["total_weight_kg"]),
            "shipment_box_count_total": int(row["box_count"]),
            "shipment_weight_basis": row["weight_basis"],
            "label_weight_kg": float(row["label_weight_kg"]),
            "fabric_weight_kg": float(row["fabric_weight_kg"]),
            "zipper_button_weight_kg": float(row["zipper_button_weight_kg"]),
            "completed_release_list": completed_list,
            "export_port": row["destination"],
            "packing_list": {
                "filename": f"packing_list_{row['shipment_batch_id']}.csv",
                "content_type": "text/csv",
                "period_from": row["shipment_date"],
                "period_to": row["shipment_date"],
                "total_qty": int(row["garment_units"]),
                "total_weight_kg": float(row["total_weight_kg"]),
                "label_code_count": 1,
                "csv_base64": "",
                "csv_size_bytes": 0,
            },
            "apparel_info": {
                "target_retail_year": int(row["target_retail_year"]),
                "season": row["season"],
                "gender": row["gender"],
                "fabric": row["fabric"],
                "garment_type": row["garment_type"],
                "color": row["color"],
            },
            "ai_report": {
                "analysis_type": "demo_rule_based",
                "uses_openai": False,
                "summary": (
                    f"{row['shipment_batch_id']} {row['season']} {row['gender']} {row['garment_type']} "
                    f"{int(row['garment_units']):,}장 출고"
                ),
            },
            "scenario_tag": row["scenario_tag"],
            "report_id": f"demo-{row['shipment_batch_id']}",
        }
        rows.append(
            {
                "id": message_id,
                "channel": "label",
                "direction": "inbound",
                "source_agent": "케어라벨사",
                "target_agent": "플랫폼",
                "event_type": "collected_release",
                "related_code": row["label_code"],
                "title": "출고완료 보고",
                "summary": payload["ai_report"]["summary"],
                "payload_json": payload,
                "status": "수신완료",
                "created_at": row["shipment_date"] + "T17:00:00",
            }
        )
        message_id += 1

    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize(material_rows: list[dict], production_rows: list[dict], shipment_rows: list[dict], logistics_rows: list[dict]) -> dict:
    severe_material = [row for row in material_rows if int(row["delay_days"]) >= 21]
    late_production = [row for row in production_rows if row["is_late"] == "Y"]
    tight_production = [row for row in production_rows if int(row["due_buffer_days"]) <= 5]
    year_summary = {}
    for year in YEARS:
        y_shipments = [row for row in shipment_rows if int(row["production_year"]) == year]
        y_material = [row for row in material_rows if int(row["year"]) == year]
        y_production = [row for row in production_rows if row["production_due_date"].startswith(str(year))]
        year_summary[str(year)] = {
            "garment_units": sum(int(row["garment_units"]) for row in y_shipments),
            "shipment_batches": len(y_shipments),
            "avg_material_delay_days": round(sum(int(row["delay_days"]) for row in y_material) / max(len(y_material), 1), 2),
            "material_delay_21d_count": sum(1 for row in y_material if int(row["delay_days"]) >= 21),
            "avg_production_due_buffer_days": round(sum(int(row["due_buffer_days"]) for row in y_production) / max(len(y_production), 1), 2),
            "tight_or_late_production_count": sum(1 for row in y_production if int(row["due_buffer_days"]) <= 5),
        }
    return {
        "dataset": "four_year_supply_chain_demo",
        "period": "2023-01-01 to 2026-12-31",
        "total_garment_units": sum(int(row["garment_units"]) for row in shipment_rows),
        "shipment_batches": len(shipment_rows),
        "production_batches": len(production_rows),
        "material_receipts": len(material_rows),
        "round_trip_demo_import_rows": sum(1 for row in material_rows if row.get("round_trip_candidate") == "Y"),
        "logistics_performance_rows": len(logistics_rows),
        "severe_material_delay_rows_21d_plus": len(severe_material),
        "late_production_rows": len(late_production),
        "tight_production_rows_buffer_5d_or_less": len(tight_production),
        "year_summary": year_summary,
        "intended_story": [
            "2023~2024: 공급/생산 모두 정상 기준선",
            "2025: 특정 공급사의 분기 원자재 입고가 2~3주 밀리기 시작",
            "2026: 같은 공급사가 3~6주 지연되고 생산완료도 납기 직전/당일까지 밀림",
            "분기 원자재 입고 특성상 21일 이상 반복 지연부터 공급사 문제 후보로 판단",
            "올해 출고/판매 흐름은 전년도 생산 데이터의 선행 신호로 해석",
        ],
    }


def main() -> None:
    rng = Random(20260615)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    plans = build_shipment_plans(rng)
    material_rows = build_material_receipts(plans, rng)
    shipment_rows = build_finished_shipments(plans)
    production_rows = build_production_batches(plans, rng)
    logistics_perf_rows = build_logistics_performance(plans, rng)
    logistics_snapshot_rows = build_logistics_snapshots(rng)
    platform_message_rows = build_platform_report_messages(material_rows, production_rows, shipment_rows)
    summary = summarize(material_rows, production_rows, shipment_rows, logistics_perf_rows)

    write_csv(OUT_DIR / "material_receipts.csv", material_rows)
    write_csv(OUT_DIR / "production_batches.csv", production_rows)
    write_csv(OUT_DIR / "finished_shipments.csv", shipment_rows)
    write_csv(OUT_DIR / "logistics_performance.csv", logistics_perf_rows)
    write_csv(OUT_DIR / "logistics_snapshots.csv", logistics_snapshot_rows)
    write_csv(OUT_DIR / "platform_report_messages.csv", platform_message_rows)

    with (OUT_DIR / "platform_report_messages.jsonl").open("w", encoding="utf-8") as f:
        for row in platform_message_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with (OUT_DIR / "dataset_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    readme = f"""# Four Year Supply Chain Demo Data

기간: 2023-01-01 ~ 2026-12-31

목적:
- 총 의류 {summary['total_garment_units']:,}장 규모의 4년치 시연 데이터
- 1~2년차는 정상 운영, 3년차는 자재 공급 지연 시작, 4년차는 자재 지연 + 생산성 저하가 확실하게 드러나도록 설계
- AI 인사이트 / 분석 페이지에서 공급사 변경, 선발주, 생산성 개선, 물류 전략 제안을 만들기 위한 근거 데이터

파일:
- material_receipts.csv: 분기별 원자재 발주/납기/실제입고/공급사/지연일
- material_receipts.csv 안의 round_trip_candidate=Y 10건: 수출 납기일 D-0~D-2에 같은 항구로 도착한 귀로매칭 시연용 BL
- production_batches.csv: 생산사별 생산시작/완료/납기/납기여유일
- finished_shipments.csv: 월 3~4회 출고묶음과 패킹리스트 성격의 생산품 구성
- logistics_performance.csv: 물류 배차 요청/확정/배송 지연
- logistics_snapshots.csv: 월별 기사/차량 스냅샷
- platform_report_messages.csv/jsonl: 플랫폼 report_message 적재용 보고 이벤트
- dataset_summary.json: 의도된 패턴과 요약 통계

무게/수량 산식:
- 라벨agent: 완제품 라벨 1,000장 = 1kg, 라벨원단 1m = 25장 생산분, 잉크 1통 = 10,000장 생산분, 잉크 10통 = 1kg
- 옷감agent: 출고 원단 1야드 = 0.3kg, 원사 1kg당 생산량은 C 3.0야드 / P 5.0야드 / L 2.5야드 / W 2.0야드 / M 3.5야드
- 지퍼단추agent: 출고품은 개당 5g, 플라스틱단추 200개/kg, 금속단추 150개/kg, 지퍼 1개당 지퍼테이프 1m
- 플랫폼 label 채널의 shipment_total_weight_kg는 라벨사 출고중량만 의미한다. 옷감/지퍼단추 중량은 fabric_weight_kg, zipper_button_weight_kg로 분리한다.

플랫폼 DB 적재:
- dry-run: `python 플랫폼agent/backend/seed_four_year_demo.py`
- 실제 적재: `python 플랫폼agent/backend/seed_four_year_demo.py --apply`
- 기존 demo report_id(`demo-*`) 행 정리 후 재적재: `python 플랫폼agent/backend/seed_four_year_demo.py --apply --reset-demo`

중요 판단 기준:
- 원자재는 분기 1회 입고이므로 3~7일 지연은 정상 변동으로 본다.
- 21일 이상 지연이 반복될 때 공급사 문제 후보로 본다.
- 2025년부터 일부 공급사의 21일 이상 지연이 발생한다.
- 2026년에는 21~45일 지연과 생산 납기 여유일 0~5일/일부 지연이 함께 발생한다.
- 올해 출고/판매 흐름은 전년도 생산 데이터의 선행 신호로 해석한다.
- 귀로매칭 시연용 BL은 항구 무료보관 2일을 반영해 수출 납기일이 수입 도착일~도착일+2일 사이에 들어오도록 설계한다.
"""
    (OUT_DIR / "README.md").write_text(readme, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
