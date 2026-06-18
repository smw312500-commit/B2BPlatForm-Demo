import React, { useState, useEffect } from 'react';
import { productionApi, releaseApi } from '../api';

const FABRIC_NAMES = { C: '면(Cotton)', P: '폴리에스터', L: '린넨(Linen)', W: '울(Wool)', M: '혼방(Mixed)' };
const COLOR_NAMES  = { BK: '블랙', WH: '화이트', NV: '네이비', GY: '그레이', BE: '베이지', RD: '레드' };

const today = new Date().toISOString().split('T')[0];
const monthStart = today.slice(0, 7) + '-01';

export default function CompletedTab() {
  const [items,   setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [plFrom,  setPlFrom]  = useState(monthStart);
  const [plTo,    setPlTo]    = useState(today);
  const [plLoading, setPlLoading] = useState(false);

  const load = async () => {
    try {
      const res = await productionApi.getCompleted();
      setItems(res.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handlePackingList = async () => {
    if (!plFrom || !plTo) { alert('날짜 범위를 설정하세요.'); return; }
    setPlLoading(true);
    try {
      await releaseApi.downloadPackingList(plFrom, plTo);
    } catch (err) {
      const msg = err.response?.status === 404
        ? '해당 기간에 출고완료 건이 없습니다.'
        : (err.response?.data?.detail || '패킹리스트 생성 실패');
      alert(msg);
    } finally { setPlLoading(false); }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`[${name}] 완성 이력을 삭제하시겠습니까?`)) return;
    try { await productionApi.delete(id); await load(); }
    catch (err) { alert(err.response?.data?.detail || '삭제 실패'); }
  };

  const totalYards = items.reduce((sum, i) => sum + parseFloat(i.quantity), 0);

  return (
    <div>
      {/* 헤더 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>완성 이력</h3>
          <span style={{ fontSize: 12, background: '#dcfce7', color: '#166534',
            padding: '2px 10px', borderRadius: 12, fontWeight: 600 }}>
            총 {items.length}건
          </span>
          <span style={{ fontSize: 12, background: '#dbeafe', color: '#1e40af',
            padding: '2px 10px', borderRadius: 12, fontWeight: 600 }}>
            {totalYards.toLocaleString()} 야드
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input type="date" value={plFrom} onChange={e => setPlFrom(e.target.value)}
            style={{ fontSize: 12, padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 5 }} />
          <span style={{ fontSize: 12, color: '#6b7280' }}>~</span>
          <input type="date" value={plTo} onChange={e => setPlTo(e.target.value)}
            style={{ fontSize: 12, padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 5 }} />
          <button onClick={handlePackingList} disabled={plLoading}
            style={{
              padding: '5px 12px', fontSize: 12, borderRadius: 6, cursor: 'pointer',
              border: '1px solid #2563eb', background: '#2563eb', color: '#fff',
              opacity: plLoading ? 0.6 : 1,
            }}>
            {plLoading ? '생성중...' : '📄 패킹리스트'}
          </button>
          <button className="btn btn-secondary" style={{ padding: '5px 12px', fontSize: 12 }}
            onClick={load}>새로고침</button>
        </div>
      </div>

      {/* 원단별 요약 */}
      {items.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {['C', 'P', 'L', 'W', 'M'].map(code => {
            const count = items.filter(i => i.fabric_code === code).length;
            const yards = items.filter(i => i.fabric_code === code)
              .reduce((s, i) => s + parseFloat(i.quantity), 0);
            if (count === 0) return null;
            return (
              <div key={code} style={{
                padding: '8px 14px', borderRadius: 8, background: '#f8faff',
                border: '1px solid #dbeafe', fontSize: 12,
              }}>
                <span style={{ fontWeight: 700, color: '#1e40af' }}>{FABRIC_NAMES[code].split('(')[0]}</span>
                <span style={{ color: '#6b7280', marginLeft: 6 }}>{count}건 · {yards.toLocaleString()}야드</span>
              </div>
            );
          })}
        </div>
      )}

      {/* 완성 이력 테이블 */}
      {loading ? (
        <p style={{ fontSize: 13, color: '#9ca3af' }}>불러오는 중...</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>원자재명</th>
                <th>생산량 (야드)</th>
                <th>완성일시</th>
                <th>목표일</th>
                <th>납기 준수</th>
                <th>담당자</th>
                <th>비고</th>
                <th style={{ width: 60 }}>삭제</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', color: '#9ca3af', padding: 32 }}>
                    완성된 생산 이력 없음
                  </td>
                </tr>
              )}
              {items.map(item => {
                const name = `${FABRIC_NAMES[item.fabric_code] || item.fabric_code} / ${COLOR_NAMES[item.color_code] || item.color_code}`;
                const completedAt = item.completed_at || item.updated_at;
                const completedDate = completedAt ? new Date(completedAt) : null;
                const targetDate   = item.target_date ? new Date(item.target_date) : null;
                const onTime = completedDate && targetDate
                  ? completedDate <= new Date(item.target_date + 'T23:59:59')
                  : null;
                return (
                  <tr key={item.id} style={{ background: '#f0fdf4' }}>
                    <td style={{ fontWeight: 600 }}>{name}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: '#16a34a' }}>
                      {parseFloat(item.quantity).toLocaleString()} 야드
                    </td>
                    <td style={{ fontSize: 12, color: '#166534', fontWeight: 600, whiteSpace: 'nowrap' }}>
                      {completedDate ? completedDate.toLocaleString('ko-KR') : '-'}
                    </td>
                    <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{item.target_date}</td>
                    <td style={{ textAlign: 'center' }}>
                      {onTime === null ? (
                        <span style={{ fontSize: 12, color: '#9ca3af' }}>-</span>
                      ) : onTime ? (
                        <span className="badge badge-ok">납기 준수</span>
                      ) : (
                        <span className="badge badge-danger">납기 초과</span>
                      )}
                    </td>
                    <td style={{ fontSize: 12 }}>{item.worker || '—'}</td>
                    <td style={{ fontSize: 12, color: '#6b7280' }}>{item.note || '—'}</td>
                    <td style={{ textAlign: 'center' }}>
                      <button className="btn btn-danger" style={{ padding: '3px 8px', fontSize: 11 }}
                        onClick={() => handleDelete(item.id, name)}>삭제</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
