const DAILY_HOURS = 9
const PER_MACHINE_HOURLY_QTY = 800
const FABRIC_PCS_PER_METER = 25
const INK_PCS_PER_CAN = 10000

const STATUS_TONE = {
  납기가능: 'bg-emerald-50 border-emerald-200 text-emerald-700',
  납기위험: 'bg-amber-50 border-amber-200 text-amber-700',
  납기불가: 'bg-rose-50 border-rose-200 text-rose-700',
}

function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatNumber(value) {
  return toNumber(value).toLocaleString('ko-KR')
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleDateString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
  })
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatClock(value) {
  if (!value) return '-'
  return new Date(value).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getDueDateDelta(dueDate) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const target = new Date(`${dueDate}T00:00:00`)
  target.setHours(0, 0, 0, 0)

  return Math.ceil((target - today) / 86400000)
}

function getProductionDaysLeft(dueDate) {
  return Math.max(getDueDateDelta(dueDate) + 1, 1)
}

function getRemainingQty(order, machineMap) {
  const machine = machineMap.get(order.id)
  if (!machine || machine.release_id !== order.id) {
    return order.release_qty
  }

  if (machine.total_qty > 0) {
    return Math.max(Math.ceil(toNumber(machine.remaining_qty)), 0)
  }

  return order.release_qty
}

function getRequiredFabricMeters(qty) {
  return Math.ceil(toNumber(qty) / FABRIC_PCS_PER_METER)
}

function getRequiredInkCans(qty) {
  return Math.ceil(toNumber(qty) / INK_PCS_PER_CAN)
}

function buildDashboard(status) {
  const machineStatuses = status?.machine_statuses || []
  const machineMap = new Map(
    machineStatuses
      .filter((machine) => machine.release_id)
      .map((machine) => [machine.release_id, machine])
  )

  const orders = (status?.active_orders || [])
    .map((order) => {
      const remainingQty = getRemainingQty(order, machineMap)
      const productionDaysLeft = getProductionDaysLeft(order.due_date)
      const dailyTargetQty = remainingQty > 0 ? Math.ceil(remainingQty / productionDaysLeft) : 0

      return {
        ...order,
        remaining_qty: remainingQty,
        production_days_left: productionDaysLeft,
        daily_target_qty: dailyTargetQty,
        estimated_finish_at: order.machine_estimated_completion_at || order.estimated_completion_at || null,
      }
    })
    .sort((left, right) => {
      const severity = {
        납기불가: 3,
        납기위험: 2,
        납기가능: 1,
      }

      const severityGap =
        (severity[right.deadline_status] || 0) - (severity[left.deadline_status] || 0)
      if (severityGap !== 0) return severityGap

      return new Date(left.due_date) - new Date(right.due_date)
    })

  const machineCount =
    toNumber(status?.machine_summary?.total) || machineStatuses.length || 0
  const dailyCapacity = machineCount * PER_MACHINE_HOURLY_QTY * DAILY_HOURS
  const remainingTotalQty = orders.reduce((sum, order) => sum + order.remaining_qty, 0)
  const factoryHourlyCapacity = machineCount * PER_MACHINE_HOURLY_QTY

  const fabricCurrent = toNumber(status?.stock_summary?.fabric?.current_qty)
  const inkCurrent = toNumber(status?.stock_summary?.ink?.current_qty)
  const fabricRequired = orders.reduce(
    (sum, order) => sum + getRequiredFabricMeters(order.remaining_qty),
    0
  )
  const inkRequired = orders.reduce(
    (sum, order) => sum + getRequiredInkCans(order.remaining_qty),
    0
  )

  const stock = {
    fabric: {
      label: '라벨원단',
      unit: 'm',
      current: fabricCurrent,
      required: fabricRequired,
      remaining: fabricCurrent - fabricRequired,
      shortage: Math.max(fabricRequired - fabricCurrent, 0),
    },
    ink: {
      label: '잉크',
      unit: '통',
      current: inkCurrent,
      required: inkRequired,
      remaining: inkCurrent - inkRequired,
      shortage: Math.max(inkRequired - inkCurrent, 0),
    },
  }

  const riskOrders = orders.filter((order) => order.deadline_status !== '납기가능')
  const nearestDueDate = orders.reduce((earliest, order) => {
    if (!earliest) return order.due_date
    return new Date(order.due_date) < new Date(earliest) ? order.due_date : earliest
  }, null)
  const latestDueDate = orders.reduce((latest, order) => {
    if (!latest) return order.due_date
    return new Date(order.due_date) > new Date(latest) ? order.due_date : latest
  }, null)
  const nearestDueQty = nearestDueDate
    ? orders
      .filter((order) => order.due_date === nearestDueDate)
      .reduce((sum, order) => sum + order.remaining_qty, 0)
    : 0
  const nearestDueDaysLeft = nearestDueDate ? getProductionDaysLeft(nearestDueDate) : 0
  const nearestDailyTargetQty =
    nearestDueQty > 0 && nearestDueDaysLeft > 0
      ? Math.ceil(nearestDueQty / nearestDueDaysLeft)
      : 0
  const overallDaysLeft = latestDueDate ? getProductionDaysLeft(latestDueDate) : 0
  const overallDailyTargetQty =
    remainingTotalQty > 0 && overallDaysLeft > 0
      ? Math.ceil(remainingTotalQty / overallDaysLeft)
      : 0
  const requiredFactoryHours =
    remainingTotalQty > 0 && factoryHourlyCapacity > 0
      ? Math.ceil((remainingTotalQty / factoryHourlyCapacity) * 10) / 10
      : 0
  const requiredFactoryDays =
    requiredFactoryHours > 0 ? Math.ceil(requiredFactoryHours / DAILY_HOURS) : 0
  const capacityGap = Math.max(
    nearestDailyTargetQty - dailyCapacity,
    overallDailyTargetQty - dailyCapacity,
    0
  )
  const scheduleSummary = {
    nearestDueDate,
    nearestDueQty,
    nearestDueDaysLeft,
    nearestDailyTargetQty,
    latestDueDate,
    overallDaysLeft,
    overallDailyTargetQty,
    requiredFactoryHours,
    requiredFactoryDays,
  }
  const actions = []

  if (stock.fabric.shortage > 0) {
    actions.push(
      `라벨원단이 ${formatNumber(stock.fabric.shortage)}m 부족합니다. 현재 발주분 전체 생산 전 원단 확보가 필요합니다.`
    )
  }

  if (stock.ink.shortage > 0) {
    actions.push(
      `잉크가 ${formatNumber(stock.ink.shortage)}통 부족합니다. 현재 발주분 전체 생산 전 잉크 확보가 필요합니다.`
    )
  }

  if (capacityGap > 0) {
    actions.push(
      `현재 평균 일 필요 생산량이 공장 일 생산가능량보다 ${formatNumber(capacityGap)}장 많습니다. 잔업 또는 우선순위 조정이 필요합니다.`
    )
  }

  riskOrders.slice(0, 4).forEach((order) => {
    if (order.deadline_status === '납기불가') {
      actions.push(
        `${order.label_code}은 현재 일정상 ${formatDateTime(order.estimated_finish_at)} 완료 예정으로 납기를 넘깁니다. 추가 생산이 필요합니다.`
      )
      return
    }

    actions.push(
      `${order.label_code}은 납기 위험입니다. 납기까지 하루 ${formatNumber(order.daily_target_qty)}장 수준으로 유지해야 합니다.`
    )
  })

  if (actions.length === 0) {
    actions.push('현재 재고와 09:00~18:00 기준 생산 스케줄로 진행 가능합니다.')
  }

  return {
    orders,
    machineCount,
    dailyCapacity,
    remainingTotalQty,
    stock,
    riskOrders,
    scheduleSummary,
    actions,
  }
}

export default function AgentPanel({ status, loading, lastUpdated, onRefresh }) {
  const dashboard = buildDashboard(status)

  return (
    <div className="p-4 h-full flex flex-col gap-4">
      <div className="border-b pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-gray-800">생산 운영판단</h2>
            <p className="text-[11px] text-gray-500 mt-1">
              1차 재고 점검, 납기 기준 일일 생산량, 추가 대응 필요 여부를 표시합니다.
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="text-xs text-blue-600 hover:underline whitespace-nowrap"
          >
            새로고침
          </button>
        </div>
        <p className="text-[11px] text-gray-400 mt-2">
          기준 근무시간 09:00-18:00
          {lastUpdated ? ` / 마지막 조회 ${formatClock(lastUpdated)}` : ''}
        </p>
      </div>

      {loading ? (
        <p className="text-xs text-gray-400">생산 판단 데이터를 계산하는 중입니다.</p>
      ) : !status ? (
        <p className="text-xs text-red-500">생산 판단 데이터를 불러오지 못했습니다.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <MetricCard label="진행 주문" value={`${formatNumber(dashboard.orders.length)}건`} />
            <MetricCard label="남은 생산량" value={`${formatNumber(dashboard.remainingTotalQty)}장`} />
            <MetricCard label="전체 일 목표량" value={`${formatNumber(dashboard.scheduleSummary.overallDailyTargetQty)}장`} />
            <MetricCard label="일 생산 가능량" value={`${formatNumber(dashboard.dailyCapacity)}장`} />
          </div>

          <Section title="1. 재고 점검">
            <div className="space-y-2">
              <MaterialCard item={dashboard.stock.fabric} />
              <MaterialCard item={dashboard.stock.ink} />

              {dashboard.stock.fabric.shortage > 0 || dashboard.stock.ink.shortage > 0 ? (
                <AlertBox tone="danger">
                  현재 접수된 생산건 기준으로 1차 재고가 부족합니다. 부족 자재를 먼저 확보해야 합니다.
                </AlertBox>
              ) : (
                <AlertBox tone="ok">
                  현재 접수된 생산건 기준으로 1차 재고는 생산 가능 수준입니다.
                </AlertBox>
              )}
            </div>
          </Section>

          <Section title="2. 납기 생산 스케줄">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-xs font-semibold text-slate-700">
                설비 {formatNumber(dashboard.machineCount)}대 기준
              </p>
              <p className="text-[11px] text-slate-500 mt-1">
                대당 시간당 800장, 하루 9시간 기준으로 일 생산 가능량을 계산합니다.
              </p>
            </div>

            <ScheduleSummary dashboard={dashboard} />
          </Section>

          <Section title="3. 추가 대응 필요">
            <div className="space-y-2">
              {dashboard.actions.map((action, index) => (
                <AlertBox
                  key={`action-${index}`}
                  tone={action.includes('가능합니다') ? 'ok' : 'warning'}
                >
                  {action}
                </AlertBox>
              ))}
            </div>
          </Section>
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

function MetricCard({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-3 py-2">
      <p className="text-[11px] text-gray-500">{label}</p>
      <p className="text-sm font-bold text-gray-800 mt-1">{value}</p>
    </div>
  )
}

function MaterialCard({ item }) {
  const shortage = item.shortage > 0

  return (
    <div
      className={`rounded-xl border px-3 py-2 ${
        shortage ? 'border-rose-200 bg-rose-50' : 'border-emerald-200 bg-emerald-50'
      }`}
    >
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-gray-800">{item.label}</span>
        <span className={shortage ? 'text-rose-700 font-bold' : 'text-emerald-700 font-bold'}>
          {shortage ? '부족' : '가능'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-2 text-[11px] text-gray-600">
        <div>
          <p className="text-gray-400">현재 재고</p>
          <p className="font-semibold text-gray-800">
            {formatNumber(item.current)}
            {item.unit}
          </p>
        </div>
        <div>
          <p className="text-gray-400">필요 수량</p>
          <p className="font-semibold text-gray-800">
            {formatNumber(item.required)}
            {item.unit}
          </p>
        </div>
        <div>
          <p className="text-gray-400">{shortage ? '부족 수량' : '생산 후 잔량'}</p>
          <p className={`font-semibold ${shortage ? 'text-rose-700' : 'text-emerald-700'}`}>
            {formatNumber(Math.abs(item.shortage > 0 ? item.shortage : item.remaining))}
            {item.unit}
          </p>
        </div>
      </div>
    </div>
  )
}

function ScheduleSummary({ dashboard }) {
  if (dashboard.orders.length === 0) {
    return <EmptyText text="진행 중인 생산 주문이 없습니다." />
  }

  const { scheduleSummary } = dashboard
  const nearestCapacitySafe = scheduleSummary.nearestDailyTargetQty <= dashboard.dailyCapacity
  const overallCapacitySafe = scheduleSummary.overallDailyTargetQty <= dashboard.dailyCapacity

  return (
    <div className="space-y-2 mt-2">
      <div className="rounded-xl border border-gray-200 bg-white px-3 py-3">
        <div className="grid grid-cols-2 gap-3 text-[11px] text-gray-600">
          <div>
            <p className="text-gray-400">가장 빠른 납기</p>
            <p className="mt-1 font-semibold text-gray-800">
              {formatDate(scheduleSummary.nearestDueDate)}
            </p>
          </div>
          <div>
            <p className="text-gray-400">그 납기 물량</p>
            <p className="mt-1 font-semibold text-gray-800">
              {formatNumber(scheduleSummary.nearestDueQty)}장
            </p>
          </div>
          <div>
            <p className="text-gray-400">그 납기까지 하루 목표</p>
            <p className={`mt-1 font-semibold ${nearestCapacitySafe ? 'text-blue-700' : 'text-rose-700'}`}>
              {formatNumber(scheduleSummary.nearestDailyTargetQty)}장
            </p>
          </div>
          <div>
            <p className="text-gray-400">남은 기간</p>
            <p className="mt-1 font-semibold text-gray-800">
              {formatNumber(scheduleSummary.nearestDueDaysLeft)}일
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white px-3 py-3">
        <div className="grid grid-cols-2 gap-3 text-[11px] text-gray-600">
          <div>
            <p className="text-gray-400">전체 최종 납기</p>
            <p className="mt-1 font-semibold text-gray-800">
              {formatDate(scheduleSummary.latestDueDate)}
            </p>
          </div>
          <div>
            <p className="text-gray-400">전체 물량</p>
            <p className="mt-1 font-semibold text-gray-800">
              {formatNumber(dashboard.remainingTotalQty)}장
            </p>
          </div>
          <div>
            <p className="text-gray-400">전체 하루 목표</p>
            <p className={`mt-1 font-semibold ${overallCapacitySafe ? 'text-blue-700' : 'text-rose-700'}`}>
              {formatNumber(scheduleSummary.overallDailyTargetQty)}장
            </p>
          </div>
          <div>
            <p className="text-gray-400">공장 필요 작업량</p>
            <p className="mt-1 font-semibold text-gray-800">
              {formatNumber(scheduleSummary.requiredFactoryDays)}일 / {scheduleSummary.requiredFactoryHours.toLocaleString('ko-KR')}시간
            </p>
          </div>
        </div>
      </div>

      <AlertBox tone={nearestCapacitySafe && overallCapacitySafe ? 'ok' : 'warning'}>
        {nearestCapacitySafe && overallCapacitySafe
          ? `현재 설비 기준으로 가장 빠른 납기 물량과 전체 물량 모두 소화 가능한 수준입니다.`
          : `현재 설비 기준 하루 생산 가능량 ${formatNumber(dashboard.dailyCapacity)}장보다 필요한 목표 생산량이 큽니다. 추가 생산이나 우선순위 조정이 필요합니다.`}
      </AlertBox>
    </div>
  )
}

function AlertBox({ tone, children }) {
  const className =
    tone === 'danger'
      ? 'bg-rose-50 border-rose-200 text-rose-700'
      : tone === 'ok'
        ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
        : 'bg-amber-50 border-amber-200 text-amber-800'

  return <p className={`rounded-xl border px-3 py-2 text-xs leading-5 ${className}`}>{children}</p>
}

function EmptyText({ text }) {
  return <p className="text-xs text-gray-400">{text}</p>
}
