VALID_MATERIALS   = {"WOOD", "PLASTIC", "METAL"}
VALID_COLORS      = {"BK", "WH", "NV", "GY", "BR", "SV"}
VALID_ZIPPER_SIZES = {"S", "M", "L"}

MATERIAL_LABEL = {"WOOD": "원목단추", "PLASTIC": "플라스틱단추", "METAL": "금속단추"}
COLOR_LABEL    = {"BK": "블랙", "WH": "화이트", "NV": "네이비", "GY": "그레이", "BR": "브라운", "SV": "실버"}
SIZE_LABEL     = {"S": "소형", "M": "중형", "L": "대형"}


def validate_item_code(item_name: str) -> tuple[bool, str]:
    if not item_name:
        return False, "품목코드를 입력하세요"

    parts = item_name.strip().upper().split("_")

    if parts[0] == "ZIPPER":
        if len(parts) != 2 or parts[1] not in VALID_ZIPPER_SIZES:
            return False, f"지퍼 코드 형식 오류 (ZIPPER_S / ZIPPER_M / ZIPPER_L)"
        return True, f"✅ 지퍼 {SIZE_LABEL[parts[1]]}"

    if len(parts) != 2:
        return False, "단추 코드 형식 오류 (소재코드_컬러코드)"

    material, color = parts
    if material not in VALID_MATERIALS:
        return False, f"소재코드 오류: {material} (WOOD / PLASTIC / METAL)"
    if color not in VALID_COLORS:
        return False, f"컬러코드 오류: {color} (BK / WH / NV / GY / BR / SV)"

    return True, f"✅ {MATERIAL_LABEL[material]} {COLOR_LABEL[color]}"


def item_name_to_label(item_name: str) -> str:
    """WOOD_BR → '원목단추 브라운' 형태로 변환"""
    ok, msg = validate_item_code(item_name)
    if ok:
        return msg.replace("✅ ", "")
    return item_name


def item_name_to_type(item_name: str) -> str:
    """WOOD_BR → '원목단추', ZIPPER_M → '지퍼' 변환"""
    parts = item_name.strip().upper().split("_")
    if parts[0] == "ZIPPER":
        return "지퍼"
    return MATERIAL_LABEL.get(parts[0], item_name)
