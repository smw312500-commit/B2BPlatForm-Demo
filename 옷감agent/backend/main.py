import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from demo_mode import seed_demo_mode_if_enabled
from routers import stock, order, release, agent, production
from services.platform_retry import run_platform_retry_loop

Base.metadata.create_all(bind=engine)

app = FastAPI(title="옷감회사 업무자동화 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router)
app.include_router(order.router)
app.include_router(release.router)
app.include_router(agent.router)
app.include_router(production.router)


@app.on_event("startup")
async def _start_platform_retry_loop() -> None:
    await asyncio.to_thread(seed_demo_mode_if_enabled)
    asyncio.create_task(run_platform_retry_loop())


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "옷감회사 업무자동화"}
