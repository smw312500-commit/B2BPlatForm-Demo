import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from demo_mode import seed_demo_mode_if_enabled
from init_db import init

load_dotenv()

from routers import agent_report, collected, dashboard, dispatch, insights, labelcode, logistics_sync, packing_list, report_channels  # noqa: E402

app = FastAPI(title="B2B Platform Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(collected.router, prefix="/api", tags=["출고수집"])
app.include_router(dispatch.router, prefix="/api", tags=["배차"])
app.include_router(insights.router, prefix="/api", tags=["인사이트"])
app.include_router(dashboard.router, prefix="/api", tags=["대시보드"])
app.include_router(labelcode.router, prefix="/api", tags=["라벨코드"])
app.include_router(agent_report.router, prefix="/api", tags=["에이전트 보고"])
app.include_router(report_channels.router, prefix="/api", tags=["보고 채널"])
app.include_router(logistics_sync.router, prefix="/api", tags=["물류 동기화"])
app.include_router(packing_list.router, prefix="/api", tags=["패킹리스트"])


@app.on_event("startup")
def startup():
    init()
    seed_demo_mode_if_enabled()


@app.get("/")
def root():
    return {"service": "B2B Platform Agent", "status": "running", "port": 8000}
