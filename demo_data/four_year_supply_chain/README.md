# Four Year Supply Chain Demo Data

기간: 2023-01-01 ~ 2026-12-31

목적:
- 총 의류 6,000,000장 규모의 4년치 시연 데이터
- 1~2년차는 정상 운영, 3년차는 자재 공급 지연 시작, 4년차는 자재 지연 + 생산성 저하가 확실하게 드러나도록 설계
- AI 인사이트 / 분석 페이지에서 공급사 변경, 선발주, 생산성 개선, 물류 전략 제안을 만들기 위한 근거 데이터

파일:
- material_receipts.csv: 분기별 원자재 발주/납기/실제입고/공급사/지연일
- material_receipts.csv 안의 round_trip_candidate=Y 10건: 수출 납기일 D-0~D-2에 같은 항구로 도착한 귀로매칭 시연용 BL
- production_batches.csv: 생산사별 생산시작/완료/납기/납기여유일
- finished_shipments.csv: 월 3~4회 출고묶음과 패킹리스트 성격의 생산품 구성
- logistics_performance.csv: 물류 배차 요청/확정/배송 지연
- logistics_snapshots.csv: 월별 기사/차량 스냅샷
- platform_report_messages.csv/jsonl: 플랫폼 report_message 적재용 보고 이벤트
- dataset_summary.json: 의도된 패턴과 요약 통계

무게/수량 산식:
- 라벨agent: 완제품 라벨 1,000장 = 1kg, 라벨원단 1m = 25장 생산분, 잉크 1통 = 10,000장 생산분, 잉크 10통 = 1kg
- 옷감agent: 출고 원단 1야드 = 0.3kg, 원사 1kg당 생산량은 C 3.0야드 / P 5.0야드 / L 2.5야드 / W 2.0야드 / M 3.5야드
- 지퍼단추agent: 출고품은 개당 5g, 플라스틱단추 200개/kg, 금속단추 150개/kg, 지퍼 1개당 지퍼테이프 1m
- 플랫폼 label 채널의 shipment_total_weight_kg는 라벨사 출고중량만 의미한다. 옷감/지퍼단추 중량은 fabric_weight_kg, zipper_button_weight_kg로 분리한다.

플랫폼 DB 적재:
- dry-run: `python 플랫폼agent/backend/seed_four_year_demo.py`
- 실제 적재: `python 플랫폼agent/backend/seed_four_year_demo.py --apply`
- 기존 demo report_id(`demo-*`) 행 정리 후 재적재: `python 플랫폼agent/backend/seed_four_year_demo.py --apply --reset-demo`

중요 판단 기준:
- 원자재는 분기 1회 입고이므로 3~7일 지연은 정상 변동으로 본다.
- 21일 이상 지연이 반복될 때 공급사 문제 후보로 본다.
- 2025년부터 일부 공급사의 21일 이상 지연이 발생한다.
- 2026년에는 21~45일 지연과 생산 납기 여유일 0~5일/일부 지연이 함께 발생한다.
- 올해 출고/판매 흐름은 전년도 생산 데이터의 선행 신호로 해석한다.
- 귀로매칭 시연용 BL은 항구 무료보관 2일을 반영해 수출 납기일이 수입 도착일~도착일+2일 사이에 들어오도록 설계한다.
