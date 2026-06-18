from datetime import datetime

from sqlalchemy import DECIMAL, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class CompanyInfo(Base):
    __tablename__ = "company_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(100), nullable=False)
    company_type = Column(String(20))
    address_si = Column(String(20))
    address_gu = Column(String(20))

    releases = relationship("CollectedRelease", back_populates="company")
    dispatches = relationship("Dispatch", back_populates="company")


class CollectedRelease(Base):
    __tablename__ = "collected_release"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("company_info.id"), nullable=False)
    item_name = Column(String(100))
    quantity = Column(DECIMAL(10, 1))
    unit = Column(String(10))
    due_date = Column(Date)
    status = Column(String(20), default="출고완료")
    label_code = Column(String(9), nullable=True)
    collected_at = Column(DateTime, default=datetime.now)

    company = relationship("CompanyInfo", back_populates="releases")


class Dispatch(Base):
    __tablename__ = "dispatch"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label_code = Column(String(9), nullable=True)
    company_id = Column(Integer, ForeignKey("company_info.id"), nullable=False)
    dispatch_type = Column(String(20), nullable=False, default="export")
    source_report_id = Column(String(100), nullable=True)
    origin_port = Column(String(50), nullable=True)
    destination = Column(String(20), default="인천항")
    cargo_detail = Column(String(200), nullable=True)
    weight_kg = Column(DECIMAL(8, 1), nullable=True)
    due_date = Column(Date, nullable=True)
    pickup_date = Column(Date, nullable=True)
    logistics_delivery_id = Column(Integer, nullable=True)
    logistics_driver_id = Column(Integer, nullable=True)
    driver_name = Column(String(50), nullable=True)
    logistics_vehicle_id = Column(Integer, nullable=True)
    vehicle_plate = Column(String(20), nullable=True)
    empty_return = Column(String(100), nullable=True)
    logistics_message = Column(Text, nullable=True)
    status = Column(String(20), default="대기")
    created_at = Column(DateTime, default=datetime.now)

    company = relationship("CompanyInfo", back_populates="dispatches")


class InsightLog(Base):
    __tablename__ = "insight_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insight_type = Column(String(50))
    content = Column(Text)
    related_code = Column(String(9), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class AgentReport(Base):
    __tablename__ = "agent_report"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("company_info.id"), nullable=False)
    company_name = Column(String(100))
    report_type = Column(String(20))
    item = Column(String(100), nullable=True)
    qty = Column(Integer, nullable=True)
    start_at = Column(String(30), nullable=True)
    estimated_completion = Column(String(30), nullable=True)
    status = Column(String(20), nullable=True)
    reason = Column(String(200), nullable=True)
    material = Column(String(50), nullable=True)
    arrival_date = Column(String(20), nullable=True)
    bl_number = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class ReportMessage(Base):
    __tablename__ = "report_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(20), nullable=False)
    direction = Column(String(20), nullable=False)
    source_agent = Column(String(50), nullable=False)
    target_agent = Column(String(50), nullable=False)
    event_type = Column(String(50), nullable=False)
    related_code = Column(String(100), nullable=True)
    title = Column(String(100), nullable=False)
    summary = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)
    status = Column(String(20), nullable=True)
    source_report_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class PackingList(Base):
    __tablename__ = "packing_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collected_release_id = Column(Integer, ForeignKey("collected_release.id"), nullable=True)
    company_id = Column(Integer, ForeignKey("company_info.id"), nullable=True)
    label_code = Column(String(9), nullable=True)
    report_batch_due_date = Column(Date, nullable=True)
    filename = Column(String(200), nullable=True)
    content_type = Column(String(50), nullable=True)
    period_from = Column(Date, nullable=True)
    period_to = Column(Date, nullable=True)
    total_qty = Column(Integer, nullable=True)
    total_weight_kg = Column(DECIMAL(10, 3), nullable=True)
    label_code_count = Column(Integer, nullable=True)
    csv_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class LogisticsDriverCache(Base):
    __tablename__ = "logistics_driver_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(50), nullable=True)
    phone = Column(String(20), nullable=True)
    location_si = Column(String(20), nullable=True)
    location_gu = Column(String(20), nullable=True)
    base_region = Column(String(20), nullable=True)
    vehicle_type = Column(String(30), nullable=True)
    vehicle_id = Column(Integer, nullable=True)
    vehicle_plate = Column(String(20), nullable=True)
    vehicle_max_weight = Column(DECIMAL(8, 1), nullable=True)
    status = Column(String(20), nullable=True)
    current_delivery_id = Column(Integer, nullable=True)
    current_destination = Column(String(50), nullable=True)
    estimated_arrival = Column(Date, nullable=True)
    last_synced_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
