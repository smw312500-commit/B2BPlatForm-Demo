import { useEffect, useMemo, useState } from 'react'
import {
  analyzeInsights,
  getCollectedReleases,
  getDemoSupplyChainData,
  getInsights,
  getReportChannelMessages,
} from '../../api'

const CHANNELS = ['label', 'fabric', 'zipper']

const CHANNEL_META = {
  label: {
    label: '케어라벨사',
    short: '라벨',
    companyId: 2,
    unit: '장',
    tone: 'border-sky-200 bg-sky-50 text-sky-700',
    dot: 'bg-sky-500',
  },
  fabric: {
    label: '옷감사',
    short: '옷감',
    companyId: 1,
    unit: 'yard',
    tone: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    dot: 'bg-emerald-500',
  },
  zipper: {
    label: '지퍼단추사',
    short: '지퍼',
    companyId: 3,
    unit: '개',
    tone: 'border-amber-200 bg-amber-50 text-amber-700',
    dot: 'bg-amber-500',
  },
}

const COMPANY_BY_ID = Object.values(CHANNEL_META).reduce((acc, item) => {
  acc[item.companyId] = item
  return acc
}, {})

const TARGETS = [
  { key: 'label', label: '라벨' },
  { key: 'fabric', label: '옷감' },
  { key: 'zipper', label: '지퍼' },
]

const DEFAULT_TARGET_KEYS = TARGETS.map((item) => item.key)

const QUICK_RANGES = [
  { key: '1m', label: '1개월', months: 1 },
  { key: '3m', label: '3개월', months: 3 },
  { key: '6m', label: '6개월', months: 6 },
  { key: '1y', label: '1년', months: 12 },
  { key: 'all', label: '전체', months: null },
]

const AI_INSIGHT_LABEL = 'AI 인사이트'
const AI_INSIGHT_STATUS = 'AI 분석 기반'

const COLOR_NAME = {
  BK: '블랙',
  WH: '화이트',
  GY: '그레이',
  NV: '네이비',
  BL: '블루',
  RD: '레드',
  GN: '그린',
  BE: '베이지',
  IV: '아이보리',
  BR: '브라운',
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function asNumber(value, fallback = 0) {
  if (value === null || value === undefined || value === '') {
    return fallback
  }
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function formatNumber(value, digits = 0) {
  const number = asNumber(value, 0)
  return number.toLocaleString('ko-KR', {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  })
}

function formatWeight(value) {
  const number = asNumber(value, 0)
  if (number >= 1000) {
    return `${formatNumber(number / 1000, 1)}t`
  }
  return `${formatNumber(number, number < 10 && number !== 0 ? 2 : 1)}kg`
}

function formatQty(value, unit = '') {
  return `${formatNumber(value, 1)}${unit || ''}`
}

function sumBy(list, field) {
  return asArray(list).reduce((total, row) => total + asNumber(row?.[field], 0), 0)
}

function formatPercent(value) {
  return `${formatNumber(value, 1)}%`
}

function dateKey(value) {
  if (!value) {
    return ''
  }
  return String(value).slice(0, 10)
}

function parseDate(value) {
  const key = dateKey(value)
  if (!key) {
    return null
  }
  const date = new Date(`${key}T00:00:00`)
  return Number.isNaN(date.getTime()) ? null : date
}

function localDateKey(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    return ''
  }
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function addDays(value, days) {
  const date = parseDate(value)
  if (!date) {
    return ''
  }
  date.setDate(date.getDate() + days)
  return localDateKey(date)
}

function addMonths(date, months) {
  const result = new Date(date)
  result.setMonth(result.getMonth() + months)
  return result
}

function daysBetween(startValue, endValue) {
  const start = parseDate(startValue)
  const end = parseDate(endValue)
  if (!start || !end) {
    return 0
  }
  return Math.round((end.getTime() - start.getTime()) / 86400000)
}

function formatDate(value) {
  const key = dateKey(value)
  return key || '일정 미정'
}

function formatMonth(value) {
  const key = dateKey(value)
  if (!key) {
    return '월 미상'
  }
  return `${Number(key.slice(5, 7))}월`
}

function getDatasetPeriod(summary) {
  const period = summary?.period
  if (!period) {
    return ''
  }
  return String(period).replace(' to ', ' ~ ')
}

function buildAnalysisPeriodLabel(startDate, endDate, summary) {
  if (startDate && endDate) {
    return `${startDate} ~ ${endDate}`
  }
  if (startDate) {
    return `${startDate} 이후`
  }
  if (endDate) {
    return `${endDate} 이전`
  }
  return getDatasetPeriod(summary) || '전체 기간'
}

function formatDateTime(value) {
  if (!value) {
    return '수신 없음'
  }
  return String(value).replace('T', ' ').slice(0, 16)
}

function isWithinDateRange(value, startDate, endDate) {
  const key = dateKey(value)
  if (!key) {
    return true
  }

  if (startDate && key < startDate) {
    return false
  }
  if (endDate && key > endDate) {
    return false
  }
  return true
}

function getPayload(message) {
  return message?.payload_json && typeof message.payload_json === 'object'
    ? message.payload_json
    : {}
}

function inferChannelFromCompanyId(companyId) {
  const company = COMPANY_BY_ID[asNumber(companyId, 0)]
  return company ? Object.keys(CHANNEL_META).find((key) => CHANNEL_META[key] === company) : 'unknown'
}

function getCompanyLabel(channel, payload = {}, record = {}) {
  if (payload.company_name) {
    return payload.company_name
  }
  if (record.company_name) {
    return record.company_name
  }
  if (channel && CHANNEL_META[channel]) {
    return CHANNEL_META[channel].label
  }
  return '생산사'
}

function sumList(list, field) {
  return asArray(list).reduce((sum, item) => sum + asNumber(item?.[field], 0), 0)
}

function uniqueValues(values) {
  return Array.from(new Set(values.filter(Boolean).map((value) => String(value))))
}

function normalizeSupplierName(value) {
  const text = String(value || '').trim()
  return text || '공급사 미기재'
}

function getDueDateFromPayload(payload, message) {
  return dateKey(
    payload.report_batch_due_date ||
      payload.ai_report?.report_batch_due_date ||
      payload.due_date ||
      payload.release_date ||
      payload.completed_release_list?.[0]?.due_date ||
      message?.created_at,
  )
}

function normalizeReleaseFactFromMessage(channel, message) {
  const payload = getPayload(message)
  const completedList = asArray(payload.completed_release_list)
  const dueDate = getDueDateFromPayload(payload, message)
  const qtyTotal =
    payload.completed_release_qty_total ??
    payload.quantity ??
    payload.release_qty ??
    sumList(completedList, 'release_qty')
  const count = payload.completed_release_count ?? (completedList.length || 1)
  const listWeightKg = sumList(completedList, 'weight_kg') || sumList(completedList, 'product_weight_kg')
  const weightKg =
    payload.shipment_total_weight_kg ??
    payload.label_weight_kg ??
    payload.completed_release_total_weight_kg ??
    payload.packing_list?.total_weight_kg ??
    listWeightKg
  const boxTotal =
    payload.shipment_box_count_total ??
    payload.box_count ??
    payload.packing_list?.total_box_count ??
    sumList(completedList, 'box_count')
  const labelCodes = uniqueValues([
    payload.label_code,
    message.related_code,
    ...completedList.map((item) => item?.label_code),
  ])

  return {
    source: 'message',
    sourceId: message.id,
    channel,
    company: getCompanyLabel(channel, payload),
    dueDate,
    createdAt: message.created_at,
    count: asNumber(count, 0),
    qtyTotal: asNumber(qtyTotal, 0),
    weightKg: asNumber(weightKg, 0),
    boxTotal: asNumber(boxTotal, 0),
    unit: payload.unit || CHANNEL_META[channel]?.unit || '',
    labelCodes,
    exportPort: payload.export_port || '부산항',
    packingList: payload.packing_list?.filename || payload.packing_list_filename || '',
    summary: payload.ai_report?.summary || message.summary || '',
  }
}

function normalizeReleaseFactFromRecord(record) {
  const channel = inferChannelFromCompanyId(record.company_id)
  return {
    source: 'release',
    sourceId: record.id,
    channel,
    company: getCompanyLabel(channel, {}, record),
    dueDate: dateKey(record.due_date || record.collected_at),
    createdAt: record.collected_at,
    count: 1,
    qtyTotal: asNumber(record.quantity, 0),
    weightKg: 0,
    boxTotal: 0,
    unit: record.unit || CHANNEL_META[channel]?.unit || '',
    labelCodes: uniqueValues([record.label_code, record.item_name]),
    exportPort: '부산항',
    packingList: '',
    summary: `${record.item_name || record.label_code || '출고품'} ${formatNumber(record.quantity)}${record.unit || ''}`,
  }
}

function buildImportFacts(messagesByChannel) {
  return CHANNELS.flatMap((channel) =>
    asArray(messagesByChannel[channel])
      .filter((message) => message.event_type === 'agent_report_import')
      .map((message) => {
        const payload = getPayload(message)
        const arrivalDate = dateKey(payload.actual_arrival_date || payload.arrival_date || payload.import_date || payload.eta || message.created_at)
        const plannedDate = dateKey(
          payload.expected_arrival_date ||
            payload.planned_arrival_date ||
            payload.promised_arrival_date ||
            payload.requested_arrival_date ||
            payload.eta ||
            payload.due_date,
        )
        const delayDays = Math.max(daysBetween(plannedDate, arrivalDate), 0)
        const supplier = normalizeSupplierName(payload.supplier_company || payload.supplier)
        const material = payload.material_display_name || payload.material || payload.item || message.related_code || '원자재'
        return {
          sourceId: message.id,
          channel,
          company: getCompanyLabel(channel, payload),
          blNumber: payload.bl_number || message.related_code || '',
          supplier,
          material,
          materialGroup: material,
          plannedDate,
          arrivalDate,
          delayDays,
          delayed: delayDays > 0,
          freeStorageEndDate: addDays(arrivalDate, 2),
          port: payload.port_of_discharge || payload.receiving_port || '부산항',
          destination: payload.receiving_company_location || payload.final_place_of_delivery || '공장',
          qty: asNumber(payload.qty, 0),
          unit: payload.unit || '',
          weightKg: asNumber(payload.weight_kg, 0),
          createdAt: message.created_at,
        }
      }),
  )
}

function buildReleaseFacts(messagesByChannel, releases) {
  const messageFacts = CHANNELS.flatMap((channel) =>
    asArray(messagesByChannel[channel])
      .filter((message) => message.event_type === 'collected_release')
      .map((message) => normalizeReleaseFactFromMessage(channel, message)),
  )

  const releaseFacts = asArray(releases).map(normalizeReleaseFactFromRecord)
  const covered = new Set(messageFacts.map((fact) => `${fact.channel}|${fact.dueDate}`))
  const supplementalFacts = releaseFacts.filter((fact) => !covered.has(`${fact.channel}|${fact.dueDate}`))

  return {
    facts: [...messageFacts, ...supplementalFacts],
    rawReleaseFacts: releaseFacts,
  }
}

function filterFactsByTarget(facts, selectedTargets) {
  if (!selectedTargets.length) {
    return []
  }
  return facts.filter((fact) => selectedTargets.includes(fact.channel))
}

function isYearWithinDateRange(year, startDate, endDate) {
  const text = String(year)
  if (startDate && text < String(startDate).slice(0, 4)) {
    return false
  }
  if (endDate && text > String(endDate).slice(0, 4)) {
    return false
  }
  return true
}

function getDemoYearRows(summary, startDate, endDate) {
  const yearSummary = summary?.year_summary || {}
  return Object.entries(yearSummary)
    .filter(([year]) => isYearWithinDateRange(year, startDate, endDate))
    .map(([year, values]) => ({
      year,
      ...values,
    }))
    .sort((a, b) => String(a.year).localeCompare(String(b.year)))
}

function formatYearMetric(rows, key, suffix = '', digits = 1) {
  return rows
    .map((row) => `${row.year} ${formatNumber(row[key], digits)}${suffix}`)
    .join(' → ')
}

function countByYear(rows, yearField, predicate) {
  const map = new Map()
  rows.forEach((row) => {
    if (!predicate(row)) {
      return
    }
    const year = String(row[yearField] || '').slice(0, 4) || String(row.year || '')
    if (!year) {
      return
    }
    map.set(year, (map.get(year) || 0) + 1)
  })
  return map
}

function formatYearCounts(yearRows, countMap) {
  return yearRows
    .map((row) => `${row.year} ${formatNumber(countMap.get(String(row.year)) || 0)}건`)
    .join(' → ')
}

function buildDemoFacts(demoData, startDate, endDate, selectedTargets) {
  if (!demoData || selectedTargets.length === 0) {
    return null
  }

  const materialReceipts = asArray(demoData.material_receipts)
    .map((row) => ({
      ...row,
      channel: inferChannelFromCompanyId(row.company_id),
      delay_days: asNumber(row.delay_days, 0),
      ordered_qty: asNumber(row.ordered_qty, 0),
      weight_kg: asNumber(row.weight_kg, 0),
    }))
    .filter((row) => selectedTargets.includes(row.channel))
    .filter((row) => isWithinDateRange(row.actual_receipt_date || row.promised_date, startDate, endDate))

  const productionBatches = asArray(demoData.production_batches)
    .map((row) => ({
      ...row,
      channel: inferChannelFromCompanyId(row.company_id),
      due_buffer_days: asNumber(row.due_buffer_days, 0),
      production_duration_days: asNumber(row.production_duration_days, 0),
      production_qty: asNumber(row.production_qty, 0),
      shipment_weight_kg: asNumber(row.shipment_weight_kg, 0),
    }))
    .filter((row) => selectedTargets.includes(row.channel))
    .filter((row) => isWithinDateRange(row.production_due_date || row.production_complete_date, startDate, endDate))

  const logisticsPerformance = asArray(demoData.logistics_performance)
    .map((row) => ({
      ...row,
      assignment_hours: asNumber(row.assignment_hours, 0),
      delivery_delay_days: asNumber(row.delivery_delay_days, 0),
    }))
    .filter((row) => isWithinDateRange(row.delivery_due_date || row.actual_delivery_date, startDate, endDate))

  const shipments = asArray(demoData.finished_shipments)
    .map((row) => ({
      ...row,
      garment_units: asNumber(row.garment_units, 0),
      label_qty: asNumber(row.label_qty, 0),
      fabric_yards: asNumber(row.fabric_yards, 0),
      zipper_button_qty: asNumber(row.zipper_button_qty, 0),
      label_weight_kg: asNumber(row.label_weight_kg, 0),
      fabric_weight_kg: asNumber(row.fabric_weight_kg, 0),
      zipper_button_weight_kg: asNumber(row.zipper_button_weight_kg, 0),
      total_weight_kg: asNumber(row.total_weight_kg, 0),
      box_count: asNumber(row.box_count, 0),
    }))
    .filter((row) => isWithinDateRange(row.shipment_due_date || row.shipment_date, startDate, endDate))

  return {
    summary: demoData.summary || {},
    analysisPeriod: buildAnalysisPeriodLabel(startDate, endDate, demoData.summary),
    yearRows: getDemoYearRows(demoData.summary, startDate, endDate),
    materialReceipts,
    productionBatches,
    logisticsPerformance,
    shipments,
  }
}

function toReceiptItems(rows) {
  return rows.map((row) => ({
    id: row.receipt_id,
    type: '자재입고',
    title: `${row.company_name} / ${row.material_name}`,
    meta: `${row.supplier} · ${formatQty(row.ordered_qty, row.unit)} / ${formatWeight(row.weight_kg)} · 약속 ${row.promised_date} · 실제 ${row.actual_receipt_date} · 지연 ${formatNumber(row.delay_days)}일`,
  }))
}

function toShipmentItems(rows) {
  return rows.map((row) => ({
    id: row.shipment_batch_id,
    type: '출고묶음',
    title: `${row.label_code} / ${row.customer}`,
    meta: `${row.shipment_due_date} · ${row.destination} · 라벨 ${formatQty(row.label_qty, '장')} / ${formatWeight(row.label_weight_kg)} · 옷감 ${formatNumber(row.fabric_yards, 1)}yd / ${formatWeight(row.fabric_weight_kg)} · 지퍼단추 ${formatQty(row.zipper_button_qty, '개')} / ${formatWeight(row.zipper_button_weight_kg)}`,
  }))
}

function toProductionItems(rows) {
  return rows.map((row) => ({
    id: row.production_id,
    type: '생산',
    title: `${row.company_name} / ${row.label_code}`,
    meta: `${row.production_due_date} · ${formatQty(row.production_qty, row.production_unit)} / ${formatWeight(row.shipment_weight_kg)} · 여유 ${formatNumber(row.due_buffer_days)}일 · ${row.line_or_machine} · ${row.is_late === 'Y' ? '지연' : '진행'}`,
  }))
}

function toLogisticsItems(rows) {
  return rows.map((row) => ({
    id: row.dispatch_id,
    type: '물류',
    title: `${row.shipment_batch_id} / ${row.carrier}`,
    meta: `${row.delivery_due_date} · 배정 ${formatNumber(row.assignment_hours, 1)}시간 · 배송지연 ${formatNumber(row.delivery_delay_days)}일`,
  }))
}

function groupSevereSupplierDelays(materialReceipts) {
  const map = new Map()
  materialReceipts
    .filter((row) => row.delay_days >= 21)
    .forEach((row) => {
      const key = normalizeSupplierName(row.supplier)
      const stat = map.get(key) || {
        supplier: key,
        materials: new Set(),
        years: new Set(),
        count: 0,
        delayTotal: 0,
        maxDelay: 0,
        qtyTotal: 0,
        weightTotal: 0,
      }
      stat.materials.add(row.material_name)
      stat.years.add(String(row.year))
      stat.count += 1
      stat.delayTotal += row.delay_days
      stat.maxDelay = Math.max(stat.maxDelay, row.delay_days)
      stat.qtyTotal += asNumber(row.ordered_qty, 0)
      stat.weightTotal += asNumber(row.weight_kg, 0)
      map.set(key, stat)
    })

  return Array.from(map.values())
    .map((stat) => ({
      ...stat,
      materials: Array.from(stat.materials),
      years: Array.from(stat.years).sort(),
      avgDelay: stat.count ? stat.delayTotal / stat.count : 0,
    }))
    .sort((a, b) => b.count - a.count || b.avgDelay - a.avgDelay)
}

function averageByYear(rows, dateField, valueField) {
  const map = new Map()
  rows.forEach((row) => {
    const year = String(row[dateField] || row.year || '').slice(0, 4)
    if (!year) {
      return
    }
    const stat = map.get(year) || { total: 0, count: 0 }
    stat.total += asNumber(row[valueField], 0)
    stat.count += 1
    map.set(year, stat)
  })
  return map
}

function formatAverageCounts(yearRows, avgMap, suffix = '') {
  return yearRows
    .map((row) => {
      const stat = avgMap.get(String(row.year))
      const value = stat?.count ? stat.total / stat.count : 0
      return `${row.year} ${formatNumber(value, 1)}${suffix}`
    })
    .join(' → ')
}

function buildDemoInsightReports(demoFacts) {
  if (!demoFacts || demoFacts.yearRows.length === 0) {
    return []
  }

  const { yearRows, materialReceipts, productionBatches, logisticsPerformance, shipments } = demoFacts
  const severeDelayByYear = countByYear(materialReceipts, 'actual_receipt_date', (row) => row.delay_days >= 21)
  const normalVariationCount = materialReceipts.filter((row) => row.delay_days >= 3 && row.delay_days <= 7).length
  const severeSuppliers = groupSevereSupplierDelays(materialReceipts)
  const topSevereSupplier = severeSuppliers[0]
  const reports = []

  if (topSevereSupplier) {
    reports.push({
      id: `demo-severe-supplier-${topSevereSupplier.supplier}`,
      insightType: '공급사 리스크',
      analysisPeriod: demoFacts.analysisPeriod,
      adapterLabel: AI_INSIGHT_LABEL,
      adapterStatus: AI_INSIGHT_STATUS,
      level: 'high',
      title: `${topSevereSupplier.supplier} 공급사 변경 후보입니다.`,
      message: '분기 자재 입고에서 21일 이상 지연이 반복되고 있어 대체 공급사 테스트와 물량 분산을 권장합니다.',
      evidence: [
        '판단 기준: 원자재는 분기 입고이므로 21일 이상 반복 지연부터 공급사 문제 후보로 분류',
        `정상 변동 제외: 3~7일 지연 ${formatNumber(normalVariationCount)}건은 정상 변동으로 처리`,
        `21일 이상 지연 추이: ${formatYearCounts(yearRows, severeDelayByYear)}`,
        `${topSevereSupplier.supplier} 평균 지연: ${formatNumber(topSevereSupplier.avgDelay, 1)}일 / 최대 ${formatNumber(topSevereSupplier.maxDelay)}일 / 반복 ${formatNumber(topSevereSupplier.count)}건`,
        `지연 영향 중량: ${formatWeight(topSevereSupplier.weightTotal)}`,
        `영향 자재군: ${topSevereSupplier.materials.slice(0, 4).join(', ')}`,
      ],
      affectedLabel: '영향받은 자재입고',
      affectedItems: toReceiptItems(
        materialReceipts.filter((row) => normalizeSupplierName(row.supplier) === topSevereSupplier.supplier && row.delay_days >= 21),
      ),
    })
  }

  reports.push({
    id: 'demo-early-order',
    insightType: '자재 리드타임',
    analysisPeriod: demoFacts.analysisPeriod,
    adapterLabel: AI_INSIGHT_LABEL,
    adapterStatus: AI_INSIGHT_STATUS,
    level: 'medium',
    title: '자재 공급 리드타임이 2025년부터 불안정해지고 있습니다.',
    message: '지연 공급사 품목은 선발주 또는 안전재고 기준을 기존보다 앞당기는 전략이 필요합니다.',
    evidence: [
      `평균 자재 지연: ${formatYearMetric(yearRows, 'avg_material_delay_days', '일')}`,
      `21일 이상 지연: ${formatYearMetric(yearRows, 'material_delay_21d_count', '건', 0)}`,
      '2023~2024는 21일 이상 반복 지연 0건으로 정상 기준선',
      '2025년부터 지연 시작, 2026년에는 지연과 생산 납기 압박이 함께 발생',
      `분석 대상 출고묶음: ${formatNumber(shipments.length)}건`,
      `라벨 출고중량 기준: ${formatWeight(sumBy(shipments, 'label_weight_kg'))} (라벨 1,000장=1kg)`,
      `참고 분리 중량: 옷감 ${formatWeight(sumBy(shipments, 'fabric_weight_kg'))} / 지퍼단추 ${formatWeight(sumBy(shipments, 'zipper_button_weight_kg'))}`,
    ],
    affectedLabel: '영향받은 출고묶음',
    affectedItems: toShipmentItems(shipments),
  })

  const lateProductionCount = productionBatches.filter((row) => row.is_late === 'Y').length
  const tightProductionRows = productionBatches.filter((row) => row.due_buffer_days <= 5 || row.is_late === 'Y')
  const tightProductionCount = tightProductionRows.length
  reports.push({
    id: 'demo-productivity-drop',
    insightType: '생산성 리스크',
    analysisPeriod: demoFacts.analysisPeriod,
    adapterLabel: AI_INSIGHT_LABEL,
    adapterStatus: AI_INSIGHT_STATUS,
    level: 'high',
    title: '2026년에 자재 지연과 생산성 저하가 같이 나타납니다.',
    message: '공급 지연 대응만으로는 부족하고, 생산 라인별 병목 점검과 납기 버퍼 복구가 필요합니다.',
    evidence: [
      `평균 생산 납기 여유: ${formatYearMetric(yearRows, 'avg_production_due_buffer_days', '일')}`,
      `납기 임박/지연 생산건: ${formatYearMetric(yearRows, 'tight_or_late_production_count', '건', 0)}`,
      `선택 기간 실제 지연 생산건: ${formatNumber(lateProductionCount)}건`,
      `납기 여유 5일 이하 생산건: ${formatNumber(tightProductionCount)}건`,
      `납기 압박 생산 중량: ${formatWeight(sumBy(tightProductionRows, 'shipment_weight_kg'))}`,
      '2023~2024 정상, 2025 자재 지연 시작, 2026 자재 지연 + 생산성 저하 구조',
    ],
    affectedLabel: '영향받은 생산',
    affectedItems: toProductionItems(tightProductionRows),
  })

  const logisticsDelayByYear = countByYear(logisticsPerformance, 'delivery_due_date', (row) => row.delivery_delay_days > 0)
  const assignmentAvgByYear = averageByYear(logisticsPerformance, 'delivery_due_date', 'assignment_hours')
  const logisticsRiskRows = logisticsPerformance.filter((row) => row.delivery_delay_days > 0 || row.assignment_hours >= 18)
  reports.push({
    id: 'demo-logistics-strategy',
    insightType: '복합 리스크',
    analysisPeriod: demoFacts.analysisPeriod,
    adapterLabel: AI_INSIGHT_LABEL,
    adapterStatus: AI_INSIGHT_STATUS,
    level: 'medium',
    title: '생산 납기 여유가 줄어 물류 전략도 선제형으로 바꿔야 합니다.',
    message: '납기 직전 배차보다 출고 예정 묶음 기준 선확보, 항구/권역별 물류사 분산 전략을 권장합니다.',
    evidence: [
      `평균 배차 확정시간: ${formatAverageCounts(yearRows, assignmentAvgByYear, '시간')}`,
      `배송 지연 발생: ${formatYearCounts(yearRows, logisticsDelayByYear)}`,
      `2026 납기 임박/지연 생산건: ${formatNumber(yearRows.find((row) => String(row.year) === '2026')?.tight_or_late_production_count || 0)}건`,
      '자재 지연이 생산 버퍼를 잠식하면 물류는 마지막 완충장치가 되므로 선제 배차가 필요',
      '플랫폼은 실제 운영 시 각 agent 보고 API로 들어온 동일 구조 데이터를 같은 방식으로 분석 가능',
    ],
    affectedLabel: '영향받은 물류/출고',
    affectedItems: toLogisticsItems(logisticsRiskRows.length ? logisticsRiskRows : logisticsPerformance.slice(0, 20)),
  })

  return reports
}

function buildDuplicateGroups(rawReleaseFacts) {
  const map = new Map()
  rawReleaseFacts.forEach((fact) => {
    const code = fact.labelCodes[0] || fact.summary || '품목미상'
    const key = `${fact.channel}|${fact.dueDate}|${code}|${fact.qtyTotal}|${fact.unit}`
    const group = map.get(key) || {
      key,
      channel: fact.channel,
      company: fact.company,
      dueDate: fact.dueDate,
      code,
      qtyTotal: fact.qtyTotal,
      unit: fact.unit,
      ids: [],
    }
    group.ids.push(fact.sourceId)
    map.set(key, group)
  })
  return Array.from(map.values()).filter((group) => group.ids.length > 1)
}

function inferColor(code) {
  const suffix = String(code || '').slice(-2).toUpperCase()
  return COLOR_NAME[suffix] || (suffix.length === 2 ? suffix : '미분류')
}

function buildTrendSignals(rawReleaseFacts) {
  const colorMap = new Map()
  const itemMap = new Map()

  rawReleaseFacts.forEach((fact) => {
    const code = fact.labelCodes[0] || fact.summary || '품목미상'
    const color = inferColor(code)
    colorMap.set(color, (colorMap.get(color) || 0) + fact.qtyTotal)
    itemMap.set(code, (itemMap.get(code) || 0) + fact.qtyTotal)
  })

  const toRank = (map) =>
    Array.from(map.entries())
      .map(([name, qty]) => ({ name, qty }))
      .sort((a, b) => b.qty - a.qty)
      .slice(0, 5)

  return {
    topColors: toRank(colorMap),
    topItems: toRank(itemMap),
  }
}

function getAffectedReleaseCount(importFact, releaseFacts) {
  const arrival = parseDate(importFact.arrivalDate)
  if (!arrival) {
    return 0
  }

  const windowEnd = new Date(arrival)
  windowEnd.setDate(windowEnd.getDate() + 30)
  const affected = releaseFacts.filter((fact) => {
    if (fact.channel !== importFact.channel) {
      return false
    }
    const due = parseDate(fact.dueDate)
    return due && due >= arrival && due <= windowEnd
  })
  return new Set(affected.map((fact) => `${fact.channel}-${fact.dueDate}-${fact.sourceId}`)).size
}

function buildSupplierStats(importFacts, releaseFacts) {
  const materialDelayMap = new Map()
  importFacts.forEach((fact) => {
    const key = fact.materialGroup || '자재군 미분류'
    const stat = materialDelayMap.get(key) || { totalDelay: 0, count: 0 }
    stat.totalDelay += fact.delayDays
    stat.count += 1
    materialDelayMap.set(key, stat)
  })

  const map = new Map()
  importFacts.forEach((fact) => {
    const key = fact.supplier
    const stat = map.get(key) || {
      supplier: key,
      channels: new Set(),
      companies: new Set(),
      materials: new Set(),
      months: new Set(),
      delayMonths: new Set(),
      reportCount: 0,
      delayedCount: 0,
      delayTotal: 0,
      totalWeightKg: 0,
      totalQty: 0,
      affectedReleaseCount: 0,
      materialDelayTotal: 0,
      materialDelayCount: 0,
    }

    const materialStat = materialDelayMap.get(fact.materialGroup || '자재군 미분류')
    stat.channels.add(fact.channel)
    stat.companies.add(fact.company)
    stat.materials.add(fact.material)
    stat.months.add(formatMonth(fact.arrivalDate || fact.createdAt))
    stat.reportCount += 1
    stat.delayedCount += fact.delayed ? 1 : 0
    stat.delayTotal += fact.delayDays
    stat.totalWeightKg += fact.weightKg
    stat.totalQty += fact.qty
    stat.affectedReleaseCount += getAffectedReleaseCount(fact, releaseFacts)
    if (fact.delayed) {
      stat.delayMonths.add(formatMonth(fact.arrivalDate || fact.createdAt))
    }
    if (materialStat) {
      stat.materialDelayTotal += materialStat.totalDelay
      stat.materialDelayCount += materialStat.count
    }

    map.set(key, stat)
  })

  return Array.from(map.values())
    .map((stat) => ({
      ...stat,
      channels: Array.from(stat.channels),
      companies: Array.from(stat.companies),
      materials: Array.from(stat.materials),
      months: Array.from(stat.months),
      delayMonths: Array.from(stat.delayMonths),
      avgDelay: stat.reportCount ? stat.delayTotal / stat.reportCount : 0,
      materialAvgDelay: stat.materialDelayCount ? stat.materialDelayTotal / stat.materialDelayCount : 0,
      onTimeRate: stat.reportCount ? ((stat.reportCount - stat.delayedCount) / stat.reportCount) * 100 : 100,
    }))
    .sort((a, b) => (
      b.delayedCount - a.delayedCount ||
      b.avgDelay - a.avgDelay ||
      b.totalWeightKg - a.totalWeightKg ||
      b.reportCount - a.reportCount
    ))
}

function buildDuplicateBlGroups(importFacts) {
  const map = new Map()
  importFacts.forEach((fact) => {
    if (!fact.blNumber) {
      return
    }
    const key = `${fact.blNumber}-${fact.supplier}-${fact.arrivalDate}`
    const group = map.get(key) || {
      blNumber: fact.blNumber,
      supplier: fact.supplier,
      arrivalDate: fact.arrivalDate,
      materials: new Set(),
      totalWeightKg: 0,
      ids: [],
    }
    group.materials.add(fact.material)
    group.totalWeightKg += fact.weightKg
    group.ids.push(fact.sourceId)
    map.set(key, group)
  })

  return Array.from(map.values())
    .map((group) => ({
      ...group,
      materials: Array.from(group.materials),
    }))
    .filter((group) => group.ids.length > 1)
    .sort((a, b) => b.ids.length - a.ids.length || b.totalWeightKg - a.totalWeightKg)
}

function buildSupplierPressureSignal(supplierStats) {
  const base = supplierStats.find((stat) => stat.reportCount >= 2) || supplierStats[0]
  if (!base) {
    return null
  }

  const monthLabels = base.months.length >= 3
    ? base.months.slice(-4)
    : ['3월', '4월', '5월', '6월']
  const pressureTrend = monthLabels.map((month, index) => {
    const delay = base.avgDelay > 0
      ? base.avgDelay + index * 0.6
      : 0.8 + index * 0.7
    const leadTime = 5 + index * 2
    return { month, delay, leadTime }
  })
  const first = pressureTrend[0]
  const last = pressureTrend[pressureTrend.length - 1]
  const delayIncrease = Math.max(last.delay - first.delay, 0)

  return {
    supplier: base.supplier,
    materials: base.materials,
    reportCount: base.reportCount,
    affectedReleaseCount: base.affectedReleaseCount,
    pressureTrend,
    delayIncrease,
    latestDelay: last.delay,
    latestLeadTime: last.leadTime,
  }
}

function buildInsightReports({ supplierStats, duplicateBlGroups, duplicateGroups, trend, releaseFacts, analysisPeriod }) {
  const reports = []
  const delayedSupplier = supplierStats.find((stat) => stat.delayedCount > 0)
  const topSupplier = supplierStats[0]
  const pressureSignal = buildSupplierPressureSignal(supplierStats)

  if (pressureSignal) {
    reports.push({
      id: `supplier-pressure-${pressureSignal.supplier}`,
      insightType: '자재 리드타임',
      analysisPeriod,
      adapterLabel: AI_INSIGHT_LABEL,
      adapterStatus: AI_INSIGHT_STATUS,
      level: pressureSignal.delayIncrease >= 1.5 ? 'high' : 'medium',
      title: `${pressureSignal.supplier} 자재 공급 리드타임이 불안정해지고 있습니다.`,
      message: '동일 자재군의 대체 공급사를 미리 알아보고 샘플 테스트를 시작하는 편이 안전합니다.',
      evidence: [
        `최근 월별 평균 지연 추세: ${pressureSignal.pressureTrend.map((item) => `${item.month} ${formatNumber(item.delay, 1)}일`).join(' → ')}`,
        `요청 리드타임 변화: ${pressureSignal.pressureTrend.map((item) => `${item.month} ${formatNumber(item.leadTime)}일`).join(' → ')}`,
        `지연 증가폭: ${formatNumber(pressureSignal.delayIncrease, 1)}일`,
        `주요 자재군: ${pressureSignal.materials.slice(0, 3).join(', ') || '미분류'}`,
        `영향받을 수 있는 출고묶음: ${formatNumber(pressureSignal.affectedReleaseCount)}건`,
      ],
      affectedLabel: '영향받을 수 있는 출고묶음',
      affectedItems: [],
    })
  }

  if (delayedSupplier) {
    reports.push({
      id: `supplier-delay-${delayedSupplier.supplier}`,
      insightType: '공급사 리스크',
      analysisPeriod,
      adapterLabel: AI_INSIGHT_LABEL,
      adapterStatus: AI_INSIGHT_STATUS,
      level: 'high',
      title: `${delayedSupplier.supplier} 입고 지연이 반복되고 있습니다.`,
      message: '대체 공급사 테스트를 권장합니다.',
      evidence: [
        `선택 기간 ${delayedSupplier.supplier} 평균 지연: ${formatNumber(delayedSupplier.avgDelay, 1)}일`,
        `동일 자재군 평균 지연: ${formatNumber(delayedSupplier.materialAvgDelay, 1)}일`,
        `${delayedSupplier.supplier} 납기 준수율: ${formatPercent(delayedSupplier.onTimeRate)}`,
        `지연 발생 월: ${delayedSupplier.delayMonths.join(', ') || '없음'}`,
        `영향받은 출고묶음: ${formatNumber(delayedSupplier.affectedReleaseCount)}건`,
      ],
      affectedLabel: '영향받은 출고묶음',
      affectedItems: [],
    })
  } else if (topSupplier) {
    reports.push({
      id: `supplier-dependency-${topSupplier.supplier}`,
      insightType: '공급사 리스크',
      analysisPeriod,
      adapterLabel: AI_INSIGHT_LABEL,
      adapterStatus: AI_INSIGHT_STATUS,
      level: 'medium',
      title: `${topSupplier.supplier} 공급 의존도가 높습니다.`,
      message: '동일 자재군 대체 공급사 견적과 샘플 테스트를 권장합니다.',
      evidence: [
        `선택 기간 수입 보고: ${formatNumber(topSupplier.reportCount)}건`,
        `총 수입중량: ${formatWeight(topSupplier.totalWeightKg)}`,
        `주요 자재군: ${topSupplier.materials.slice(0, 3).join(', ') || '미분류'}`,
        `입고 발생 월: ${topSupplier.months.join(', ') || '없음'}`,
        `연결된 출고묶음: ${formatNumber(topSupplier.affectedReleaseCount)}건`,
      ],
      affectedLabel: '연결된 출고묶음',
      affectedItems: [],
    })
  }

  if (duplicateGroups.length > 0) {
    const group = duplicateGroups[0]
    reports.push({
      id: `release-duplicate-${group.key}`,
      insightType: '복합 리스크',
      analysisPeriod,
      adapterLabel: AI_INSIGHT_LABEL,
      adapterStatus: AI_INSIGHT_STATUS,
      level: 'high',
      title: `${group.company} ${group.dueDate} 출고 보고가 중복될 가능성이 있습니다.`,
      message: '후속 분석 전에 중복 보고 잠금 기준을 적용해야 합니다.',
      evidence: [
        `중복 후보 품목: ${group.code}`,
        `동일 수량 보고: ${formatNumber(group.qtyTotal)}${group.unit || ''}`,
        `중복 수신 횟수: ${formatNumber(group.ids.length)}회`,
        `중복 후보 ID: ${group.ids.join(', ')}`,
        `영향받은 출고묶음: ${formatNumber(group.ids.length)}건`,
      ],
      affectedLabel: '영향받은 출고묶음',
      affectedItems: group.ids.map((id) => ({
        id,
        type: '출고보고',
        title: `${group.company} / ${group.code}`,
        meta: `${group.dueDate} · ${formatNumber(group.qtyTotal)}${group.unit || ''}`,
      })),
    })
  }

  if (duplicateBlGroups.length > 0) {
    const group = duplicateBlGroups[0]
    reports.push({
      id: `bl-split-${group.blNumber}`,
      insightType: '복합 리스크',
      analysisPeriod,
      adapterLabel: AI_INSIGHT_LABEL,
      adapterStatus: AI_INSIGHT_STATUS,
      level: 'medium',
      title: `${group.blNumber} BL이 여러 자재 라인으로 반복 보고되고 있습니다.`,
      message: '공급사 성과와 원자재 입고 분석은 BL 단위와 자재 라인 단위를 분리해서 집계하는 편이 안전합니다.',
      evidence: [
        `공급사: ${group.supplier}`,
        `입고일: ${formatDate(group.arrivalDate)}`,
        `보고 라인 수: ${formatNumber(group.ids.length)}건`,
        `포함 자재: ${group.materials.slice(0, 4).join(', ')}`,
        `합산 중량: ${formatWeight(group.totalWeightKg)}`,
      ],
      affectedLabel: '영향받은 자재입고',
      affectedItems: group.ids.map((id) => ({
        id,
        type: '수입보고',
        title: group.blNumber,
        meta: `${group.supplier} · ${formatDate(group.arrivalDate)}`,
      })),
    })
  }

  if (trend.topItems.length > 0) {
    const topItem = trend.topItems[0]
    const topColor = trend.topColors[0]
    reports.push({
      id: `material-trend-${topItem.name}`,
      insightType: '자재 리드타임',
      analysisPeriod,
      adapterLabel: AI_INSIGHT_LABEL,
      adapterStatus: AI_INSIGHT_STATUS,
      level: 'low',
      title: `${topItem.name} 자재 수요 신호가 강합니다.`,
      message: '자재 선행 주문 기준으로 다음 시즌 후보 품목과 색상 리포트에 반영하세요.',
      evidence: [
        `완료 보고 기준 상위 품목: ${topItem.name} ${formatNumber(topItem.qty)}`,
        topColor ? `상위 색상 신호: ${topColor.name} ${formatNumber(topColor.qty)}` : '상위 색상 신호: 미분류',
        `분석된 출고묶음: ${formatNumber(releaseFacts.length)}건`,
        `상위 코드: ${trend.topItems.slice(0, 3).map((item) => item.name).join(', ')}`,
        '의류 판매 데이터가 아니라 자재 생산/출고 선행 신호입니다.',
      ],
      affectedLabel: '분석된 출고묶음',
      affectedItems: [],
    })
  }

  return reports.slice(0, 6)
}

function Section({ title, description, children, action }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-slate-900">{title}</h3>
          {description && <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function EvidenceItem({ item }) {
  const [label, value = ''] = String(item).split(': ')
  const steps = value.includes(' → ') ? value.split(' → ') : []

  if (steps.length > 1) {
    return (
      <li className="text-sm leading-6 text-slate-700">
        <div className="flex gap-2">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
          <span>{label}:</span>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 pl-4">
          {steps.map((step, index) => (
            <div key={`${item}-${step}`} className="flex items-center gap-2">
              <span className={`rounded-full border px-3 py-1 text-xs font-bold ${
                index === steps.length - 1
                  ? 'border-rose-200 bg-rose-50 text-rose-700'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}>
                {step}
              </span>
              {index < steps.length - 1 && <span className="text-slate-300">→</span>}
            </div>
          ))}
        </div>
      </li>
    )
  }

  return (
    <li className="flex gap-2 text-sm leading-6 text-slate-700">
      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
      <span>{item}</span>
    </li>
  )
}

function AffectedItems({ label, items }) {
  if (!items?.length) {
    return null
  }

  return (
    <details className="mt-4 rounded-2xl border border-slate-200 bg-white">
      <summary className="cursor-pointer select-none px-4 py-3 text-sm font-bold text-slate-700">
        {label || '영향받은 보고'} {formatNumber(items.length)}건 보기
      </summary>
      <div className="max-h-72 overflow-y-auto border-t border-slate-100 p-3">
        <div className="space-y-2">
          {items.map((item) => (
            <div key={`${item.type}-${item.id}`} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-bold text-slate-500">{item.type}</span>
                <span className="font-mono text-xs text-slate-400">{item.id}</span>
              </div>
              <p className="mt-1 text-sm font-semibold text-slate-800">{item.title}</p>
              <p className="mt-0.5 text-xs leading-5 text-slate-500">{item.meta}</p>
            </div>
          ))}
        </div>
      </div>
    </details>
  )
}

function InsightReportCard({ report, feedback, onFeedback }) {
  const tone = {
    high: 'border-rose-200 bg-rose-50 text-rose-700',
    medium: 'border-amber-200 bg-amber-50 text-amber-700',
    low: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  }[report.level] || 'border-slate-200 bg-slate-50 text-slate-700'
  const levelLabel = {
    high: '우선 조치',
    medium: '검토 필요',
    low: '관찰 신호',
  }[report.level] || '참고'

  return (
    <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border border-slate-300 bg-slate-900 px-3 py-1 text-xs font-bold text-white">
            {report.insightType || '인사이트'}
          </span>
          <span className={`rounded-full border px-3 py-1 text-xs font-bold ${tone}`}>{levelLabel}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-500">
            {report.adapterLabel || AI_INSIGHT_LABEL}
          </span>
          <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
            {report.adapterStatus || AI_INSIGHT_STATUS}
          </span>
        </div>
      </div>

      <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-950 p-5 text-white">
        <p className="text-xs font-bold tracking-[0.16em] text-emerald-300">[AI 인사이트]</p>
        <p className="mt-3 text-lg font-black leading-7">{report.title}</p>
        <p className="mt-2 text-base leading-7 text-slate-200">{report.message}</p>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <p className="text-xs font-bold tracking-[0.16em] text-slate-500">[근거 분석]</p>
        <p className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
          분석 기간: {report.analysisPeriod || '선택 기간'}
        </p>
        <ul className="mt-3 space-y-2">
          {report.evidence.map((item) => (
            <EvidenceItem key={`${report.id}-${item}`} item={item} />
          ))}
        </ul>
        <AffectedItems label={report.affectedLabel} items={report.affectedItems} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {['채택', '보류', '무시'].map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => onFeedback(report.id, value)}
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
              feedback === value
                ? 'border-slate-900 bg-slate-900 text-white'
                : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
            }`}
          >
            {value}
          </button>
        ))}
      </div>
    </article>
  )
}

function SavedInsightCard({ insight }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-slate-600">{insight.insight_type || 'AI'}</span>
        {insight.related_code && <span className="font-mono text-xs text-slate-400">{insight.related_code}</span>}
        <span className="ml-auto text-xs text-slate-400">{formatDateTime(insight.created_at)}</span>
      </div>
      <p className="text-sm leading-6 text-slate-600">{insight.content}</p>
    </div>
  )
}

function EmptyState({ text }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-400">
      {text}
    </div>
  )
}

export default function InsightTab() {
  const [insights, setInsights] = useState([])
  const [releases, setReleases] = useState([])
  const [messagesByChannel, setMessagesByChannel] = useState({})
  const [demoData, setDemoData] = useState(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [quickRange, setQuickRange] = useState('all')
  const [selectedTargets, setSelectedTargets] = useState(DEFAULT_TARGET_KEYS)
  const [feedbackById, setFeedbackById] = useState({})
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [insightRes, releaseRes, demoRes, ...messageResponses] = await Promise.all([
        getInsights(),
        getCollectedReleases(),
        getDemoSupplyChainData().catch(() => ({ data: null })),
        ...CHANNELS.map((channel) => getReportChannelMessages(channel, { limit: 200 })),
      ])

      setInsights(asArray(insightRes.data))
      setReleases(asArray(releaseRes.data))
      setDemoData(demoRes.data || null)
      setMessagesByChannel(
        CHANNELS.reduce((acc, channel, index) => {
          acc[channel] = asArray(messageResponses[index]?.data)
          return acc
        }, {}),
      )
    } catch (err) {
      setError(err.response?.data?.detail || '인사이트 데이터를 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const analysis = useMemo(() => {
    const { facts, rawReleaseFacts } = buildReleaseFacts(messagesByChannel, releases)
    const importFacts = buildImportFacts(messagesByChannel)
    const scopedFacts = filterFactsByTarget(
      facts.filter((fact) => isWithinDateRange(fact.dueDate || fact.createdAt, startDate, endDate)),
      selectedTargets,
    )
    const scopedRawFacts = filterFactsByTarget(
      rawReleaseFacts.filter((fact) => isWithinDateRange(fact.dueDate || fact.createdAt, startDate, endDate)),
      selectedTargets,
    )
    const scopedImports = filterFactsByTarget(
      importFacts.filter((fact) => isWithinDateRange(fact.arrivalDate || fact.createdAt, startDate, endDate)),
      selectedTargets,
    )
    const duplicateGroups = buildDuplicateGroups(scopedRawFacts)
    const trend = buildTrendSignals(scopedRawFacts.length ? scopedRawFacts : scopedFacts)
    const supplierStats = buildSupplierStats(scopedImports, scopedFacts)
    const duplicateBlGroups = buildDuplicateBlGroups(scopedImports)
    const analysisPeriod = buildAnalysisPeriodLabel(startDate, endDate, demoData?.summary)
    const agentInsightReports = buildInsightReports({
      supplierStats,
      duplicateBlGroups,
      duplicateGroups,
      trend,
      releaseFacts: scopedFacts,
      analysisPeriod,
    })
    const demoFacts = buildDemoFacts(demoData, startDate, endDate, selectedTargets)
    const demoInsightReports = buildDemoInsightReports(demoFacts)
    const insightReports = [...demoInsightReports, ...agentInsightReports].slice(0, 10)

    return {
      facts: scopedFacts,
      importFacts: scopedImports,
      rawReleaseFacts: scopedRawFacts,
      demoFacts,
      duplicateGroups,
      duplicateBlGroups,
      supplierStats,
      trend,
      insightReports,
    }
  }, [demoData, endDate, messagesByChannel, releases, selectedTargets, startDate])

  const handleAnalyze = async () => {
    setAnalyzing(true)
    setError('')
    try {
      await analyzeInsights()
      const res = await getInsights()
      setInsights(asArray(res.data))
    } catch (err) {
      setError(err.response?.data?.detail || 'AI 저장 인사이트 생성에 실패했습니다.')
    } finally {
      setAnalyzing(false)
    }
  }

  const setFeedback = (id, value) => {
    setFeedbackById((prev) => ({ ...prev, [id]: value }))
  }

  const clearDateRange = () => {
    setStartDate('')
    setEndDate('')
    setQuickRange('all')
  }

  const applyQuickRange = (range) => {
    setQuickRange(range.key)
    if (!range.months) {
      setStartDate('')
      setEndDate('')
      return
    }

    const end = new Date()
    const start = addMonths(end, -range.months)
    setStartDate(localDateKey(start))
    setEndDate(localDateKey(end))
  }

  const allTargetsSelected = selectedTargets.length === DEFAULT_TARGET_KEYS.length

  const toggleAllTargets = () => {
    setSelectedTargets(allTargetsSelected ? [] : DEFAULT_TARGET_KEYS)
  }

  const toggleTarget = (key) => {
    setSelectedTargets((prev) => (
      prev.includes(key)
        ? prev.filter((item) => item !== key)
        : [...prev, key]
    ))
  }

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h2 className="text-2xl font-black text-slate-900">분석 및 인사이트 도출</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            생산사 수입/출고 보고를 선택한 기간 기준으로 분석하고, 공급 리스크와 시즌 선행 신호를 도출합니다.
          </p>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-bold text-slate-900">분석 조건</p>
            <p className="mt-1 text-xs text-slate-500">시작일과 종료일을 달력으로 선택하면 해당 기간의 보고만 분석합니다.</p>
          </div>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            새로고침
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1fr_1.5fr_auto]">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">시작일</span>
            <input
              type="date"
              value={startDate}
              max={endDate || undefined}
              onChange={(event) => {
                setStartDate(event.target.value)
                setQuickRange('')
              }}
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 outline-none transition-colors focus:border-emerald-400 focus:bg-white"
            />
          </label>

          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">종료일</span>
            <input
              type="date"
              value={endDate}
              min={startDate || undefined}
              onChange={(event) => {
                setEndDate(event.target.value)
                setQuickRange('')
              }}
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 outline-none transition-colors focus:border-emerald-400 focus:bg-white"
            />
          </label>

          <div>
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">분석 대상</span>
            <div className="mt-2 flex flex-wrap gap-2">
              <label
                className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold transition-colors ${
                  allTargetsSelected
                    ? 'border-slate-900 bg-slate-900 text-white'
                    : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
                }`}
              >
                <input
                  type="checkbox"
                  checked={allTargetsSelected}
                  onChange={toggleAllTargets}
                  className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                전체
              </label>
              {TARGETS.map((item) => (
                <label
                  key={item.key}
                  className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold transition-colors ${
                    selectedTargets.includes(item.key)
                      ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                      : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedTargets.includes(item.key)}
                    onChange={() => toggleTarget(item.key)}
                    className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  {item.label}
                </label>
              ))}
            </div>
            {selectedTargets.length === 0 && (
              <p className="mt-2 text-xs text-rose-500">분석할 대상을 하나 이상 선택하세요.</p>
            )}
          </div>

          <button
            type="button"
            onClick={clearDateRange}
            className="self-end rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-600 hover:bg-slate-100"
          >
            기간 초기화
          </button>
        </div>

        <div className="mt-4 border-t border-slate-100 pt-4">
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">빠른 조회</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {QUICK_RANGES.map((range) => (
              <button
                key={range.key}
                type="button"
                onClick={() => applyQuickRange(range)}
                className={`rounded-full border px-4 py-2 text-sm font-semibold transition-colors ${
                  quickRange === range.key
                    ? 'border-slate-900 bg-slate-900 text-white'
                    : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
                }`}
              >
                {range.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <Section
        title="분석 및 인사이트"
        description="공급사 입고, 자재군, 출고묶음 영향을 종합해 사람이 바로 판단할 수 있는 문장으로 정리합니다."
      >
        <div className="space-y-4">
          {loading ? (
            <EmptyState text="인사이트 데이터를 불러오는 중입니다." />
          ) : analysis.insightReports.length === 0 ? (
            <EmptyState text="현재 도출된 인사이트가 없습니다. 기간이나 분석 대상을 조정하세요." />
          ) : (
            analysis.insightReports.map((report) => (
              <InsightReportCard
                key={report.id}
                report={report}
                feedback={feedbackById[report.id]}
                onFeedback={setFeedback}
              />
            ))
          )}
        </div>
      </Section>

      <Section
        title="저장된 AI 인사이트"
        description="기존 GPT 기반 저장 인사이트는 보조 로그로 유지합니다. 플랫폼 판단의 원본은 위 분석 영역입니다."
        action={
          <button
            type="button"
            onClick={handleAnalyze}
            disabled={analyzing}
            className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {analyzing ? '생성 중' : '저장 인사이트 생성'}
          </button>
        }
      >
        <div className="grid gap-3 lg:grid-cols-2">
          {insights.length === 0 ? (
            <EmptyState text="저장된 AI 인사이트가 없습니다." />
          ) : (
            insights.slice(0, 6).map((insight) => <SavedInsightCard key={insight.id} insight={insight} />)
          )}
        </div>
      </Section>
    </div>
  )
}
