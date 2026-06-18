from __future__ import annotations

import os
from typing import Any

import httpx
from sqlalchemy.orm import Session

from models import Delivery, Driver, Vehicle

PLATFORM_API_URL = os.getenv("PLATFORM_API_URL", "http://localhost:8000")


def _find_primary_vehicle(driver: Driver) -> Vehicle | None:
    if not driver.vehicles:
        return None
    return sorted(driver.vehicles, key=lambda current: current.id or 0)[0]


def _find_current_delivery(driver: Driver) -> Delivery | None:
    active = [delivery for delivery in driver.deliveries if delivery.status != "완료"]
    if not active:
        return None

    def _sort_key(delivery: Delivery):
        return (
            str(delivery.pickup_date or ""),
            str(delivery.due_date or ""),
            delivery.id or 0,
        )

    return sorted(active, key=_sort_key, reverse=True)[0]


def build_driver_sync_payload(db: Session) -> dict[str, Any]:
    drivers = db.query(Driver).all()
    payload_drivers: list[dict[str, Any]] = []

    available_count = 0
    driving_count = 0
    off_count = 0
    linked_vehicle_count = 0

    for driver in drivers:
        vehicle = _find_primary_vehicle(driver)
        current_delivery = _find_current_delivery(driver)

        if driver.status == "가용":
            available_count += 1
        elif driver.status == "운행중":
            driving_count += 1
        elif driver.status == "휴무":
            off_count += 1

        if vehicle:
            linked_vehicle_count += 1

        payload_drivers.append({
            "driver_id": driver.id,
            "name": driver.name,
            "phone": driver.phone,
            "location_si": driver.location_si or driver.base_region,
            "vehicle_type": vehicle.vehicle_type if vehicle else None,
            "vehicle_plate": vehicle.plate_no if vehicle else None,
            "status": driver.status,
            "current_delivery_id": current_delivery.id if current_delivery else None,
            "current_destination": current_delivery.destination if current_delivery else None,
            "estimated_arrival": str(current_delivery.due_date or current_delivery.pickup_date) if current_delivery else None,
            "base_region": driver.base_region,
            "location_gu": driver.location_gu,
            "vehicle_id": vehicle.id if vehicle else None,
            "vehicle_max_weight": float(vehicle.max_weight) if vehicle and vehicle.max_weight is not None else None,
        })

    return {
        "drivers": payload_drivers,
        "summary": {
            "driver_count": len(payload_drivers),
            "available_count": available_count,
            "driving_count": driving_count,
            "off_count": off_count,
            "linked_vehicle_count": linked_vehicle_count,
        },
    }


def sync_drivers_to_platform(db: Session) -> dict[str, Any]:
    payload = build_driver_sync_payload(db)
    response_json = None
    delivered = False
    error_message = None

    try:
        with httpx.Client(timeout=8) as client:
            response = client.post(f"{PLATFORM_API_URL}/api/logistics/drivers/sync", json={"drivers": payload["drivers"]})
            response.raise_for_status()
            response_json = response.json()
            delivered = True
    except Exception as exc:
        error_message = str(exc)

    return {
        "success": delivered,
        "count": payload["summary"]["driver_count"],
        "summary": payload["summary"],
        "platform_response": response_json,
        "error": error_message,
    }
