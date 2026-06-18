import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect as sa_inspect, text
from database import engine, Base
from demo_mode import seed_demo_mode_if_enabled
from routers import stock, order, release, agent, machine
from services.platform_retry import run_platform_retry_loop

Base.metadata.create_all(bind=engine)


def _ensure_report_id_columns() -> None:
    """Add report_id column to existing label_platform_report_* tables (no-op if already present).
    SQLite/MySQL 공통 — information_schema 대신 SQLAlchemy inspector 로 컬럼 존재 확인."""
    inspector = sa_inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.connect() as conn:
        for table in ("label_platform_report_event", "label_platform_report_message"):
            if table not in existing_tables:
                continue
            columns = {col["name"] for col in inspector.get_columns(table)}
            if "report_id" not in columns:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN report_id VARCHAR(50) NULL"))
                conn.commit()


_ensure_report_id_columns()

app = FastAPI(title="케어라벨회사 AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 — /api 접두사로 통일 (EXE 정적 서빙 + dev proxy 모두 호환)
app.include_router(stock.router, prefix="/api")
app.include_router(order.router, prefix="/api")
app.include_router(release.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(machine.router, prefix="/api")


@app.on_event("startup")
async def _start_platform_retry_loop() -> None:
    await asyncio.to_thread(seed_demo_mode_if_enabled)
    asyncio.create_task(run_platform_retry_loop())


@app.get("/api/health")
def health():
    return {"service": "케어라벨회사 AI Agent", "status": "running"}


# 빌드된 프론트엔드 정적 서빙 — API 라우터 등록 후 마지막에 마운트
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
