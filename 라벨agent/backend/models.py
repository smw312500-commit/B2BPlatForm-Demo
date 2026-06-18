from sqlalchemy import Column, Date, DateTime, DECIMAL, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base
from services.weight_logic import (
    calculate_fabric_weight_kg_for_release,
    calculate_ink_weight_kg_for_release,
    calculate_material_weight_kg_for_release,
    calculate_label_weight_kg,
    calculate_order_weight_kg,
    calculate_stock_weight_kg,
)


class LabelStock(Base):
    __tablename__ = "label_stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_name = Column(String(50), nullable=False)
    unit = Column(String(10), nullable=False)
    stock_qty = Column(DECIMAL(10, 1), nullable=False, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def weight_kg(self) -> float | None:
        return calculate_stock_weight_kg(self.material_name, float(self.stock_qty or 0))


class LabelOrder(Base):
    __tablename__ = "label_order"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_name = Column(String(50), nullable=False)
    order_qty = Column(DECIMAL(10, 1), nullable=False)
    supplier = Column(String(100), nullable=True)
    order_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="대기중")
    note = Column(Text, nullable=True)

    @property
    def weight_kg(self) -> float | None:
        return calculate_order_weight_kg(self.material_name, float(self.order_qty or 0))


class LabelRelease(Base):
    __tablename__ = "label_release"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label_code = Column(String(9), nullable=False)
    release_qty = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="생산중")
    release_date = Column(Date, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    @property
    def product_weight_kg(self) -> float:
        return calculate_label_weight_kg(self.release_qty or 0)

    @property
    def fabric_weight_kg(self) -> float:
        return calculate_fabric_weight_kg_for_release(self.release_qty or 0)

    @property
    def ink_weight_kg(self) -> float:
        return calculate_ink_weight_kg_for_release(self.release_qty or 0)

    @property
    def material_weight_kg(self) -> float:
        return calculate_material_weight_kg_for_release(self.release_qty or 0)


class LabelMachine(Base):
    __tablename__ = "label_machine"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="대기중")
    release_id = Column(Integer, nullable=True)
    label_code = Column(String(9), nullable=True)
    total_qty = Column(Integer, nullable=False, default=0)
    produced_qty = Column(DECIMAL(10, 1), nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    running_started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LabelMachineQueue(Base):
    __tablename__ = "label_machine_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(Integer, ForeignKey("label_machine.id"), nullable=False, index=True)
    release_id = Column(Integer, ForeignKey("label_release.id"), nullable=False, unique=True)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class LabelPlatformReportEvent(Base):
    __tablename__ = "label_platform_report_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_type = Column(String(30), nullable=False)
    report_type_label = Column(String(50), nullable=False)
    item_ref = Column(String(100), nullable=False)
    path = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False, default="전송중")
    message = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)
    report_id = Column(String(50), nullable=True, index=True)
    channel_message_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LabelPlatformReportMessage(Base):
    __tablename__ = "label_platform_report_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("label_platform_report_event.id"), nullable=True, index=True)
    direction = Column(String(20), nullable=False)
    sender = Column(String(50), nullable=False)
    receiver = Column(String(50), nullable=False)
    report_type = Column(String(30), nullable=False)
    report_type_label = Column(String(50), nullable=False)
    item_ref = Column(String(100), nullable=False)
    path = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False)
    summary = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)
    report_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
