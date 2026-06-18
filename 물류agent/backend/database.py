from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3307")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "company_logistics")
SCHEMA_NAME = DB_NAME

_root_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}?charset=utf8mb4"
try:
    _tmp = create_engine(_root_url)
    with _tmp.begin() as connection:
        connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4"))
    _tmp.dispose()
except Exception as exc:
    print(f"[DB] could not auto-create database: {exc}")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema_updates():
    inspector = inspect(engine)
    if not inspector.has_table("driver", schema=SCHEMA_NAME):
        return

    driver_columns = {column["name"] for column in inspector.get_columns("driver", schema=SCHEMA_NAME)}

    if "base_region" not in driver_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"ALTER TABLE `{SCHEMA_NAME}`.`driver` "
                    "ADD COLUMN `base_region` VARCHAR(20) NULL AFTER `location_gu`"
                )
            )

    if inspector.has_table("delivery", schema=SCHEMA_NAME):
        delivery_columns = {
            column["name"]: column
            for column in inspector.get_columns("delivery", schema=SCHEMA_NAME)
        }
        empty_return = delivery_columns.get("empty_return")
        if empty_return is not None and getattr(empty_return.get("type"), "length", None) != 100:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        f"ALTER TABLE `{SCHEMA_NAME}`.`delivery` "
                        "MODIFY COLUMN `empty_return` VARCHAR(100) NULL DEFAULT '미정'"
                    )
                )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
