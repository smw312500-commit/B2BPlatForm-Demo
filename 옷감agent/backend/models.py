from sqlalchemy import Column, ForeignKey, Integer, String, Numeric, Date, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class FabricStock(Base):
    __tablename__ = "fabric_stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fabric_code = Column(String(1), nullable=False)   # C/P/L/W/M
    color_code = Column(String(2), nullable=False)    # BK/WH/NV/GY/BE/RD
    stock_qty = Column(Numeric(10, 1), nullable=False, default=0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class FabricOrder(Base):
    __tablename__ = "fabric_order"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_name = Column(String(50), nullable=False)   # 원사 종류
    order_qty = Column(Numeric(10, 1), nullable=False)   # 발주량 (kg)
    supplier = Column(String(100), nullable=False)
    order_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="대기중")  # 대기중/입고완료/취소
    note = Column(Text)


class FabricRelease(Base):
    __tablename__ = "fabric_release"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label_code = Column(String(9), nullable=False)      # 연동 라벨코드
    fabric_code = Column(String(1), nullable=False)     # C/P/L/W/M
    color_code = Column(String(2), nullable=False)
    release_qty = Column(Numeric(10, 1), nullable=False)  # 출고량 (야드)
    due_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="생산중")  # 생산중/출고완료
    release_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=func.now())


class FabricProduction(Base):
    __tablename__ = "fabric_production"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fabric_code = Column(String(1), nullable=False)       # C/P/L/W/M
    color_code = Column(String(2), nullable=False)        # BK/WH/NV 등
    quantity = Column(Numeric(10, 1), nullable=False)     # 생산량 (야드)
    stage = Column(String(20), nullable=False, default="원사입고")
    # 원사입고 → 정경·제직 → 염색 → 가공 → 검품 → 완성
    target_date = Column(Date, nullable=False)
    worker = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=func.now())
    updated_at   = Column(DateTime, default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)


# ── 플랫폼 보고 채널 (보고 이벤트 / 채팅형 타임라인) ──────────────────
class FabricPlatformReportEvent(Base):
    __tablename__ = "fabric_platform_report_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_type       = Column(String(30), nullable=False)   # schedule/reschedule/import/release
    report_type_label = Column(String(50), nullable=False)
    item_ref          = Column(String(100), nullable=False)
    path              = Column(String(120), nullable=True)
    status            = Column(String(30), nullable=False, default="전송중")
    # 전송중 / 전송완료 / 플랫폼 보고 대기
    message           = Column(Text, nullable=False)
    payload_json      = Column(Text, nullable=True)
    report_id         = Column(String(50), nullable=True, index=True)
    channel_message_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class FabricPlatformReportMessage(Base):
    __tablename__ = "fabric_platform_report_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("fabric_platform_report_event.id"), nullable=True, index=True)
    direction = Column(String(20), nullable=False)   # outbound(옷감agent→플랫폼) / inbound(플랫폼→옷감agent)
    sender    = Column(String(50), nullable=False)
    receiver  = Column(String(50), nullable=False)
    report_type       = Column(String(30), nullable=False)
    report_type_label = Column(String(50), nullable=False)
    item_ref = Column(String(100), nullable=False)
    path     = Column(String(120), nullable=True)
    status   = Column(String(30), nullable=False)
    summary  = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)
    report_id    = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
