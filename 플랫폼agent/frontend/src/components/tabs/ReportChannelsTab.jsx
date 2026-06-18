import { useEffect, useMemo, useState } from 'react'
import { getPackingListDownloadUrl, getReportChannelMessages, getReportChannels } from '../../api'

const STATUS_CLS = {
  출고완료: 'bg-emerald-100 text-emerald-700',
  입고완료: 'bg-indigo-100 text-indigo-700',
  완료: 'bg-emerald-100 text-emerald-700',
  배차완료: 'bg-blue-100 text-blue-700',
  연결완료: 'bg-violet-100 text-violet-700',
  전송완료: 'bg-blue-100 text-blue-700',
  전송실패: 'bg-rose-100 text-rose-700',
}

function formatDateTime(value) {
  if (!value) return '시각 없음'

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

function formatFileSize(value) {
  if (value == null || value === '') return null
  const size = Number(value)
  if (Number.isNaN(size) || size <= 0) return null
  if (size < 1024) return `${size}B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`
  return `${(size / (1024 * 1024)).toFixed(1)}MB`
}

function inferPackingListFormat(packingList) {
  const filename = String(packingList?.filename || '').toLowerCase()
  const contentType = String(packingList?.content_type || '').toLowerCase()
  if (filename.endsWith('.xlsx') || contentType.includes('spreadsheetml')) return 'xlsx'
  if (filename.endsWith('.pdf') || contentType.includes('pdf')) return 'pdf'
  return 'csv'
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
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_CLS[status] || 'bg-slate-100 text-slate-600'}`}>
      {status}
    </span>
  )
}

function buildMessageSummary(message) {
  const payload = message.payload_json || {}

  if (message.event_type === 'collected_release') {
    const aiSummary = payload.ai_report?.summary
    if (aiSummary) {
      return aiSummary
    }

    const completedReleaseList = payload.completed_release_list || []
    const completedReleaseCount = payload.completed_release_count
    const completedReleaseQtyTotal =
      payload.completed_release_qty_total ??
      (completedReleaseList.length
        ? completedReleaseList.reduce((sum, item) => sum + Number(item.release_qty || 0), 0)
        : null)
    const shipmentTotalWeightKg =
      payload.shipment_total_weight_kg ??
      payload.completed_release_total_weight_kg ??
      payload.packing_list?.total_weight_kg
    const shipmentBoxCountTotal =
      payload.shipment_box_count_total ??
      (completedReleaseList.length
        ? completedReleaseList.reduce((sum, item) => sum + Number(item.box_count || 0), 0)
        : null)

    if (
      completedReleaseCount != null ||
      completedReleaseQtyTotal != null ||
      shipmentTotalWeightKg != null ||
      shipmentBoxCountTotal != null
    ) {
      return [
        `수출 묶음 ${formatNumber(completedReleaseCount || 1)}건 ${formatNumber(completedReleaseQtyTotal)}장`,
        shipmentTotalWeightKg != null ? formatWeight(shipmentTotalWeightKg) : null,
        shipmentBoxCountTotal != null ? `${formatNumber(shipmentBoxCountTotal)}박스` : null,
        payload.report_batch_due_date ? `납기묶음 ${payload.report_batch_due_date}` : null,
      ]
        .filter(Boolean)
        .join(' · ')
    }

    const parsedItemName = payload.parsed_info?.item_name
    const itemText = parsedItemName || payload.item_name || message.related_code || '출고품'
    const qtyValue = payload.quantity ?? payload.release_qty
    const qtyText = qtyValue != null ? `${formatNumber(qtyValue)}${payload.unit || ''}` : '수량 미상'

    return [
      `${itemText} 출고완료 보고`,
      payload.label_code ? `라벨코드 ${payload.label_code}` : null,
      `수량 ${qtyText}`,
      payload.due_date ? `납기 ${payload.due_date}` : null,
      payload.export_port ? `수출항 ${payload.export_port}` : null,
      payload.pickup_location ? `픽업위치 ${payload.pickup_location}` : null,
    ]
      .filter(Boolean)
      .join('. ')
  }

  if (message.event_type === 'agent_report_import') {
    const materialText = payload.material_display_name || payload.material || message.related_code || '원자재'
    const qtyText = `${formatNumber(payload.qty)}${payload.unit || ''}`

    return [
      `${materialText} ${qtyText} 수입 입고 보고`,
      payload.bl_number ? `BL ${payload.bl_number}` : null,
      payload.port_of_loading ? `선적항 ${payload.port_of_loading}` : null,
      payload.port_of_discharge || payload.receiving_port
        ? `도착항 ${payload.port_of_discharge || payload.receiving_port}`
        : null,
      payload.receiving_company_location ? `수령위치 ${payload.receiving_company_location}` : null,
      payload.weight_kg != null ? `중량 ${formatWeight(payload.weight_kg)}` : null,
    ]
      .filter(Boolean)
      .join('. ')
  }

  return message.summary
}

function buildDetailRows(message) {
  const payload = message.payload_json || {}

  if (message.event_type === 'collected_release') {
    const completedReleaseList = payload.completed_release_list || []
    const completedReleaseCount = payload.completed_release_count
    const completedReleaseQtyTotal =
      payload.completed_release_qty_total ??
      (completedReleaseList.length
        ? completedReleaseList.reduce((sum, item) => sum + Number(item.release_qty || 0), 0)
        : null)
    const shipmentTotalWeightKg =
      payload.shipment_total_weight_kg ??
      payload.completed_release_total_weight_kg ??
      payload.packing_list?.total_weight_kg
    const shipmentBoxCountTotal =
      payload.shipment_box_count_total ??
      (completedReleaseList.length
        ? completedReleaseList.reduce((sum, item) => sum + Number(item.box_count || 0), 0)
        : null)

    const qtyValue = completedReleaseQtyTotal ?? (payload.quantity ?? payload.release_qty)
    const boxValue = shipmentBoxCountTotal ?? payload.box_count

    return [
      ['회사', payload.company_name || payload.company_type || message.source_agent || null],
      ['품목', payload.parsed_info?.item_name || payload.item_name || null],
      ['라벨코드', payload.label_code || null],
      ['출고수량', qtyValue != null ? `${formatNumber(qtyValue)}${payload.unit || ''}` : null],
      ['완료 건수', completedReleaseCount != null ? `${formatNumber(completedReleaseCount)}건` : null],
      ['납기', payload.due_date || null],
      ['출고일', payload.release_date || null],
      ['픽업회사', payload.pickup_company || null],
      ['픽업위치', payload.pickup_location || null],
      ['수출항', payload.export_port || null],
      ['박스수', boxValue != null ? `${formatNumber(boxValue)}박스` : null],
      ['제품중량', formatWeight(payload.product_weight_kg)],
      ['출고총중량', formatWeight(shipmentTotalWeightKg)],
    ].filter(([, value]) => value)
  }

  if (message.event_type === 'agent_report_import') {
    return [
      ['품목', payload.material_display_name || payload.material || null],
      ['수입수량', payload.qty != null ? `${formatNumber(payload.qty)}${payload.unit || ''}` : null],
      ['수입중량', formatWeight(payload.weight_kg)],
      ['BL 번호', payload.bl_number || null],
      ['선적항', payload.port_of_loading || null],
      ['도착항', payload.port_of_discharge || payload.receiving_port || null],
      ['최종도착지', payload.final_place_of_delivery || null],
      ['공급사', payload.supplier_company || payload.supplier || null],
      ['수령회사', payload.receiving_company || null],
      ['수령위치', payload.receiving_company_location || null],
      ['입고일', payload.arrival_date || null],
    ].filter(([, value]) => value)
  }

  return []
}

function buildPackingListAttachment(message) {
  if (message.event_type !== 'collected_release') {
    return null
  }

  const payload = message.payload_json || {}
  const packingList = payload.packing_list
  if (!packingList || typeof packingList !== 'object' || !packingList.filename) {
    return null
  }

  const packingListId = payload.packing_list_id || packingList.packing_list_id
  const downloadUrl =
    payload.packing_list_download_url ||
    packingList.download_url ||
    (packingListId ? getPackingListDownloadUrl(packingListId) : null)

  return {
    format: inferPackingListFormat(packingList),
    filename: packingList.filename,
    totalQty: packingList.total_qty ?? payload.completed_release_qty_total,
    totalWeightKg: packingList.total_weight_kg ?? payload.shipment_total_weight_kg,
    labelCodeCount: packingList.label_code_count,
    sizeText: formatFileSize(packingList.csv_size_bytes ?? packingList.pdf_size_bytes),
    periodFrom: packingList.period_from,
    periodTo: packingList.period_to,
    downloadUrl,
  }
}

function MessageCard({ message }) {
  const [expanded, setExpanded] = useState(false)
  const isOutbound = message.direction === 'outbound'
  const displaySummary = buildMessageSummary(message)
  const detailRows = buildDetailRows(message)
  const packingListAttachment = buildPackingListAttachment(message)
  const hasDetails = detailRows.length > 0 || packingListAttachment || message.payload_json

  return (
    <div className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}>
      <div className={`w-full max-w-3xl rounded-2xl border px-4 py-3 shadow-sm ${
        isOutbound
          ? 'border-blue-200 bg-blue-50/90'
          : 'border-slate-200 bg-white'
      }`}>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <EventChip>{isOutbound ? '플랫폼 발신' : 'Agent 수신'}</EventChip>
          <EventChip>{message.event_type}</EventChip>
          {message.related_code && <EventChip>{message.related_code}</EventChip>}
          <StatusBadge status={message.status} />
          <span className="ml-auto text-[11px] text-slate-400">{formatDateTime(message.created_at)}</span>
        </div>

        <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
          <span className="font-semibold text-slate-700">{message.source_agent}</span>
          <span>→</span>
          <span className="font-semibold text-slate-700">{message.target_agent}</span>
        </div>

        <h3 className="text-sm font-semibold text-slate-800">{message.title}</h3>
        <p className="mt-1 text-sm leading-6 text-slate-600">{displaySummary}</p>

        {hasDetails && (
          <div className="mt-3 border-t border-slate-100 pt-2">
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="flex w-full items-center justify-between rounded-xl px-2 py-2 text-left text-xs font-semibold text-slate-500 transition-colors hover:bg-slate-50"
            >
              <span>{expanded ? '상세 접기' : '상세 보기'}</span>
              <span className={`text-base transition-transform ${expanded ? 'rotate-180' : ''}`}>⌄</span>
            </button>
          </div>
        )}

        {expanded && (
          <div className="mt-2">
            {detailRows.length > 0 && (
              <div className="grid gap-2 rounded-xl border border-slate-200 bg-white/70 p-3 sm:grid-cols-2">
                {detailRows.map(([label, value]) => (
                  <div key={`${message.id}-${label}`} className="rounded-lg bg-slate-50 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{label}</p>
                    <p className="mt-1 text-sm font-medium leading-6 text-slate-700">{value}</p>
                  </div>
                ))}
              </div>
            )}

            {packingListAttachment && (
              <div className="mt-3 rounded-2xl border border-sky-200 bg-sky-50/80 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700">
                      {`패킹리스트 ${String(packingListAttachment.format || 'csv').toUpperCase()}`}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-slate-800">{packingListAttachment.filename}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-600">
                      {[
                        packingListAttachment.periodFrom && packingListAttachment.periodTo
                          ? `${packingListAttachment.periodFrom} ~ ${packingListAttachment.periodTo}`
                          : null,
                        packingListAttachment.sizeText,
                      ]
                        .filter(Boolean)
                        .join(' · ') || '수출 묶음 첨부파일'}
                    </p>
                  </div>

                  {packingListAttachment.downloadUrl ? (
                    <a
                      href={packingListAttachment.downloadUrl}
                      className="rounded-xl border border-sky-300 bg-white px-3 py-2 text-sm font-medium text-sky-700 transition-colors hover:bg-sky-100"
                    >
                      {`${String(packingListAttachment.format || 'csv').toUpperCase()} 다운로드`}
                    </a>
                  ) : (
                    <span className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-500">
                      다운로드 준비중
                    </span>
                  )}
                </div>

                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  {packingListAttachment.totalQty != null && (
                    <div className="rounded-xl bg-white px-3 py-2">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">총수량</p>
                      <p className="mt-1 text-sm font-semibold text-slate-700">{formatNumber(packingListAttachment.totalQty)}장</p>
                    </div>
                  )}
                  {packingListAttachment.totalWeightKg != null && (
                    <div className="rounded-xl bg-white px-3 py-2">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">총중량</p>
                      <p className="mt-1 text-sm font-semibold text-slate-700">{formatWeight(packingListAttachment.totalWeightKg)}</p>
                    </div>
                  )}
                  {packingListAttachment.labelCodeCount != null && (
                    <div className="rounded-xl bg-white px-3 py-2">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">품목수</p>
                      <p className="mt-1 text-sm font-semibold text-slate-700">{formatNumber(packingListAttachment.labelCodeCount)}개</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {message.payload_json && (
              <details className="mt-3 rounded-xl border border-slate-200 bg-slate-950/95 p-3 text-xs text-slate-100">
                <summary className="cursor-pointer select-none text-slate-300">원본 API payload</summary>
                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all leading-5">
                  {JSON.stringify(message.payload_json, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ReportChannelsTab() {
  const [channels, setChannels] = useState([])
  const [activeChannel, setActiveChannel] = useState('label')
  const [messages, setMessages] = useState([])

  useEffect(() => {
    let alive = true

    const loadChannels = async () => {
      try {
        const response = await getReportChannels()
        if (!alive) return
        setChannels(response.data)
        setActiveChannel((current) => {
          if (response.data.some((channel) => channel.channel === current)) return current
          return response.data[0]?.channel || current
        })
      } catch {}
    }

    loadChannels()
    const timer = setInterval(loadChannels, 30000)

    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (!activeChannel) return

    let alive = true

    const loadMessages = async () => {
      try {
        const response = await getReportChannelMessages(activeChannel)
        if (!alive) return
        setMessages(response.data)
      } catch {
        if (alive) setMessages([])
      }
    }

    loadMessages()
    const timer = setInterval(loadMessages, 15000)

    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [activeChannel])

  const activeInfo = useMemo(
    () => channels.find((channel) => channel.channel === activeChannel),
    [activeChannel, channels],
  )

  return (
    <div className="grid min-h-[720px] grid-cols-[280px_minmax(0,1fr)] gap-5">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-4 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Agent Channels</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-800">1:1 보고 채널</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">채널에는 완료, 입고, 배차확정처럼 끝난 이벤트만 표시합니다.</p>
        </div>

        <div className="divide-y divide-slate-100">
          {channels.map((channel) => {
            const active = channel.channel === activeChannel
            return (
              <button
                key={channel.channel}
                onClick={() => setActiveChannel(channel.channel)}
                className={`w-full px-4 py-4 text-left transition-colors ${
                  active ? 'bg-slate-900 text-white' : 'bg-white hover:bg-slate-50'
                }`}
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className={`text-sm font-semibold ${active ? 'text-white' : 'text-slate-800'}`}>{channel.label}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                    active ? 'bg-white/15 text-white' : 'bg-slate-100 text-slate-600'
                  }`}>
                    {channel.message_count}건
                  </span>
                </div>
                <p className={`text-xs ${active ? 'text-slate-300' : 'text-slate-500'}`}>{channel.last_summary || '아직 기록 없음'}</p>
                <p className={`mt-2 text-[11px] ${active ? 'text-slate-400' : 'text-slate-400'}`}>
                  {channel.last_message_at ? formatDateTime(channel.last_message_at) : '기록 없음'}
                </p>
              </button>
            )
          })}
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-b from-slate-50 to-white shadow-sm">
        <div className="border-b border-slate-200 bg-white/80 px-6 py-4 backdrop-blur">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Current Channel</p>
              <h2 className="mt-1 text-xl font-semibold text-slate-800">{activeInfo?.label || '보고 채널'}</h2>
              <p className="mt-1 text-sm text-slate-500">
                {activeInfo ? `${activeInfo.counterparty} agent와 플랫폼 간 완료 이벤트 타임라인` : '채널을 선택하세요.'}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-right">
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Messages</p>
              <p className="text-2xl font-semibold text-slate-800">{activeInfo?.message_count ?? 0}</p>
            </div>
          </div>
        </div>

        <div className="space-y-4 p-6">
          {messages.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white/80 px-6 py-12 text-center">
              <p className="text-sm font-medium text-slate-600">이 채널에 아직 기록된 보고 이벤트가 없습니다.</p>
              <p className="mt-2 text-xs text-slate-400">완료 조건을 만족한 이벤트만 여기 타임라인에 표시됩니다.</p>
            </div>
          )}

          {messages.map((message) => (
            <MessageCard key={message.id} message={message} />
          ))}
        </div>
      </section>
    </div>
  )
}
