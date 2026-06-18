from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import date, datetime


# ── 수신: 생산사 출고완료 신호 ──────────────────────────────
class CollectedReleaseIn(BaseModel):
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None   # 케어라벨사 등 (company_id 없을 때 매핑용)
    item_name: Optional[str] = None
    quantity: Optional[float] = None
    release_qty: Optional[float] = None  # 라벨agent가 보내는 필드명
    unit: Optional[str] = None
    due_date: Optional[date] = None
    release_date: Optional[date] = None  # 지퍼단추agent가 보내는 필드명
    status: Optional[str] = "출고완료"
    label_code: Optional[str] = None
    trend_signal: Optional[str] = None
    parsed_info: Optional[Any] = None
    pickup_company: Optional[str] = None
    pickup_location: Optional[str] = None
    export_port: Optional[str] = None
    box_count: Optional[int] = None
    box_count_rule: Optional[str] = None
    product_weight_kg: Optional[float] = None
    shipping_weight_kg: Optional[float] = None
    fabric_weight_kg: Optional[float] = None
    ink_weight_kg: Optional[float] = None
    material_weight_kg: Optional[float] = None
    completed_release_list: Optional[Any] = None
    completed_release_count: Optional[int] = None
    completed_release_qty_total: Optional[int] = None
    completed_release_total_weight_kg: Optional[float] = None
    shipment_total_weight_kg: Optional[float] = None
    shipment_box_count_total: Optional[int] = None
    report_batch_due_date: Optional[date] = None
    material_order_snapshot: Optional[Any] = None
    pending_material_order_snapshot: Optional[Any] = None
    pending_material_order_count: Optional[int] = None
    bl_material_orders: Optional[Any] = None
    bl_material_order_count: Optional[int] = None
    stock_snapshot: Optional[Any] = None
    ai_report: Optional[Any] = None
    packing_list: Optional[Any] = None
    report_id: Optional[str] = None


# ── 응답: 수집된 출고 ───────────────────────────────────────
class CollectedReleaseOut(BaseModel):
    id: int
    company_id: int
    company_name: Optional[str] = None
    item_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    label_code: Optional[str] = None
    collected_at: Optional[datetime] = None
    report_id: Optional[str] = None
    received: Optional[bool] = None

    class Config:
        from_attributes = True


# ── 수신: 물류사 배송완료 신호 ─────────────────────────────
class LogisticsCompleteIn(BaseModel):
    delivery_id: Optional[int] = None
    company_id: Optional[int] = None
    destination: Optional[str] = None
    complete_date: Optional[str] = None
    status: Optional[str] = None


# ── 응답: 배차 ─────────────────────────────────────────────
class DispatchOut(BaseModel):
    id: int
    label_code: Optional[str] = None
    company_id: int
    company_name: Optional[str] = None
    dispatch_type: Optional[str] = None
    source_report_id: Optional[str] = None
    origin_port: Optional[str] = None
    destination: Optional[str] = None
    cargo_detail: Optional[str] = None
    weight_kg: Optional[float] = None
    due_date: Optional[date] = None
    pickup_date: Optional[date] = None
    logistics_delivery_id: Optional[int] = None
    logistics_driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    logistics_vehicle_id: Optional[int] = None
    vehicle_plate: Optional[str] = None
    empty_return: Optional[str] = None
    logistics_message: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── 응답: 인사이트 ─────────────────────────────────────────
class InsightOut(BaseModel):
    id: int
    insight_type: Optional[str] = None
    content: Optional[str] = None
    related_code: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── 응답: 대시보드 요약 ────────────────────────────────────
class DashboardSummary(BaseModel):
    total_releases: int
    completed_releases: int
    pending_dispatches: int
    active_insights: int


# ── 응답: 라벨코드 추적 ────────────────────────────────────
class CompanyStatus(BaseModel):
    status: Optional[str] = None
    item_name: Optional[str] = None
    qty: Optional[float] = None


class LabelCodeStatus(BaseModel):
    label_code: str
    옷감사: CompanyStatus
    라벨사: CompanyStatus
    지퍼단추사: CompanyStatus
    all_complete: bool


class ReportChannelOut(BaseModel):
    channel: str
    label: str
    counterparty: str
    message_count: int
    last_message_at: Optional[datetime] = None
    last_summary: Optional[str] = None
    last_direction: Optional[str] = None
    last_status: Optional[str] = None


class PackingListOut(BaseModel):
    id: int
    collected_release_id: Optional[int] = None
    company_id: Optional[int] = None
    label_code: Optional[str] = None
    report_batch_due_date: Optional[date] = None
    filename: Optional[str] = None
    content_type: Optional[str] = None
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    total_qty: Optional[int] = None
    total_weight_kg: Optional[float] = None
    label_code_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReportMessageOut(BaseModel):
    id: int
    channel: str
    direction: str
    source_agent: str
    target_agent: str
    event_type: str
    related_code: Optional[str] = None
    title: str
    summary: str
    payload_json: Optional[Any] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class LogisticsDriverAvailabilityOut(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    location_si: Optional[str] = None
    location_gu: Optional[str] = None
    base_region: Optional[str] = None
    status: Optional[str] = None
    vehicle_id: Optional[int] = None
    vehicle_plate: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_max_weight: Optional[float] = None
    current_delivery_id: Optional[int] = None
    current_destination: Optional[str] = None
    estimated_arrival: Optional[date] = None
    last_synced_at: Optional[datetime] = None


class LogisticsVehicleAvailabilityOut(BaseModel):
    id: Optional[int] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    plate_no: Optional[str] = None
    max_weight: Optional[float] = None
    vehicle_type: Optional[str] = None


class DispatchAvailabilityOut(BaseModel):
    total_driver_count: int = 0
    available_driver_count: int
    available_vehicle_count: int
    drivers: list[LogisticsDriverAvailabilityOut]
    vehicles: list[LogisticsVehicleAvailabilityOut]
    last_synced_at: Optional[datetime] = None


class DispatchMatchOut(BaseModel):
    dispatch_id: int
    status: str
    logistics_delivery_id: Optional[int] = None
    logistics_driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    logistics_vehicle_id: Optional[int] = None
    vehicle_plate: Optional[str] = None
    pickup_date: Optional[date] = None
    empty_return: Optional[str] = None
    logistics_message: Optional[str] = None


# ── 수신: 물류 기사 목록 동기화 ─────────────────────────────
class LogisticsDriverSyncItem(BaseModel):
    driver_id: int
    name: Optional[str] = None
    phone: Optional[str] = None
    location_si: Optional[str] = None
    location_gu: Optional[str] = None
    base_region: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_id: Optional[int] = None
    vehicle_plate: Optional[str] = None
    vehicle_max_weight: Optional[float] = None
    status: Optional[str] = None
    current_delivery_id: Optional[int] = None
    current_destination: Optional[str] = None
    estimated_arrival: Optional[str] = None


class LogisticsDriverSyncIn(BaseModel):
    drivers: list[LogisticsDriverSyncItem]
