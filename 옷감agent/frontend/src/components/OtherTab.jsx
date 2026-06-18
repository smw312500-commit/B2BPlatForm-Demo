import React from 'react';

const PRODUCTION_RULES = [
  { code: 'C', name: '면(Cotton)',      speed: 8,  safe: 500,  yarn: 3.0 },
  { code: 'P', name: '폴리에스터',      speed: 15, safe: 300,  yarn: 5.0 },
  { code: 'L', name: '린넨(Linen)',     speed: 5,  safe: 200,  yarn: 2.5 },
  { code: 'W', name: '울(Wool)',        speed: 4,  safe: 150,  yarn: 2.0 },
  { code: 'M', name: '혼방(Mixed)',     speed: 10, safe: 250,  yarn: 3.5 },
];

export default function OtherTab() {
  return (
    <div>
      <div className="section-title">생산 설정값 (읽기 전용)</div>
      <p style={{ fontSize: 12, color: '#6b7280', marginBottom: 16 }}>
        기계: 직조기 5대 / 일일 가동시간: 9시간 (09:00~18:00)
      </p>

      <div className="table-wrap" style={{ marginBottom: 24 }}>
        <table>
          <thead>
            <tr>
              <th>코드</th>
              <th>원단명</th>
              <th>시간당 생산량 (야드/h × 1대)</th>
              <th>최대 일일 생산량 (야드)</th>
              <th>원사 변환비율 (1kg → 야드)</th>
              <th>안전 재고 (야드)</th>
            </tr>
          </thead>
          <tbody>
            {PRODUCTION_RULES.map(r => (
              <tr key={r.code}>
                <td style={{ fontWeight: 700 }}>{r.code}</td>
                <td>{r.name}</td>
                <td>{r.speed} 야드/h</td>
                <td>{(r.speed * 5 * 9).toLocaleString()} 야드</td>
                <td>{r.yarn} 야드</td>
                <td>{r.safe.toLocaleString()} 야드</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-title">AI Agent 계산 공식</div>
      <div style={{ background: '#fff', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 2, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
        <div><strong>소요시간(h)</strong> = 주문량(야드) ÷ (직조기 5대 × 원단별 시간당 생산량)</div>
        <div><strong>납기 가능일수</strong> = 소요시간 ÷ 9시간 (소수점 올림)</div>
        <div><strong>필요 원사(kg)</strong> = 주문량(야드) ÷ 원사 변환비율 (소수점 올림)</div>
        <div style={{ marginTop: 8, color: '#6b7280', fontSize: 12 }}>
          ✅ 납기 가능: 남은 일수 ≥ 납기 가능일수<br/>
          ⚠ 납기 위험: 남은 일수 &lt; 납기 가능일수 + 1<br/>
          ❌ 납기 불가: 남은 일수 &lt; 납기 가능일수
        </div>
      </div>
    </div>
  );
}
