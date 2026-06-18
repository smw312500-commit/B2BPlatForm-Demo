from sqlalchemy import inspect, text

from database import Base, SessionLocal, engine
import models  # noqa: F401

INITIAL_COMPANIES = [
    {"id": 1, "company_name": "옷감사", "company_type": "생산사", "address_si": "서울시", "address_gu": "구로구"},
    {"id": 2, "company_name": "케어라벨사", "company_type": "생산사", "address_si": "서울시", "address_gu": "금천구"},
    {"id": 3, "company_name": "지퍼단추사", "company_type": "생산사", "address_si": "서울시", "address_gu": "구로구"},
    {"id": 4, "company_name": "물류사", "company_type": "물류사", "address_si": "서울시", "address_gu": "금천구"},
]


def init():
    Base.metadata.create_all(bind=engine)
    _ensure_dispatch_columns()
    _ensure_report_message_columns()
    _ensure_logistics_driver_cache_columns()

    db = SessionLocal()
    try:
        for data in INITIAL_COMPANIES:
            exists = db.query(models.CompanyInfo).filter(models.CompanyInfo.id == data["id"]).first()
            if not exists:
                db.add(models.CompanyInfo(**data))
                continue

            exists.company_name = data["company_name"]
            exists.company_type = data["company_type"]
            exists.address_si = data["address_si"]
            exists.address_gu = data["address_gu"]
        db.commit()
        print("DB 초기화 완료")
    finally:
        db.close()


def _ensure_dispatch_columns():
    inspector = inspect(engine)
    if not inspector.has_table("dispatch"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("dispatch")}
    alter_statements = []

    if "dispatch_type" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN dispatch_type VARCHAR(20) NOT NULL DEFAULT 'export'")
    if "source_report_id" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN source_report_id VARCHAR(100) NULL")
    if "origin_port" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN origin_port VARCHAR(50) NULL")
    if "cargo_detail" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN cargo_detail VARCHAR(200) NULL")
    if "logistics_delivery_id" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN logistics_delivery_id INT NULL")
    if "logistics_driver_id" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN logistics_driver_id INT NULL")
    if "driver_name" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN driver_name VARCHAR(50) NULL")
    if "logistics_vehicle_id" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN logistics_vehicle_id INT NULL")
    if "vehicle_plate" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN vehicle_plate VARCHAR(20) NULL")
    if "empty_return" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN empty_return VARCHAR(100) NULL")
    if "logistics_message" not in existing_columns:
        alter_statements.append("ALTER TABLE dispatch ADD COLUMN logistics_message TEXT NULL")

    if not alter_statements:
        return

    with engine.begin() as conn:
        for statement in alter_statements:
            conn.execute(text(statement))


def _ensure_report_message_columns():
    inspector = inspect(engine)
    if not inspector.has_table("report_message"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("report_message")}
    if "source_report_id" in existing_columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE report_message ADD COLUMN source_report_id VARCHAR(100) NULL"))


def _ensure_logistics_driver_cache_columns():
    inspector = inspect(engine)
    if not inspector.has_table("logistics_driver_cache"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("logistics_driver_cache")}
    alter_statements = []

    if "phone" not in existing_columns:
        alter_statements.append("ALTER TABLE logistics_driver_cache ADD COLUMN phone VARCHAR(20) NULL")
    if "location_gu" not in existing_columns:
        alter_statements.append("ALTER TABLE logistics_driver_cache ADD COLUMN location_gu VARCHAR(20) NULL")
    if "base_region" not in existing_columns:
        alter_statements.append("ALTER TABLE logistics_driver_cache ADD COLUMN base_region VARCHAR(20) NULL")
    if "vehicle_id" not in existing_columns:
        alter_statements.append("ALTER TABLE logistics_driver_cache ADD COLUMN vehicle_id INT NULL")
    if "vehicle_max_weight" not in existing_columns:
        alter_statements.append("ALTER TABLE logistics_driver_cache ADD COLUMN vehicle_max_weight DECIMAL(8,1) NULL")

    if not alter_statements:
        return

    with engine.begin() as conn:
        for statement in alter_statements:
            conn.execute(text(statement))


if __name__ == "__main__":
    init()
