from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LabelStockBase(BaseModel):
    material_name: str
    unit: str
    stock_qty: Decimal


class LabelStockUpdate(BaseModel):
    stock_qty: Decimal


class LabelStockOut(LabelStockBase):
    id: int
    updated_at: Optional[datetime]
    weight_kg: Optional[float] = None

    class Config:
        from_attributes = True


class LabelOrderCreate(BaseModel):
    material_name: str
    order_qty: Decimal
    supplier: Optional[str] = None
    order_date: date
    due_date: date
    note: Optional[str] = None


class LabelOrderOut(LabelOrderCreate):
    id: int
    status: str
    weight_kg: Optional[float] = None

    class Config:
        from_attributes = True


class LabelReleaseCreate(BaseModel):
    label_code: str
    release_qty: int
    due_date: date

    @field_validator("label_code")
    @classmethod
    def validate_label_code(cls, value: str) -> str:
        from services.label_validator import validate_label_code

        ok, message = validate_label_code(value)
        if not ok:
            raise ValueError(message)
        return value


class LabelReleaseComplete(BaseModel):
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class PackingListSelection(BaseModel):
    release_ids: list[int] = Field(default_factory=list)


class IncidentReport(BaseModel):
    reason: str
    new_estimated_completion: Optional[datetime] = None


class LabelReleaseOut(LabelReleaseCreate):
    id: int
    status: str
    release_date: Optional[date]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: Optional[datetime]
    product_weight_kg: float = 0
    fabric_weight_kg: float = 0
    ink_weight_kg: float = 0
    material_weight_kg: float = 0

    class Config:
        from_attributes = True


class LabelMachineQueueItemOut(BaseModel):
    release_id: int
    label_code: str
    release_qty: int
    due_date: str
    sequence: int


class LabelMachineOut(BaseModel):
    id: int
    name: str
    status: str
    release_id: Optional[int] = None
    label_code: Optional[str] = None
    total_qty: int
    produced_qty: float
    remaining_qty: float
    started_at: Optional[str] = None
    running_started_at: Optional[str] = None
    finished_at: Optional[str] = None
    estimated_completion_at: Optional[str] = None
    queue_count: int = 0
    queue_items: list[LabelMachineQueueItemOut] = Field(default_factory=list)


class LabelMachineAction(BaseModel):
    action: str
    release_id: Optional[int] = None
    release_ids: Optional[list[int]] = None
    status: Optional[str] = None


class AgentRequest(BaseModel):
    label_code: str
    release_qty: int
    due_date: date


class AgentResponse(BaseModel):
    label_code: str
    is_valid: bool
    parsed_info: Optional[dict]
    required_hours: float
    required_days: int
    rule_based_status: Optional[str] = None
    schedule_status: Optional[str] = None
    deadline_status: str
    days_remaining: int
    required_fabric_m: float
    required_ink_count: int
    product_weight_kg: float
    required_fabric_weight_kg: float
    required_ink_weight_kg: float
    required_material_weight_kg: float
    fabric_stock: float
    ink_stock: float
    available_fabric_after_m: Optional[float] = None
    available_ink_after_count: Optional[float] = None
    stock_ok: bool
    estimated_start_at: Optional[str] = None
    estimated_completion_at: Optional[str] = None
    warnings: list[str]
    instructions: list[str]
    status_basis: list[str] = Field(default_factory=list)
    priority_rank: Optional[int] = None


class PlatformReportReply(BaseModel):
    report_type: str
    item_ref: str
    status: str = "수신확인"
    message: str
    payload: Optional[dict] = None
