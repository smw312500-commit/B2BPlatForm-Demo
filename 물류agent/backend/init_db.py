from database import engine, Base, SessionLocal, ensure_schema_updates
from models import Driver, Vehicle

Base.metadata.create_all(bind=engine)
ensure_schema_updates()

SAMPLE_DRIVERS = [
    {"name": "김철수", "phone": "010-1122-3344", "location_si": "부산시", "location_gu": "사하구", "base_region": "부산권", "status": "가용", "vehicle": {"plate_no": "12가 3456", "max_weight": 5000, "vehicle_type": "5톤 트럭"}},
    {"name": "이민호", "phone": "010-2233-4455", "location_si": "부산시", "location_gu": "강서구", "base_region": "부산권", "status": "가용", "vehicle": {"plate_no": "34나 5678", "max_weight": 8000, "vehicle_type": "탑차"}},
    {"name": "박준혁", "phone": "010-3344-5566", "location_si": "부산시", "location_gu": "북구", "base_region": "부산권", "status": "운행중", "vehicle": {"plate_no": "56다 7890", "max_weight": 11000, "vehicle_type": "11톤 트럭"}},
    {"name": "최성훈", "phone": "010-4455-6677", "location_si": "부산시", "location_gu": "사상구", "base_region": "부산권", "status": "가용", "vehicle": {"plate_no": "78라 1234", "max_weight": 3000, "vehicle_type": "탑차"}},
    {"name": "정대한", "phone": "010-5566-7788", "location_si": "부산시", "location_gu": "기장군", "base_region": "부산권", "status": "가용", "vehicle": {"plate_no": "90마 2345", "max_weight": 25000, "vehicle_type": "25톤 트럭"}},
    {"name": "강민수", "phone": "010-6677-8899", "location_si": "부산시", "location_gu": "해운대구", "base_region": "부산권", "status": "운행중", "vehicle": {"plate_no": "11바 3456", "max_weight": 5000, "vehicle_type": "5톤 트럭"}},
    {"name": "윤상철", "phone": "010-7788-9900", "location_si": "부산시", "location_gu": "서구", "base_region": "부산권", "status": "가용", "vehicle": {"plate_no": "22사 4567", "max_weight": 8000, "vehicle_type": "화물차"}},
    {"name": "한기범", "phone": "010-8899-0011", "location_si": "부산시", "location_gu": "영도구", "base_region": "부산권", "status": "휴무", "vehicle": {"plate_no": "33아 5678", "max_weight": 3000, "vehicle_type": "탑차"}},
    {"name": "조현우", "phone": "010-9900-1122", "location_si": "부산시", "location_gu": "동래구", "base_region": "부산권", "status": "가용", "vehicle": {"plate_no": "44자 6789", "max_weight": 11000, "vehicle_type": "11톤 트럭"}},
    {"name": "오동훈", "phone": "010-1234-2345", "location_si": "서울시", "location_gu": "금천구", "base_region": "수도권", "status": "가용", "vehicle": {"plate_no": "55차 7890", "max_weight": 5000, "vehicle_type": "5톤 트럭"}},
    {"name": "임재현", "phone": "010-2345-3456", "location_si": "서울시", "location_gu": "강서구", "base_region": "수도권", "status": "가용", "vehicle": {"plate_no": "66카 8901", "max_weight": 8000, "vehicle_type": "탑차"}},
    {"name": "신동엽", "phone": "010-3456-4567", "location_si": "서울시", "location_gu": "구로구", "base_region": "수도권", "status": "운행중", "vehicle": {"plate_no": "77타 9012", "max_weight": 3000, "vehicle_type": "화물차"}},
    {"name": "권혁준", "phone": "010-4567-5678", "location_si": "서울시", "location_gu": "영등포구", "base_region": "수도권", "status": "가용", "vehicle": {"plate_no": "88파 0123", "max_weight": 11000, "vehicle_type": "11톤 트럭"}},
    {"name": "류민호", "phone": "010-5678-6789", "location_si": "서울시", "location_gu": "관악구", "base_region": "수도권", "status": "가용", "vehicle": {"plate_no": "99하 1234", "max_weight": 5000, "vehicle_type": "5톤 트럭"}},
    {"name": "황성진", "phone": "010-6789-7890", "location_si": "서울시", "location_gu": "양천구", "base_region": "수도권", "status": "휴무", "vehicle": {"plate_no": "00거 2345", "max_weight": 8000, "vehicle_type": "탑차"}},
    {"name": "송재원", "phone": "010-1111-2222", "location_si": "인천시", "location_gu": "중구", "base_region": "인천권", "status": "가용", "vehicle": {"plate_no": "11너 3456", "max_weight": 5000, "vehicle_type": "5톤 트럭"}},
    {"name": "배성민", "phone": "010-2222-3333", "location_si": "인천시", "location_gu": "연수구", "base_region": "인천권", "status": "가용", "vehicle": {"plate_no": "22더 4567", "max_weight": 8000, "vehicle_type": "탑차"}},
    {"name": "문태영", "phone": "010-3333-4444", "location_si": "인천시", "location_gu": "남동구", "base_region": "인천권", "status": "운행중", "vehicle": {"plate_no": "33러 5678", "max_weight": 11000, "vehicle_type": "11톤 트럭"}},
    {"name": "노진혁", "phone": "010-4444-5555", "location_si": "인천시", "location_gu": "서구", "base_region": "인천권", "status": "가용", "vehicle": {"plate_no": "44머 6789", "max_weight": 3000, "vehicle_type": "화물차"}},
    {"name": "양승현", "phone": "010-5555-6666", "location_si": "인천시", "location_gu": "부평구", "base_region": "인천권", "status": "가용", "vehicle": {"plate_no": "55버 7890", "max_weight": 5000, "vehicle_type": "5톤 트럭"}},
    {"name": "서준호", "phone": "010-6111-7101", "location_si": "부산시", "location_gu": "남구", "base_region": "부산권", "status": "가용", "vehicle": {"plate_no": "61소 1111", "max_weight": 14000, "vehicle_type": "14톤 윙바디"}},
    {"name": "장민혁", "phone": "010-6222-7202", "location_si": "부산시", "location_gu": "금정구", "base_region": "부산권", "status": "운행중", "vehicle": {"plate_no": "62오 2222", "max_weight": 25000, "vehicle_type": "25톤 카고"}},
    {"name": "백도윤", "phone": "010-6333-7303", "location_si": "서울시", "location_gu": "송파구", "base_region": "수도권", "status": "가용", "vehicle": {"plate_no": "63조 3333", "max_weight": 1000, "vehicle_type": "1톤 냉동탑차"}},
    {"name": "민건우", "phone": "010-6444-7404", "location_si": "서울시", "location_gu": "강동구", "base_region": "수도권", "status": "휴무", "vehicle": {"plate_no": "64초 4444", "max_weight": 3500, "vehicle_type": "3.5톤 윙바디"}},
    {"name": "차우석", "phone": "010-6555-7505", "location_si": "인천시", "location_gu": "동구", "base_region": "인천권", "status": "가용", "vehicle": {"plate_no": "65코 5555", "max_weight": 18000, "vehicle_type": "18톤 카고"}},
    {"name": "유태민", "phone": "010-6666-7606", "location_si": "인천시", "location_gu": "계양구", "base_region": "인천권", "status": "운행중", "vehicle": {"plate_no": "66투 6666", "max_weight": 5000, "vehicle_type": "5톤 냉동탑차"}},
    {"name": "홍시우", "phone": "010-6777-7707", "location_si": "대전시", "location_gu": "대덕구", "base_region": "중부권", "status": "가용", "vehicle": {"plate_no": "67포 7777", "max_weight": 11000, "vehicle_type": "11톤 윙바디"}},
    {"name": "남현준", "phone": "010-6888-7808", "location_si": "대구시", "location_gu": "달서구", "base_region": "영남권", "status": "가용", "vehicle": {"plate_no": "68후 8888", "max_weight": 8000, "vehicle_type": "8톤 카고"}},
    {"name": "심도현", "phone": "010-6999-7909", "location_si": "광주시", "location_gu": "광산구", "base_region": "호남권", "status": "휴무", "vehicle": {"plate_no": "69구 9999", "max_weight": 3000, "vehicle_type": "3톤 탑차"}},
    {"name": "진예찬", "phone": "010-7000-8010", "location_si": "울산시", "location_gu": "남구", "base_region": "영남권", "status": "가용", "vehicle": {"plate_no": "70누 1010", "max_weight": 25000, "vehicle_type": "25톤 트랙터"}},
]


def seed():
    db = SessionLocal()
    try:
        existing_drivers = db.query(Driver).all()
        drivers_by_phone = {driver.phone: driver for driver in existing_drivers if driver.phone}
        vehicles = db.query(Vehicle).all()
        vehicles_by_plate = {vehicle.plate_no: vehicle for vehicle in vehicles if vehicle.plate_no}

        created_drivers = 0
        created_vehicles = 0

        for sample in SAMPLE_DRIVERS:
            driver = drivers_by_phone.get(sample["phone"])
            if driver is None:
                driver = Driver(
                    name=sample["name"],
                    phone=sample["phone"],
                    location_si=sample["location_si"],
                    location_gu=sample["location_gu"],
                    base_region=sample["base_region"],
                    status=sample["status"],
                )
                db.add(driver)
                db.flush()
                drivers_by_phone[driver.phone] = driver
                created_drivers += 1
            else:
                driver.name = sample["name"]
                driver.location_si = sample["location_si"]
                driver.location_gu = sample["location_gu"]
                driver.base_region = sample["base_region"]
                if not driver.status:
                    driver.status = sample["status"]

            vehicle_sample = sample["vehicle"]
            vehicle = vehicles_by_plate.get(vehicle_sample["plate_no"])
            if vehicle is None:
                vehicle = Vehicle(
                    driver_id=driver.id,
                    plate_no=vehicle_sample["plate_no"],
                    max_weight=vehicle_sample["max_weight"],
                    vehicle_type=vehicle_sample["vehicle_type"],
                )
                db.add(vehicle)
                db.flush()
                vehicles_by_plate[vehicle.plate_no] = vehicle
                created_vehicles += 1
            else:
                vehicle.driver_id = driver.id
                vehicle.max_weight = vehicle_sample["max_weight"]
                vehicle.vehicle_type = vehicle_sample["vehicle_type"]

        for driver in db.query(Driver).all():
            if not driver.base_region:
                driver.base_region = driver.location_si or "미지정"

        db.commit()
        print(f"기사 샘플 {len(SAMPLE_DRIVERS)}명 기준 동기화 완료")
        print(f"  신규 기사 {created_drivers}명 / 신규 차량 {created_vehicles}대")
        print(f"  현재 DB 기사 {db.query(Driver).count()}명 / 차량 {db.query(Vehicle).count()}대")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
