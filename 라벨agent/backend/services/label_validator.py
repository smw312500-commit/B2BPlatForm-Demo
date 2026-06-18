"""
라벨코드 9자리 유효성 검증
구조: 브랜드(1) 계절(1) 성별(1) 품목(1) 원단(1) 스타일(2) 컬러(2)
예)  W         3       M       J       W       01      NV
"""

BRAND_CODES = {"W"}
SEASON_CODES = {"1", "2", "3", "4"}
GENDER_CODES = {"W", "M"}
ITEM_CODES = {"T", "P", "J", "D"}
FABRIC_CODES = {"C", "P", "L", "W", "M"}
COLOR_CODES = {"BK", "WH", "NV", "GY", "BE", "RD"}

SEASON_MAP = {"1": "봄", "2": "여름", "3": "가을", "4": "겨울"}
GENDER_MAP = {"W": "여성", "M": "남성"}
ITEM_MAP = {"T": "티셔츠", "P": "바지", "J": "재킷", "D": "다운"}
FABRIC_MAP = {"C": "면", "P": "폴리에스터", "L": "린넨", "W": "울", "M": "혼방"}
COLOR_MAP = {"BK": "블랙", "WH": "화이트", "NV": "네이비", "GY": "그레이", "BE": "베이지", "RD": "레드"}


def validate_label_code(code: str) -> tuple[bool, str]:
    if not isinstance(code, str):
        return False, "라벨코드는 문자열이어야 합니다"
    if len(code) != 9:
        return False, f"라벨코드는 9자리여야 합니다 (현재: {len(code)}자리)"

    brand = code[0]
    season = code[1]
    gender = code[2]
    item = code[3]
    fabric = code[4]
    style = code[5:7]
    color = code[7:9]

    if brand not in BRAND_CODES:
        return False, f"유효하지 않은 브랜드코드: {brand}"
    if season not in SEASON_CODES:
        return False, f"유효하지 않은 계절코드: {season} (1~4)"
    if gender not in GENDER_CODES:
        return False, f"유효하지 않은 성별코드: {gender} (W/M)"
    if item not in ITEM_CODES:
        return False, f"유효하지 않은 품목코드: {item} (T/P/J/D)"
    if fabric not in FABRIC_CODES:
        return False, f"유효하지 않은 원단코드: {fabric} (C/P/L/W/M)"
    if not style.isdigit() or not (1 <= int(style) <= 99):
        return False, f"유효하지 않은 스타일번호: {style} (01~99)"
    if color not in COLOR_CODES:
        return False, f"유효하지 않은 컬러코드: {color}"

    return True, "유효한 라벨코드"


def parse_label_code(code: str) -> dict:
    return {
        "brand": code[0],
        "season": code[1],
        "season_name": SEASON_MAP.get(code[1], ""),
        "gender": code[2],
        "gender_name": GENDER_MAP.get(code[2], ""),
        "item": code[3],
        "item_name": ITEM_MAP.get(code[3], ""),
        "fabric": code[4],
        "fabric_name": FABRIC_MAP.get(code[4], ""),
        "style": code[5:7],
        "color": code[7:9],
        "color_name": COLOR_MAP.get(code[7:9], ""),
    }
