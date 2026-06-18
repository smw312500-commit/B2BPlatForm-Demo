from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


# ── 재고 ──────────────────────────────────────────────
class StockOut(BaseModel):
    id: int
    material_name: str
    unit: str
    stock_qty: Decimal
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── 발주 ──────────────────────────────────────────────
class OrderCreate(BaseModel):
    material_name: str
    order_qty: Decimal
    supplier: Optional[str] = None
    order_date: date
    due_date: date
    note: Optional[str] = None

class OrderOut(OrderCreate):
    id: int
    status: str

    class Config:
        from_attributes = True


# ── 출고 ──────────────────────────────────────────────
class ReleaseCreate(BaseModel):
    item_name: str
    release_qty: int
    due_date: date
    label_code: Optional[str] = None

class ReleaseComplete(BaseModel):
    started_at:  Optional[datetime] = None
    finished_at: Optional[datetime] = None

class ReleaseOut(BaseModel):
    id: int
    item_name: str
    release_qty: int
    due_date: date
    label_code: Optional[str]
    status: str
    release_date: Optional[date]
    started_at:   Optional[datetime]
    finished_at:  Optional[datetime]
    created_at:   Optional[datetime]

    class Config:
        from_attributes = True


# ── 돌발상황 보고 ──────────────────────────────────────
class IncidentReport(BaseModel):
    release_id:               int
    reason:                   str
    new_estimated_completion: Optional[datetime] = None


# ── AI Agent ──────────────────────────────────────────
class AgentRequest(BaseModel):
    item_name:   str
    release_qty: int
    due_date:    date

class AgentResponse(BaseModel):
    item_name:       str
    item_type:       str
    release_qty:     int
    required_hours:  float
    required_days:   int
    raw_material:    str
    raw_needed:      float
    raw_unit:        str
    stock_ok:        bool
    days_remaining:  int
    deadline_status: str
    warnings:        list[str]
    instructions:    list[str]
    is_valid:        bool


# ── 플랫폼 보고 채널 ────────────────────────────────────
class PlatformReportReply(BaseModel):
    report_type: str
    item_ref:    str
    status:      str = "수신확인"
    message:     str
    payload:     Optional[dict] = None
