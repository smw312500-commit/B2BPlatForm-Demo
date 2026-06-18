import React, { useState, useEffect, useRef } from 'react';
import * as XLSX from 'xlsx';
import { orderApi, releaseApi, agentApi } from '../api';

const STATUS_BADGE = { '대기중': 'badge-blue', '입고완료': 'badge-ok', '취소': 'badge-gray' };
const FABRIC_NAMES = { C: '면', P: '폴리에스터', L: '린넨', W: '울', M: '혼방' };
const FABRIC_CODES = ['C', 'P', 'L', 'W', 'M'];
const COLOR_CODES  = ['BK', 'WH', 'NV', 'GY', 'BE', 'RD'];

function periodStr(start, end) {
  if (!start || !end) return '-';
  return `${start} ~ ${end}`;
}

function excelDateToISO(val) {
  if (!val && val !== 0) return null;
  if (val instanceof Date) {
    const y = val.getFullYear();
    const m = String(val.getMonth() + 1).padStart(2, '0');
    const d = String(val.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
  if (typeof val === 'number') {
    const ms = Math.round((val - 25569) * 86400 * 1000);
    const date = new Date(ms);
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth()+1).padStart(2,'0')}-${String(date.getUTCDate()).padStart(2,'0')}`;
  }
  if (typeof val === 'string') {
    const cleaned = val.replace(/\//g, '-').trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(cleaned)) return cleaned;
  }
  return null;
}

function downloadOrderTemplate() {
  const ws = XLSX.utils.aoa_to_sheet([
    ['품목(원자재명)', '발주처', '발주일', '납기요청일', '수량(kg)', '비고'],
    ['면 원사',   '한국원사공업', '2026-06-01', '2026-06-15', 500, ''],
    ['폴리에스터 원사', '글로벌섬유', '2026-06-01', '2026-06-20', 300, '급발주'],
    ['린넨 원사',  '자연섬유사', '2026-06-02', '2026-06-18', 200, ''],
  ]);
  ws['!cols'] = [{ wch: 16 }, { wch: 14 }, { wch: 13 }, { wch: 13 }, { wch: 10 }, { wch: 16 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '발주등록');
  XLSX.writeFile(wb, '원자재발주_양식.xlsx');
}

function downloadReleaseTemplate() {
  const ws = XLSX.utils.aoa_to_sheet([
    ['라벨코드(9자리)', '원단코드', '컬러코드', '주문량(야드)', '납기일'],
    ['W3MJW01NV', 'C', 'NV', 500, '2026-06-20'],
    ['W3MJW01BK', 'P', 'BK', 300, '2026-06-25'],
    ['W3MJL01WH', 'L', 'WH', 200, '2026-07-01'],
  ]);
  ws['!cols'] = [{ wch: 16 }, { wch: 10 }, { wch: 10 }, { wch: 13 }, { wch: 13 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '출고등록');
  XLSX.writeFile(wb, '출고주문_양식.xlsx');
}

export default function OrderTab({ onRefreshAgent }) {
  const [orders,   setOrders]   = useState([]);
  const [releases, setReleases] = useState([]);

  const [showOrderForm,   setShowOrderForm]   = useState(false);
  const [showReleaseForm, setShowReleaseForm] = useState(false);
  const [showOrderExcel,   setShowOrderExcel]   = useState(false);
  const [showReleaseExcel, setShowReleaseExcel] = useState(false);

  const [orderForm, setOrderForm] = useState({
    material_name: '', order_qty: '', supplier: '', order_date: '', due_date: '', note: ''
  });
  const [releaseForm, setReleaseForm] = useState({
    label_code: '', fabric_code: 'C', color_code: 'BK', release_qty: '', due_date: ''
  });

  // 발주 엑셀 상태
  const [orderPreview,  setOrderPreview]  = useState([]);
  const [orderErrors,   setOrderErrors]   = useState([]);
  const [orderUploading, setOrderUploading] = useState(false);
  const [orderResult,   setOrderResult]   = useState(null);
  const orderFileRef = useRef(null);

  // 출고 엑셀 상태
  const [releasePreview,  setReleasePreview]  = useState([]);
  const [releaseErrors,   setReleaseErrors]   = useState([]);
  const [releaseUploading, setReleaseUploading] = useState(false);
  const [releaseResult,   setReleaseResult]   = useState(null);
  const releaseFileRef = useRef(null);

  // BL 업로드 상태
  const [showBL,      setShowBL]      = useState(false);
  const [blParsing,   setBlParsing]   = useState(false);
  const [blData,      setBlData]      = useState(null);   // 파싱 결과
  const [blDueDate,   setBlDueDate]   = useState('');     // 사용자가 수정할 납기일
  const [blRegResult, setBlRegResult] = useState(null);
  const [blRegistering, setBlRegistering] = useState(false);
  const blFileRef = useRef(null);

  // BL 코드 → 원자재명 매핑 (옷감사 원사)
  const BL_CODE_MAP = {
    COTTON_YARN: '면 원사',
    POLY_YARN:   '폴리에스터 원사',
    LINEN_YARN:  '린넨 원사',
    WOOL_YARN:   '울 원사',
    MIXED_YARN:  '혼방 원사',
  };

  const loadAll = async () => {
    try {
      const [oRes, rRes] = await Promise.all([orderApi.getAll(), releaseApi.getAll()]);
      setOrders(oRes.data);
      setReleases(rRes.data);
    } catch {}
  };

  useEffect(() => { loadAll(); }, []);

  const handleOrderSubmit = async (e) => {
    e.preventDefault();
    try {
      await orderApi.create({ ...orderForm, order_qty: parseFloat(orderForm.order_qty) });
      setOrderForm({ material_name: '', order_qty: '', supplier: '', order_date: '', due_date: '', note: '' });
      setShowOrderForm(false);
      await loadAll();
    } catch (err) { alert(err.response?.data?.detail || '발주 등록 실패'); }
  };

  const handleOrderComplete = async (id) => {
    try { await orderApi.complete(id); await loadAll(); onRefreshAgent(); }
    catch (err) { alert(err.response?.data?.detail || '완료 처리 실패'); }
  };

  const handleReleaseSubmit = async (e) => {
    e.preventDefault();
    try {
      await releaseApi.create({ ...releaseForm, release_qty: parseFloat(releaseForm.release_qty) });
      setReleaseForm({ label_code: '', fabric_code: 'C', color_code: 'BK', release_qty: '', due_date: '' });
      setShowReleaseForm(false);
      await loadAll(); onRefreshAgent();
    } catch (err) { alert(err.response?.data?.detail || '출고 등록 실패'); }
  };

  const handleReleaseComplete = async (id) => {
    if (!window.confirm('출고 완료 처리하시겠습니까?\n재고가 차감되고 플랫폼으로 신호가 전송됩니다.')) return;
    try { await releaseApi.complete(id); await loadAll(); onRefreshAgent(); }
    catch (err) { alert(err.response?.data?.detail || '완료 처리 실패'); }
  };

  /* ── 발주 엑셀 ── */
  const handleOrderFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setOrderResult(null);
    const reader = new FileReader();
    reader.onload = (evt) => {
      const wb  = XLSX.read(evt.target.result, { type: 'array', cellDates: true });
      const ws  = wb.Sheets[wb.SheetNames[0]];
      const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
      const rows = raw.slice(1).filter(r => r.some(c => c !== '')).map(r => ({
        material_name: String(r[0] ?? '').trim(),
        supplier:      String(r[1] ?? '').trim(),
        order_date:    excelDateToISO(r[2]),
        due_date:      excelDateToISO(r[3]),
        order_qty:     r[4],
        note:          String(r[5] ?? '').trim(),
      }));
      const errs = [];
      rows.forEach((row, i) => {
        if (!row.material_name) errs.push(`${i+1}행: 품목명 없음`);
        if (!row.order_qty || isNaN(Number(row.order_qty)) || Number(row.order_qty) <= 0)
          errs.push(`${i+1}행: 수량 오류`);
        if (!row.order_date) errs.push(`${i+1}행: 발주일 형식 오류`);
        if (!row.due_date)   errs.push(`${i+1}행: 납기일 형식 오류`);
      });
      setOrderPreview(rows);
      setOrderErrors(errs);
    };
    reader.readAsArrayBuffer(file);
  };

  const handleOrderUpload = async () => {
    if (orderErrors.length > 0 || orderPreview.length === 0) return;
    setOrderUploading(true);
    let success = 0; const failDetails = [];
    for (const [i, row] of orderPreview.entries()) {
      try {
        await orderApi.create({ ...row, order_qty: Number(row.order_qty) });
        success++;
      } catch (err) {
        failDetails.push(`${i+1}행 (${row.material_name}): ${err.response?.data?.detail || err.message}`);
      }
    }
    setOrderUploading(false);
    setOrderResult({ success, fail: failDetails.length, failDetails });
    if (failDetails.length === 0) { setOrderPreview([]); setOrderErrors([]); if (orderFileRef.current) orderFileRef.current.value = ''; }
    loadAll();
  };

  /* ── 출고 엑셀 ── */
  const handleReleaseFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setReleaseResult(null);
    const reader = new FileReader();
    reader.onload = (evt) => {
      const wb  = XLSX.read(evt.target.result, { type: 'array', cellDates: true });
      const ws  = wb.Sheets[wb.SheetNames[0]];
      const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
      const rows = raw.slice(1).filter(r => r.some(c => c !== '')).map(r => ({
        label_code:  String(r[0] ?? '').trim().toUpperCase(),
        fabric_code: String(r[1] ?? '').trim().toUpperCase(),
        color_code:  String(r[2] ?? '').trim().toUpperCase(),
        release_qty: r[3],
        due_date:    excelDateToISO(r[4]),
      }));
      const errs = [];
      rows.forEach((row, i) => {
        if (!/^[A-Z0-9]{9}$/.test(row.label_code)) errs.push(`${i+1}행: 라벨코드 9자리 오류 (${row.label_code})`);
        if (!['C','P','L','W','M'].includes(row.fabric_code)) errs.push(`${i+1}행: 원단코드 오류 (${row.fabric_code})`);
        if (!row.release_qty || Number(row.release_qty) <= 0) errs.push(`${i+1}행: 주문량 오류`);
        if (!row.due_date) errs.push(`${i+1}행: 납기일 형식 오류`);
      });
      setReleasePreview(rows);
      setReleaseErrors(errs);
    };
    reader.readAsArrayBuffer(file);
  };

  /* ── BL 업로드 ── */
  const handleBLFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setBlParsing(true); setBlData(null); setBlRegResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await agentApi.parseBL(fd);
      setBlData(res.data);
      setBlDueDate(res.data.eta || '');
    } catch (err) {
      alert(err.response?.data?.detail || 'BL 파싱 실패 — BL 파서(포트 8010)가 실행 중인지 확인하세요.');
    } finally {
      setBlParsing(false);
      if (blFileRef.current) blFileRef.current.value = '';
    }
  };

  const handleBLRegister = async () => {
    if (!blData?.items?.length) return;
    if (!blDueDate) { alert('납기요청일을 입력하세요.'); return; }
    setBlRegistering(true); setBlRegResult(null);
    const today = new Date().toISOString().split('T')[0];
    let success = 0; const fails = [];
    for (const item of blData.items) {
      const matName = BL_CODE_MAP[item.code] || item.name;
      try {
        await orderApi.create({
          material_name: matName,
          order_qty:     item.qty,
          supplier:      blData.shipper || '',
          order_date:    today,
          due_date:      blDueDate,
          note:          [
            blData.bl_number ? `BL ${blData.bl_number}` : '',
            blData.port_of_loading ? `POL ${blData.port_of_loading}` : '',
            blData.port_of_discharge ? `POD ${blData.port_of_discharge}` : '',
            '자동등록',
          ].filter(Boolean).join(' / '),
        });
        success++;
      } catch (err) {
        fails.push(`${matName}: ${err.response?.data?.detail || err.message}`);
      }
    }
    setBlRegResult({ success, fails });
    if (fails.length === 0) { setBlData(null); }
    await loadAll(); onRefreshAgent();
    setBlRegistering(false);
  };

  const handleReleaseUpload = async () => {
    if (releaseErrors.length > 0 || releasePreview.length === 0) return;
    setReleaseUploading(true);
    let success = 0; const failDetails = [];
    for (const [i, row] of releasePreview.entries()) {
      try {
        await releaseApi.create({ ...row, release_qty: Number(row.release_qty) });
        success++;
      } catch (err) {
        failDetails.push(`${i+1}행 (${row.label_code}): ${err.response?.data?.detail || err.message}`);
      }
    }
    setReleaseUploading(false);
    setReleaseResult({ success, fail: failDetails.length, failDetails });
    if (failDetails.length === 0) { setReleasePreview([]); setReleaseErrors([]); if (releaseFileRef.current) releaseFileRef.current.value = ''; }
    loadAll(); onRefreshAgent();
  };

  return (
    <div>
      {/* ── 원자재 발주 ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div className="section-title" style={{ margin: 0 }}>원자재 발주 현황</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <label style={{
            padding: '5px 12px', fontSize: 12, borderRadius: 6, cursor: 'pointer',
            border: '1px solid #7c3aed', background: showBL ? '#7c3aed' : '#fff',
            color: showBL ? '#fff' : '#7c3aed', opacity: blParsing ? 0.6 : 1,
            pointerEvents: blParsing ? 'none' : 'auto',
          }}>
            {blParsing ? '⏳ 파싱중...' : '📋 BL 업로드'}
            <input ref={blFileRef} type="file" accept=".pdf" style={{ display: 'none' }}
              onChange={(e) => { setShowBL(true); setShowOrderExcel(false); setShowOrderForm(false); handleBLFile(e); }} />
          </label>
          <button className="btn btn-secondary" style={{ padding: '5px 12px', fontSize: 12 }}
            onClick={() => { setShowOrderExcel(v => !v); setShowOrderForm(false); setShowBL(false); }}>
            📂 엑셀 업로드
          </button>
          <button className="btn btn-primary" style={{ padding: '5px 14px' }}
            onClick={() => { setShowOrderForm(v => !v); setShowOrderExcel(false); setShowBL(false); }}>
            {showOrderForm ? '닫기' : '+ 발주 등록'}
          </button>
        </div>
      </div>

      {/* BL 파싱 결과 패널 */}
      {showBL && (
        <div style={{ background: '#faf5ff', border: '1px solid #c4b5fd', borderRadius: 8, padding: 14, marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#6d28d9' }}>📋 BL 선하증권 파싱</span>
            <button style={{ fontSize: 12, color: '#9ca3af', background: 'none', border: 'none', cursor: 'pointer' }}
              onClick={() => { setShowBL(false); setBlData(null); setBlRegResult(null); }}>닫기</button>
          </div>

          {!blData && !blParsing && (
            <p style={{ fontSize: 12, color: '#9ca3af' }}>PDF 파일을 선택하면 자동으로 파싱됩니다.</p>
          )}
          {blParsing && (
            <p style={{ fontSize: 12, color: '#7c3aed' }}>⏳ 파싱 중...</p>
          )}

          {blData && (
            <>
              {/* BL 기본 정보 */}
              <div style={{ background: '#ede9fe', borderRadius: 6, padding: '8px 12px', marginBottom: 10, fontSize: 12 }}>
                {blData.bl_number && <span style={{ marginRight: 16 }}><b>BL No.</b> {blData.bl_number}</span>}
                {blData.shipper   && <span style={{ marginRight: 16 }}><b>공급사</b> {blData.shipper}</span>}
                {blData.eta       && <span><b>ETA</b> {blData.eta}</span>}
              </div>

              {/* 품목 테이블 */}
              <div style={{ overflowX: 'auto', marginBottom: 10 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: '#ddd6fe' }}>
                      {['코드', '원자재명', '수량', '단위'].map(h => (
                        <th key={h} style={{ padding: '5px 10px', border: '1px solid #c4b5fd', textAlign: 'left' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {blData.items.map((item, i) => (
                      <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#f5f3ff' }}>
                        <td style={{ padding: '4px 10px', border: '1px solid #e5e7eb', fontFamily: 'monospace', fontSize: 11 }}>{item.code}</td>
                        <td style={{ padding: '4px 10px', border: '1px solid #e5e7eb', fontWeight: 600 }}>
                          {BL_CODE_MAP[item.code] || item.name}
                        </td>
                        <td style={{ padding: '4px 10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>{Number(item.qty).toLocaleString()}</td>
                        <td style={{ padding: '4px 10px', border: '1px solid #e5e7eb', color: '#6b7280' }}>{item.unit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 납기요청일 입력 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>납기요청일</label>
                <input type="date" value={blDueDate}
                  onChange={e => setBlDueDate(e.target.value)}
                  style={{ fontSize: 12, padding: '4px 8px', border: '1px solid #c4b5fd', borderRadius: 5 }} />
                <span style={{ fontSize: 11, color: '#9ca3af' }}>BL의 ETA를 기본값으로 사용</span>
              </div>

              <button className="btn btn-success" onClick={handleBLRegister} disabled={blRegistering || !blDueDate}>
                {blRegistering ? '등록 중...' : `✅ ${blData.items.length}건 발주 등록`}
              </button>
            </>
          )}

          {blRegResult && (
            <div style={{
              marginTop: 10, padding: '8px 12px', borderRadius: 6, fontSize: 12,
              background: blRegResult.fails.length === 0 ? '#f0fdf4' : '#fff1f2',
              border: `1px solid ${blRegResult.fails.length === 0 ? '#86efac' : '#fecaca'}`,
            }}>
              <p style={{ fontWeight: 700, color: blRegResult.fails.length === 0 ? '#166534' : '#dc2626' }}>
                성공 {blRegResult.success}건 {blRegResult.fails.length > 0 && `/ 실패 ${blRegResult.fails.length}건`}
              </p>
              {blRegResult.fails.map((f, i) => <p key={i} style={{ color: '#dc2626' }}>{f}</p>)}
            </div>
          )}
        </div>
      )}

      {showOrderExcel && (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: 14, marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#15803d' }}>📂 엑셀 일괄 등록</span>
            <button style={{ fontSize: 12, padding: '3px 10px', borderRadius: 5, border: '1px solid #16a34a',
              background: '#fff', color: '#15803d', cursor: 'pointer' }}
              onClick={downloadOrderTemplate}>⬇ 양식 다운로드</button>
            <input ref={orderFileRef} type="file" accept=".xlsx,.xls"
              style={{ fontSize: 12 }} onChange={handleOrderFile} />
          </div>
          {orderErrors.length > 0 && (
            <div style={{ background: '#fff1f2', border: '1px solid #fecaca', borderRadius: 6, padding: '8px 12px', marginBottom: 8 }}>
              {orderErrors.map((e, i) => <p key={i} style={{ fontSize: 12, color: '#dc2626', margin: 0 }}>⚠ {e}</p>)}
            </div>
          )}
          {orderPreview.length > 0 && orderErrors.length === 0 && (
            <>
              <p style={{ fontSize: 12, color: '#374151', marginBottom: 6 }}>미리보기 ({orderPreview.length}행)</p>
              <div style={{ overflowX: 'auto', marginBottom: 8 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: '#dcfce7' }}>
                      {['품목', '발주처', '발주일', '납기일', '수량(kg)', '비고'].map(h => (
                        <th key={h} style={{ padding: '4px 8px', border: '1px solid #bbf7d0', textAlign: 'left' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {orderPreview.map((r, i) => (
                      <tr key={i}>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.material_name}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.supplier}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.order_date}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.due_date}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb', textAlign: 'right' }}>{Number(r.order_qty).toLocaleString()}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb', color: '#6b7280' }}>{r.note || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="btn btn-success" onClick={handleOrderUpload} disabled={orderUploading}>
                {orderUploading ? '업로드 중...' : `✅ ${orderPreview.length}건 등록`}
              </button>
            </>
          )}
          {orderResult && (
            <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 6,
              background: orderResult.fail === 0 ? '#f0fdf4' : '#fff1f2',
              border: `1px solid ${orderResult.fail === 0 ? '#86efac' : '#fecaca'}` }}>
              <p style={{ fontSize: 13, fontWeight: 700, color: orderResult.fail === 0 ? '#166534' : '#dc2626' }}>
                성공 {orderResult.success}건 / 실패 {orderResult.fail}건
              </p>
              {orderResult.failDetails.map((d, i) => <p key={i} style={{ fontSize: 12, color: '#dc2626' }}>{d}</p>)}
            </div>
          )}
        </div>
      )}

      {showOrderForm && (
        <form className="form-row" onSubmit={handleOrderSubmit}
          style={{ background: '#f8faff', border: '1px solid #dbeafe', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <div className="form-group">
            <label>품목 (원자재명)</label>
            <input placeholder="예: 면 원사" value={orderForm.material_name}
              onChange={e => setOrderForm(f => ({ ...f, material_name: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label>발주처</label>
            <input placeholder="공급업체명" value={orderForm.supplier}
              onChange={e => setOrderForm(f => ({ ...f, supplier: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label>발주일</label>
            <input type="date" value={orderForm.order_date}
              onChange={e => setOrderForm(f => ({ ...f, order_date: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label>납기요청일</label>
            <input type="date" value={orderForm.due_date}
              onChange={e => setOrderForm(f => ({ ...f, due_date: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label>수량 (kg)</label>
            <input type="number" placeholder="kg" value={orderForm.order_qty}
              onChange={e => setOrderForm(f => ({ ...f, order_qty: e.target.value }))}
              style={{ width: 100 }} required />
          </div>
          <div className="form-group">
            <label>비고</label>
            <input placeholder="선택" value={orderForm.note}
              onChange={e => setOrderForm(f => ({ ...f, note: e.target.value }))} style={{ width: 110 }} />
          </div>
          <div className="form-group">
            <label>&nbsp;</label>
            <button type="submit" className="btn btn-success">등록</button>
          </div>
        </form>
      )}

      <div className="table-wrap" style={{ marginBottom: 24 }}>
        <table>
          <thead>
            <tr>
              <th>품목</th><th>발주처</th><th>날짜</th>
              <th>기간 (발주 ~ 납기)</th><th>수량 (kg)</th>
              <th>비고</th><th>상태</th><th>처리</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr><td colSpan={8} style={{ textAlign: 'center', color: '#9ca3af' }}>발주 내역 없음</td></tr>
            ) : orders.map(o => (
              <tr key={o.id}>
                <td style={{ fontWeight: 600 }}>{o.material_name}</td>
                <td>{o.supplier}</td>
                <td style={{ whiteSpace: 'nowrap' }}>{o.order_date}</td>
                <td style={{ fontSize: 12, color: '#374151', whiteSpace: 'nowrap' }}>
                  {periodStr(o.order_date, o.due_date)}
                </td>
                <td style={{ textAlign: 'right' }}>{parseFloat(o.order_qty).toLocaleString()}</td>
                <td style={{ fontSize: 12, color: '#6b7280' }}>{o.note || '—'}</td>
                <td><span className={`badge ${STATUS_BADGE[o.status] || 'badge-gray'}`}>{o.status}</span></td>
                <td>
                  {o.status === '대기중' && (
                    <button className="btn btn-success" style={{ padding: '3px 10px' }}
                      onClick={() => handleOrderComplete(o.id)}>입고완료</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── 출고 주문 ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div className="section-title" style={{ margin: 0 }}>출고 주문 현황</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-secondary" style={{ padding: '5px 12px', fontSize: 12 }}
            onClick={() => { setShowReleaseExcel(v => !v); setShowReleaseForm(false); }}>
            📂 엑셀 업로드
          </button>
          <button className="btn btn-primary" style={{ padding: '5px 14px' }}
            onClick={() => { setShowReleaseForm(v => !v); setShowReleaseExcel(false); }}>
            {showReleaseForm ? '닫기' : '+ 출고 등록'}
          </button>
        </div>
      </div>

      {showReleaseExcel && (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: 14, marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#15803d' }}>📂 엑셀 일괄 등록</span>
            <button style={{ fontSize: 12, padding: '3px 10px', borderRadius: 5, border: '1px solid #16a34a',
              background: '#fff', color: '#15803d', cursor: 'pointer' }}
              onClick={downloadReleaseTemplate}>⬇ 양식 다운로드</button>
            <input ref={releaseFileRef} type="file" accept=".xlsx,.xls"
              style={{ fontSize: 12 }} onChange={handleReleaseFile} />
          </div>
          {releaseErrors.length > 0 && (
            <div style={{ background: '#fff1f2', border: '1px solid #fecaca', borderRadius: 6, padding: '8px 12px', marginBottom: 8 }}>
              {releaseErrors.map((e, i) => <p key={i} style={{ fontSize: 12, color: '#dc2626', margin: 0 }}>⚠ {e}</p>)}
            </div>
          )}
          {releasePreview.length > 0 && releaseErrors.length === 0 && (
            <>
              <p style={{ fontSize: 12, color: '#374151', marginBottom: 6 }}>미리보기 ({releasePreview.length}행)</p>
              <div style={{ overflowX: 'auto', marginBottom: 8 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: '#dcfce7' }}>
                      {['라벨코드', '원단', '컬러', '주문량(야드)', '납기일'].map(h => (
                        <th key={h} style={{ padding: '4px 8px', border: '1px solid #bbf7d0', textAlign: 'left' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {releasePreview.map((r, i) => (
                      <tr key={i}>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb', fontFamily: 'monospace', fontWeight: 700 }}>{r.label_code}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{FABRIC_NAMES[r.fabric_code] || r.fabric_code}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.color_code}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb', textAlign: 'right' }}>{Number(r.release_qty).toLocaleString()}</td>
                        <td style={{ padding: '3px 8px', border: '1px solid #e5e7eb' }}>{r.due_date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="btn btn-success" onClick={handleReleaseUpload} disabled={releaseUploading}>
                {releaseUploading ? '업로드 중...' : `✅ ${releasePreview.length}건 등록`}
              </button>
            </>
          )}
          {releaseResult && (
            <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 6,
              background: releaseResult.fail === 0 ? '#f0fdf4' : '#fff1f2',
              border: `1px solid ${releaseResult.fail === 0 ? '#86efac' : '#fecaca'}` }}>
              <p style={{ fontSize: 13, fontWeight: 700, color: releaseResult.fail === 0 ? '#166534' : '#dc2626' }}>
                성공 {releaseResult.success}건 / 실패 {releaseResult.fail}건
              </p>
              {releaseResult.failDetails.map((d, i) => <p key={i} style={{ fontSize: 12, color: '#dc2626' }}>{d}</p>)}
            </div>
          )}
        </div>
      )}

      {showReleaseForm && (
        <form className="form-row" onSubmit={handleReleaseSubmit}
          style={{ background: '#f8faff', border: '1px solid #dbeafe', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <div className="form-group">
            <label>라벨코드 (9자리)</label>
            <input placeholder="예: W3MJW01NV" maxLength={9} value={releaseForm.label_code}
              onChange={e => setReleaseForm(f => ({ ...f, label_code: e.target.value.toUpperCase() }))}
              style={{ width: 120, fontFamily: 'monospace', letterSpacing: 1 }} required />
          </div>
          <div className="form-group">
            <label>원단코드</label>
            <select value={releaseForm.fabric_code}
              onChange={e => setReleaseForm(f => ({ ...f, fabric_code: e.target.value }))}>
              {FABRIC_CODES.map(c => <option key={c} value={c}>{c} — {FABRIC_NAMES[c]}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>컬러코드</label>
            <select value={releaseForm.color_code}
              onChange={e => setReleaseForm(f => ({ ...f, color_code: e.target.value }))}>
              {COLOR_CODES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>주문량 (야드)</label>
            <input type="number" placeholder="야드" value={releaseForm.release_qty}
              onChange={e => setReleaseForm(f => ({ ...f, release_qty: e.target.value }))}
              style={{ width: 100 }} required />
          </div>
          <div className="form-group">
            <label>납기일</label>
            <input type="date" value={releaseForm.due_date}
              onChange={e => setReleaseForm(f => ({ ...f, due_date: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label>&nbsp;</label>
            <button type="submit" className="btn btn-success">등록</button>
          </div>
        </form>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>라벨코드</th><th>품목 (원단/컬러)</th><th>날짜 (등록일)</th>
              <th>기간 (등록 ~ 납기)</th><th>수량 (야드)</th><th>비고 (상태)</th><th>완료</th>
            </tr>
          </thead>
          <tbody>
            {releases.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: '#9ca3af' }}>출고 주문 없음</td></tr>
            ) : releases.map(r => (
              <tr key={r.id}>
                <td style={{ fontWeight: 700, fontFamily: 'monospace', letterSpacing: 1 }}>{r.label_code}</td>
                <td>{FABRIC_NAMES[r.fabric_code] || r.fabric_code} / {r.color_code}</td>
                <td style={{ whiteSpace: 'nowrap', fontSize: 12, color: '#6b7280' }}>
                  {r.created_at ? r.created_at.slice(0, 10) : '-'}
                </td>
                <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                  {periodStr(r.created_at ? r.created_at.slice(0, 10) : null, r.due_date)}
                </td>
                <td style={{ textAlign: 'right', fontWeight: 600 }}>{parseFloat(r.release_qty).toLocaleString()}</td>
                <td>
                  <span className={`badge ${r.status === '출고완료' ? 'badge-ok' : 'badge-blue'}`}>{r.status}</span>
                  {r.release_date && <span style={{ fontSize: 11, color: '#6b7280', marginLeft: 6 }}>{r.release_date}</span>}
                </td>
                <td>
                  {r.status === '생산중' && (
                    <button className="btn btn-success" style={{ padding: '3px 10px' }}
                      onClick={() => handleReleaseComplete(r.id)}>완료</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
