"""
2026년 7월 지퍼/단추회사 시연 데이터 생성 스크립트.
지시이력.txt [2026-06-15] "7월 시연용 가짜 데이터 생성 지시" 구현.
라벨agent/backend/seed_july_demo.py 패턴을 지퍼단추agent 구조(머신 없음,
routers/release.py의 complete_release 로직을 과거 날짜로 재현)에 맞게 적용.

실행: (옷감agent venv) python seed_july_demo.py
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime

from database import SessionLocal
from models import ZipperOrder, ZipperRelease, ZipperStock
from services.ai_agent import RAW_MATERIAL_MAP, get_item_type
from services.platform_sender import send_release_to_platform

SUPPLIER = {
    "원목":        "원목공급사",
    "플라스틱원료": "플라스틱공급사",
    "금속원료":    "금속공급사",
    "지퍼테이프":  "부자재공급사",
}

UNIT = {
    "원목":        "kg",
    "플라스틱원료": "kg",
    "금속원료":    "kg",
    "지퍼테이프":  "m",
}

# 라벨agent LABEL_CODES 중 ITEM_CODE_MAP 기준으로 부자재가 일치하는 코드를
# label_code(공통 묶음 식별값)로 연동 (T=티셔츠->플라스틱단추, P=바지->금속단추)
LABEL_LINK = {
    "PLASTIC_BK": "W1MTP05BE",  # 라벨agent 1주차~5주차 공통 T라벨(티셔츠) - 플라스틱단추
    "METAL_SV":   "W2WPL07BE",  # 라벨agent 1주차~5주차 공통 P라벨(바지) - 금속단추
}

WEEKS = [
    {
        "label": "1주차(07-03) 정상 배차",
        "due_date": date(2026, 7, 3),
        "release_date": date(2026, 7, 2),
        "started_at": datetime(2026, 7, 2, 9, 0),
        "finished_at": datetime(2026, 7, 2, 15, 0),
        "items": {"WOOD_BR": 200, "PLASTIC_BK": 400, "METAL_SV": 300, "ZIPPER_M": 300},
        "restock": {"원목": 10.0, "플라스틱원료": 5.0, "금속원료": 5.0, "지퍼테이프": 350.0},
        "order_date": date(2026, 6, 26),
        "order_due_date": date(2026, 7, 1),
        "resend": False,
    },
    {
        "label": "2주차(07-10) 납기임박 배차",
        "due_date": date(2026, 7, 10),
        "release_date": date(2026, 7, 10),
        "started_at": datetime(2026, 7, 10, 9, 0),
        "finished_at": datetime(2026, 7, 10, 17, 30),
        "items": {"WOOD_BR": 200, "PLASTIC_BK": 400, "METAL_SV": 300, "ZIPPER_M": 300},
        "restock": {"원목": 10.0, "플라스틱원료": 5.0, "금속원료": 5.0, "지퍼테이프": 350.0},
        "order_date": date(2026, 7, 3),
        "order_due_date": date(2026, 7, 8),
        "resend": False,
    },
    {
        "label": "3주차(07-17) 귀로가능 배차",
        "due_date": date(2026, 7, 17),
        "release_date": date(2026, 7, 15),
        "started_at": datetime(2026, 7, 15, 9, 0),
        "finished_at": datetime(2026, 7, 15, 10, 30),
        "items": {"WOOD_BR": 40, "PLASTIC_BK": 80, "METAL_SV": 60, "ZIPPER_M": 60},
        "restock": {"원목": 5.0, "플라스틱원료": 2.0, "금속원료": 2.0, "지퍼테이프": 100.0},
        "order_date": date(2026, 7, 10),
        "order_due_date": date(2026, 7, 14),
        "resend": False,
    },
    {
        "label": "4주차(07-24) 소형차제외 중량 배차",
        "due_date": date(2026, 7, 24),
        "release_date": date(2026, 7, 23),
        "started_at": datetime(2026, 7, 22, 9, 0),
        "finished_at": datetime(2026, 7, 23, 15, 0),
        "items": {"WOOD_BR": 600, "PLASTIC_BK": 4000, "METAL_SV": 2000, "ZIPPER_M": 2000},
        "restock": {"원목": 15.0, "플라스틱원료": 25.0, "금속원료": 15.0, "지퍼테이프": 2200.0},
        "order_date": date(2026, 7, 15),
        "order_due_date": date(2026, 7, 21),
        "resend": False,
    },
    {
        "label": "5주차(07-31) 중복보고방지 재전송 배차",
        "due_date": date(2026, 7, 31),
        "release_date": date(2026, 7, 30),
        "started_at": datetime(2026, 7, 30, 9, 0),
        "finished_at": datetime(2026, 7, 30, 15, 0),
        "items": {"WOOD_BR": 200, "PLASTIC_BK": 400, "METAL_SV": 300, "ZIPPER_M": 300},
        "restock": {"원목": 10.0, "플라스틱원료": 5.0, "금속원료": 5.0, "지퍼테이프": 350.0},
        "order_date": date(2026, 7, 22),
        "order_due_date": date(2026, 7, 28),
        "resend": True,
    },
]


def _restock(db, week):
    for material, qty in week["restock"].items():
        stock = db.query(ZipperStock).filter(ZipperStock.material_name == material).first()
        if stock is None:
            stock = ZipperStock(material_name=material, unit=UNIT[material], stock_qty=0)
            db.add(stock)
            db.flush()

        db.add(ZipperOrder(
            material_name=material,
            order_qty=qty,
            supplier=SUPPLIER[material],
            order_date=week["order_date"],
            due_date=week["order_due_date"],
            status="입고완료",
            note=f"{week['label']} 생산 대비 {material} 입고",
        ))
        stock.stock_qty = float(stock.stock_qty) + qty
    db.commit()


def _produce_week(db, week):
    """releases.py의 complete_release 로직(재고차감 + 출고완료 처리)을
    과거 날짜(release_date/started_at/finished_at)로 재현한다."""
    releases = []
    for item_name, qty in week["items"].items():
        release = ZipperRelease(
            item_name=item_name,
            release_qty=qty,
            due_date=week["due_date"],
            label_code=LABEL_LINK.get(item_name),
            status="생산중",
        )
        db.add(release)
        releases.append(release)
    db.commit()
    for release in releases:
        db.refresh(release)

    for release in releases:
        item_type = get_item_type(release.item_name)
        raw_info = RAW_MATERIAL_MAP.get(item_type)
        if raw_info:
            raw_needed = release.release_qty / raw_info["rate"]
            stock = db.query(ZipperStock).filter(
                ZipperStock.material_name == raw_info["name"]
            ).first()
            stock.stock_qty = float(stock.stock_qty) - raw_needed

        release.status = "출고완료"
        release.release_date = week["release_date"]
        release.started_at = week["started_at"]
        release.finished_at = week["finished_at"]
    db.commit()
    for release in releases:
        db.refresh(release)

    return releases


async def _send(db, release):
    return await send_release_to_platform(
        db,
        item_name=release.item_name,
        release_qty=release.release_qty,
        due_date=release.due_date,
        release_date=release.release_date,
        label_code=release.label_code,
    )


def main():
    db = SessionLocal()
    try:
        existing = db.query(ZipperRelease).filter(
            ZipperRelease.due_date >= date(2026, 7, 1),
            ZipperRelease.due_date <= date(2026, 7, 31),
        ).count()
        if existing:
            print(f"[중단] 7월 지퍼단추 출고건이 이미 {existing}건 존재합니다. 데모 시드를 건너뜁니다.")
            return

        for week in WEEKS:
            print("===", week["label"], "===")
            _restock(db, week)
            releases = _produce_week(db, week)

            total_qty = sum(r.release_qty for r in releases)
            total_weight = round(total_qty * 5 / 1000, 3)
            print(
                f"  releases id={releases[0].id}-{releases[-1].id} "
                f"total_qty={total_qty} total_weight={total_weight}kg"
            )

            anchor = releases[-1]  # enrich_release_payload가 같은 due_date 묶음 전체를 모아 보고
            result = asyncio.run(_send(db, anchor))
            print("  report send:", result)

            if week["resend"]:
                result2 = asyncio.run(_send(db, anchor))
                print("  report RESEND:", result2)

        print("=== final stock ===")
        for s in db.query(ZipperStock).order_by(ZipperStock.id).all():
            print(f"  {s.material_name}: {s.stock_qty}{s.unit}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
