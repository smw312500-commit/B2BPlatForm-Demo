"""
2026년 7월 옷감회사 시연 데이터 생성 스크립트.
지시이력.txt [2026-06-15] "7월 시연용 가짜 데이터 생성 지시" 구현.
(라벨agent/backend/seed_july_demo.py 패턴을 옷감agent 구조에 맞춰 적용)

실행: (옷감agent venv) python seed_july_demo.py

각 주차 = 1개 출고묶음 = 1개 물류 매칭 시나리오:
  · 1주차(07-03) 정상 배차       - 여유 있게 완료, 표준 중량
  · 2주차(07-10) 납기임박 배차    - release_date == due_date (마감 당일 출고)
  · 3주차(07-17) 귀로가능 배차    - 가장 가벼움(소량) → 귀로 화물 매칭 적합
  · 4주차(07-24) 중량제약 배차    - 가장 무거움(대량, 2일 작업) → 소형차 제외 대상
  · 5주차(07-31) 중복방지 재전송  - 동일 묶음 보고를 2회 전송(같은 report_batch_due_date)

원자재(원사) 입고 → 원단 생산완료 → 재고 → 출고완료 → 플랫폼 묶음 보고 순서로
실제 업무 플로우를 그대로 재현한다. 플랫폼agent 미기동 시 보고는 "플랫폼 보고 대기"로
남지만 payload는 정상 저장된다(정상 동작).
"""
from __future__ import annotations

import asyncio
import math
from datetime import date, datetime

from database import SessionLocal
from models import FabricOrder, FabricProduction, FabricRelease, FabricStock
from services.platform_reporter import report_release_batch
from services.production_rules import FABRIC_NAMES, YARN_RATIO

BOX_YARDS = 500            # 박스 1개 = 500야드 기준 (박스수 = ceil(총야드 / 500))
KG_PER_YARD = 0.3          # routers/release.py 패킹리스트와 동일 환산 기준
YARN_SUPPLIER = "India Cotton Export Ltd."

# 주차별 출고묶음 정의. items = [(label_code, fabric_code, color_code, release_qty(야드)), ...]
WEEKS = [
    {
        "label": "1주차(07-03) 정상 배차",
        "due_date": date(2026, 7, 3),
        "release_date": date(2026, 7, 2),
        "completed_at": datetime(2026, 7, 2, 10, 0),
        "destination": "서울 통합물류센터",
        "order_date": date(2026, 6, 26),
        "order_due_date": date(2026, 7, 1),
        "items": [("W2MTC05BK", "C", "BK", 800), ("W2WTP06NV", "P", "NV", 700)],
        "resend": False,
    },
    {
        "label": "2주차(07-10) 납기임박 배차",
        "due_date": date(2026, 7, 10),
        "release_date": date(2026, 7, 10),   # 마감 당일 출고
        "completed_at": datetime(2026, 7, 10, 17, 30),
        "destination": "부산 통합물류센터",
        "order_date": date(2026, 7, 3),
        "order_due_date": date(2026, 7, 8),
        "items": [("W2MTL05BE", "L", "BE", 800), ("W2WTW06GY", "W", "GY", 700)],
        "resend": False,
    },
    {
        "label": "3주차(07-17) 귀로가능 배차",
        "due_date": date(2026, 7, 17),
        "release_date": date(2026, 7, 15),
        "completed_at": datetime(2026, 7, 15, 9, 30),
        "destination": "인천 통합물류센터",
        "order_date": date(2026, 7, 10),
        "order_due_date": date(2026, 7, 14),
        "items": [("W2MTC07WH", "C", "WH", 400)],   # 가장 가벼움
        "resend": False,
    },
    {
        "label": "4주차(07-24) 중량제약 배차",
        "due_date": date(2026, 7, 24),
        "release_date": date(2026, 7, 23),
        "completed_at": datetime(2026, 7, 23, 15, 0),   # 2일 작업(07-22~07-23)
        "destination": "대구 통합물류센터",
        "order_date": date(2026, 7, 15),
        "order_due_date": date(2026, 7, 21),
        "items": [
            ("W2MTC08BK", "C", "BK", 2000),
            ("W2WTP08NV", "P", "NV", 2000),
            ("W2MTW08GY", "W", "GY", 2000),
        ],  # 6,000야드 → 1,800kg, 12박스 (가장 무거움)
        "resend": False,
    },
    {
        "label": "5주차(07-31) 중복보고방지 재전송 배차",
        "due_date": date(2026, 7, 31),
        "release_date": date(2026, 7, 30),
        "completed_at": datetime(2026, 7, 30, 10, 15),
        "destination": "광주 통합물류센터",
        "order_date": date(2026, 7, 22),
        "order_due_date": date(2026, 7, 28),
        "items": [("W2MTC09BK", "C", "BK", 800), ("W2WTP09NV", "P", "NV", 700)],
        "resend": True,   # 동일 묶음 보고 2회 전송
    },
]


def _get_or_create_stock(db, fabric_code: str, color_code: str) -> FabricStock:
    stock = db.query(FabricStock).filter(
        FabricStock.fabric_code == fabric_code,
        FabricStock.color_code == color_code,
    ).first()
    if not stock:
        stock = FabricStock(fabric_code=fabric_code, color_code=color_code, stock_qty=0)
        db.add(stock)
        db.flush()
    return stock


def _seed_raw_material(db, week):
    """주차별 원사 입고(입고완료)를 원단코드별로 시드. (과거 완료 이력처럼 직접 기록)"""
    by_fabric: dict[str, float] = {}
    for _code, fc, _cc, qty in week["items"]:
        by_fabric[fc] = by_fabric.get(fc, 0.0) + qty
    for fc, yards in by_fabric.items():
        yarn_kg = round(yards * YARN_RATIO.get(fc, 3.0), 1)
        db.add(FabricOrder(
            material_name=f"{FABRIC_NAMES.get(fc, fc)} 원사",
            order_qty=yarn_kg,
            supplier=YARN_SUPPLIER,
            order_date=week["order_date"],
            due_date=week["order_due_date"],
            status="입고완료",
            note=f"{week['label']} 생산 대비 원사 입고",
        ))


def _produce_and_release(db, week):
    """생산완료(stage=완성) + 재고확보 → 출고건 생성 → 출고완료(재고차감) 처리."""
    releases = []
    for label_code, fc, cc, qty in week["items"]:
        # 1) 원단 생산완료 이력
        db.add(FabricProduction(
            fabric_code=fc, color_code=cc, quantity=qty,
            stage="완성", target_date=week["due_date"],
            worker="시연라인", note=f"{week['label']} 생산완료",
            completed_at=week["completed_at"],
        ))
        # 2) 생산 산출분을 원단 재고에 반영
        stock = _get_or_create_stock(db, fc, cc)
        stock.stock_qty = float(stock.stock_qty) + qty
        # 3) 출고건 생성
        release = FabricRelease(
            label_code=label_code, fabric_code=fc, color_code=cc,
            release_qty=qty, due_date=week["due_date"], status="생산중",
        )
        db.add(release)
        releases.append(release)
    db.commit()
    for r in releases:
        db.refresh(r)

    # 4) 출고완료 처리 (routers/release.py complete_release 로직과 동일: 재고차감 + 상태/출고일)
    for r in releases:
        stock = _get_or_create_stock(db, r.fabric_code, r.color_code)
        stock.stock_qty = float(stock.stock_qty) - float(r.release_qty)
        r.status = "출고완료"
        r.release_date = week["release_date"]
    db.commit()
    for r in releases:
        db.refresh(r)
    return releases


async def _send_batch(releases, week, box_count):
    await report_release_batch(
        releases,
        destination=week["destination"],
        report_batch_due_date=week["due_date"],
        box_count=box_count,
    )


def main():
    db = SessionLocal()
    try:
        # 중복 시드 방지: 7월 출고건이 이미 있으면 중단
        existing = db.query(FabricRelease).filter(
            FabricRelease.due_date >= date(2026, 7, 1),
            FabricRelease.due_date <= date(2026, 7, 31),
        ).count()
        if existing:
            print(f"[중단] 7월 출고건이 이미 {existing}건 존재합니다. 재시드하려면 기존 행 정리 후 실행하세요.")
            return

        for week in WEEKS:
            print("===", week["label"], "===")
            _seed_raw_material(db, week)
            db.commit()
            releases = _produce_and_release(db, week)

            total_qty = sum(float(r.release_qty) for r in releases)
            total_weight = round(total_qty * KG_PER_YARD, 1)
            box_count = math.ceil(total_qty / BOX_YARDS)
            print(
                f"  release id={releases[0].id}-{releases[-1].id} "
                f"items={len(releases)} total={total_qty:,.0f}야드 "
                f"weight={total_weight}kg box={box_count} dest={week['destination']}"
            )

            asyncio.run(_send_batch(releases, week, box_count))
            print("  묶음 보고 전송")
            if week["resend"]:
                asyncio.run(_send_batch(releases, week, box_count))
                print("  묶음 보고 재전송(중복방지 시연용)")

        print("=== 완료 ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
