"""
옷감사 기존 출고완료 이력 → 플랫폼 DB 마이그레이션
실행: python migrate_fabric.py
"""
import pymysql
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

PLATFORM_DB = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": "platform",
    "charset": "utf8mb4",
}

FABRIC_DB = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": "company_fabric",
    "charset": "utf8mb4",
}

FABRIC_NAMES = {"C": "면", "P": "폴리에스터", "L": "린넨", "W": "울", "M": "혼방"}


def run():
    fabric_conn = pymysql.connect(**FABRIC_DB)
    platform_conn = pymysql.connect(**PLATFORM_DB)

    try:
        with fabric_conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 전체 현황 먼저 확인
            cur.execute("SELECT status, COUNT(*) as cnt FROM fabric_release GROUP BY status")
            for row in cur.fetchall():
                print(f"  status='{row['status']}' : {row['cnt']}건")

            cur.execute("""
                SELECT id, fabric_code, color_code, release_qty, due_date,
                       status, release_date, label_code, created_at
                FROM fabric_release
                WHERE status = '출고완료'
                ORDER BY created_at
            """)
            rows = cur.fetchall()

        print(f"옷감사 출고완료 이력: {len(rows)}건")

        inserted = 0
        skipped = 0

        with platform_conn.cursor() as cur:
            for r in rows:
                fabric_name = FABRIC_NAMES.get(r["fabric_code"], r["fabric_code"])
                item_name = f"{fabric_name}_{r['color_code']}"
                collected_at = r.get("created_at") or r.get("release_date") or datetime.now()

                # 중복 체크 (같은 company_id + item_name + due_date + label_code)
                cur.execute("""
                    SELECT id FROM collected_release
                    WHERE company_id = 1
                      AND item_name = %s
                      AND due_date = %s
                      AND (label_code = %s OR (label_code IS NULL AND %s IS NULL))
                    LIMIT 1
                """, (item_name, r["due_date"], r["label_code"], r["label_code"]))

                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute("""
                    INSERT INTO collected_release
                        (company_id, item_name, quantity, unit, due_date, status, label_code, collected_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    1,
                    item_name,
                    float(r["release_qty"]),
                    "야드",
                    r["due_date"],
                    "출고완료",
                    r["label_code"],
                    collected_at,
                ))
                inserted += 1

        platform_conn.commit()
        print(f"완료: {inserted}건 삽입, {skipped}건 중복 스킵")

    finally:
        fabric_conn.close()
        platform_conn.close()


if __name__ == "__main__":
    run()
