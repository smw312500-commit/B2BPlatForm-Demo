const STATUS_CLASS = {
  수신확인: 'bg-emerald-100 text-emerald-700',
  전송완료: 'bg-blue-100 text-blue-700',
  전송중: 'bg-sky-100 text-sky-700',
  '플랫폼 보고 대기': 'bg-amber-100 text-amber-800',
  실패: 'bg-rose-100 text-rose-700',
  오류: 'bg-rose-100 text-rose-700',
  추가지시: 'bg-purple-100 text-purple-700',
}

const AI_TONE_CLASS = {
  정상: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  주의: 'border-amber-200 bg-amber-50 text-amber-900',
  긴급: 'border-rose-200 bg-rose-50 text-rose-800',
}

function formatDateTime(value) {
  if (!value) return '기록 없음'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value).replace('T', ' ').slice(0, 16)
  }

  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
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

function hasValue(value) {
  return value != null && value !== ''
}

function getReleaseMetrics(payload) {
  const aiReport = payload.ai_report || null
  const completedReleaseList = payload.completed_release_list || []
  const completedReleaseCount =
    aiReport?.completed_release_count ??
    payload.completed_release_count ??
    completedReleaseList.length
  const completedReleaseQtyTotal =
    aiReport?.completed_release_qty_total ??
    payload.completed_release_qty_total ??
    completedReleaseList.reduce((sum, item) => sum + Number(item.release_qty || 0), 0)
  const shipmentTotalWeightKg =
    aiReport?.shipment_total_weight_kg ??
    payload.shipment_total_weight_kg ??
    payload.completed_release_total_weight_kg ??
    payload.packing_list?.total_weight_kg
  const shipmentBoxCountTotal =
    aiReport?.shipment_box_count_total ??
    payload.shipment_box_count_total ??
    completedReleaseList.reduce((sum, item) => sum + Number(item.box_count || 0), 0)

  return {
    aiReport,
    completedReleaseCount,
    completedReleaseQtyTotal,
    shipmentTotalWeightKg,
    shipmentBoxCountTotal,
  }
}

function getReportBatchLabel(payload, aiReport) {
  return (
    aiReport?.report_batch_label ||
    (payload.report_batch_due_date ? `납기 ${payload.report_batch_due_date} 묶음` : null)
  )
}

function buildMessageSummary(message) {
  const payload = message.payload || {}

  if (message.report_type !== 'release') {
    return message.summary
  }

  const {
    aiReport,
    completedReleaseCount,
    completedReleaseQtyTotal,
    shipmentTotalWeightKg,
    shipmentBoxCountTotal,
  } = getReleaseMetrics(payload)

  if (aiReport?.summary) {
    return aiReport.summary
  }

  const batchLabel = getReportBatchLabel(payload, aiReport) || message.item_ref

  if (completedReleaseCount || shipmentTotalWeightKg != null) {
    return [
      `${batchLabel} 완료 ${formatNumber(completedReleaseCount || 1)}건 ${formatNumber(completedReleaseQtyTotal)}장`,
      shipmentTotalWeightKg != null ? `총중량 ${formatWeight(shipmentTotalWeightKg)}` : null,
      shipmentBoxCountTotal ? `총 박스 ${formatNumber(shipmentBoxCountTotal)}개` : null,
      payload.packing_list?.filename ? `${payload.packing_list.filename} 포함` : null,
    ]
      .filter(Boolean)
      .join('. ')
  }

  return message.summary
}

function buildDetailRows(message) {
  const payload = message.payload || {}
  const {
    aiReport,
    completedReleaseCount,
    completedReleaseQtyTotal,
    shipmentTotalWeightKg,
    shipmentBoxCountTotal,
  } = getReleaseMetrics(payload)

  if (message.report_type === 'import') {
    const status = payload.status || '입고완료'
    return [
      ['품목', payload.material_display_name || payload.material || null],
      ['처리상태', status],
      ['수입수량', payload.qty != null ? `${formatNumber(payload.qty)}${payload.unit || ''}` : null],
      ['수입중량', formatWeight(payload.weight_kg)],
      ['공급사', payload.supplier_company || payload.supplier || null],
      ['수입항', payload.receiving_port || payload.port_of_discharge || null],
      ['선적항', payload.port_of_loading || null],
      ['수령회사', payload.receiving_company || null],
      ['수령위치', payload.receiving_company_location || null],
      [status === '입고완료' ? '입고일' : `${status}일`, payload.arrival_date || null],
      ['BL 번호', payload.bl_number || null],
    ].filter(([, value]) => value)
  }

  if (message.report_type === 'release') {
    const reportBatchLabel = getReportBatchLabel(payload, aiReport)
    const reportMode =
      aiReport?.analysis_type === 'db_rule_based' || aiReport?.uses_openai === false
        ? '라벨회사 DB 판단'
        : aiReport?.report_batch_type === 'due_date'
          ? '납기 묶음 판단'
          : null
    const decisionText =
      hasValue(aiReport?.decision_level) && hasValue(aiReport?.decision)
        ? `${aiReport.decision_level} / ${aiReport.decision}`
        : null
    const dueResultText =
      hasValue(aiReport?.on_time_count) || hasValue(aiReport?.delayed_count)
        ? `준수 ${formatNumber(aiReport?.on_time_count || 0)}건 · 지연 ${formatNumber(aiReport?.delayed_count || 0)}건`
        : null

    return [
      ['보고 묶음', reportBatchLabel],
      ['보고 기준', reportMode],
      [
        '완료 현황',
        hasValue(completedReleaseCount) || hasValue(completedReleaseQtyTotal)
          ? `${formatNumber(completedReleaseCount || 0)}건 / ${formatNumber(completedReleaseQtyTotal || 0)}장`
          : null,
      ],
      ['출고 판정', decisionText],
      ['납기 결과', dueResultText],
      ['현재 재고', aiReport?.stock_summary_text || null],
      [
        '대기 발주',
        aiReport?.pending_order_summary_text ||
          (hasValue(aiReport?.pending_material_order_count)
            ? `${formatNumber(aiReport.pending_material_order_count)}건`
            : null),
      ],
      [
        '수출 묶음',
        shipmentTotalWeightKg != null || shipmentBoxCountTotal != null
          ? `${formatWeight(shipmentTotalWeightKg) || '-'} / ${formatNumber(shipmentBoxCountTotal)}박스`
          : null,
      ],
      ['출항항구', payload.export_port || null],
      ['출발회사', payload.pickup_company || payload.company_name || null],
      ['출발위치', payload.pickup_location || null],
      ['패킹리스트', payload.packing_list?.filename || aiReport?.packing_list_filename || null],
      ['AI/DB 요약', aiReport?.summary || null],
    ].filter(([, value]) => value)
  }

  return []
}

function buildPayloadPreview(message) {
  const payload = message.payload || {}
  if (!payload || Object.keys(payload).length === 0) return null

  if (message.report_type !== 'release') {
    return payload
  }

  return {
    label_code: payload.label_code,
    due_date: payload.due_date,
    release_date: payload.release_date,
    report_batch_due_date: payload.report_batch_due_date,
    export_port: payload.export_port,
    shipment_total_weight_kg: payload.shipment_total_weight_kg,
    shipment_box_count_total: payload.shipment_box_count_total,
    packing_list: payload.packing_list
      ? {
          filename: payload.packing_list.filename,
          total_weight_kg: payload.packing_list.total_weight_kg,
          total_quantity: payload.packing_list.total_quantity,
        }
      : null,
    ai_report: payload.ai_report
      ? {
          report_batch_type: payload.ai_report.report_batch_type,
          report_batch_due_date: payload.ai_report.report_batch_due_date,
          report_batch_label: payload.ai_report.report_batch_label,
          completed_release_count: payload.ai_report.completed_release_count,
          completed_release_qty_total: payload.ai_report.completed_release_qty_total,
          shipment_total_weight_kg: payload.ai_report.shipment_total_weight_kg,
          shipment_box_count_total: payload.ai_report.shipment_box_count_total,
          packing_list_filename: payload.ai_report.packing_list_filename,
          summary: payload.ai_report.summary,
          decision_level: payload.ai_report.decision_level,
          decision: payload.ai_report.decision,
          on_time_count: payload.ai_report.on_time_count,
          delayed_count: payload.ai_report.delayed_count,
        }
      : null,
    completed_release_list: payload.completed_release_list || null,
    completed_release_count: payload.completed_release_count,
    completed_release_qty_total: payload.completed_release_qty_total,
    pending_material_order_count: payload.pending_material_order_count,
    stock_snapshot: payload.stock_snapshot || null,
  }
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
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
        STATUS_CLASS[status] || 'bg-slate-100 text-slate-600'
      }`}
    >
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

function AiDecisionCard({ aiReport, payload }) {
  if (!aiReport?.summary && !aiReport?.decision) return null

  const reportBatchLabel = getReportBatchLabel(payload, aiReport)
  const toneClass = AI_TONE_CLASS[aiReport?.decision_level] || 'border-slate-200 bg-slate-50 text-slate-800'
  const analysisLabel =
    aiReport?.analysis_type === 'db_rule_based' || aiReport?.uses_openai === false
      ? 'DB 규칙 기반'
      : 'AI 판단'

  return (
    <div className={`mt-3 rounded-2xl border px-4 py-3 ${toneClass}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-70">AI/DB 판단 보고</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-semibold">
          {analysisLabel}
        </span>
        {reportBatchLabel && (
          <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-semibold">
            {reportBatchLabel}
          </span>
        )}
        {aiReport.decision_level && (
          <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-semibold">
            {aiReport.decision_level}
          </span>
        )}
      </div>
      <p className="mt-2 text-sm font-semibold leading-6">{aiReport.summary || aiReport.decision}</p>
      {aiReport.decision && aiReport.summary && aiReport.decision !== aiReport.summary && (
        <p className="mt-2 text-sm leading-6 opacity-80">{aiReport.decision}</p>
      )}
    </div>
  )
}

function MessageCard({ message }) {
  const isOutbound = message.direction === 'outbound'
  const payload = buildPayloadPreview(message)
  const detailRows = buildDetailRows(message)
  const typeLabel = message.report_type === 'import' ? '수입' : '수출'
  const aiReport = message.payload?.ai_report || null
  const displaySummary = buildMessageSummary(message)

  return (
    <div className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`w-full max-w-3xl rounded-2xl border px-4 py-3 shadow-sm ${
          isOutbound ? 'border-blue-200 bg-blue-50/90' : 'border-slate-200 bg-white'
        }`}
      >
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <EventChip>{isOutbound ? '라벨사 보고' : '플랫폼 응답'}</EventChip>
          <EventChip>{typeLabel}</EventChip>
          {message.item_ref && <EventChip>{message.item_ref}</EventChip>}
          <StatusBadge status={message.status} />
          <span className="ml-auto text-[11px] text-slate-400">{formatDateTime(message.updated_at)}</span>
        </div>

        <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
          <span className="font-semibold text-slate-700">{message.sender}</span>
          <span>→</span>
          <span className="font-semibold text-slate-700">{message.receiver}</span>
        </div>

        <h3 className="text-sm font-semibold text-slate-800">
          {message.report_type_label || '플랫폼 보고'}
        </h3>
        <p className="mt-1 text-sm leading-6 text-slate-600">{displaySummary}</p>

        {message.report_type === 'release' && isOutbound && <AiDecisionCard aiReport={aiReport} payload={message.payload || {}} />}

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

        {payload && (
          <details className="mt-3 rounded-xl border border-slate-200 bg-slate-950/95 p-3 text-xs text-slate-100">
            <summary className="cursor-pointer select-none text-slate-300">채팅 표시용 payload</summary>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all leading-5">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  )
}

export default function PlatformReportTab({ status, loading, lastUpdated, onRefresh }) {
  const reportStatus = status?.platform_report_status || {}
  const messages = reportStatus.channel_messages || []
  const latestMessage = messages[0]
  const latestMessageSummary = latestMessage ? buildMessageSummary(latestMessage) : null

  return (
    <div className="grid min-h-[720px] grid-cols-[280px_minmax(0,1fr)] gap-5">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-4 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Trade Channel</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-800">수입/수출 보고 채널</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            자재 입고는 수입으로, 완료 수출건은 라벨회사 DB 판단 요약과 함께 플랫폼에 보고합니다.
          </p>
        </div>

        <div className="border-b border-slate-100 p-4">
          <button className="w-full rounded-2xl bg-slate-900 px-4 py-4 text-left text-white">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-sm font-semibold">플랫폼 보고 채널</span>
              <span className="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-semibold">
                {messages.length}건
              </span>
            </div>
            <p className="text-xs text-slate-300">
              {latestMessageSummary || '아직 누적된 수입/수출 메시지가 없습니다.'}
            </p>
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
            value={
              lastUpdated
                ? lastUpdated.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
                : '-'
            }
          />
          <button
            onClick={onRefresh}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            새로고침
          </button>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-b from-slate-50 to-white shadow-sm">
        <div className="border-b border-slate-200 bg-white/80 px-6 py-4 backdrop-blur">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Current Channel</p>
              <h2 className="mt-1 text-xl font-semibold text-slate-800">수입/수출 채팅창</h2>
              <p className="mt-1 text-sm text-slate-500">
                수입은 항구와 수령회사 기준으로, 수출은 납기·재고·발주를 DB에서 판단한 요약 기준으로만 보여줍니다.
              </p>
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
              <p className="text-sm font-medium text-slate-600">수입/수출 보고 채널을 불러오는 중입니다.</p>
            </div>
          )}

          {!loading && !status && (
            <div className="rounded-2xl border border-dashed border-rose-200 bg-rose-50 px-6 py-12 text-center">
              <p className="text-sm font-medium text-rose-700">수입/수출 보고 채널을 불러오지 못했습니다.</p>
            </div>
          )}

          {!loading && status && messages.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white/80 px-6 py-12 text-center">
              <p className="text-sm font-medium text-slate-600">아직 누적된 수입/수출 보고가 없습니다.</p>
              <p className="mt-2 text-xs text-slate-400">
                자재 입고 처리 또는 완료 처리 후 플랫폼 보고가 여기에 누적됩니다.
              </p>
            </div>
          )}

          {!loading && messages.map((message) => <MessageCard key={message.id} message={message} />)}
        </div>
      </section>
    </div>
  )
}
