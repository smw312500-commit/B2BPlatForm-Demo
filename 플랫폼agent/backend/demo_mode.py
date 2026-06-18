import asyncio
import os
from datetime import date

from database import SessionLocal
from models import Dispatch, LogisticsDriverCache, ReportMessage
from seed_four_year_demo import (
    MESSAGES_PATH,
    SNAPSHOTS_PATH,
    load_jsonl,
    load_latest_snapshots,
    seed_export_dispatches,
    seed_import_dispatches,
    seed_latest_driver_cache,
    seed_messages,
    seed_summary_insight,
)


DEMO_DISPATCH_MONTH = "2026-07"


def demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def seed_demo_mode_if_enabled() -> None:
    if not demo_mode_enabled():
        return

    print("[DEMO_MODE] 플랫폼 4년치 시연 데이터 확인")
    messages = load_jsonl(MESSAGES_PATH)
    snapshots = load_latest_snapshots(SNAPSHOTS_PATH)

    db = SessionLocal()
    try:
        demo_message_count = (
            db.query(ReportMessage)
            .filter(ReportMessage.source_report_id.like("demo-%"))
            .count()
        )
        if demo_message_count == 0:
            message_count, release_count = seed_messages(db, messages)
            print(f"[DEMO_MODE] 플랫폼 보고 데이터 적재: messages={message_count}, releases={release_count}")
        else:
            print(f"[DEMO_MODE] 플랫폼 보고 데이터 존재: messages={demo_message_count}")

        if db.query(LogisticsDriverCache).count() == 0:
            driver_count = seed_latest_driver_cache(db, snapshots)
            print(f"[DEMO_MODE] 물류 기사 스냅샷 적재: drivers={driver_count}")

        july_export_count = (
            db.query(Dispatch)
            .filter(
                Dispatch.dispatch_type == "export",
                Dispatch.source_report_id.like("demo-%"),
                Dispatch.due_date >= date(2026, 7, 1),
                Dispatch.due_date <= date(2026, 7, 31),
            )
            .count()
        )
        if july_export_count == 0:
            import_count = asyncio.run(seed_import_dispatches(db, messages, DEMO_DISPATCH_MONTH))
            export_count = asyncio.run(seed_export_dispatches(db, messages, DEMO_DISPATCH_MONTH))
            print(f"[DEMO_MODE] 7월 배차 시드: import_dispatches={import_count}, export_dispatches={export_count}")
        else:
            print(f"[DEMO_MODE] 7월 배차 데이터 존재: export_dispatches={july_export_count}")

        if seed_summary_insight(db):
            print("[DEMO_MODE] 요약 인사이트 적재 완료")
    except Exception as exc:
        print(f"[DEMO_MODE] 플랫폼 데모 데이터 시드 실패: {exc}")
    finally:
        db.close()
