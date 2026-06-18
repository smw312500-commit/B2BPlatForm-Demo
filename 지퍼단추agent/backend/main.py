import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from demo_mode import seed_demo_mode_if_enabled
from routers import stock, order, release, agent
from services.platform_retry import run_platform_retry_loop

Base.metadata.create_all(bind=engine)

app = FastAPI(title="지퍼단추사 AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router)
app.include_router(order.router)
app.include_router(release.router)
app.include_router(agent.router)


@app.on_event("startup")
async def _start_platform_retry_loop() -> None:
    await asyncio.to_thread(seed_demo_mode_if_enabled)
    asyncio.create_task(run_platform_retry_loop())


@app.get("/")
def root():
    return {"service": "지퍼단추사 AI Agent", "status": "running"}
