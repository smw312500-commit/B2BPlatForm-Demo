import React, { useState, useEffect } from 'react';
import { stockApi } from '../api';

const FABRIC_NAMES = { C: '면(Cotton)', P: '폴리에스터', L: '린넨(Linen)', W: '울(Wool)', M: '혼방(Mixed)' };
const COLOR_NAMES  = { BK: '블랙', WH: '화이트', NV: '네이비', GY: '그레이', BE: '베이지', RD: '레드' };
const SAFE_STOCK   = { C: 500, P: 300, L: 200, W: 150, M: 250 };
const FABRIC_CODES = ['C', 'P', 'L', 'W', 'M'];
const COLOR_CODES  = ['BK', 'WH', 'NV', 'GY', 'BE', 'RD'];

export default function StockTab({ onRefreshAgent }) {
  const [stocks,  setStocks]  = useState([]);
  const [checked, setChecked] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ fabric_code: 'C', color_code: 'BK', stock_qty: '' });
  const [showForm, setShowForm] = useState(false);
  const [editId,  setEditId]  = useState(null);
  const [editQty, setEditQty] = useState('');

  const load = async () => {
    try {
      const res = await stockApi.getAll();
      setStocks(res.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const toggleOne = (id) => setChecked(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
  const toggleAll = () => {
    if (checked.size === stocks.length) setChecked(new Set());
    else setChecked(new Set(stocks.map(s => s.id)));
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.stock_qty) return;
    try {
      await stockApi.create({ ...form, stock_qty: parseFloat(form.stock_qty) });
      setForm({ fabric_code: 'C', color_code: 'BK', stock_qty: '' });
      setShowForm(false);
      await load();
      onRefreshAgent();
    } catch (err) { alert(err.response?.data?.detail || '등록 실패'); }
  };

  const handleEdit = async (id) => {
    if (!editQty) return;
    try {
      await stockApi.update(id, { stock_qty: parseFloat(editQty) });
      setEditId(null); setEditQty('');
      await load(); onRefreshAgent();
    } catch (err) { alert(err.response?.data?.detail || '수정 실패'); }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`[${name}] 재고를 삭제하시겠습니까?`)) return;
    try {
      await stockApi.delete(id);
      await load(); onRefreshAgent();
    } catch (err) { alert(err.response?.data?.detail || '삭제 실패'); }
  };

  const statusOf = (s) => {
    const qty = parseFloat(s.stock_qty);
    const safe = SAFE_STOCK[s.fabric_code] || 0;
    if (qty === 0) return 'critical';
    if (qty <= safe) return 'low';
    return 'ok';
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700 }}>원자재 재고 현황</h3>
        <button className="btn btn-primary" style={{ padding: '5px 14px' }}
          onClick={() => setShowForm(v => !v)}>
          {showForm ? '닫기' : '+ 재고 추가'}
        </button>
      </div>

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
            <label>수량 (야드)</label>
            <input type="number" placeholder="예: 1000" value={form.stock_qty}
              onChange={e => setForm(f => ({ ...f, stock_qty: e.target.value }))} style={{ width: 120 }} />
          </div>
          <div className="form-group">
            <label>&nbsp;</label>
            <button type="submit" className="btn btn-success">추가</button>
          </div>
        </form>
      )}

      {loading ? (
        <p style={{ fontSize: 13, color: '#9ca3af' }}>불러오는 중...</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input type="checkbox"
                    checked={stocks.length > 0 && checked.size === stocks.length}
                    onChange={toggleAll} style={{ cursor: 'pointer' }} />
                </th>
                <th>원자재명</th>
                <th>단위</th>
                <th>현재 재고</th>
                <th>안전재고</th>
                <th>상태</th>
                <th>최종 업데이트</th>
                <th style={{ width: 60 }}>삭제</th>
              </tr>
            </thead>
            <tbody>
              {stocks.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', color: '#9ca3af' }}>재고 데이터 없음</td></tr>
              )}
              {stocks.map(s => {
                const st   = statusOf(s);
                const safe = SAFE_STOCK[s.fabric_code] || 0;
                const qty  = parseFloat(s.stock_qty);
                const name = `${FABRIC_NAMES[s.fabric_code] || s.fabric_code} / ${COLOR_NAMES[s.color_code] || s.color_code}`;
                return (
                  <tr key={s.id} onClick={() => toggleOne(s.id)}
                    style={{ cursor: 'pointer', background: checked.has(s.id) ? '#fff1f2' : '' }}>
                    <td style={{ textAlign: 'center' }}>
                      <input type="checkbox" checked={checked.has(s.id)}
                        onChange={() => toggleOne(s.id)}
                        onClick={e => e.stopPropagation()} style={{ cursor: 'pointer' }} />
                    </td>
                    <td style={{ fontWeight: 600 }}>{name}</td>
                    <td style={{ color: '#6b7280' }}>야드</td>
                    <td>
                      {editId === s.id ? (
                        <span style={{ display: 'flex', gap: 4 }} onClick={e => e.stopPropagation()}>
                          <input type="number" value={editQty} onChange={e => setEditQty(e.target.value)}
                            style={{ width: 80, padding: '3px 6px', border: '1px solid #2563eb', borderRadius: 4 }} />
                          <button className="btn btn-success" style={{ padding: '3px 8px' }} onClick={() => handleEdit(s.id)}>저장</button>
                          <button className="btn btn-secondary" style={{ padding: '3px 8px' }} onClick={() => setEditId(null)}>취소</button>
                        </span>
                      ) : (
                        <span
                          style={{ fontWeight: 700, color: st !== 'ok' ? '#dc2626' : '#111827', cursor: 'text', textDecoration: 'underline dotted' }}
                          onClick={e => { e.stopPropagation(); setEditId(s.id); setEditQty(String(qty)); }}>
                          {qty.toLocaleString()} 야드
                        </span>
                      )}
                    </td>
                    <td style={{ color: '#6b7280', fontSize: 12 }}>{safe ? `${safe} 야드` : '-'}</td>
                    <td style={{ fontSize: 12 }}>
                      {st === 'ok'       && <span style={{ color: '#16a34a' }}>✅ 정상</span>}
                      {st === 'low'      && <span style={{ color: '#b45309', fontWeight: 600 }}>⚠ 발주 권고</span>}
                      {st === 'critical' && <span style={{ color: '#dc2626', fontWeight: 700 }}>❌ 긴급 발주</span>}
                    </td>
                    <td style={{ fontSize: 11, color: '#9ca3af' }}>
                      {s.updated_at ? new Date(s.updated_at).toLocaleString('ko-KR') : '-'}
                    </td>
                    <td style={{ textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                      <button className="btn btn-danger" style={{ padding: '3px 8px', fontSize: 11 }}
                        onClick={() => handleDelete(s.id, name)}>
                        삭제
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 안전재고 기준 안내 */}
      <div className="safe-stock-info">
        안전재고 기준: 면 500야드 / 폴리에스터 300야드 / 린넨 200야드 / 울 150야드 / 혼방 250야드 이하 시 AI Agent 발주 권고
      </div>
    </div>
  );
}
