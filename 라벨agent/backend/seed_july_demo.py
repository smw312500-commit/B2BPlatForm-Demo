"""
2026년 7월 라벨회사 시연 데이터 생성 스크립트.
지시이력.txt [2026-06-15] "7월 시연용 가짜 데이터 생성 지시" 구현.

실행: (옷감agent venv) python seed_july_demo.py
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime

from database import SessionLocal
from models import LabelMachine, LabelOrder, LabelRelease, LabelStock
from services.machine_state import assign_release_to_machine
from services.platform_sender import send_release_to_platform
from services.release_completion import build_release_platform_send_kwargs, finalize_release_record

LABEL_CODES = [
    "W1MTP05BE",
    "W2WTL06WH",
    "W2WPL07BE",
    "W2MTC08RD",
    "W2MPL09NV",
    "W2WPM10GY",
]

SUPPLIER = "LABEL MATERIAL SUPPLY CO., LTD."

WEEKS = [
    {
        "label": "1주차(07-03) 정상 배차",
        "due_date": date(2026, 7, 3),
        "release_date": date(2026, 7, 2),
        "started_at": datetime(2026, 7, 2, 9, 0),
        "finished_at": datetime(2026, 7, 2, 10, 15),
        "release_qty": 1000,
        "fabric_order_qty": 500.0,
        "ink_order_qty": 10.0,
        "order_date": date(2026, 6, 26),
        "order_due_date": date(2026, 7, 1),
        "resend": False,
    },
    {
        "label": "2주차(07-10) 납기임박 배차",
        "due_date": date(2026, 7, 10),
        "release_date": date(2026, 7, 10),
        "started_at": datetime(2026, 7, 10, 9, 0),
        "finished_at": datetime(2026, 7, 10, 17, 45),
        "release_qty": 1000,
        "fabric_order_qty": 500.0,
        "ink_order_qty": 10.0,
        "order_date": date(2026, 7, 3),
        "order_due_date": date(2026, 7, 8),
        "resend": False,
    },
    {
        "label": "3주차(07-17) 귀로가능 배차",
        "due_date": date(2026, 7, 17),
        "release_date": date(2026, 7, 15),
        "started_at": datetime(2026, 7, 15, 9, 0),
        "finished_at": datetime(2026, 7, 15, 9, 30),
        "release_qty": 200,
        "fabric_order_qty": 200.0,
        "ink_order_qty": 5.0,
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
        "release_qty": 12000,
        "fabric_order_qty": 2000.0,
        "ink_order_qty": 15.0,
        "order_date": date(2026, 7, 15),
        "order_due_date": date(2026, 7, 21),
        "resend": False,
    },
    {
        "label": "5주차(07-31) 중복보고방지 재전송 배차",
        "due_date": date(2026, 7, 31),
        "release_date": date(2026, 7, 30),
        "started_at": datetime(2026, 7, 30, 9, 0),
        "finished_at": datetime(2026, 7, 30, 10, 15),
        "release_qty": 1000,
        "fabric_order_qty": 500.0,
        "ink_order_qty": 10.0,
        "order_date": date(2026, 7, 22),
        "order_due_date": date(2026, 7, 28),
        "resend": True,
    },
]


def _restock(db, week):
    fabric = db.query(LabelStock).filter(LabelStock.material_name == "라벨원단").first()
    ink = db.query(LabelStock).filter(LabelStock.material_name == "잉크").first()

    db.add_all([
        LabelOrder(
            material_name="라벨원단",
            order_qty=week["fabric_order_qty"],
            supplier=SUPPLIER,
            order_date=week["order_date"],
            due_date=week["order_due_date"],
            status="입고완료",
            note=f"{week['label']} 생산 대비 라벨원단 입고",
        ),
        LabelOrder(
            material_name="잉크",
            order_qty=week["ink_order_qty"],
            supplier=SUPPLIER,
            order_date=week["order_date"],
            due_date=week["order_due_date"],
            status="입고완료",
            note=f"{week['label']} 생산 대비 잉크 입고",
        ),
    ])

    fabric.stock_qty = float(fabric.stock_qty) + week["fabric_order_qty"]
    ink.stock_qty = float(ink.stock_qty) + week["ink_order_qty"]
    db.commit()


def _produce_week(db, week):
    releases = []
    for code in LABEL_CODES:
        release = LabelRelease(
            label_code=code,
            release_qty=week["release_qty"],
            due_date=week["due_date"],
            status="생산중",
        )
        db.add(release)
        releases.append(release)
    db.commit()
    for release in releases:
        db.refresh(release)

    machines = (
        db.query(LabelMachine)
        .filter(LabelMachine.id.in_(range(1, 7)))
        .order_by(LabelMachine.id)
        .all()
    )
    for machine, release in zip(machines, releases):
        assign_release_to_machine(machine, release)
        machine.started_at = week["started_at"]
    db.commit()

    export_payload = None
    for release in releases:
        release, export_payload = finalize_release_record(
            db,
            release,
            started_at=week["started_at"],
            finished_at=week["finished_at"],
            release_date=week["release_date"],
        )

    for machine, release in zip(machines, releases):
        machine.status = "완료"
        machine.produced_qty = release.release_qty
        machine.running_started_at = None
        machine.finished_at = week["finished_at"]
    db.commit()

    return releases, export_payload


async def _send(release, export_payload):
    return await send_release_to_platform(**build_release_platform_send_kwargs(release, export_payload))


def main():
    db = SessionLocal()
    try:
        existing = db.query(LabelRelease).filter(
            LabelRelease.due_date >= date(2026, 7, 1),
            LabelRelease.due_date <= date(2026, 7, 31),
        ).count()
        if existing:
            print(f"[중단] 7월 라벨 출고건이 이미 {existing}건 존재합니다. 데모 시드를 건너뜁니다.")
            return

        for mid in (5, 6):
            machine = db.query(LabelMachine).filter(LabelMachine.id == mid).first()
            if machine and machine.status == "점검중":
                machine.status = "대기중"
                print(f"인쇄기 {mid}호 정비완료 -> 대기중")
        db.commit()

        for week in WEEKS:
            print("===", week["label"], "===")
            _restock(db, week)
            releases, export_payload = _produce_week(db, week)
            last_release = releases[-1]

            total_weight = sum(r.product_weight_kg for r in releases)
            print(
                f"  releases id={releases[0].id}-{releases[-1].id} "
                f"qty/ea={week['release_qty']} total_weight={total_weight}kg "
                f"box_total={export_payload['shipment_box_count_total']}"
            )

            result = asyncio.run(_send(last_release, export_payload))
            print("  report send:", result)

            if week["resend"]:
                result2 = asyncio.run(_send(last_release, export_payload))
                print("  report RESEND:", result2)

        fabric = db.query(LabelStock).filter(LabelStock.material_name == "라벨원단").first()
        ink = db.query(LabelStock).filter(LabelStock.material_name == "잉크").first()
        print("=== final stock ===")
        print("라벨원단:", fabric.stock_qty, "잉크:", ink.stock_qty)
    finally:
        db.close()


if __name__ == "__main__":
    main()
