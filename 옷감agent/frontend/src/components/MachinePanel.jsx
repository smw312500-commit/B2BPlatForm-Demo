// 기계 상태 colors (inline style 기반)
const STATUS_STYLE = {
  가동중: { bg: '#f0fdf4', border: '#4ade80', dot: '#16a34a', badge: '#16a34a' },
  대기중: { bg: '#f9fafb', border: '#d1d5db', dot: '#9ca3af', badge: '#6b7280' },
  점검중: { bg: '#fff1f2', border: '#fca5a5', dot: '#dc2626', badge: '#dc2626' },
  완료:   { bg: '#eff6ff', border: '#93c5fd', dot: '#2563eb', badge: '#2563eb' },
};

const FABRIC_LABEL = { C: '면', P: '폴리에스터', L: '린넨', W: '울', M: '혼방' };
// 야드/시간 — backend agent.py PRODUCTION_SPEED와 동일
const SPEED_PER_HOUR = { C: 8, P: 15, L: 5, W: 4, M: 10 };

function fmtTime(d) {
  if (!d) return '-';
  return new Date(d).toLocaleString('ko-KR', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function remainingStr(m) {
  const speed = SPEED_PER_HOUR[m.fabricType] || 8;
  const rem = m.total - m.produced;
  const hours = rem / speed;
  if (hours < 1) return `약 ${Math.ceil(hours * 60)}분 남음`;
  return `약 ${hours.toFixed(1)}시간 남음`;
}

export default function MachinePanel({
  machines, productions = [],
  selected, onSelectToggle,
  onStart, onStop, onReset, onAssign, onStatusChange,
}) {
  const counts = {
    가동중: machines.filter(m => m.status === '가동중').length,
    대기중: machines.filter(m => m.status === '대기중').length,
    점검중: machines.filter(m => m.status === '점검중').length,
    완료:   machines.filter(m => m.status === '완료').length,
  };

  return (
    <div>
      {/* 현황 뱃지 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#374151' }}>기계 현황</span>
        {counts.가동중 > 0 && <span style={{ fontSize: 11, background: '#dcfce7', color: '#15803d', padding: '2px 10px', borderRadius: 20, fontWeight: 600 }}>가동 {counts.가동중}대</span>}
        {counts.대기중 > 0 && <span style={{ fontSize: 11, background: '#f3f4f6', color: '#6b7280', padding: '2px 10px', borderRadius: 20, fontWeight: 600 }}>대기 {counts.대기중}대</span>}
        {counts.점검중 > 0 && <span style={{ fontSize: 11, background: '#fee2e2', color: '#dc2626', padding: '2px 10px', borderRadius: 20, fontWeight: 600 }}>점검 {counts.점검중}대</span>}
        {counts.완료   > 0 && <span style={{ fontSize: 11, background: '#dbeafe', color: '#1d4ed8', padding: '2px 10px', borderRadius: 20, fontWeight: 600 }}>완료 {counts.완료}대</span>}
        <span style={{ fontSize: 11, color: '#9ca3af', marginLeft: 'auto' }}>기계 클릭 → 작업 설정</span>
      </div>

      {/* 기계 그리드 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {machines.map(m => {
          const s      = STATUS_STYLE[m.status] ?? STATUS_STYLE['대기중'];
          const isOpen = selected === m.id;
          const pct    = m.total > 0 ? Math.min((m.produced / m.total) * 100, 100) : 0;
          const running = m.status === '가동중';
          const done    = m.status === '완료';
          const prodName = m.prodId ? (productions.find(p => p.id === m.prodId)
            ? `${FABRIC_LABEL[m.fabricType]}/${m.colorCode} ${parseFloat(m.total).toLocaleString()}야드`
            : '—') : null;

          return (
            <div key={m.id} style={{ position: 'relative' }}>
              <div style={{
                borderRadius: 14, border: `2px solid ${s.border}`, background: s.bg,
                padding: 14, boxShadow: running ? '0 4px 16px rgba(0,0,0,0.1)' : 'none',
                transition: 'box-shadow 0.2s',
              }}>
                {/* 헤더 */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#111827' }}>{m.name}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {m.prodId && !running && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onReset(m.id); }}
                        title="작업 빼기"
                        style={{
                          fontSize: 13, lineHeight: 1, width: 18, height: 18,
                          borderRadius: '50%', border: '1px solid #fca5a5',
                          background: '#fff1f2', color: '#dc2626',
                          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          padding: 0,
                        }}>×</button>
                    )}
                    <span style={{
                      width: 10, height: 10, borderRadius: '50%', background: s.dot,
                      animation: running ? 'pulse 1.5s infinite' : 'none',
                    }} />
                  </div>
                </div>

                {/* 기어 아이콘 */}
                <div
                  onClick={() => onSelectToggle(m.id)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    height: 80, borderRadius: 10, border: `2px solid ${s.border}`,
                    background: 'rgba(255,255,255,0.7)', marginBottom: 10,
                    cursor: 'pointer',
                  }}
                >
                  <svg
                    width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                    style={{
                      color: running ? '#16a34a' : done ? '#2563eb' : m.status === '점검중' ? '#dc2626' : '#d1d5db',
                      animation: running ? 'spin 3s linear infinite' : 'none',
                    }}
                  >
                    <circle cx="12" cy="12" r="3" strokeWidth="2"/>
                    <path strokeWidth="2" strokeLinecap="round"
                      d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/>
                  </svg>
                </div>

                {/* 상태 뱃지 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 700, color: '#fff', padding: '2px 8px',
                    borderRadius: 10, background: s.badge,
                  }}>{m.status}</span>
                  {prodName && <span style={{ fontSize: 11, color: '#4f46e5', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{prodName}</span>}
                </div>

                {/* 진행률 */}
                {m.total > 0 ? (
                  <div style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                      <span style={{ fontWeight: 700, color: done ? '#2563eb' : '#111827' }}>
                        {m.produced.toFixed(1)} / {m.total.toLocaleString()} 야드
                      </span>
                      <span style={{ color: '#9ca3af' }}>{pct.toFixed(1)}%</span>
                    </div>
                    <div style={{ background: 'rgba(255,255,255,0.7)', borderRadius: 4, height: 6, border: '1px solid #e5e7eb' }}>
                      <div style={{
                        height: '100%', borderRadius: 4,
                        background: done ? '#2563eb' : '#16a34a',
                        width: `${pct}%`, transition: 'width 0.5s',
                      }} />
                    </div>
                    {running && <p style={{ fontSize: 11, color: '#6b7280', marginTop: 3 }}>{remainingStr(m)}</p>}
                    <div style={{ marginTop: 4 }}>
                      {m.started_at  && <p style={{ fontSize: 10, color: '#6b7280' }}>시작 {fmtTime(m.started_at)}</p>}
                      {m.finished_at && <p style={{ fontSize: 10, color: '#2563eb', fontWeight: 600 }}>완료 {fmtTime(m.finished_at)}</p>}
                    </div>
                  </div>
                ) : (
                  <p style={{ fontSize: 12, color: '#9ca3af', marginBottom: 10 }}>작업 없음</p>
                )}

                {/* 버튼 */}
                <div style={{ display: 'flex', gap: 4 }}>
                  {!done && m.total > 0 && !running && (
                    <button onClick={() => onStart(m.id)} style={{
                      flex: 1, fontSize: 11, fontWeight: 700, background: '#16a34a', color: '#fff',
                      border: 'none', borderRadius: 6, padding: '5px 0', cursor: 'pointer',
                    }}>▶ 시작</button>
                  )}
                  {running && (
                    <button onClick={() => onStop(m.id)} style={{
                      flex: 1, fontSize: 11, fontWeight: 700, background: '#d97706', color: '#fff',
                      border: 'none', borderRadius: 6, padding: '5px 0', cursor: 'pointer',
                    }}>■ 정지</button>
                  )}
                  {(done || m.produced > 0) && (
                    <button onClick={() => onReset(m.id)} style={{
                      flex: 1, fontSize: 11, background: '#f3f4f6', color: '#6b7280',
                      border: '1px solid #e5e7eb', borderRadius: 6, padding: '5px 0', cursor: 'pointer',
                    }}>↺ 초기화</button>
                  )}
                  {m.total === 0 && !done && (
                    <button onClick={() => onSelectToggle(m.id)} style={{
                      flex: 1, fontSize: 11, background: '#eff6ff', color: '#2563eb',
                      border: '1px solid #bfdbfe', borderRadius: 6, padding: '5px 0', cursor: 'pointer',
                    }}>+ 작업 할당</button>
                  )}
                </div>
              </div>

              {/* 작업 할당 드롭다운 */}
              {isOpen && (
                <div style={{
                  position: 'absolute', left: 0, top: '100%', marginTop: 4, zIndex: 30,
                  background: '#fff', border: '1px solid #e5e7eb', borderRadius: 10,
                  boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: 12, width: '100%', minWidth: 200,
                }}>
                  <p style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', marginBottom: 8 }}>상태 변경</p>
                  <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
                    {['대기중', '점검중'].map(st => (
                      <button key={st} onClick={() => onStatusChange(m.id, st)} style={{
                        flex: 1, fontSize: 11, padding: '4px 0', borderRadius: 6, cursor: 'pointer',
                        border: `1px solid ${m.status === st ? s.border : '#e5e7eb'}`,
                        background: m.status === st ? s.bg : '#f9fafb',
                        fontWeight: m.status === st ? 700 : 400,
                      }}>{st}</button>
                    ))}
                  </div>
                  <p style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', marginBottom: 6 }}>작업 할당</p>
                  <select
                    value={m.prodId || ''}
                    onChange={e => onAssign(m.id, e.target.value ? Number(e.target.value) : null)}
                    style={{ width: '100%', padding: '5px 8px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 12 }}
                  >
                    <option value="">— 작업 없음 —</option>
                    {productions
                      .filter(p => p.fabric_code === m.fabricType && p.stage !== '완성')
                      .map(p => (
                        <option key={p.id} value={p.id}>
                          {FABRIC_LABEL[p.fabric_code]}/{p.color_code} {parseFloat(p.quantity).toLocaleString()}야드 (D-{Math.ceil((new Date(p.target_date) - new Date()) / 86400000)})
                        </option>
                      ))
                    }
                  </select>
                  {productions.filter(p => p.fabric_code === m.fabricType && p.stage !== '완성').length === 0 && (
                    <p style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>할당 가능한 {FABRIC_LABEL[m.fabricType]} 작업 없음</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
      `}</style>
    </div>
  );
}
