import { useEffect, useRef, useState } from 'react'
import Header from './components/Header'
import StockTab from './components/tabs/StockTab'
import OrderTab from './components/tabs/OrderTab'
import ProductionTab from './components/tabs/ProductionTab'
import CompleteTab from './components/tabs/CompleteTab'
import PlatformReportTab from './components/tabs/PlatformReportTab'
import AgentPanel from './components/AgentPanel'
import { analyzeOrder, validateItem } from './services/api'

const TABS = [
  { id: 'stock',           label: '재고' },
  { id: 'order',           label: '발주' },
  { id: 'production',      label: '생산' },
  { id: 'complete',        label: '완료' },
  { id: 'platform-report', label: '지퍼단추사 채팅창' },
]

function toISO(d) { return d.toISOString().split('T')[0] }

export default function App() {
  const [activeTab, setActiveTab] = useState('stock')

  const todayStr = toISO(new Date())
  const [dateFrom, setDateFrom] = useState(todayStr.slice(0, 7) + '-01')
  const [dateTo,   setDateTo]   = useState(todayStr)
  const [searched, setSearched] = useState(null)

  const [pickerOpen, setPickerOpen]   = useState(null)
  const [aiPanelOpen, setAiPanelOpen] = useState(false)

  const pickerRef = useRef(null)
  const aiRef     = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) setPickerOpen(null)
      if (aiRef.current     && !aiRef.current.contains(e.target))     setAiPanelOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      {/* 탭 바 */}
      <div className="bg-white border-b border-gray-200 px-4 flex items-center justify-between">
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* 우측 툴바 */}
        <div className="flex items-center gap-2 py-2">

          {/* AI 납기 분석 버튼 */}
          <div className="relative" ref={aiRef}>
            <button onClick={() => setAiPanelOpen(!aiPanelOpen)}
              className={`flex items-center gap-1.5 text-sm px-4 py-1.5 rounded border shadow-sm transition-colors ${
                aiPanelOpen
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-indigo-700 border-indigo-300 hover:bg-indigo-50'
              }`}>
              <span>✦</span> AI 납기 분석
            </button>
            {aiPanelOpen && <AiAnalysisPanel onClose={() => setAiPanelOpen(false)} />}
          </div>

          <div className="w-px h-5 bg-gray-200" />

          {/* 날짜 필터 */}
          <div className="flex items-center gap-2" ref={pickerRef}>
            <div className="relative">
              <button onClick={() => setPickerOpen(pickerOpen === 'from' ? null : 'from')}
                className="flex items-center gap-1.5 border rounded px-3 py-1.5 text-sm bg-white hover:bg-gray-50 shadow-sm">
                <CalIcon /><span className="text-gray-700">{dateFrom}</span>
              </button>
              {pickerOpen === 'from' && (
                <MiniCalendar value={dateFrom} onChange={(v) => { setDateFrom(v); setPickerOpen(null) }} />
              )}
            </div>
            <span className="text-gray-400 text-sm">~</span>
            <div className="relative">
              <button onClick={() => setPickerOpen(pickerOpen === 'to' ? null : 'to')}
                className="flex items-center gap-1.5 border rounded px-3 py-1.5 text-sm bg-white hover:bg-gray-50 shadow-sm">
                <CalIcon /><span className="text-gray-700">{dateTo}</span>
              </button>
              {pickerOpen === 'to' && (
                <MiniCalendar value={dateTo} onChange={(v) => { setDateTo(v); setPickerOpen(null) }} align="right" />
              )}
            </div>
            <button onClick={() => setSearched({ from: dateFrom, to: dateTo })}
              className="bg-indigo-600 text-white text-sm px-4 py-1.5 rounded hover:bg-indigo-700 shadow-sm">
              조회
            </button>
            {searched && (
              <button onClick={() => setSearched(null)} className="text-xs text-gray-400 hover:underline">초기화</button>
            )}
          </div>
        </div>
      </div>

      {searched && (
        <div className="bg-indigo-50 border-b border-indigo-100 px-5 py-1.5 text-xs text-indigo-600">
          {searched.from} ~ {searched.to} 기간 조회 중
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-scroll p-4">
          {activeTab === 'stock'      && <StockTab      searched={searched} />}
          {activeTab === 'order'      && <OrderTab      searched={searched} />}
          {activeTab === 'production' && <ProductionTab searched={searched} />}
          {activeTab === 'complete'   && <CompleteTab   searched={searched} />}
          {activeTab === 'platform-report' && <PlatformReportTab />}
        </div>
        <div className="w-80 border-l border-gray-200 bg-white overflow-y-auto flex-shrink-0">
          <AgentPanel />
        </div>
      </div>
    </div>
  )
}

/* ── AI 납기 분석 패널 ───────────────────── */
const ITEM_OPTIONS = [
  'WOOD_BR','WOOD_BK','PLASTIC_BK','PLASTIC_WH','METAL_SV','METAL_BK','ZIPPER_S','ZIPPER_M','ZIPPER_L',
]

function AiAnalysisPanel({ onClose }) {
  const [form, setForm]           = useState({ item_name: 'WOOD_BR', release_qty: '', due_date: '' })
  const [validation, setValidation] = useState(null)
  const [result, setResult]       = useState(null)
  const [loading, setLoading]     = useState(false)

  const handleValidate = async () => {
    try {
      const res = await validateItem(form.item_name)
      setValidation(res.data)
    } catch { setValidation({ valid: false, message: '서버 오류' }) }
  }

  const handleAnalyze = async () => {
    if (!form.item_name || !form.release_qty || !form.due_date) return
    setLoading(true); setResult(null)
    try {
      const res = await analyzeOrder({
        item_name:   form.item_name,
        release_qty: Number(form.release_qty),
        due_date:    form.due_date,
      })
      setResult(res.data)
    } catch (err) {
      setResult({ deadline_status: '오류', warnings: [err.response?.data?.detail || '분석 실패'], instructions: [], is_valid: false })
    } finally { setLoading(false) }
  }

  const STATUS_CLS = {
    납기가능: 'bg-green-50 border-green-300 text-green-800',
    납기위험: 'bg-yellow-50 border-yellow-300 text-yellow-800',
    납기불가: 'bg-red-50 border-red-300 text-red-800',
    오류:     'bg-red-50 border-red-300 text-red-800',
  }

  return (
    <div className="absolute right-0 top-10 z-50 bg-white border border-indigo-200 rounded-lg shadow-xl p-4 w-80">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-indigo-700">✦ AI 납기 분석</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
      </div>

      <div className="space-y-2 text-sm">
        <div>
          <label className="text-xs text-gray-500">품목코드</label>
          <div className="flex gap-1 mt-1">
            <select value={form.item_name}
              onChange={(e) => { setForm({ ...form, item_name: e.target.value }); setValidation(null); setResult(null) }}
              className="flex-1 border rounded px-2 py-1.5 font-mono text-sm">
              {ITEM_OPTIONS.map((o) => <option key={o}>{o}</option>)}
            </select>
            <button type="button" onClick={handleValidate}
              className="text-xs bg-gray-100 px-2 rounded hover:bg-gray-200 border">검증</button>
          </div>
          {validation && (
            <p className={`text-xs mt-1 ${validation.valid ? 'text-green-600' : 'text-red-600'}`}>
              {validation.message}
            </p>
          )}
        </div>

        <div>
          <label className="text-xs text-gray-500">주문량 (개)</label>
          <input type="number" value={form.release_qty}
            onChange={(e) => { setForm({ ...form, release_qty: e.target.value }); setResult(null) }}
            className="w-full border rounded px-2 py-1.5 mt-1 text-sm" placeholder="수량" />
        </div>

        <div>
          <label className="text-xs text-gray-500">납기일</label>
          <input type="date" value={form.due_date}
            onChange={(e) => { setForm({ ...form, due_date: e.target.value }); setResult(null) }}
            className="w-full border rounded px-2 py-1.5 mt-1 text-sm" />
        </div>

        <button onClick={handleAnalyze} disabled={loading || !form.release_qty || !form.due_date}
          className="w-full bg-indigo-600 text-white py-2 rounded hover:bg-indigo-700 disabled:opacity-40 text-sm font-medium">
          {loading ? '분석 중...' : '분석하기'}
        </button>
      </div>

      {result && (
        <div className={`mt-3 rounded border p-3 text-xs space-y-1 ${STATUS_CLS[result.deadline_status] || 'bg-gray-50 border-gray-200'}`}>
          <p className="font-bold text-sm">
            {result.deadline_status}
            {result.days_remaining != null ? ` — D-${result.days_remaining}` : ''}
          </p>
          {result.is_valid && (
            <>
              <p>소요: {result.required_hours}h ({result.required_days}일)</p>
              <p>원자재({result.raw_material}): {result.raw_needed}{result.raw_unit} 필요</p>
              <p className={result.stock_ok ? 'text-green-700' : 'text-red-600'}>
                재고: {result.stock_ok ? '✅ 충분' : '⚠ 부족'}
              </p>
            </>
          )}
          {result.warnings?.map((w, i) => <p key={i}>{w}</p>)}
          {result.instructions?.map((ins, i) => <p key={i} className="opacity-75">{ins}</p>)}
        </div>
      )}
    </div>
  )
}

function CalIcon() {
  return (
    <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <rect x="3" y="4" width="18" height="18" rx="2" strokeWidth="2" />
      <path d="M16 2v4M8 2v4M3 10h18" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function MiniCalendar({ value, onChange, align = 'left' }) {
  const init  = value ? new Date(value + 'T00:00:00') : new Date()
  const [year,  setYear]  = useState(init.getFullYear())
  const [month, setMonth] = useState(init.getMonth())

  const DAYS = ['일', '월', '화', '수', '목', '금', '토']
  const firstDay    = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  const select = (d) => {
    if (!d) return
    onChange(`${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`)
  }
  const prevMonth = () => { if (month === 0) { setYear(y => y - 1); setMonth(11) } else setMonth(m => m - 1) }
  const nextMonth = () => { if (month === 11) { setYear(y => y + 1); setMonth(0) }  else setMonth(m => m + 1) }

  const isSelected = (d) => {
    if (!d || !value) return false
    const v = new Date(value + 'T00:00:00')
    return v.getFullYear() === year && v.getMonth() === month && v.getDate() === d
  }
  const today = new Date()
  const isToday = (d) => d && today.getFullYear() === year && today.getMonth() === month && today.getDate() === d

  return (
    <div className={`absolute top-10 z-50 bg-white border border-gray-200 rounded-lg shadow-xl p-3 w-64 ${align === 'right' ? 'right-0' : 'left-0'}`}>
      <div className="flex items-center justify-between mb-2">
        <button onClick={prevMonth} className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-600 text-lg">‹</button>
        <span className="text-sm font-semibold">{year}년 {month + 1}월</span>
        <button onClick={nextMonth} className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-600 text-lg">›</button>
      </div>
      <div className="grid grid-cols-7 mb-1">
        {DAYS.map((d, i) => (
          <div key={d} className={`text-center text-xs py-1 font-medium ${i === 0 ? 'text-red-400' : i === 6 ? 'text-blue-400' : 'text-gray-500'}`}>{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-y-1">
        {cells.map((d, i) => (
          <button key={i} onClick={() => select(d)} disabled={!d}
            className={`text-xs py-1.5 rounded text-center transition-colors
              ${!d ? 'invisible' :
                isSelected(d)  ? 'bg-indigo-600 text-white font-bold' :
                isToday(d)     ? 'bg-indigo-50 text-indigo-600 font-semibold ring-1 ring-indigo-300' :
                i % 7 === 0    ? 'text-red-500 hover:bg-red-50' :
                i % 7 === 6    ? 'text-blue-500 hover:bg-blue-50' :
                                 'text-gray-700 hover:bg-gray-100'}`}>
            {d ?? ''}
          </button>
        ))}
      </div>
    </div>
  )
}
