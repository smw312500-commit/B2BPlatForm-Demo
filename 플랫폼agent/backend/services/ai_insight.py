import os
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import CollectedRelease
from openai import AsyncOpenAI


async def generate_insights(db: Session) -> list[dict]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    client = AsyncOpenAI(api_key=api_key)

    cutoff = datetime.now() - timedelta(days=30)
    records = (
        db.query(CollectedRelease)
        .filter(CollectedRelease.collected_at >= cutoff)
        .order_by(CollectedRelease.collected_at.desc())
        .all()
    )

    data_rows = []
    for r in records:
        data_rows.append({
            "company_id": r.company_id,
            "item_name": r.item_name,
            "quantity": float(r.quantity) if r.quantity else 0,
            "unit": r.unit,
            "due_date": str(r.due_date) if r.due_date else None,
            "status": r.status,
            "label_code": r.label_code,
            "collected_at": str(r.collected_at)[:10] if r.collected_at else None,
        })

    prompt = f"""
다음은 B2B 의류 부자재 공급망 플랫폼의 최근 30일 출고 수집 데이터입니다.
회사 ID: 1=옷감사, 2=케어라벨사, 3=지퍼단추사

데이터:
{json.dumps(data_rows, ensure_ascii=False, indent=2)}

아래 3가지 인사이트를 분석해 한국어 JSON 배열로 응답하세요. 반드시 JSON만 출력하세요.

1. 납기위험 감지
   - 같은 label_code인데 일부 회사만 출고완료이고 납기일이 3일 이내인 경우
   - 예: "W3MJW01NV — 옷감 완료, 지퍼 미출고, 납기 D-2 위험"

2. 패션 트렌드 추론
   - 원목단추(item_name에 "원목" 포함) 출고 증가 → 프리미엄 셔츠 수요
   - 폴리에스터+다운(label_code 4번째 D, 원단코드 P) 동시 급증 → 아웃도어 시즌
   - 울+재킷(label_code 5번째 W, 4번째 J) 급증 → 고급 울재킷 강세

3. 물류 최적화
   - dispatch 대기 건 중 출발지 같거나 경로 겹치는 건 묶음 배송 제안

응답 형식 (반드시 이 JSON 배열만 출력):
[
  {{"type": "납기위험", "content": "...", "related_code": "W3MJW01NV"}},
  {{"type": "트렌드", "content": "...", "related_code": null}},
  {{"type": "물류최적화", "content": "...", "related_code": null}}
]
"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content.strip()
    # JSON 블록 추출
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        results = json.loads(raw)
        return results if isinstance(results, list) else []
    except json.JSONDecodeError:
        return [{"type": "오류", "content": f"인사이트 파싱 실패: {raw[:200]}", "related_code": None}]
