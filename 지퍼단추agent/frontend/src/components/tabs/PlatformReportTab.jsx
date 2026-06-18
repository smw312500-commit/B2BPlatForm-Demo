import { useEffect, useState, useCallback } from 'react'
import { getAgentStatus } from '../../services/api'

const STATUS_CLASS = {
  수신확인: 'bg-emerald-100 text-emerald-700',
  전송완료: 'bg-blue-100 text-blue-700',
  전송중: 'bg-sky-100 text-sky-700',
  '플랫폼 보고 대기': 'bg-amber-100 text-amber-800',
  실패: 'bg-rose-100 text-rose-700',
  오류: 'bg-rose-100 text-rose-700',
}

function formatDateTime(value) {
  if (!value) return '기록 없음'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).replace('T', ' ').slice(0, 16)
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date)
}

function formatNumber(value) {
  if (value == null || value === '') return '-'
  const number = Number(value)
  return Number.isNaN(number) ? String(value) : number.toLocaleString()
}

function formatWeight(value) {
  if (value == null || value === '') return null
  const number = Number(value)
  if (Number.isNaN(number)) return String(value)
  return `${number.toLocaleString()}kg`
}

function buildDetailRows(message) {
  const payload = message.payload || {}
  const aiReport = payload.ai_report || {}

  if (message.report_type === 'schedule') {
    return [
      ['품목', payload.item],
      ['수량', payload.qty != null ? `${formatNumber(payload.qty)}개` : null],
      ['납기', payload.due_date],
      ['예상완료', payload.estimated_completion ? formatDateTime(payload.estimated_completion) : null],
      ['상태', payload.status],
    ].filter(([, value]) => value)
  }

  if (message.report_type === 'reschedule') {
    return [
      ['대상', message.item_ref],
      ['사유', payload.reason],
      ['새 예상완료', payload.new_estimated_completion ? formatDateTime(payload.new_estimated_completion) : null],
    ].filter(([, value]) => value)
  }

  if (message.report_type === 'import') {
    const status = payload.status || '입고완료'
    return [
      ['원자재', payload.material_display_name || payload.material],
      ['입고수량', payload.qty != null ? `${formatNumber(payload.qty)}${payload.unit || ''}` : null],
      ['중량', formatWeight(payload.weight_kg)],
      [status === '입고완료' ? '입고일' : `${status}일`, payload.arrival_date],
      ['BL 번호', payload.bl_number],
    ].filter(([, value]) => value)
  }

  if (message.report_type === 'release') {
    const completedCount = aiReport.completed_release_count ?? payload.completed_release_count
    const completedQty = aiReport.completed_release_qty_total ?? payload.completed_release_qty_total
    return [
      ['보고 묶음', aiReport.report_batch_label],
      [
        '완료 현황',
        completedCount != null || completedQty != null
          ? `${formatNumber(completedCount || 0)}건 / ${formatNumber(completedQty || 0)}개`
          : null,
      ],
      ['총중량', formatWeight(aiReport.shipment_total_weight_kg ?? payload.shipment_total_weight_kg)],
      ['현재 원자재 재고', aiReport.stock_summary_text],
      ['연동 라벨코드', payload.label_code],
      ['출항항구', payload.export_port],
      ['출발회사', payload.pickup_company || payload.company_name],
      ['패킹리스트', payload.packing_list?.filename],
    ].filter(([, value]) => value)
  }

  return []
}

function EventChip({ children }) {
  return (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
      {children}
    </span>
  )
}

function StatusBadge({ status }) {
  if (!status) return null
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_CLASS[status] || 'bg-slate-100 text-slate-600'}`}>
      {status}
    </span>
  )
}

function SummaryCard({ label, value, tone }) {
  const className =
    tone === 'green'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : tone === 'yellow'
        ? 'border-amber-200 bg-amber-50 text-amber-800'
        : 'border-slate-200 bg-white text-slate-700'

  return (
    <div className={`rounded-2xl border px-4 py-3 ${className}`}>
      <p className="text-[11px] uppercase tracking-[0.18em] opacity-70">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  )
}

function MessageCard({ message }) {
  const isOutbound = message.direction === 'outbound'
  const detailRows = buildDetailRows(message)
  const payload = message.payload || {}

  return (
    <div className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}>
      <div className={`w-full max-w-3xl rounded-2xl border px-4 py-3 shadow-sm ${isOutbound ? 'border-indigo-200 bg-indigo-50/90' : 'border-slate-200 bg-white'}`}>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <EventChip>{isOutbound ? '지퍼단추사 보고' : '플랫폼 응답'}</EventChip>
          {message.item_ref && <EventChip>{message.item_ref}</EventChip>}
          <StatusBadge status={message.status} />
          <span className="ml-auto text-[11px] text-slate-400">{formatDateTime(message.updated_at)}</span>
        </div>

        <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
          <span className="font-semibold text-slate-700">{message.sender}</span>
          <span>→</span>
          <span className="font-semibold text-slate-700">{message.receiver}</span>
        </div>

        <h3 className="text-sm font-semibold text-slate-800">{message.report_type_label || '플랫폼 보고'}</h3>
        <p className="mt-1 text-sm leading-6 text-slate-600">{message.summary}</p>

        {detailRows.length > 0 && (
          <div className="mt-3 grid gap-2 rounded-xl border border-slate-200 bg-white/70 p-3 sm:grid-cols-2">
            {detailRows.map(([label, value]) => (
              <div key={`${message.id}-${label}`} className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{label}</p>
                <p className="mt-1 text-sm font-medium leading-6 text-slate-700">{value}</p>
              </div>
            ))}
          </div>
        )}

        {payload && Object.keys(payload).length > 0 && (
          <details className="mt-3 rounded-xl border border-slate-200 bg-slate-950/95 p-3 text-xs text-slate-100">
            <summary className="cursor-pointer select-none text-slate-300">보고 payload</summary>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all leading-5">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  )
}

export default function PlatformReportTab() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await getAgentStatus()
      setStatus(res.data)
      setLastUpdated(new Date())
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

  const reportStatus = status?.platform_report_status || {}
  const messages = reportStatus.channel_messages || []
  const latestMessage = messages[0]

  return (
    <div className="grid min-h-[720px] grid-cols-[280px_minmax(0,1fr)] gap-5">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-4 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Report Channel</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-800">지퍼단추사 - 플랫폼 채팅창</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            지퍼단추agent가 판단한 생산일정/원자재입고/출고완료 보고만 표시합니다. 자유채팅이 아닙니다.
          </p>
        </div>

        <div className="border-b border-slate-100 p-4">
          <button className="w-full rounded-2xl bg-slate-900 px-4 py-4 text-left text-white">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-sm font-semibold">플랫폼 보고 채널</span>
              <span className="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-semibold">{messages.length}건</span>
            </div>
            <p className="text-xs text-slate-300">{latestMessage?.summary || '아직 누적된 보고가 없습니다.'}</p>
            <p className="mt-2 text-[11px] text-slate-400">
              {latestMessage?.updated_at ? formatDateTime(latestMessage.updated_at) : '기록 없음'}
            </p>
          </button>
        </div>

        <div className="grid gap-3 p-4">
          <SummaryCard label="전송완료" value={reportStatus.success_count ?? 0} tone="green" />
          <SummaryCard label="대기" value={reportStatus.waiting_count ?? 0} tone="yellow" />
          <SummaryCard
            label="마지막 조회"
            value={lastUpdated ? lastUpdated.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : '-'}
          />
          <button onClick={fetchStatus} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            새로고침
          </button>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-b from-slate-50 to-white shadow-sm">
        <div className="border-b border-slate-200 bg-white/80 px-6 py-4 backdrop-blur">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Current Channel</p>
              <h2 className="mt-1 text-xl font-semibold text-slate-800">플랫폼 보고 타임라인</h2>
              <p className="mt-1 text-sm text-slate-500">생산일정/재조정/원자재입고/출고완료 보고 이벤트를 시간순으로 보여줍니다.</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-right">
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Messages</p>
              <p className="text-2xl font-semibold text-slate-800">{messages.length}</p>
            </div>
          </div>
        </div>

        <div className="space-y-4 p-6">
          {loading && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white/80 px-6 py-12 text-center">
              <p className="text-sm font-medium text-slate-600">플랫폼 보고 채널을 불러오는 중입니다.</p>
            </div>
          )}

          {!loading && !status && (
            <div className="rounded-2xl border border-dashed border-rose-200 bg-rose-50 px-6 py-12 text-center">
              <p className="text-sm font-medium text-rose-700">플랫폼 보고 채널을 불러오지 못했습니다.</p>
            </div>
          )}

          {!loading && status && messages.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white/80 px-6 py-12 text-center">
              <p className="text-sm font-medium text-slate-600">아직 누적된 플랫폼 보고가 없습니다.</p>
              <p className="mt-2 text-xs text-slate-400">발주/입고/생산등록/출고완료 처리 후 플랫폼 보고가 여기에 누적됩니다.</p>
            </div>
          )}

          {!loading && messages.map((message) => <MessageCard key={message.id} message={message} />)}
        </div>
      </section>
    </div>
  )
}
