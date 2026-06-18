import { useState, useRef, useEffect } from 'react'
import { queryInsight } from '../api'

const SUGGESTED = [
  '최근 6개월 생산성이 어때?',
  '자재 입고 지연 추이 보여줘',
  '공급사별 평균 지연일 비교해줘',
  '물류 배차 성과가 어떤가?',
  '라벨사 납기여유일이 악화되고 있어?',
  '2023년부터 2026년까지 전체 추이 분석해줘',
]

function MiniChart({ chart }) {
  if (!chart || !chart.data?.length || !chart.lines?.length) return null

  const { type = 'line', title, data, lines, y_label = '' } = chart

  const W = 380
  const H = 180
  const pad = { top: 20, right: 12, bottom: 44, left: 46 }
  const innerW = W - pad.left - pad.right
  const innerH = H - pad.top - pad.bottom

  const allVals = lines.flatMap(({ key }) =>
    data.map((d) => (d[key] != null ? Number(d[key]) : null)).filter((v) => v != null)
  )
  if (!allVals.length) return null

  const rawMin = Math.min(...allVals)
  const rawMax = Math.max(...allVals)
  const minY = rawMin >= 0 ? 0 : rawMin
  const maxY = rawMax <= 0 ? 0 : rawMax
  const yRange = maxY - minY || 1

  const toY = (v) => pad.top + innerH - ((Number(v) - minY) / yRange) * innerH

  const toX = (i) =>
    type === 'bar'
      ? pad.left + (i + 0.5) * (innerW / data.length)
      : pad.left + (data.length > 1 ? (i / (data.length - 1)) * innerW : innerW / 2)

  const yTicks = Array.from({ length: 5 }, (_, i) => minY + (yRange * i) / 4)

  const xSkip = Math.max(1, Math.ceil(data.length / 6))

  const shortenLabel = (name) =>
    String(name)
      .replace(/^20(\d{2})-Q/, "'$1-Q")
      .replace(/^20(\d{2})$/, "'$1")

  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      {title && (
        <p className="mb-1.5 text-[11px] font-semibold text-slate-600">{title}</p>
      )}
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
        {/* Y gridlines + labels */}
        {yTicks.map((tick, i) => (
          <g key={i}>
            <line
              x1={pad.left}
              x2={W - pad.right}
              y1={toY(tick)}
              y2={toY(tick)}
              stroke="#e2e8f0"
              strokeWidth="1"
            />
            <text
              x={pad.left - 5}
              y={toY(tick) + 3.5}
              textAnchor="end"
              fontSize="9"
              fill="#94a3b8"
            >
              {Number(tick.toFixed(1))}
            </text>
          </g>
        ))}

        {/* Y unit label */}
        {y_label && (
          <text
            x={10}
            y={pad.top + innerH / 2}
            textAnchor="middle"
            fontSize="8"
            fill="#94a3b8"
            transform={`rotate(-90,10,${pad.top + innerH / 2})`}
          >
            {y_label}
          </text>
        )}

        {/* X axis baseline */}
        <line
          x1={pad.left}
          x2={W - pad.right}
          y1={toY(0) > pad.top + innerH ? pad.top + innerH : toY(0)}
          y2={toY(0) > pad.top + innerH ? pad.top + innerH : toY(0)}
          stroke="#cbd5e1"
          strokeWidth="1"
        />

        {/* X labels */}
        {data.map((d, i) => {
          if (i % xSkip !== 0 && i !== data.length - 1) return null
          return (
            <text
              key={i}
              x={toX(i)}
              y={H - pad.bottom + 14}
              textAnchor="middle"
              fontSize="8"
              fill="#94a3b8"
            >
              {shortenLabel(d.name)}
            </text>
          )
        })}

        {/* Lines */}
        {type === 'line' &&
          lines.map(({ key, color }) => {
            const validPts = data
              .map((d, i) => (d[key] != null ? [toX(i), toY(d[key])] : null))
              .filter(Boolean)
            if (!validPts.length) return null
            return (
              <g key={key}>
                <polyline
                  points={validPts.map(([x, y]) => `${x},${y}`).join(' ')}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                {data.map((d, i) =>
                  d[key] != null ? (
                    <circle
                      key={i}
                      cx={toX(i)}
                      cy={toY(d[key])}
                      r="3"
                      fill={color}
                      stroke="white"
                      strokeWidth="1.5"
                    />
                  ) : null
                )}
              </g>
            )
          })}

        {/* Bars */}
        {type === 'bar' &&
          lines.map(({ key, color }, li) => {
            const groupW = innerW / data.length
            const barW = Math.max(4, (groupW - 4) / lines.length - 2)
            const groupOffset = (li - (lines.length - 1) / 2) * (barW + 2)
            return data.map((d, i) => {
              if (d[key] == null) return null
              const cx = toX(i) + groupOffset
              const yTop = toY(Math.max(0, Number(d[key])))
              const yBot = toY(0) > pad.top + innerH ? pad.top + innerH : toY(0)
              const barH = Math.abs(yBot - yTop)
              return (
                <rect
                  key={`${li}-${i}`}
                  x={cx - barW / 2}
                  y={Math.min(yTop, yBot)}
                  width={barW}
                  height={Math.max(barH, 1)}
                  fill={color}
                  rx="2"
                  opacity="0.85"
                />
              )
            })
          })}
      </svg>

      {lines.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-3">
          {lines.map(({ key, color }) => (
            <div key={key} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-5 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-[10px] text-slate-500">{key}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AIChatPanel({ open, onClose }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = async (question) => {
    const q = question.trim()
    if (!q || loading) return
    setMessages((prev) => [...prev, { type: 'user', content: q }])
    setInput('')
    setLoading(true)
    try {
      const res = await queryInsight(q)
      setMessages((prev) => [
        ...prev,
        {
          type: 'ai',
          content: res.data.answer,
          chart: res.data.chart,
          data_sources: res.data.data_sources,
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        { type: 'ai', content: '오류가 발생했습니다. 잠시 후 다시 시도해 주세요.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const clearChat = () => setMessages([])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 z-50 flex h-full w-[480px] max-w-full flex-col bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950 px-5 py-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base">🤖</span>
              <h2 className="text-sm font-bold text-white">AI 인사이트 채팅</h2>
            </div>
            <p className="mt-0.5 text-[11px] text-slate-400">
              공급망 데이터를 자연어로 질문하세요 · 독립 답변 모드
            </p>
          </div>
          <div className="flex items-center gap-3">
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
              >
                초기화
              </button>
            )}
            <button
              onClick={onClose}
              className="text-2xl leading-none text-slate-400 hover:text-white transition-colors"
            >
              ×
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <div>
              <p className="mb-3 text-xs font-medium text-slate-400">💡 질문 예시</p>
              <div className="flex flex-col gap-2">
                {SUGGESTED.map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-left text-xs text-slate-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((msg, i) =>
                msg.type === 'user' ? (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[78%] rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-2.5 text-sm leading-6 text-white">
                      {msg.content}
                    </div>
                  </div>
                ) : (
                  <div key={i} className="flex justify-start">
                    <div className="max-w-[94%]">
                      <div className="rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-3 text-sm leading-7 text-slate-800">
                        {msg.content}
                      </div>
                      {msg.chart && <MiniChart chart={msg.chart} />}
                      {msg.data_sources?.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {msg.data_sources.map((s) => (
                            <span
                              key={s}
                              className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-400"
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              )}

              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-3 text-sm text-slate-400">
                    <span className="animate-pulse">분석 중...</span>
                  </div>
                </div>
              )}

              <div ref={endRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-slate-200 bg-white p-4">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="질문을 입력하고 Enter..."
              disabled={loading}
              className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:opacity-50"
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || loading}
              className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              전송
            </button>
          </div>
          <p className="mt-2 text-center text-[10px] text-slate-400">
            각 질문은 독립적으로 처리됩니다 · demo 데이터 기반
          </p>
        </div>
      </div>
    </>
  )
}
