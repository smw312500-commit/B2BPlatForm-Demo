import { useEffect, useMemo, useState } from 'react'
import {
  getDispatchAvailability,
  getDispatches,
  getReportChannelMessages,
  getReportChannels,
} from '../../api'

const CHANNEL_ORDER = ['label', 'fabric', 'zipper', 'logistics']

const CHANNEL_META = {
  label: {
    label: '케어라벨사',
    role: '수출완료 / 패킹리스트',
    accent: 'border-sky-200 bg-sky-50 text-sky-700',
  },
  fabric: {
    label: '옷감사',
    role: '원자재 수입 보고',
    accent: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  zipper: {
    label: '지퍼단추사',
    role: '원자재 수입 보고',
    accent: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  logistics: {
    label: '물류사',
    role: '기사/차량 스냅샷',
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
  },
}

const EVENT_LABEL = {
  collected_release: '수출완료',
  agent_report_import: '수입보고',
  dispatch_planned: '배차판단',
  dispatch_confirmed: '배차확정',
  round_trip_result: '귀로매칭',
  logistics_complete: '배송완료',
  platform_signal: '플랫폼신호',
}

const STATUS_TONE = {
  대기: 'bg-amber-50 text-amber-700 border-amber-200',
  배차완료: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  진행중: 'bg-sky-50 text-sky-700 border-sky-200',
  완료: 'bg-slate-100 text-slate-700 border-slate-200',
}

function localDateKey(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return date.toLocaleDateString('sv-SE')
}

function formatDate(value) {
  if (!value) {
    return '일정 미정'
  }
  return String(value).slice(0, 10)
}

function formatDateTime(value) {
  if (!value) {
    return '수신 없음'
  }

  const text = String(value).replace('T', ' ')
  return text.slice(0, 16)
}

function formatNumber(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return '0'
  }
  return Number(value).toLocaleString('ko-KR')
}

function isDone(status) {
  return status === '배차완료' || status === '완료'
}

function isRoundTrip(dispatch) {
  const memo = `${dispatch.empty_return || ''} ${dispatch.logistics_message || ''}`
  return memo.includes('연결완료') || (memo.includes('수입품') && memo.includes('수출물건'))
}

function isImportDispatch(dispatch) {
  return dispatch.dispatch_type === 'import' || (!dispatch.label_code && dispatch.company_id !== 4)
}

function getCargoLabel(dispatch) {
  return dispatch.cargo_detail || dispatch.label_code || dispatch.destination || `배차 #${dispatch.id}`
}

function getStatusClass(status) {
  return STATUS_TONE[status] || 'bg-gray-50 text-gray-600 border-gray-200'
}

function getPayload(message) {
  return message?.payload_json && typeof message.payload_json === 'object' ? message.payload_json : {}
}

function formatQty(value, unit = '') {
  if (value == null || Number.isNaN(Number(value))) {
    return ''
  }

  return `${Number(value).toLocaleString('ko-KR')}${unit || ''}`
}

function normalizePortName(value) {
  if (!value) {
    return ''
  }

  const text = String(value).toLowerCase()
  if (text.includes('busan') || text.includes('부산')) {
    return '부산항'
  }
  if (text.includes('incheon') || text.includes('인천')) {
    return '인천항'
  }
  if (text.includes('pyeongtaek') || text.includes('평택')) {
    return '평택항'
  }
  return String(value)
}

function getChannelDispatchText(channel, dispatches) {
  const companyIdByChannel = {
    fabric: 1,
    label: 2,
    zipper: 3,
  }
  const companyId = companyIdByChannel[channel]
  if (!companyId) {
    return ''
  }

  const companyDispatches = dispatches.filter((dispatch) => dispatch.company_id === companyId)
  if (companyDispatches.length === 0) {
    return '아직 연결된 배차는 없습니다.'
  }

  const doneCount = companyDispatches.filter((dispatch) => isDone(dispatch.status)).length
  const pendingCount = companyDispatches.length - doneCount

  if (pendingCount > 0) {
    return `배차는 ${doneCount}건 확정, ${pendingCount}건 확인 중입니다.`
  }
  return `배차는 ${doneCount}건 모두 확정됐습니다.`
}

function buildImportReportText(channel, message, dispatches) {
  const payload = getPayload(message)
  const meta = CHANNEL_META[channel]
  const company = payload.receiving_company || payload.company_name || meta?.label || '생산사'
  const material = payload.material_display_name || payload.material || payload.item || '원자재'
  const qtyText = formatQty(payload.qty ?? payload.weight_kg, payload.unit || 'kg')
  const arrivalDate = formatDate(payload.arrival_date || payload.due_date)
  const port = normalizePortName(payload.receiving_port || payload.port_of_discharge)
  const destination = payload.receiving_company_location || payload.final_place_of_delivery || '공장'
  const dispatchText = getChannelDispatchText(channel, dispatches)

  const main = `${company}에서 ${arrivalDate} 입고 예정 원자재 ${material}${qtyText ? ` ${qtyText}` : ''}을 보고했습니다.`
  const detail = port
    ? `${port}에서 회수해 ${destination}으로 넣는 건으로 배차 판단에 반영했습니다. ${dispatchText}`
    : `${destination} 입고 건으로 접수했지만 항구 정보는 확인이 필요합니다. ${dispatchText}`

  return { main, detail }
}

function buildReleaseReportText(channel, message, dispatches) {
  const payload = getPayload(message)
  const company = payload.company_name || CHANNEL_META[channel]?.label || '생산사'
  const dueDate = formatDate(payload.report_batch_due_date || payload.due_date)
  const count = payload.completed_release_count || payload.completed_release_list?.length
  const qty = formatQty(payload.completed_release_qty_total ?? payload.quantity, payload.unit || '장')
  const weight = formatQty(payload.shipment_total_weight_kg, 'kg')
  const boxes = formatQty(payload.shipment_box_count_total, '박스')
  const dispatchText = getChannelDispatchText(channel, dispatches)

  const countText = count ? `${formatNumber(count)}건` : '완료 물량'
  const loadText = [qty, weight, boxes].filter(Boolean).join(' / ')

  return {
    main: `${company}에서 ${dueDate} 납기 수출 물량 ${countText}을 완료 보고했습니다.`,
    detail: `${loadText || '패킹 기준'}으로 항구 반입 배차 판단에 반영했습니다. ${dispatchText}`,
  }
}

function buildLogisticsReportText(messages, availability) {
  const lastMessage = messages[0]
  const payload = getPayload(lastMessage)
  const driver = payload.driver_name || payload.name
  const vehicle = payload.vehicle_plate || payload.plate_no
  const cargo = payload.cargo_detail || payload.item
  const destination = payload.destination

  if (lastMessage?.event_type === 'dispatch_confirmed') {
    return {
      main: `물류사에서 ${driver || '기사'}${vehicle ? ` / ${vehicle}` : ''} 배차 확정을 회신했습니다.`,
      detail: `${cargo || '화물'}${destination ? `은 ${destination} 도착 기준` : ''}으로 처리 중입니다. 가용 기사는 ${formatNumber(availability.available_driver_count)}명입니다.`,
    }
  }

  return {
    main: `물류사 기사/차량 스냅샷이 플랫폼에 반영됐습니다.`,
    detail: `현재 가용 기사 ${formatNumber(availability.available_driver_count)}명, 가용 차량 ${formatNumber(availability.available_vehicle_count)}대 기준으로 배차 판단합니다.`,
  }
}

function buildHumanReportText(channel, messages, channelInfo, availability, dispatches) {
  const lastMessage = messages[0]
  if (!lastMessage && !channelInfo?.last_message_at) {
    return {
      main: `${CHANNEL_META[channel]?.label || '거래처'} 보고가 아직 들어오지 않았습니다.`,
      detail: '플랫폼 판단 대기 상태입니다.',
    }
  }

  if (channel === 'logistics') {
    return buildLogisticsReportText(messages, availability)
  }

  if (lastMessage?.event_type === 'collected_release') {
    return buildReleaseReportText(channel, lastMessage, dispatches)
  }

  if (lastMessage?.event_type === 'agent_report_import') {
    return buildImportReportText(channel, lastMessage, dispatches)
  }

  return {
    main: `${CHANNEL_META[channel]?.label || '거래처'}에서 최근 보고를 보냈습니다.`,
    detail: `${EVENT_LABEL[lastMessage?.event_type] || lastMessage?.title || '보고'} 상태로 접수했습니다.`,
  }
}

function getDecisionLogSummary(message, dispatches, availability) {
  if (message.event_type === 'agent_report_import') {
    return buildImportReportText(message.channel, message, dispatches).main
  }

  if (message.event_type === 'collected_release') {
    return buildReleaseReportText(message.channel, message, dispatches).main
  }

  if (message.event_type === 'dispatch_confirmed' && message.channel === 'logistics') {
    return buildLogisticsReportText([message], availability).main
  }

  return message.summary
}

function StatTile({ label, value, caption, tone = 'slate' }) {
  const toneClass = {
    slate: 'border-slate-200 bg-white text-slate-900',
    blue: 'border-sky-200 bg-sky-50 text-sky-950',
    green: 'border-emerald-200 bg-emerald-50 text-emerald-950',
    amber: 'border-amber-200 bg-amber-50 text-amber-950',
    rose: 'border-rose-200 bg-rose-50 text-rose-950',
  }[tone]

  return (
    <div className={`rounded-lg border p-4 ${toneClass}`}>
      <div className="text-[12px] font-medium text-slate-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold leading-none">{value}</div>
      <div className="mt-2 break-keep text-[12px] leading-5 text-slate-500">{caption}</div>
    </div>
  )
}

function SectionTitle({ title, caption, action }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        {caption && <p className="mt-1 break-keep text-[12px] leading-5 text-slate-500">{caption}</p>}
      </div>
      {action}
    </div>
  )
}

function buildExceptions(dispatches, channels, availability) {
  const exceptions = []

  dispatches.forEach((dispatch) => {
    if (isImportDispatch(dispatch) && !dispatch.origin_port) {
      exceptions.push({
        level: '확인필요',
        title: `${dispatch.company_name || '생산사'} 수입건 항구 정보 없음`,
        detail: `${getCargoLabel(dispatch)} / ${formatDate(dispatch.pickup_date || dispatch.due_date)}`,
      })
    }

    if (!isDone(dispatch.status) && !dispatch.driver_name) {
      exceptions.push({
        level: '대기',
        title: `${dispatch.company_name || '생산사'} 배차 미확정`,
        detail: dispatch.logistics_message || getCargoLabel(dispatch),
      })
    }

    if ((dispatch.logistics_message || '').match(/실패|없음|미확인/)) {
      exceptions.push({
        level: '검토',
        title: `배차 #${dispatch.id} 판단 메시지 검토`,
        detail: dispatch.logistics_message,
      })
    }
  })

  CHANNEL_ORDER.filter((channel) => channel !== 'logistics').forEach((channel) => {
    const info = channels.find((item) => item.channel === channel)
    if (!info || info.message_count === 0) {
      exceptions.push({
        level: '미수신',
        title: `${CHANNEL_META[channel].label} 보고 없음`,
        detail: '플랫폼 보고 채널에 수신된 완료/수입 보고가 없습니다.',
      })
    }
  })

  if (!availability.last_synced_at) {
    exceptions.push({
      level: '미동기화',
      title: '물류 기사 스냅샷 미수신',
      detail: '물류사가 보낸 기사/차량 최신 상태가 없습니다.',
    })
  }

  if (availability.available_driver_count === 0) {
    exceptions.push({
      level: '부족',
      title: '가용 기사 없음',
      detail: '새 배차 판단 시 수동 확인이 필요합니다.',
    })
  }

  return exceptions
}

function buildPortSchedule(dispatches) {
  const rows = []

  dispatches.forEach((dispatch) => {
    if (isImportDispatch(dispatch)) {
      rows.push({
        id: `import-${dispatch.id}`,
        date: dispatch.pickup_date || dispatch.due_date,
        type: '수입 회수',
        place: dispatch.origin_port || '항구 미확인',
        company: dispatch.company_name || `회사 #${dispatch.company_id}`,
        cargo: getCargoLabel(dispatch),
        status: dispatch.status,
      })
    } else {
      rows.push({
        id: `export-${dispatch.id}`,
        date: dispatch.due_date || dispatch.pickup_date,
        type: '수출 반입',
        place: dispatch.destination || '도착 항구 미정',
        company: dispatch.company_name || `회사 #${dispatch.company_id}`,
        cargo: getCargoLabel(dispatch),
        status: dispatch.status,
      })
    }
  })

  return rows
    .filter((row) => row.date)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
    .slice(0, 8)
}

export default function DashboardTab() {
  const [dispatches, setDispatches] = useState([])
  const [channels, setChannels] = useState([])
  const [messagesByChannel, setMessagesByChannel] = useState({})
  const [availability, setAvailability] = useState({
    total_driver_count: 0,
    available_driver_count: 0,
    available_vehicle_count: 0,
    drivers: [],
    vehicles: [],
    last_synced_at: null,
  })
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const [dispatchRes, availabilityRes, channelRes] = await Promise.all([
        getDispatches(),
        getDispatchAvailability(),
        getReportChannels(),
      ])

      const messagePairs = await Promise.all(
        CHANNEL_ORDER.map(async (channel) => {
          try {
            const response = await getReportChannelMessages(channel)
            return [channel, response.data || []]
          } catch {
            return [channel, []]
          }
        }),
      )

      setDispatches(dispatchRes.data || [])
      setAvailability(availabilityRes.data || {})
      setChannels(channelRes.data || [])
      setMessagesByChannel(Object.fromEntries(messagePairs))
      setUpdatedAt(new Date())
    } catch {
      setDispatches([])
      setChannels([])
      setMessagesByChannel({})
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const dashboard = useMemo(() => {
    const allMessages = Object.values(messagesByChannel).flat()
    const today = localDateKey()
    const producerMessages = allMessages.filter((message) => message.channel !== 'logistics')
    const todayReports = producerMessages.filter((message) => localDateKey(message.created_at) === today)
    const completedDispatches = dispatches.filter((dispatch) => isDone(dispatch.status))
    const pendingDispatches = dispatches.filter((dispatch) => !isDone(dispatch.status))
    const roundTrips = dispatches.filter(isRoundTrip)
    const exceptions = buildExceptions(dispatches, channels, availability)
    const portSchedule = buildPortSchedule(dispatches)
    const decisionLogs = allMessages
      .filter((message) =>
        ['dispatch_planned', 'dispatch_confirmed', 'round_trip_result', 'agent_report_import', 'collected_release'].includes(
          message.event_type,
        ),
      )
      .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
      .slice(0, 8)

    return {
      todayReports,
      completedDispatches,
      pendingDispatches,
      roundTrips,
      exceptions,
      portSchedule,
      decisionLogs,
    }
  }, [availability, channels, dispatches, messagesByChannel])

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-slate-200 bg-white">
        <div className="flex flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-[12px] font-semibold uppercase text-slate-400">B2B Platform Control Board</p>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">플랫폼 오케스트레이션 대시보드</h1>
            <p className="mt-1 break-keep text-sm leading-6 text-slate-500">
              생산사 보고, 물류 가용상황, 플랫폼 배차 판단 결과를 한 화면에서 추적합니다.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right text-[12px] leading-5 text-slate-500">
              <div>마지막 갱신</div>
              <div className="font-medium text-slate-700">{updatedAt ? formatDateTime(updatedAt) : '대기 중'}</div>
            </div>
            <button
              onClick={load}
              disabled={loading}
              className="rounded-lg border border-slate-300 px-3 py-2 text-[12px] font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-wait disabled:text-slate-400"
            >
              {loading ? '갱신 중' : '새로고침'}
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <StatTile
          label="오늘 수신 보고"
          value={formatNumber(dashboard.todayReports.length)}
          caption="생산사 채널 기준"
          tone="blue"
        />
        <StatTile
          label="배차 대기"
          value={formatNumber(dashboard.pendingDispatches.length)}
          caption="플랫폼 판단 또는 물류 반영 필요"
          tone="amber"
        />
        <StatTile
          label="배차 완료"
          value={formatNumber(dashboard.completedDispatches.length)}
          caption="기사/차량 확정 건"
          tone="green"
        />
        <StatTile
          label="귀로 매칭"
          value={formatNumber(dashboard.roundTrips.length)}
          caption="수입 회수와 수출 반입 연결"
          tone="slate"
        />
        <StatTile
          label="예외 알림"
          value={formatNumber(dashboard.exceptions.length)}
          caption="항구정보 누락, 미배정, 동기화 이슈"
          tone="rose"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-lg border border-slate-200 bg-white">
          <SectionTitle
            title="회사별 보고 상태"
            caption="각 agent가 플랫폼에 마지막으로 올린 보고와 수신 건수를 보여줍니다."
          />
          <div className="divide-y divide-slate-100">
            {CHANNEL_ORDER.map((channel) => {
              const meta = CHANNEL_META[channel]
              const channelInfo = channels.find((item) => item.channel === channel)
              const messages = messagesByChannel[channel] || []
              const lastMessage = messages[0]
              const humanReport = buildHumanReportText(channel, messages, channelInfo, availability, dispatches)
              const lastAt = lastMessage?.created_at || channelInfo?.last_message_at

              return (
                <div key={channel} className="grid gap-3 px-4 py-3 md:grid-cols-[150px_1fr_120px] md:items-center">
                  <div>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[12px] font-semibold ${meta.accent}`}>
                      {meta.label}
                    </span>
                    <p className="mt-1 text-[12px] text-slate-500">{meta.role}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="break-keep text-sm font-medium leading-6 text-slate-800">{humanReport.main}</p>
                    <p className="mt-1 break-keep text-[12px] leading-5 text-slate-500">{humanReport.detail}</p>
                    <p className="mt-1 text-[12px] text-slate-400">{formatDateTime(lastAt)}</p>
                  </div>
                  <div className="text-left md:text-right">
                    <div className="text-2xl font-semibold text-slate-900">{formatNumber(channelInfo?.message_count || messages.length)}</div>
                    <div className="text-[12px] text-slate-500">표시 보고</div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white">
          <SectionTitle
            title="배차 판단 큐"
            caption="플랫폼이 종합 판단한 최근 배차 결과입니다."
            action={
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-medium text-slate-600">
                총 {formatNumber(dispatches.length)}건
              </span>
            }
          />
          <div className="divide-y divide-slate-100">
            {dispatches.length === 0 && <div className="px-4 py-8 text-center text-sm text-slate-400">배차 데이터가 없습니다.</div>}
            {dispatches.slice(0, 7).map((dispatch) => (
              <div key={dispatch.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="break-keep text-sm font-semibold text-slate-800">
                      {dispatch.company_name || `회사 #${dispatch.company_id}`} · {getCargoLabel(dispatch)}
                    </p>
                    <p className="mt-1 break-keep text-[12px] leading-5 text-slate-500">
                      {isImportDispatch(dispatch) ? `${dispatch.origin_port || '항구 미확인'} → ${dispatch.destination || '공장'}` : `${dispatch.company_name || '생산사'} → ${dispatch.destination || '항구'}`}
                    </p>
                  </div>
                  <span className={`rounded-full border px-2.5 py-1 text-[12px] font-medium ${getStatusClass(dispatch.status)}`}>
                    {dispatch.status || '상태 미정'}
                  </span>
                </div>
                <div className="mt-2 grid gap-2 text-[12px] text-slate-500 sm:grid-cols-3">
                  <div>일정 {formatDate(dispatch.pickup_date || dispatch.due_date)}</div>
                  <div>기사 {dispatch.driver_name || '미배정'}</div>
                  <div>차량 {dispatch.vehicle_plate || '미지정'}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-lg border border-slate-200 bg-white">
          <SectionTitle
            title="항구 일정 보드"
            caption="수입 회수와 수출 반입 일정을 항구 기준으로 정렬합니다."
          />
          <div className="divide-y divide-slate-100">
            {dashboard.portSchedule.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-slate-400">항구 일정 데이터가 없습니다.</div>
            )}
            {dashboard.portSchedule.map((row) => (
              <div key={row.id} className="grid gap-2 px-4 py-3 sm:grid-cols-[94px_1fr]">
                <div className="text-[12px] font-semibold text-slate-500">{formatDate(row.date)}</div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                      {row.type}
                    </span>
                    <span className="text-sm font-semibold text-slate-800">{row.place}</span>
                  </div>
                  <p className="mt-1 break-keep text-[12px] leading-5 text-slate-500">
                    {row.company} / {row.cargo} / {row.status || '상태 미정'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white">
          <SectionTitle
            title="최근 AI 판단 로그"
            caption="보고 수신 이후 플랫폼이 만든 배차 판단과 확정 내역입니다."
          />
          <div className="divide-y divide-slate-100">
            {dashboard.decisionLogs.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-slate-400">판단 로그가 없습니다.</div>
            )}
            {dashboard.decisionLogs.map((message) => (
              <div key={`${message.channel}-${message.id}`} className="grid gap-2 px-4 py-3 md:grid-cols-[92px_1fr_112px] md:items-start">
                <span className="w-fit rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                  {EVENT_LABEL[message.event_type] || message.event_type}
                </span>
                <div className="min-w-0">
                  <p className="break-keep text-sm font-medium leading-6 text-slate-800">
                    {getDecisionLogSummary(message, dispatches, availability)}
                  </p>
                  <p className="mt-1 text-[12px] text-slate-400">
                    {CHANNEL_META[message.channel]?.label || message.channel} · {message.title}
                  </p>
                </div>
                <div className="text-left text-[12px] text-slate-400 md:text-right">{formatDateTime(message.created_at)}</div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white">
        <SectionTitle
          title="예외 알림"
          caption="플랫폼 판단 품질에 영향을 주는 항목만 따로 모았습니다."
          action={
            <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[12px] font-medium text-rose-700">
              {formatNumber(dashboard.exceptions.length)}건
            </span>
          }
        />
        <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
          {dashboard.exceptions.length === 0 && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
              현재 확인할 예외가 없습니다.
            </div>
          )}
          {dashboard.exceptions.slice(0, 6).map((item, index) => (
            <div key={`${item.title}-${index}`} className="rounded-lg border border-rose-100 bg-rose-50 px-4 py-3">
              <div className="text-[12px] font-semibold text-rose-700">{item.level}</div>
              <div className="mt-1 break-keep text-sm font-semibold leading-6 text-slate-800">{item.title}</div>
              <div className="mt-1 break-keep text-[12px] leading-5 text-slate-500">{item.detail}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
