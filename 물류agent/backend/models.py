from sqlalchemy import Column, Integer, String, Date, DateTime, DECIMAL, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Driver(Base):
    __tablename__ = "driver"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    phone = Column(String(20))
    location_si = Column(String(20))
    location_gu = Column(String(20))
    base_region = Column(String(20))
    status = Column(String(20), default="가용")  # 가용/운행중/휴무

    vehicles = relationship("Vehicle", back_populates="driver")
    deliveries = relationship("Delivery", back_populates="driver")


class Vehicle(Base):
    __tablename__ = "vehicle"

    id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(Integer, ForeignKey("driver.id"))
    plate_no = Column(String(20), nullable=False)
    max_weight = Column(DECIMAL(8, 1))
    vehicle_type = Column(String(30))

    driver = relationship("Driver", back_populates="vehicles")
    deliveries = relationship("Delivery", back_populates="vehicle")


class Delivery(Base):
    __tablename__ = "delivery"

    id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(Integer, ForeignKey("driver.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicle.id"))
    company_id = Column(Integer)
    company_name = Column(String(100))
    origin_si = Column(String(20))
    origin_gu = Column(String(20))
    destination = Column(String(20))  # 인천항/부산항
    cargo_detail = Column(Text)
    weight_kg = Column(DECIMAL(8, 1))
    due_date = Column(Date)
    pickup_date = Column(Date)
    complete_date = Column(Date)
    status = Column(String(20), default="배차대기")  # 배차대기/운행중/완료
    empty_return = Column(String(100), default="미정")  # 빈차귀환/연결완료/미정
    created_at = Column(DateTime, server_default=func.now())

    driver = relationship("Driver", back_populates="deliveries")
    vehicle = relationship("Vehicle", back_populates="deliveries")


class PlatformChannelMessage(Base):
    __tablename__ = "platform_channel_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    direction = Column(String(20), nullable=False)  # inbound / outbound
    event_type = Column(String(50), nullable=False)
    title = Column(String(100), nullable=False)
    summary = Column(Text, nullable=False)
    status = Column(String(40), nullable=False)
    related_delivery_id = Column(Integer)
    payload_json = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
