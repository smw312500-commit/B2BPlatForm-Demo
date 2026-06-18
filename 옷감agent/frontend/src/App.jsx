import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header';
import AIAgentPanel from './components/AIAgentPanel';
import StockTab from './components/StockTab';
import OrderTab from './components/OrderTab';
import ProductionTab from './components/ProductionTab';
import CompletedTab from './components/CompletedTab';
import OtherTab from './components/OtherTab';
import PlatformReportTab from './components/PlatformReportTab';
import { agentApi } from './api';
import './App.css';

const TABS = [
  { id: 'stock',      label: '재고' },
  { id: 'order',      label: '발주하기' },
  { id: 'production', label: '생산' },
  { id: 'completed',  label: '완성이력' },
  { id: 'platform-report', label: '플랫폼 보고' },
  { id: 'other',      label: '기타' },
];

const FABRIC_CODES = ['C', 'P', 'L', 'W', 'M'];
const FABRIC_NAMES = { C: '면', P: '폴리에스터', L: '린넨', W: '울', M: '혼방' };
const COLOR_CODES  = ['BK', 'WH', 'NV', 'GY', 'BE', 'RD'];

function toISO(d) { return d.toISOString().split('T')[0]; }

export default function App() {
  const [activeTab, setActiveTab]     = useState('stock');
  const [agentStatus, setAgentStatus] = useState(null);

  const today = toISO(new Date());
  const [dateFrom, setDateFrom] = useState(today.slice(0, 7) + '-01');
  const [dateTo,   setDateTo]   = useState(today);
  const [searched, setSearched] = useState(null);

  const [pickerOpen,  setPickerOpen]  = useState(null);
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const pickerRef = useRef(null);
  const aiRef     = useRef(null);

  const refreshAgent = useCallback(async () => {
    try {
      const res = await agentApi.getStatus();
      setAgentStatus(res.data);
    } catch {}
  }, []);

  useEffect(() => {
    refreshAgent();
    const t = setInterval(refreshAgent, 30000);
    return () => clearInterval(t);
  }, [refreshAgent]);

  useEffect(() => {
    const handler = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) setPickerOpen(null);
      if (aiRef.current     && !aiRef.current.contains(e.target))     setAiPanelOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const renderTab = () => {
    switch (activeTab) {
      case 'stock':  return <StockTab onRefreshAgent={refreshAgent} agentStatus={agentStatus} />;
      case 'order':  return <OrderTab onRefreshAgent={refreshAgent} />;
      case 'production': return <ProductionTab />;
      case 'completed':  return <CompletedTab />;
      case 'platform-report': return <PlatformReportTab agentStatus={agentStatus} onRefresh={refreshAgent} />;
      case 'other':      return <OtherTab />;
      default:       return null;
    }
  };

  return (
    <div className="app-root">
      <Header />

      {/* 탭바 + 툴바 */}
      <div className="toolbar-row">
        <div className="tab-list">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`tab-btn ${activeTab === t.id ? 'active' : ''}`}>
              {t.label}
            </button>
          ))}
        </div>

        <div className="toolbar-right">
          {/* AI 납기 분석 */}
          <div className="relative" ref={aiRef}>
            <button onClick={() => setAiPanelOpen(v => !v)}
              className={`ai-analyze-btn ${aiPanelOpen ? 'open' : ''}`}>
              ✦ AI 납기 분석
            </button>
            {aiPanelOpen && (
              <AiAnalysisPanel
                onClose={() => setAiPanelOpen(false)}
                onRefresh={refreshAgent}
              />
            )}
          </div>

          <div className="toolbar-divider" />

          {/* 날짜 필터 */}
          <div className="date-filter" ref={pickerRef}>
            <div className="relative">
              <button className="date-btn" onClick={() => setPickerOpen(pickerOpen === 'from' ? null : 'from')}>
                <CalIcon /> {dateFrom}
              </button>
              {pickerOpen === 'from' && (
                <MiniCalendar value={dateFrom} onChange={v => { setDateFrom(v); setPickerOpen(null); }} />
              )}
            </div>
            <span className="date-sep">~</span>
            <div className="relative">
              <button className="date-btn" onClick={() => setPickerOpen(pickerOpen === 'to' ? null : 'to')}>
                <CalIcon /> {dateTo}
              </button>
              {pickerOpen === 'to' && (
                <MiniCalendar value={dateTo} onChange={v => { setDateTo(v); setPickerOpen(null); }} align="right" />
              )}
            </div>
            <button className="search-btn" onClick={() => setSearched({ from: dateFrom, to: dateTo })}>
              조회
            </button>
            {searched && (
              <button className="reset-btn" onClick={() => setSearched(null)}>초기화</button>
            )}
          </div>
        </div>
      </div>

      {searched && (
        <div className="search-banner">
          {searched.from} ~ {searched.to} 기간 조회 중
        </div>
      )}

      {/* 메인 레이아웃 */}
      <div className="main-layout">
        <div className="content-area">{renderTab()}</div>
        <div className="agent-area">
          <AIAgentPanel status={agentStatus} onRefresh={refreshAgent} onOpenReportChannel={() => setActiveTab('platform-report')} />
        </div>
      </div>
    </div>
  );
}

/* ── AI 납기 분석 드롭다운 ─────────────────── */
function AiAnalysisPanel({ onClose, onRefresh }) {
  const FABRIC_CODES = ['C', 'P', 'L', 'W', 'M'];
  const FABRIC_NAMES = { C: '면(C)', P: '폴리에스터(P)', L: '린넨(L)', W: '울(W)', M: '혼방(M)' };
  const COLOR_CODES  = ['BK', 'WH', 'NV', 'GY', 'BE', 'RD'];

  const [form, setForm]         = useState({ fabric_code: 'C', color_code: 'BK', release_qty: '', due_date: '' });
  const [validation, setValidation] = useState(null);
  const [result, setResult]     = useState(null);
  const [loading, setLoading]   = useState(false);

  const handleValidate = async () => {
    try {
      const res = await agentApi.validate(form.fabric_code);
      setValidation(res.data);
    } catch { setValidation({ valid: false, message: '서버 오류' }); }
  };

  const handleAnalyze = async () => {
    if (!form.release_qty || !form.due_date) return;
    setLoading(true); setResult(null);
    try {
      const res = await agentApi.analyze({
        fabric_code: form.fabric_code,
        color_code:  form.color_code,
        release_qty: Number(form.release_qty),
        due_date:    form.due_date,
      });
      setResult(res.data);
      onRefresh();
    } catch (err) {
      setResult({ deadline_status: '오류', warnings: [err.response?.data?.detail || '분석 실패'], instructions: [], is_valid: false });
    } finally { setLoading(false); }
  };

  const STATUS_CLS = {
    납기가능: 'result-ok',
    납기위험: 'result-warn',
    납기불가: 'result-danger',
    오류:     'result-danger',
  };

  return (
    <div className="ai-panel-dropdown">
      <div className="ai-panel-header">
        <span>✦ AI 납기 분석</span>
        <button onClick={onClose} className="ai-panel-close">×</button>
      </div>

      <div className="ai-panel-body">
        <div className="ai-field">
          <label>원단코드</label>
          <div style={{ display: 'flex', gap: 6 }}>
            <select value={form.fabric_code}
              onChange={e => { setForm(f => ({ ...f, fabric_code: e.target.value })); setValidation(null); setResult(null); }}
              className="ai-select">
              {FABRIC_CODES.map(c => <option key={c} value={c}>{FABRIC_NAMES[c]}</option>)}
            </select>
            <button onClick={handleValidate} className="ai-validate-btn">검증</button>
          </div>
          {validation && (
            <p className={validation.valid ? 'valid-ok' : 'valid-err'}>{validation.message}</p>
          )}
        </div>

        <div className="ai-field">
          <label>컬러코드</label>
          <select value={form.color_code}
            onChange={e => { setForm(f => ({ ...f, color_code: e.target.value })); setResult(null); }}
            className="ai-select">
            {COLOR_CODES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="ai-field">
          <label>주문량 (야드)</label>
          <input type="number" placeholder="야드" value={form.release_qty}
            onChange={e => { setForm(f => ({ ...f, release_qty: e.target.value })); setResult(null); }}
            className="ai-input" />
        </div>

        <div className="ai-field">
          <label>납기일</label>
          <input type="date" value={form.due_date}
            onChange={e => { setForm(f => ({ ...f, due_date: e.target.value })); setResult(null); }}
            className="ai-input" />
        </div>

        <button onClick={handleAnalyze}
          disabled={loading || !form.release_qty || !form.due_date}
          className="ai-analyze-submit">
          {loading ? '분석 중...' : '분석하기'}
        </button>
      </div>

      {result && (
        <div className={`ai-result ${STATUS_CLS[result.deadline_status] || 'result-ok'}`}>
          <p className="ai-result-title">
            {result.deadline_status}
            {result.days_remaining != null ? ` — D-${result.days_remaining}` : ''}
          </p>
          {result.is_valid && (
            <>
              <p>소요: {result.required_hours}h ({result.required_days}일)</p>
              <p>{result.raw_material}: {result.raw_needed}{result.raw_unit} 필요</p>
              <p className={result.stock_ok ? 'text-ok' : 'text-err'}>
                재고: {result.stock_ok ? '✅ 충분' : '⚠ 부족'} ({result.stock_qty?.toLocaleString()}야드)
              </p>
            </>
          )}
          {result.warnings?.map((w, i) => <p key={i}>{w}</p>)}
          {result.instructions?.map((ins, i) => <p key={i} style={{ opacity: 0.75 }}>{ins}</p>)}
        </div>
      )}
    </div>
  );
}

/* ── 달력 아이콘 ─────────────────────────── */
function CalIcon() {
  return (
    <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#9ca3af' }}>
      <rect x="3" y="4" width="18" height="18" rx="2" strokeWidth="2" />
      <path d="M16 2v4M8 2v4M3 10h18" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/* ── 미니 달력 ───────────────────────────── */
function MiniCalendar({ value, onChange, align = 'left' }) {
  const init  = value ? new Date(value + 'T00:00:00') : new Date();
  const [year,  setYear]  = useState(init.getFullYear());
  const [month, setMonth] = useState(init.getMonth());

  const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
  const firstDay    = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const select = (d) => {
    if (!d) return;
    onChange(`${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`);
  };
  const prevMonth = () => { if (month === 0) { setYear(y => y - 1); setMonth(11); } else setMonth(m => m - 1); };
  const nextMonth = () => { if (month === 11) { setYear(y => y + 1); setMonth(0); } else setMonth(m => m + 1); };

  const isSelected = (d) => {
    if (!d || !value) return false;
    const v = new Date(value + 'T00:00:00');
    return v.getFullYear() === year && v.getMonth() === month && v.getDate() === d;
  };
  const todayD = new Date();
  const isToday = (d) => d && todayD.getFullYear() === year && todayD.getMonth() === month && todayD.getDate() === d;

  return (
    <div className={`mini-cal ${align === 'right' ? 'right' : 'left'}`}>
      <div className="mini-cal-header">
        <button onClick={prevMonth} className="mini-cal-nav">‹</button>
        <span>{year}년 {month + 1}월</span>
        <button onClick={nextMonth} className="mini-cal-nav">›</button>
      </div>
      <div className="mini-cal-days">
        {DAYS.map((d, i) => (
          <div key={d} className={`mini-cal-day-label ${i === 0 ? 'sun' : i === 6 ? 'sat' : ''}`}>{d}</div>
        ))}
      </div>
      <div className="mini-cal-cells">
        {cells.map((d, i) => (
          <button key={i} onClick={() => select(d)} disabled={!d}
            className={`mini-cal-cell
              ${!d ? 'invisible' : ''}
              ${isSelected(d) ? 'selected' : ''}
              ${isToday(d) && !isSelected(d) ? 'today' : ''}
              ${i % 7 === 0 && d ? 'sun-cell' : ''}
              ${i % 7 === 6 && d ? 'sat-cell' : ''}
            `}>
            {d ?? ''}
          </button>
        ))}
      </div>
    </div>
  );
}
