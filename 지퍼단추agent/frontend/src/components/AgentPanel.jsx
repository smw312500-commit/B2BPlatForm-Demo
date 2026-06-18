import { useEffect, useState, useCallback } from 'react'
import { getAgentStatus } from '../services/api'

const LEVEL_TONE = {
  정상: 'bg-gray-50 border-gray-200 text-gray-700',
  경고: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  긴급: 'bg-red-50 border-red-200 text-red-700',
}

const DEADLINE_TONE = {
  납기가능: 'bg-blue-50 border-blue-200 text-blue-700',
  납기위험: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  납기불가: 'bg-red-50 border-red-200 text-red-700',
}

function fmtDT(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('ko-KR', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export default function AgentPanel() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await getAgentStatus()
      setStatus(res.data)
    } catch {
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const t = setInterval(fetchStatus, 30_000)
    return () => clearInterval(t)
  }, [fetchStatus])

  return (
    <div className="p-4 h-full flex flex-col gap-4 overflow-y-auto">
      <div className="flex items-center justify-between border-b pb-2">
        <h2 className="text-sm font-bold text-gray-700">AI Agent · 지퍼단추사</h2>
        <button onClick={fetchStatus} className="text-xs text-indigo-600 hover:underline">새로고침</button>
      </div>

      {loading ? (
        <p className="text-xs text-gray-400">불러오는 중...</p>
      ) : !status ? (
        <p className="text-xs text-red-500">서버 연결 오류</p>
      ) : (
        <>
          {/* 완제품 / 원자재 재고 판단 */}
          <Section title="완제품 / 원자재 재고">
            <p className="text-[11px] text-gray-400 mb-1.5">완제품: 별도 재고 없음 — 생산중 주문 합계로 표시</p>
            <div className="space-y-1.5 mb-2">
              {status.stock_summary?.length === 0 ? (
                <p className="text-xs text-gray-400">생산중인 품목 없음</p>
              ) : status.stock_summary?.map((s) => (
                <div key={s.item_name} className="flex justify-between items-center rounded px-3 py-1.5 text-xs bg-gray-50 border border-gray-200">
                  <span className="font-mono font-semibold">{s.item_name}</span>
                  <span className="text-gray-600">{s.in_production_qty.toLocaleString()}개 ({s.order_count}건)</span>
                </div>
              ))}
            </div>
            <div className="space-y-1.5">
              {status.raw_material_summary?.map((m) => (
                <div key={m.material_name} className={`flex justify-between items-center rounded px-3 py-1.5 text-xs border ${LEVEL_TONE[m.level] ?? LEVEL_TONE.정상}`}>
                  <span className="font-medium">{m.material_name}</span>
                  <span className="font-bold">
                    {Number(m.current_qty).toLocaleString()}{m.unit}
                    <span className="font-normal text-gray-400"> / 안전 {m.safe_qty}{m.unit}</span>
                  </span>
                </div>
              ))}
            </div>
          </Section>

          {/* 납기 위험 주문 */}
          <Section title={`납기 위험 주문 (${status.risk_items?.length ?? 0}건)`}>
            {status.risk_items?.length === 0 ? (
              <p className="text-xs text-gray-400">납기 위험/불가 주문 없음</p>
            ) : status.risk_items?.map((r) => (
              <div key={r.id} className={`rounded px-3 py-2 text-xs mb-1.5 border ${DEADLINE_TONE[r.deadline_status] ?? DEADLINE_TONE.납기위험}`}>
                <div className="flex justify-between font-bold">
                  <span className="font-mono">{r.item_name}</span>
                  <span>{r.deadline_status}</span>
                </div>
                <p className="mt-0.5">{r.message}</p>
              </div>
            ))}
          </Section>

          {/* 오늘 작업 우선순위 */}
          <Section title="오늘 작업 우선순위">
            {status.schedule_recommendations?.length === 0 ? (
              <p className="text-xs text-gray-400">진행중인 생산 주문 없음</p>
            ) : status.schedule_recommendations?.map((r) => (
              <div key={r.id} className="flex items-start gap-2 text-xs mb-1.5">
                <span className="shrink-0 font-bold text-indigo-600">{r.priority}.</span>
                <div>
                  <span className="font-mono font-semibold">{r.item_name}</span>
                  <span className="text-gray-500 ml-1">{r.release_qty.toLocaleString()}개 · 납기 {r.due_date}</span>
                  <p className="text-gray-500 mt-0.5">{r.reason}</p>
                </div>
              </div>
            ))}
          </Section>

          {/* 트렌드 신호 */}
          <Section title="트렌드 신호">
            {status.trend_signals?.length === 0 ? (
              <p className="text-xs text-gray-400">감지된 트렌드 신호 없음</p>
            ) : status.trend_signals?.map((t, i) => (
              <div key={i} className="rounded px-3 py-2 text-xs mb-1.5 bg-emerald-50 border border-emerald-200 text-emerald-800">
                <p className="font-bold">📈 {t.signal}</p>
                <p className="text-gray-500 mt-0.5">{t.basis}</p>
              </div>
            ))}
          </Section>

          {/* AI 지시사항 */}
          {status.next_actions?.length > 0 && (
            <Section title="AI 지시사항">
              <div className="space-y-1">
                {status.next_actions.map((a, i) => (
                  <p key={i} className="text-xs bg-yellow-50 border border-yellow-200 rounded px-2 py-1 text-yellow-800">{a}</p>
                ))}
              </div>
            </Section>
          )}

          {/* 플랫폼 보고 상태 */}
          <Section title="플랫폼 보고 상태">
            <p className="text-xs bg-gray-50 border border-gray-200 rounded px-2 py-1.5 text-gray-500">
              {status.platform_report_status?.summary ?? '최근 플랫폼 보고 없음'}
            </p>
            {(status.platform_report_status?.success_count != null || status.platform_report_status?.waiting_count != null) && (
              <p className="text-[11px] text-gray-400 mt-1 px-0.5">
                전송완료 {status.platform_report_status?.success_count ?? 0}건 / 대기 {status.platform_report_status?.waiting_count ?? 0}건
              </p>
            )}
          </Section>

          <p className="text-[10px] text-gray-300 mt-auto">기준시각 {fmtDT(status.generated_at)}</p>
        </>
      )}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 mb-2">{title}</p>
      {children}
    </div>
  )
}
