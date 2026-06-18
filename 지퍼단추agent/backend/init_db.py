"""
DB 테이블 초기화 스크립트
기존 테이블을 전부 DROP 후 현재 스키마로 재생성
"""
from database import engine, Base
import models  # noqa: F401  — SQLAlchemy metadata 등록 side-effect

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)

print("Creating all tables with current schema...")
Base.metadata.create_all(bind=engine)

print("Done. Tables recreated:")
from sqlalchemy import inspect
for table in inspect(engine).get_table_names():
    print(f"  - {table}")
