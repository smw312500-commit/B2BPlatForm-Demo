from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()

# ── MySQL 설정 (데모에서는 사용 안 함 — SQLite 파일 시드로 대체) ───────────────
# from sqlalchemy import inspect, text
# DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
# DB_PORT = os.getenv("DB_PORT", "3307")
# DB_USER = os.getenv("DB_USER", "root")
# DB_PASSWORD = os.getenv("DB_PASSWORD", "")
# DB_NAME = os.getenv("DB_NAME", "company_logistics")
# SCHEMA_NAME = DB_NAME
#
# _root_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}?charset=utf8mb4"
# try:
#     _tmp = create_engine(_root_url)
#     with _tmp.begin() as connection:
#         connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4"))
#     _tmp.dispose()
# except Exception as exc:
#     print(f"[DB] could not auto-create database: {exc}")
#
# DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# ── SQLite 데모 DB (MySQL 서버/비밀번호 불필요, 시드 데이터 자동 적재) ─────────
_DB_FILE = Path(__file__).resolve().parent / "demo.db"
DATABASE_URL = f"sqlite:///{_DB_FILE.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema_updates():
    """MySQL 전용 컬럼 마이그레이션이었음. SQLite 데모에서는 create_all 이
    모델 정의대로 테이블/컬럼을 모두 생성하므로 별도 작업 불필요 (no-op)."""
    return


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
