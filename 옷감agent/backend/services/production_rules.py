"""
옷감회사 생산판단 공통 상수/규칙 (생산규칙.txt, AI_로직.txt 기준)
agent.py / ai_status.py / platform_reporter.py 에서 공통으로 사용한다.
"""
import math

# 생산속도 (야드/시간/대)
PRODUCTION_SPEED = {"C": 8, "P": 15, "L": 5, "W": 4, "M": 10}

# 원사 소요량 비율 (야드당 kg)
YARN_RATIO = {"C": 3.0, "P": 5.0, "L": 2.5, "W": 2.0, "M": 3.5}

# 원단코드 → 원단명
FABRIC_NAMES = {"C": "면", "P": "폴리에스터", "L": "린넨", "W": "울", "M": "혼방"}

# 안전재고 (야드)
SAFE_STOCK = {"C": 500, "P": 300, "L": 200, "W": 150, "M": 250}

MACHINES = 5       # 직기 5대
DAILY_HOURS = 9    # 1일 가동시간 (09:00~18:00)


def calc_required_days(fabric_code: str, qty: float) -> float:
    speed = PRODUCTION_SPEED.get(fabric_code, 8)
    hours = qty / (MACHINES * speed)
    days = hours / DAILY_HOURS
    return math.ceil(days * 10) / 10


def calc_required_hours(fabric_code: str, qty: float) -> float:
    speed = PRODUCTION_SPEED.get(fabric_code, 8)
    return round(qty / (MACHINES * speed), 1)


def calc_deadline_status(days_left: float, required_days: float) -> str:
    """AI_로직.txt 기준: 납기가능/납기위험/납기불가 판정"""
    if days_left < required_days:
        return "납기불가"
    elif days_left < required_days + 1:
        return "납기위험"
    return "납기가능"
