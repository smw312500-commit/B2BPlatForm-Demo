import { useEffect, useRef, useState } from 'react'
import Header from './components/Header'
import AgentPanel from './components/AgentPanel'
import CompleteTab from './components/tabs/CompleteTab'
import OrderTab from './components/tabs/OrderTab'
import PlatformReportTab from './components/tabs/PlatformReportTab'
import ProductionTab from './components/tabs/ProductionTab'
import StockTab from './components/tabs/StockTab'
import { analyzeOrder, getAgentStatus, validateLabelCode } from './services/api'

const TABS = [
  { id: 'stock', label: '재고' },
  { id: 'order', label: '발주' },
  { id: 'production', label: '생산' },
  { id: 'complete', label: '완료' },
  { id: 'platform-report', label: '케어라벨사 채팅창' },
]

function toISO(date) {
  return date.toISOString().split('T')[0]
}

function formatDday(daysRemaining) {
  return daysRemaining >= 0 ? `D-${daysRemaining}` : `D+${Math.abs(daysRemaining)}`
}

function formatWeight(value) {
  return typeof value === 'number' ? `${value.toLocaleString()}kg` : '-'
}

export default function App() {
  const [activeTab, setActiveTab] = useState('stock')
  const [searched, setSearched] = useState(null)
  const [pickerOpen, setPickerOpen] = useState(null)
  const [aiPanelOpen, setAiPanelOpen] = useState(false)

  const [agentStatus, setAgentStatus] = useState(null)
  const [agentStatusLoading, setAgentStatusLoading] = useState(true)
  const [agentLastUpdated, setAgentLastUpdated] = useState(null)

  const todayStr = toISO(new Date())
  const [dateFrom, setDateFrom] = useState(`${todayStr.slice(0, 7)}-01`)
  const [dateTo, setDateTo] = useState(todayStr)

  const pickerRef = useRef(null)
  const aiRef = useRef(null)

  const fetchAgentStatus = async () => {
    try {
      const response = await getAgentStatus()
      setAgentStatus(response.data)
      setAgentLastUpdated(new Date())
    } catch {
      setAgentStatus(null)
    } finally {
      setAgentStatusLoading(false)
    }
  }

  const syncAgentStatus = (nextStatus) => {
    setAgentStatus(nextStatus)
    setAgentLastUpdated(new Date())
    setAgentStatusLoading(false)
  }

  useEffect(() => {
    fetchAgentStatus()
  }, [])

  useEffect(() => {
    const handler = (event) => {
      if (pickerRef.current && !pickerRef.current.contains(event.target)) {
        setPickerOpen(null)
      }
      if (aiRef.current && !aiRef.current.contains(event.target)) {
        setAiPanelOpen(false)
      }
    }

    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <div className="bg-white border-b border-gray-200 px-4 flex items-center justify-between">
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 py-2">
          <div className="relative" ref={aiRef}>
            <button
              onClick={() => setAiPanelOpen((open) => !open)}
              className={`flex items-center gap-1.5 text-sm px-4 py-1.5 rounded border shadow-sm transition-colors ${
                aiPanelOpen
                  ? 'bg-purple-600 text-white border-purple-600'
                  : 'bg-white text-purple-700 border-purple-300 hover:bg-purple-50'
              }`}
            >
              <span>AI 납기 분석</span>
            </button>
            {aiPanelOpen && <AiAnalysisPanel onClose={() => setAiPanelOpen(false)} />}
          </div>

          <div className="w-px h-5 bg-gray-200" />

          <div className="flex items-center gap-2" ref={pickerRef}>
            <div className="relative">
              <button
                onClick={() => setPickerOpen(pickerOpen === 'from' ? null : 'from')}
                className="flex items-center gap-1.5 border rounded px-3 py-1.5 text-sm bg-white hover:bg-gray-50 shadow-sm"
              >
                <CalIcon />
                <span className="text-gray-700">{dateFrom}</span>
              </button>
              {pickerOpen === 'from' && (
                <MiniCalendar
                  value={dateFrom}
                  onChange={(value) => {
                    setDateFrom(value)
                    setPickerOpen(null)
                  }}
                />
              )}
            </div>

            <span className="text-gray-400 text-sm">~</span>

            <div className="relative">
              <button
                onClick={() => setPickerOpen(pickerOpen === 'to' ? null : 'to')}
                className="flex items-center gap-1.5 border rounded px-3 py-1.5 text-sm bg-white hover:bg-gray-50 shadow-sm"
              >
                <CalIcon />
                <span className="text-gray-700">{dateTo}</span>
              </button>
              {pickerOpen === 'to' && (
                <MiniCalendar
                  value={dateTo}
                  align="right"
                  onChange={(value) => {
                    setDateTo(value)
                    setPickerOpen(null)
                  }}
                />
              )}
            </div>

            <button
              onClick={() => setSearched({ from: dateFrom, to: dateTo })}
              className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded hover:bg-blue-700 shadow-sm"
            >
              조회
            </button>

            {searched && (
              <button
                onClick={() => setSearched(null)}
                className="text-xs text-gray-400 hover:underline"
              >
                초기화
              </button>
            )}
          </div>
        </div>
      </div>

      {searched && (
        <div className="bg-blue-50 border-b border-blue-100 px-5 py-1.5 text-xs text-blue-600">
          {searched.from} ~ {searched.to} 기간 조회 중
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-scroll p-4">
          {activeTab === 'stock' && <StockTab searched={searched} />}
          {activeTab === 'order' && <OrderTab searched={searched} onReportRefresh={fetchAgentStatus} />}
          {activeTab === 'production' && (
            <ProductionTab
              searched={searched}
              onAgentStatusSync={syncAgentStatus}
            />
          )}
          {activeTab === 'complete' && (
            <CompleteTab searched={searched} onReportRefresh={fetchAgentStatus} />
          )}
          {activeTab === 'platform-report' && (
            <PlatformReportTab
              status={agentStatus}
              loading={agentStatusLoading}
              lastUpdated={agentLastUpdated}
              onRefresh={fetchAgentStatus}
            />
          )}
        </div>

        <div className="w-80 border-l border-gray-200 bg-white overflow-y-auto flex-shrink-0">
          <AgentPanel
            status={agentStatus}
            loading={agentStatusLoading}
            lastUpdated={agentLastUpdated}
            onRefresh={fetchAgentStatus}
          />
        </div>
      </div>
    </div>
  )
}

function AiAnalysisPanel({ onClose }) {
  const [form, setForm] = useState({ label_code: '', release_qty: '', due_date: '' })
  const [validation, setValidation] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleValidate = async () => {
    if (!form.label_code) return
    try {
      const response = await validateLabelCode(form.label_code)
      setValidation(response.data)
    } catch {
      setValidation({ valid: false, message: '서버 오류' })
    }
  }

  const handleAnalyze = async () => {
    if (!form.label_code || !form.release_qty || !form.due_date) return

    setLoading(true)
    setResult(null)

    try {
      const response = await analyzeOrder({
        label_code: form.label_code,
        release_qty: Number(form.release_qty),
        due_date: form.due_date,
      })
      setResult(response.data)
    } catch (error) {
      setResult({
        deadline_status: '오류',
        warnings: [error.response?.data?.detail || '분석 실패'],
        instructions: [],
        is_valid: false,
      })
    } finally {
      setLoading(false)
    }
  }

  const statusClassName = {
    납기가능: 'bg-green-50 border-green-300 text-green-800',
    납기위험: 'bg-yellow-50 border-yellow-300 text-yellow-800',
    납기불가: 'bg-red-50 border-red-300 text-red-800',
    오류: 'bg-red-50 border-red-300 text-red-800',
  }

  return (
    <div className="absolute right-0 top-10 z-50 bg-white border border-purple-200 rounded-lg shadow-xl p-4 w-80">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-purple-700">AI 납기 분석</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">
          ×
        </button>
      </div>

      <div className="space-y-2 text-sm">
        <div>
          <label className="text-xs text-gray-500">라벨코드 (9자리)</label>
          <div className="flex gap-1 mt-1">
            <input
              type="text"
              maxLength={9}
              value={form.label_code}
              onChange={(event) => {
                setForm((prev) => ({ ...prev, label_code: event.target.value.toUpperCase() }))
                setValidation(null)
                setResult(null)
              }}
              className="flex-1 border rounded px-2 py-1.5 font-mono text-sm uppercase"
              placeholder="W3MJW01NV"
            />
            <button
              type="button"
              onClick={handleValidate}
              className="text-xs bg-gray-100 px-2 rounded hover:bg-gray-200 border"
            >
              검증
            </button>
          </div>
          {validation && (
            <p className={`text-xs mt-1 ${validation.valid ? 'text-green-600' : 'text-red-600'}`}>
              {validation.valid ? '정상' : '오류'} {validation.message}
            </p>
          )}
        </div>

        <div>
          <label className="text-xs text-gray-500">주문수량 (장)</label>
          <input
            type="number"
            value={form.release_qty}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, release_qty: event.target.value }))
              setResult(null)
            }}
            className="w-full border rounded px-2 py-1.5 mt-1 text-sm"
            placeholder="수량"
          />
        </div>

        <div>
          <label className="text-xs text-gray-500">납기일</label>
          <input
            type="date"
            value={form.due_date}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, due_date: event.target.value }))
              setResult(null)
            }}
            className="w-full border rounded px-2 py-1.5 mt-1 text-sm"
          />
        </div>

        <button
          onClick={handleAnalyze}
          disabled={loading || !form.label_code || !form.release_qty || !form.due_date}
          className="w-full bg-purple-600 text-white py-2 rounded hover:bg-purple-700 disabled:opacity-40 text-sm font-medium"
        >
          {loading ? '분석 중..' : '분석하기'}
        </button>
      </div>

      {result && (
        <div
          className={`mt-3 rounded border p-3 text-xs space-y-1 ${
            statusClassName[result.deadline_status] || 'bg-gray-50 border-gray-200'
          }`}
        >
          <p className="font-bold text-sm">
            {result.deadline_status}
            {result.days_remaining != null ? ` / ${formatDday(result.days_remaining)}` : ''}
          </p>

          {result.is_valid && (
            <>
              <p>소요: {result.required_hours}h ({result.required_days}일)</p>
              <p>필요 원단: {result.required_fabric_m}m / 필요 잉크: {result.required_ink_count}통</p>
              <p>완료중량: {formatWeight(result.product_weight_kg)}</p>
              <p>원단중량: {formatWeight(result.required_fabric_weight_kg)}</p>
              <p>잉크중량: {formatWeight(result.required_ink_weight_kg)}</p>
              <p>원자재 합계중량: {formatWeight(result.required_material_weight_kg)}</p>
              {result.estimated_completion_at && (
                <p>완료예정: {result.estimated_completion_at.replace('T', ' ')}</p>
              )}
              <p className={result.stock_ok ? 'text-green-700' : 'text-red-600'}>
                재고: {result.stock_ok ? '충분' : '부족'}
              </p>
            </>
          )}

          {result.warnings?.map((warning, index) => (
            <p key={`warning-${index}`}>{warning}</p>
          ))}
          {result.instructions?.map((instruction, index) => (
            <p key={`instruction-${index}`} className="opacity-75">
              {instruction}
            </p>
          ))}
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
  const initialDate = value ? new Date(`${value}T00:00:00`) : new Date()
  const [year, setYear] = useState(initialDate.getFullYear())
  const [month, setMonth] = useState(initialDate.getMonth())

  const days = ['일', '월', '화', '수', '목', '금', '토']
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const cells = []
  for (let index = 0; index < firstDay; index += 1) cells.push(null)
  for (let day = 1; day <= daysInMonth; day += 1) cells.push(day)

  const select = (day) => {
    if (!day) return
    onChange(`${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`)
  }

  const prevMonth = () => {
    if (month === 0) {
      setYear((current) => current - 1)
      setMonth(11)
      return
    }
    setMonth((current) => current - 1)
  }

  const nextMonth = () => {
    if (month === 11) {
      setYear((current) => current + 1)
      setMonth(0)
      return
    }
    setMonth((current) => current + 1)
  }

  const isSelected = (day) => {
    if (!day || !value) return false
    const selected = new Date(`${value}T00:00:00`)
    return (
      selected.getFullYear() === year &&
      selected.getMonth() === month &&
      selected.getDate() === day
    )
  }

  const today = new Date()
  const isToday = (day) =>
    day &&
    today.getFullYear() === year &&
    today.getMonth() === month &&
    today.getDate() === day

  return (
    <div
      className={`absolute top-10 z-50 bg-white border border-gray-200 rounded-lg shadow-xl p-3 w-64 ${
        align === 'right' ? 'right-0' : 'left-0'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={prevMonth}
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-600 text-lg"
        >
          ‹
        </button>
        <span className="text-sm font-semibold">
          {year}년 {month + 1}월
        </span>
        <button
          onClick={nextMonth}
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-600 text-lg"
        >
          ›
        </button>
      </div>

      <div className="grid grid-cols-7 mb-1">
        {days.map((day, index) => (
          <div
            key={day}
            className={`text-center text-xs py-1 font-medium ${
              index === 0 ? 'text-red-400' : index === 6 ? 'text-blue-400' : 'text-gray-500'
            }`}
          >
            {day}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-y-1">
        {cells.map((day, index) => (
          <button
            key={`${year}-${month}-${index}`}
            onClick={() => select(day)}
            disabled={!day}
            className={`text-xs py-1.5 rounded text-center transition-colors ${
              !day
                ? 'invisible'
                : isSelected(day)
                  ? 'bg-blue-600 text-white font-bold'
                  : isToday(day)
                    ? 'bg-blue-50 text-blue-600 font-semibold ring-1 ring-blue-300'
                    : index % 7 === 0
                      ? 'text-red-500 hover:bg-red-50'
                      : index % 7 === 6
                        ? 'text-blue-500 hover:bg-blue-50'
                        : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            {day ?? ''}
          </button>
        ))}
      </div>
    </div>
  )
}
