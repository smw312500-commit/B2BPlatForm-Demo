import { useEffect, useState } from 'react'
import { getDispatchAvailability, getDispatches, rematchDispatch } from '../../api'

const STATUS_CLS = {
  대기: 'bg-gray-100 text-gray-600',
  배차완료: 'bg-blue-100 text-blue-700',
  운행중: 'bg-orange-100 text-orange-700',
  완료: 'bg-green-100 text-green-700',
  배송완료: 'bg-green-100 text-green-700',
}

const FINAL_STATUSES = new Set(['완료', '배송완료'])

function StatCard({ label, value, tone }) {
  const tones = {
    blue: 'from-blue-500 to-blue-700',
    emerald: 'from-emerald-500 to-emerald-700',
    amber: 'from-amber-500 to-orange-600',
    slate: 'from-slate-500 to-slate-700',
  }

  return (
    <div className={`rounded-xl bg-gradient-to-br ${tones[tone]} p-4 text-white shadow`}>
      <p className="text-xs opacity-80">{label}</p>
      <p className="mt-1 text-3xl font-bold">{value}</p>
    </div>
  )
}

function formatSyncTime(value) {
  if (!value) {
    return ''
  }
  return String(value).slice(0, 16).replace('T', ' ')
}

export default function DispatchTab() {
  const [dispatches, setDispatches] = useState([])
  const [availability, setAvailability] = useState({
    total_driver_count: 0,
    available_driver_count: 0,
    available_vehicle_count: 0,
    drivers: [],
    vehicles: [],
    last_synced_at: null,
  })
  const [loadingId, setLoadingId] = useState(null)

  const load = async () => {
    try {
      const [dispatchRes, availabilityRes] = await Promise.all([
        getDispatches(),
        getDispatchAvailability(),
      ])
      setDispatches(dispatchRes.data)
      setAvailability(availabilityRes.data)
    } catch {}
  }

  useEffect(() => {
    load()
  }, [])

  const handleRematch = async (dispatchId) => {
    setLoadingId(dispatchId)
    try {
      await rematchDispatch(dispatchId)
      await load()
    } catch {
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="동기화 기사" value={availability.total_driver_count} tone="slate" />
        <StatCard label="가용 기사" value={availability.available_driver_count} tone="blue" />
        <StatCard label="가용 차량" value={availability.available_vehicle_count} tone="emerald" />
        <StatCard
          label="배차/배송 완료"
          value={dispatches.filter((dispatch) => dispatch.status === '배차완료' || FINAL_STATUSES.has(dispatch.status)).length}
          tone="amber"
        />
      </div>

      <div className="rounded-xl bg-white shadow">
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-700">배차 현황</h2>
            <p className="text-xs text-gray-400">
              플랫폼이 라벨 완료 보고와 물류 기사 스냅샷을 종합해서 배차 결과를 판단합니다.
            </p>
          </div>
          <span className="text-xs text-gray-400">
            {dispatches.length}건
            {availability.last_synced_at ? ` / 기사 동기화 ${formatSyncTime(availability.last_synced_at)}` : ''}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-[1120px] w-full table-auto text-[12px]">
            <thead>
              <tr className="border-b border-gray-100 text-[11px] text-gray-500">
                <th className="whitespace-nowrap px-3 py-2.5 text-left">고객사</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left">도착지</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left">기사</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left">차량</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left">픽업일</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left">귀로판단</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left">상태</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left">매칭 메모</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left">재실행</th>
              </tr>
            </thead>
            <tbody>
              {dispatches.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-xs text-gray-400">
                    배차 데이터가 없습니다.
                  </td>
                </tr>
              )}

              {dispatches.map((dispatch) => (
                <tr key={dispatch.id} className="border-b border-gray-50 align-top transition-colors hover:bg-gray-50">
                  <td className="whitespace-nowrap px-3 py-3 text-[12px] font-medium text-gray-700">
                    {dispatch.company_name ?? `#${dispatch.company_id}`}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-gray-600">
                    {dispatch.destination ?? '—'}
                  </td>
                  <td className="px-3 py-3">
                    <div className="whitespace-nowrap text-[12px] font-medium text-gray-700">
                      {dispatch.driver_name ?? '미배정'}
                    </div>
                    {dispatch.logistics_driver_id && (
                      <div className="whitespace-nowrap text-[11px] text-gray-400">
                        기사 ID {dispatch.logistics_driver_id}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <div className="whitespace-nowrap text-[12px] font-medium text-gray-700">
                      {dispatch.vehicle_plate ?? '미지정'}
                    </div>
                    {dispatch.logistics_vehicle_id && (
                      <div className="whitespace-nowrap text-[11px] text-gray-400">
                        차량 ID {dispatch.logistics_vehicle_id}
                      </div>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-gray-600">
                    {dispatch.pickup_date ?? '—'}
                  </td>
                  <td className="max-w-[220px] break-keep whitespace-normal px-3 py-3 text-[11px] leading-5 text-gray-600">
                    {dispatch.empty_return ?? '—'}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                        STATUS_CLS[dispatch.status] ?? 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {dispatch.status}
                    </span>
                  </td>
                  <td className="max-w-[320px] break-keep whitespace-pre-line px-3 py-3 text-[11px] leading-5 text-gray-500">
                    {dispatch.logistics_message ?? '—'}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3">
                    <button
                      onClick={() => handleRematch(dispatch.id)}
                      disabled={loadingId === dispatch.id || FINAL_STATUSES.has(dispatch.status)}
                      className="rounded-lg border border-blue-200 px-3 py-1.5 text-[11px] font-medium text-blue-700 transition-colors hover:bg-blue-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                    >
                      {loadingId === dispatch.id ? '매칭중...' : '재매칭'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-xl bg-white shadow">
        <div className="border-b border-gray-100 px-4 py-3">
          <h3 className="text-sm font-semibold text-gray-700">가용 기사 스냅샷</h3>
          <p className="mt-1 text-xs text-gray-400">물류 agent가 플랫폼으로 동기화한 기사/차량 기준입니다.</p>
        </div>
        <div className="grid gap-3 px-4 py-4 md:grid-cols-2 xl:grid-cols-3">
          {availability.drivers.length === 0 && (
            <p className="text-xs text-gray-400">가용 기사 정보가 없습니다.</p>
          )}
          {availability.drivers.map((driver) => (
            <div key={driver.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
              <div className="flex items-center justify-between gap-3">
                <div className="truncate font-semibold text-slate-800">{driver.name}</div>
                <span className="whitespace-nowrap rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500">
                  {driver.status ?? '상태미상'}
                </span>
              </div>
              <div className="mt-2 space-y-1 text-[12px] text-slate-600">
                <div className="break-keep">위치 {driver.location_si ?? '미상'} {driver.location_gu ?? ''}</div>
                <div className="break-keep">
                  차량 {driver.vehicle_plate ?? '미연결'}
                  {driver.vehicle_type ? ` / ${driver.vehicle_type}` : ''}
                </div>
                <div>적재 {driver.vehicle_max_weight != null ? `${driver.vehicle_max_weight}kg` : '미상'}</div>
                <div className="break-keep">
                  기사ID {driver.id}
                  {driver.vehicle_id ? ` / 차량ID ${driver.vehicle_id}` : ''}
                </div>
                {driver.current_destination && (
                  <div className="break-keep">현재 목적지 {driver.current_destination}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
