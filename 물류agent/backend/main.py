from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal, ensure_schema_updates
from demo_mode import seed_demo_mode_if_enabled
from routers import drivers, vehicles, deliveries, ai_agent, platform
from services.platform_sync import sync_drivers_to_platform

Base.metadata.create_all(bind=engine)
ensure_schema_updates()

app = FastAPI(title="물류 Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drivers.router, prefix="/api/drivers", tags=["기사관리"])
app.include_router(vehicles.router, prefix="/api/vehicles", tags=["차량관리"])
app.include_router(deliveries.router, prefix="/api/deliveries", tags=["화물관리"])
app.include_router(ai_agent.router, prefix="/api/ai", tags=["AI 배차"])
app.include_router(platform.router, prefix="/api/platform", tags=["플랫폼 연동"])


@app.on_event("startup")
def startup():
    seed_demo_mode_if_enabled()
    db = SessionLocal()
    try:
        sync_drivers_to_platform(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "물류 Agent API 정상 동작 중"}
