import React, { useState, useEffect, useRef } from 'react';
import * as XLSX from 'xlsx';
import { productionApi } from '../api';
import MachinePanel from './MachinePanel';

const FABRIC_NAMES = { C: '면(Cotton)', P: '폴리에스터', L: '린넨(Linen)', W: '울(Wool)', M: '혼방(Mixed)' };
const COLOR_NAMES  = { BK: '블랙', WH: '화이트', NV: '네이비', GY: '그레이', BE: '베이지', RD: '레드' };
const FABRIC_CODES = ['C', 'P', 'L', 'W', 'M'];
const COLOR_CODES  = ['BK', 'WH', 'NV', 'GY', 'BE', 'RD'];
const STAGES = ['원사입고', '정경·제직', '염색', '가공', '검품', '완성'];

// 야드/시간 — backend agent.py PRODUCTION_SPEED와 동일
const SPEED_PER_HOUR = { C: 8, P: 15, L: 5, W: 4, M: 10 };

const STAGE_COLOR = {
  '원사입고': '#6b7280', '정경·제직': '#2563eb', '염색': '#7c3aed',
  '가공': '#d97706', '검품': '#0891b2', '완성': '#16a34a',
};

// ── 기계 초기 정의 ────────────────────────────────────────────
const MACHINE_INIT = [
  { id: 1, name: '면 직기 1호',   fabricType: 'C' },
  { id: 2, name: '면 직기 2호',   fabricType: 'C' },
  { id: 3, name: '폴리 직기 1호', fabricType: 'P' },
  { id: 4, name: '폴리 직기 2호', fabricType: 'P' },
  { id: 5, name: '린넨 직기 1호', fabricType: 'L' },
  { id: 6, name: '울 직기 1호',   fabricType: 'W' },
  { id: 7, name: '혼방 직기 1호', fabricType: 'M' },
  { id: 8, name: '혼방 직기 2호', fabricType: 'M' },
].map(m => ({
  ...m,
  status: '대기중', prodId: null, colorCode: null,
  total: 0, produced: 0, started_at: null, finished_at: null,
}));

const LS_KEY = 'fabric_machines_v1';

function speedPerSec(fabricType) {
  return (SPEED_PER_HOUR[fabricType] || 8) / 3600;
}

function loadMachines() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return MACHINE_INIT;
    return JSON.parse(raw).map(m => {
      const started  = m.started_at  ? new Date(m.started_at)  : null;
      const finished = m.finished_at ? new Date(m.finished_at) : null;
      if (m.status === '가동중' && started) {
        const elapsed = (Date.now() - started.getTime()) / 1000;
        const spd  = speedPerSec(m.fabricType);
        const next = Math.min(m.produced + elapsed * spd, m.total);
        if (next >= m.total) {
          return { ...m, produced: m.total, status: '완료', started_at: started, finished_at: new Date() };
        }
        return { ...m, produced: next, started_at: started, finished_at: null };
      }
      return { ...m, started_at: started, finished_at: finished };
    });
  } catch { return MACHINE_INIT; }
}

// ── 엑셀 유틸 ────────────────────────────────────────────────
function excelDateToISO(val) {
  if (!val && val !== 0) return null;
  if (val instanceof Date) {
    return `${val.getFullYear()}-${String(val.getMonth()+1).padStart(2,'0')}-${String(val.getDate()).padStart(2,'0')}`;
  }
  if (typeof val === 'number') {
    const d = new Date(Math.round((val - 25569) * 86400 * 1000));
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;
  }
  if (typeof val === 'string') {
    const c = val.replace(/\//g, '-').trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(c)) return c;
  }
  return null;
}

function downloadProductionTemplate() {
  const ws = XLSX.utils.aoa_to_sheet([
    ['원단코드', '컬러코드', '생산량(야드)', '시작단계', '목표일', '담당자', '비고'],
    ['C', 'NV', 500, '원사입고', '2026-07-01', '김생산', ''],
    ['P', 'BK', 300, '정경·제직', '2026-07-05', '이공정', '긴급'],
    ['L', 'WH', 200, '원사입고', '2026-07-10', '박직조', ''],
    ['W', 'GY', 150, '원사입고', '2026-07-15', '최염색', ''],
    ['M', 'BE', 250, '원사입고', '2026-07-20', '', ''],
  ]);
  ws['!cols'] = [{ wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 10 }, { wch: 14 }];
  const nb = XLSX.utils.aoa_to_sheet([
    ['원단코드', 'C=면 / P=폴리에스터 / L=린넨 / W=울 / M=혼방'],
    ['컬러코드', 'BK=블랙 / WH=화이트 / NV=네이비 / GY=그레이 / BE=베이지 / RD=레드'],
    ['시작단계', STAGES.join(' / ')],
  ]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '생산등록');
  XLSX.utils.book_append_sheet(wb, nb, '코드안내');
  XLSX.writeFile(wb, '생산등록_양식.xlsx');
}

function dDay(dateStr) {
  return Math.ceil((new Date(dateStr) - new Date()) / 86400000);
}

export default function ProductionTab() {
  const [items,   setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showExcel, setShowExcel] = useState(false);
  const [form, setForm] = useState({
    fabric_code: 'C', color_code: 'BK', quantity: '', stage: '원사입고',
    target_date: '', worker: '', note: '',
  });

  // 엑셀 상태
  const [preview,   setPreview]   = useState([]);
  const [errors,    setErrors]    = useState([]);
  const [uploading, setUploading] = useState(false);
  const [result,    setResult]    = useState(null);
  const fileRef = useRef(null);

  // 기계 상태
  const [machines,   setMachines]   = useState(loadMachines);
  const [selMachine, setSelMachine] = useState(null);
  const timers   = useRef({});
  const itemsRef = useRef([]);  // 타이머 콜백에서 최신 items 참조용

  // itemsRef 동기화
  useEffect(() => { itemsRef.current = items; }, [items]);

  // localStorage 동기화
  useEffect(() => {
    localStorage.setItem(LS_KEY, JSON.stringify(machines));
  }, [machines]);

  // 마운트 시 가동 중 기계 타이머 재시작
  useEffect(() => {
    machines.forEach(m => {
      if (m.status === '가동중' && m.produced < m.total) _startTimer(m.id);
    });
    return () => Object.values(timers.current).forEach(clearInterval);
  }, []); // eslint-disable-line

  const _autoAdvanceStage = (prodId) => {
    const prod = itemsRef.current.find(p => p.id === prodId);
    if (!prod) return;
    // 기계 생산 완료 → 바로 '완성'으로 이동 + DB completed_at 기록
    productionApi.updateStage(prodId, '완성').then(() => load());
  };

  const _startTimer = (id) => {
    if (timers.current[id]) return;
    timers.current[id] = setInterval(() => {
      setMachines(prev => prev.map(m => {
        if (m.id !== id) return m;
        const spd  = speedPerSec(m.fabricType);
        const next = Math.min(m.produced + spd, m.total);
        if (next >= m.total) {
          clearInterval(timers.current[id]); delete timers.current[id];
          if (m.prodId) _autoAdvanceStage(m.prodId);
          return { ...m, produced: m.total, status: '완료', finished_at: new Date() };
        }
        return { ...m, produced: next };
      }));
    }, 1000);
  };

  const machineHandlers = {
    onStart: (id) => {
      const startTime = new Date();
      setMachines(prev => prev.map(m =>
        m.id === id ? { ...m, status: '가동중', started_at: startTime, finished_at: null } : m
      ));
      _startTimer(id);
    },
    onStop: (id) => {
      if (timers.current[id]) { clearInterval(timers.current[id]); delete timers.current[id]; }
      setMachines(prev => prev.map(m => m.id === id ? { ...m, status: '대기중' } : m));
    },
    onReset: (id) => {
      if (timers.current[id]) { clearInterval(timers.current[id]); delete timers.current[id]; }
      setMachines(prev => prev.map(m =>
        m.id === id
          ? { ...m, produced: 0, status: '대기중', prodId: null, colorCode: null, total: 0, started_at: null, finished_at: null }
          : m
      ));
    },
    onAssign: (id, prodId) => {
      if (timers.current[id]) { clearInterval(timers.current[id]); delete timers.current[id]; }
      const prod = items.find(p => p.id === prodId);
      setMachines(prev => prev.map(m =>
        m.id === id ? {
          ...m,
          prodId:    prod ? prod.id    : null,
          colorCode: prod ? prod.color_code : null,
          total:     prod ? parseFloat(prod.quantity) : 0,
          produced: 0, status: '대기중', started_at: null, finished_at: null,
        } : m
      ));
      setSelMachine(null);
    },
    onStatusChange: (id, st) => {
      if (timers.current[id]) { clearInterval(timers.current[id]); delete timers.current[id]; }
      setMachines(prev => prev.map(m =>
        m.id === id ? { ...m, status: st, prodId: st === '점검중' ? null : m.prodId } : m
      ));
      setSelMachine(null);
    },
    onSelectToggle: (id) => setSelMachine(prev => prev === id ? null : id),
  };

  const load = async () => {
    try {
      const res = await productionApi.getAll();
      setItems(res.data.filter(p => p.stage !== '완성'));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.quantity || !form.target_date) return;
    try {
      await productionApi.create({ ...form, quantity: parseFloat(form.quantity) });
      setForm({ fabric_code: 'C', color_code: 'BK', quantity: '', stage: '원사입고', target_date: '', worker: '', note: '' });
      setShowForm(false);
      await load();
    } catch (err) { alert(err.response?.data?.detail || '등록 실패'); }
  };

  const handleNextStage = async (item) => {
    const idx = STAGES.indexOf(item.stage);
    if (idx >= STAGES.length - 1) return;
    try { await productionApi.updateStage(item.id, STAGES[idx + 1]); await load(); }
    catch (err) { alert(err.response?.data?.detail || '단계 변경 실패'); }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`[${name}] 생산 항목을 삭제하시겠습니까?`)) return;
    try { await productionApi.delete(id); await load(); }
    catch (err) { alert(err.response?.data?.detail || '삭제 실패'); }
  };

  // 엑셀
  const handleFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setResult(null);
    const reader = new FileReader();
    reader.onload = (evt) => {
      const wb  = XLSX.read(evt.target.result, { type: 'array', cellDates: true });
      const ws  = wb.Sheets[wb.SheetNames[0]];
      const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
      const rows = raw.slice(1).filter(r => r.some(c => c !== '')).map(r => ({
        fabric_code: String(r[0] ?? '').trim().toUpperCase(),
        color_code:  String(r[1] ?? '').trim().toUpperCase(),
        quantity:    r[2],
        stage:       String(r[3] ?? '원사입고').trim(),
        target_date: excelDateToISO(r[4]),
        worker:      String(r[5] ?? '').trim(),
        note:        String(r[6] ?? '').trim(),
      }));
      const errs = [];
      rows.forEach((row, i) => {
        if (!FABRIC_CODES.includes(row.fabric_code)) errs.push(`${i+1}행: 원단코드 오류 (${row.fabric_code})`);
        if (!row.quantity || Number(row.quantity) <= 0) errs.push(`${i+1}행: 생산량 오류`);
        if (!STAGES.includes(row.stage)) errs.push(`${i+1}행: 단계 오류 (${row.stage})`);
        if (!row.target_date) errs.push(`${i+1}행: 목표일 형식 오류`);
      });
      setPreview(rows); setErrors(errs);
    };
    reader.readAsArrayBuffer(file);
  };

  const handleUpload = async () => {
    if (errors.length > 0 || preview.length === 0) return;
    setUploading(true);
    let success = 0; const failDetails = [];
    for (const [i, row] of preview.entries()) {
      try { await productionApi.create({ ...row, quantity: Number(row.quantity) }); success++; }
      catch (err) { failDetails.push(`${i+1}행: ${err.response?.data?.detail || err.message}`); }
    }
    setUploading(false);
    setResult({ success, fail: failDetails.length, failDetails });
    if (failDetails.length === 0) {
      setPreview([]); setErrors([]);
      if (fileRef.current) fileRef.current.value = '';
    }
    load();
  };

  return (
    <div>
      {/* ── 헤더 ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700 }}>생산 공정 현황</h3>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-secondary" style={{ padding: '5px 12px', fontSize: 12 }}
            onClick={() => { setShowExcel(v => !v); setShowForm(false); }}>
            📂 엑셀 업로드
          </button>
          <button className="btn btn-primary" style={{ padding: '5px 14px' }}
            onClick={() => { setShowForm(v => !v); setShowExcel(false); }}>
            {showForm ? '닫기' : '+ 생산 등록'}
          </button>
        </div>
      </div>

      {/* 공정 단계 안내 */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
        {STAGES.map((s, i) => (
          <React.Fragment key={s}>
            <span style={{ padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
              background: STAGE_COLOR[s], color: '#fff' }}>{s}</span>
            {i < STAGES.length - 1 && <span style={{ color: '#d1d5db', fontSize: 14 }}>→</span>}
          </React.Fragment>
        ))}
      </div>

      {/* 엑셀 업로드 패널 */}
      {showExcel && (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: 14, marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#15803d' }}>📂 엑셀 일괄 등록</span>
            <button style={{ fontSize: 12, padding: '3px 10px', borderRadius: 5, border: '1px solid #16a34a',
              background: '#fff', color: '#15803d', cursor: 'pointer' }}
              onClick={downloadProductionTemplate}>⬇ 양식 다운로드</button>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" style={{ fontSize: 12 }} onChange={handleFile} />
          </div>
          {errors.length > 0 && (
            <div style={{ background: '#fff1f2', border: '1px solid #fecaca', borderRadius: 6, padding: '8px 12px', marginBottom: 8 }}>
              {errors.map((e, i) => <p key={i} style={{ fontSize: 12, color: '#dc2626', margin: 0 }}>⚠ {e}</p>)}
            </div>
          )}
          {preview.length > 0 && errors.length === 0 && (
            <>
              <p style={{ fontSize: 12, color: '#374151', marginBottom: 6 }}>미리보기 ({preview.length}행)</p>
              <div style={{ overflowX: 'auto', marginBottom: 8 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead><tr style={{ background: '#dcfce7' }}>
                    {['원단코드', '컬러코드', '생산량(야드)', '시작단계', '목표일', '담당자'].map(h => (
                      <th key={h} style={{ padding: '4px 8px', border: '1px solid #bbf7d0', textAlign: 'left' }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {preview.map((r, i) => (
                      <tr key={i}>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{FABRIC_NAMES[r.fabric_code] || r.fabric_code}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.color_code}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb', textAlign: 'right' }}>{Number(r.quantity).toLocaleString()}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.stage}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.target_date}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb', color: '#6b7280' }}>{r.worker || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="btn btn-success" onClick={handleUpload} disabled={uploading}>
                {uploading ? '업로드 중...' : `✅ ${preview.length}건 등록`}
              </button>
            </>
          )}
          {result && (
            <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 6,
              background: result.fail === 0 ? '#f0fdf4' : '#fff1f2',
              border: `1px solid ${result.fail === 0 ? '#86efac' : '#fecaca'}` }}>
              <p style={{ fontSize: 13, fontWeight: 700, color: result.fail === 0 ? '#166534' : '#dc2626' }}>
                성공 {result.success}건 / 실패 {result.fail}건
              </p>
              {result.failDetails.map((d, i) => <p key={i} style={{ fontSize: 12, color: '#dc2626' }}>{d}</p>)}
            </div>
          )}
        </div>
      )}

      {/* 등록 폼 */}
      {showForm && (
        <form className="form-row" onSubmit={handleAdd}
          style={{ background: '#f8faff', border: '1px solid #dbeafe', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <div className="form-group">
            <label>원단코드</label>
            <select value={form.fabric_code} onChange={e => setForm(f => ({ ...f, fabric_code: e.target.value }))}>
              {FABRIC_CODES.map(c => <option key={c} value={c}>{c} — {FABRIC_NAMES[c]}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>컬러코드</label>
            <select value={form.color_code} onChange={e => setForm(f => ({ ...f, color_code: e.target.value }))}>
              {COLOR_CODES.map(c => <option key={c} value={c}>{c} — {COLOR_NAMES[c]}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>생산량 (야드)</label>
            <input type="number" placeholder="예: 500" value={form.quantity}
              onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))} style={{ width: 100 }} />
          </div>
          <div className="form-group">
            <label>시작 단계</label>
            <select value={form.stage} onChange={e => setForm(f => ({ ...f, stage: e.target.value }))}>
              {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>완성 목표일</label>
            <input type="date" value={form.target_date}
              onChange={e => setForm(f => ({ ...f, target_date: e.target.value }))} />
          </div>
          <div className="form-group">
            <label>담당자</label>
            <input type="text" placeholder="이름" value={form.worker} style={{ width: 80 }}
              onChange={e => setForm(f => ({ ...f, worker: e.target.value }))} />
          </div>
          <div className="form-group">
            <label>비고</label>
            <input type="text" placeholder="선택" value={form.note} style={{ width: 100 }}
              onChange={e => setForm(f => ({ ...f, note: e.target.value }))} />
          </div>
          <div className="form-group">
            <label>&nbsp;</label>
            <button type="submit" className="btn btn-success">등록</button>
          </div>
        </form>
      )}

      {/* 생산 목록 테이블 */}
      {loading ? (
        <p style={{ fontSize: 13, color: '#9ca3af' }}>불러오는 중...</p>
      ) : (
        <div className="table-wrap" style={{ marginBottom: 24 }}>
          <table>
            <thead>
              <tr>
                <th>원자재명</th><th>생산량</th><th>현재 공정 단계</th>
                <th>완성 목표일</th><th>D-day</th><th>담당자</th><th>비고</th>
                <th style={{ width: 120 }}>단계 진행</th><th style={{ width: 60 }}>삭제</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr><td colSpan={9} style={{ textAlign: 'center', color: '#9ca3af' }}>생산 데이터 없음</td></tr>
              )}
              {items.map(item => {
                const name  = `${FABRIC_NAMES[item.fabric_code] || item.fabric_code} / ${COLOR_NAMES[item.color_code] || item.color_code}`;
                const d     = dDay(item.target_date);
                const isDone = item.stage === '완성';
                // 이 항목을 담당하는 기계 찾기
                const mach = machines.find(m => m.prodId === item.id);
                const machPct = mach && mach.total > 0
                  ? Math.min((mach.produced / mach.total) * 100, 100) : null;
                return (
                  <tr key={item.id} style={{ background: isDone ? '#f0fdf4' : '' }}>
                    <td style={{ fontWeight: 600 }}>{name}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div>
                        {parseFloat(item.quantity).toLocaleString()} 야드
                        {mach && mach.total > 0 && (
                          <div style={{ marginTop: 3 }}>
                            <div style={{ fontSize: 10, color: mach.status === '가동중' ? '#16a34a' : '#9ca3af', marginBottom: 2 }}>
                              {mach.produced.toFixed(1)} / {mach.total} 야드 ({mach.status})
                            </div>
                            <div style={{ background: '#e5e7eb', borderRadius: 3, height: 4 }}>
                              <div style={{ background: mach.status === '완료' ? '#2563eb' : '#16a34a',
                                height: '100%', borderRadius: 3, width: `${machPct}%` }} />
                            </div>
                          </div>
                        )}
                      </div>
                    </td>
                    <td>
                      <span style={{ padding: '3px 10px', borderRadius: 10, fontSize: 12, fontWeight: 700,
                        background: STAGE_COLOR[item.stage], color: '#fff' }}>{item.stage}</span>
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>{item.target_date}</td>
                    <td style={{ textAlign: 'center', fontWeight: 700,
                      color: d < 0 ? '#dc2626' : d <= 2 ? '#b45309' : '#16a34a' }}>
                      {isDone ? '완성' : d < 0 ? `D+${Math.abs(d)}` : `D-${d}`}
                    </td>
                    <td style={{ fontSize: 12 }}>{item.worker || '—'}</td>
                    <td style={{ fontSize: 12, color: '#6b7280' }}>{item.note || '—'}</td>
                    <td>
                      {!isDone ? (
                        <button className="btn btn-primary" style={{ padding: '3px 10px', fontSize: 12 }}
                          onClick={() => handleNextStage(item)}>다음 단계 →</button>
                      ) : (
                        <span style={{ fontSize: 12, color: '#16a34a', fontWeight: 700 }}>완성</span>
                      )}
                    </td>
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

      {/* ── 기계 배치 ── */}
      <div style={{
        border: '1px solid #e5e7eb', borderRadius: 12,
        padding: 20, background: '#fafafa', marginTop: 8,
      }}>
        <MachinePanel
          machines={machines}
          productions={items}
          selected={selMachine}
          {...machineHandlers}
        />
      </div>
    </div>
  );
}
