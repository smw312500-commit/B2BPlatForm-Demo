"""
3개 생산사 기존 출고완료 이력 -> 플랫폼 DB 마이그레이션
실행: python migrate_all.py
"""
import pymysql
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

PW   = os.getenv("DB_PASSWORD", "")
USER = os.getenv("DB_USER", "root")
HOST = os.getenv("DB_HOST", "127.0.0.1")
PORT = int(os.getenv("DB_PORT", 3306))

FABRIC_NAMES = {"C": "면", "P": "폴리에스터", "L": "린넨", "W": "울", "M": "혼방"}


def conn(db_name):
    return pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PW,
        database=db_name, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def migrate_fabric(platform_cur):
    """옷감사 (company_id=1) — company_fabric.fabric_release"""
    c = conn("company_fabric")
    try:
        with c.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) cnt FROM fabric_release GROUP BY status")
            for r in cur.fetchall():
                print(f"  [옷감사] status='{r['status']}' {r['cnt']}건")

            cur.execute("""
                SELECT fabric_code, color_code, release_qty, due_date,
                       label_code, created_at, release_date
                FROM fabric_release WHERE status = '출고완료'
            """)
            rows = cur.fetchall()
    finally:
        c.close()

    inserted = 0
    for r in rows:
        name = FABRIC_NAMES.get(r["fabric_code"], r["fabric_code"])
        item = f"{name}_{r['color_code']}"
        at   = r["created_at"] or r["release_date"] or datetime.now()
        platform_cur.execute(
            "SELECT id FROM collected_release WHERE company_id=1 AND item_name=%s AND due_date=%s AND label_code<=>%s LIMIT 1",
            (item, r["due_date"], r["label_code"])
        )
        if platform_cur.fetchone():
            continue
        platform_cur.execute(
            "INSERT INTO collected_release (company_id,item_name,quantity,unit,due_date,status,label_code,collected_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (1, item, float(r["release_qty"]), "야드", r["due_date"], "출고완료", r["label_code"], at)
        )
        inserted += 1
    print(f"  [옷감사] {inserted}건 삽입")


def migrate_label(platform_cur):
    """라벨사 (company_id=2) — company_label.label_release"""
    c = conn("company_label")
    try:
        with c.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) cnt FROM label_release GROUP BY status")
            for r in cur.fetchall():
                print(f"  [라벨사] status='{r['status']}' {r['cnt']}건")

            cur.execute("""
                SELECT label_code, release_qty, due_date,
                       created_at, release_date
                FROM label_release WHERE status = '출고완료'
            """)
            rows = cur.fetchall()
    finally:
        c.close()

    inserted = 0
    for r in rows:
        at = r["created_at"] or r["release_date"] or datetime.now()
        platform_cur.execute(
            "SELECT id FROM collected_release WHERE company_id=2 AND label_code=%s AND due_date=%s LIMIT 1",
            (r["label_code"], r["due_date"])
        )
        if platform_cur.fetchone():
            continue
        platform_cur.execute(
            "INSERT INTO collected_release (company_id,item_name,quantity,unit,due_date,status,label_code,collected_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (2, r["label_code"], float(r["release_qty"]), "장", r["due_date"], "출고완료", r["label_code"], at)
        )
        inserted += 1
    print(f"  [라벨사] {inserted}건 삽입")


def migrate_zipper(platform_cur):
    """지퍼단추사 (company_id=3) — company_zipper.zipper_release"""
    c = conn("company_zipper")
    try:
        with c.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) cnt FROM zipper_release GROUP BY status")
            for r in cur.fetchall():
                print(f"  [지퍼단추사] status='{r['status']}' {r['cnt']}건")

            cur.execute("""
                SELECT item_name, release_qty, due_date,
                       label_code, created_at, release_date
                FROM zipper_release WHERE status = '출고완료'
            """)
            rows = cur.fetchall()
    finally:
        c.close()

    inserted = 0
    for r in rows:
        at = r["created_at"] or r["release_date"] or datetime.now()
        platform_cur.execute(
            "SELECT id FROM collected_release WHERE company_id=3 AND item_name=%s AND due_date=%s AND label_code<=>%s LIMIT 1",
            (r["item_name"], r["due_date"], r["label_code"])
        )
        if platform_cur.fetchone():
            continue
        platform_cur.execute(
            "INSERT INTO collected_release (company_id,item_name,quantity,unit,due_date,status,label_code,collected_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (3, r["item_name"], float(r["release_qty"]), "개", r["due_date"], "출고완료", r["label_code"], at)
        )
        inserted += 1
    print(f"  [지퍼단추사] {inserted}건 삽입")


def run():
    p = conn("platform")
    try:
        with p.cursor() as cur:
            migrate_fabric(cur)
            migrate_label(cur)
            migrate_zipper(cur)
        p.commit()
        print("\n마이그레이션 완료")
    finally:
        p.close()


if __name__ == "__main__":
    run()
