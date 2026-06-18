from sqlalchemy import Column, Integer, String, Date, DateTime, Text, DECIMAL, ForeignKey
from sqlalchemy.sql import func
from database import Base


class ZipperStock(Base):
    __tablename__ = "zipper_stock"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    material_name = Column(String(50), nullable=False)   # 원목 / 플라스틱원료 / 금속원료 / 지퍼테이프
    unit          = Column(String(10), nullable=False)   # kg / m
    stock_qty     = Column(DECIMAL(10, 1), nullable=False, default=0)
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ZipperOrder(Base):
    __tablename__ = "zipper_order"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    material_name = Column(String(50), nullable=False)
    order_qty     = Column(DECIMAL(10, 1), nullable=False)
    supplier      = Column(String(100), nullable=True)
    order_date    = Column(Date, nullable=False)
    due_date      = Column(Date, nullable=False)
    status        = Column(String(20), nullable=False, default="대기중")  # 대기중/입고완료/취소
    note          = Column(Text, nullable=True)


class ZipperRelease(Base):
    __tablename__ = "zipper_release"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    item_name   = Column(String(50), nullable=False)     # 품목코드 예: WOOD_BR, ZIPPER_M
    release_qty = Column(Integer, nullable=False)
    due_date    = Column(Date, nullable=False)
    label_code  = Column(String(9), nullable=True)       # 연동 라벨코드 (선택)
    status      = Column(String(20), nullable=False, default="생산중")  # 생산중/출고완료
    release_date = Column(Date, nullable=True)
    started_at  = Column(DateTime, nullable=True)        # 생산 시작 시간
    finished_at = Column(DateTime, nullable=True)        # 생산 완료 시간
    created_at  = Column(DateTime, server_default=func.now())


class ZipperPlatformReportEvent(Base):
    """플랫폼 보고 이벤트(전송 상태 추적용) — [2026-06-11] 표준 규격: report_id 기반 재시도/dedupe"""
    __tablename__ = "zipper_platform_report_event"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    report_type   = Column(String(30), nullable=False)   # schedule/reschedule/import/release
    report_type_label = Column(String(50), nullable=False)
    item_ref      = Column(String(100), nullable=False)
    path          = Column(String(120), nullable=True)
    status        = Column(String(30), nullable=False, default="전송중")  # 전송중/전송완료/플랫폼 보고 대기
    message       = Column(Text, nullable=False)
    payload_json  = Column(Text, nullable=True)
    report_id     = Column(String(50), nullable=True, index=True)
    channel_message_id = Column(Integer, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ZipperPlatformReportMessage(Base):
    """플랫폼 보고 채널 채팅형 메시지 — agent ↔ 플랫폼agent 송수신 이력"""
    __tablename__ = "zipper_platform_report_message"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    event_id      = Column(Integer, ForeignKey("zipper_platform_report_event.id"), nullable=True, index=True)
    direction     = Column(String(20), nullable=False)   # outbound/inbound
    sender        = Column(String(50), nullable=False)
    receiver      = Column(String(50), nullable=False)
    report_type   = Column(String(30), nullable=False)
    report_type_label = Column(String(50), nullable=False)
    item_ref      = Column(String(100), nullable=False)
    path          = Column(String(120), nullable=True)
    status        = Column(String(30), nullable=False)
    summary       = Column(Text, nullable=False)
    payload_json  = Column(Text, nullable=True)
    report_id     = Column(String(50), nullable=True, index=True)
    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())
