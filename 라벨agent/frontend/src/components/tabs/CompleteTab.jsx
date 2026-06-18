import { useEffect, useState } from 'react'
import { completeRelease, downloadSelectedPackingList, getReleases } from '../../services/api'

function inRange(dateStr, searched) {
  if (!searched || !dateStr) return true
  const date = new Date(dateStr)
  return date >= new Date(searched.from) && date <= new Date(`${searched.to}T23:59:59`)
}

function today() {
  return new Date().toISOString().split('T')[0]
}

function fmtDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function toWeightText(value) {
  return typeof value === 'number' ? `${value.toLocaleString()} kg` : '-'
}

export default function CompleteTab({ searched, onReportRefresh }) {
  const [releases, setReleases] = useState([])
  const [completing, setCompleting] = useState(null)
  const [downloadingFormat, setDownloadingFormat] = useState(null)
  const [checkedCompleted, setCheckedCompleted] = useState(new Set())

  const fetchReleases = async () => {
    const res = await getReleases()
    setReleases(res.data)
  }

  useEffect(() => {
    fetchReleases()
  }, [])

  const handleComplete = async (id) => {
    setCompleting(id)
    try {
      await completeRelease(id)
      await fetchReleases()
      await onReportRefresh?.()
    } catch (err) {
      alert(err.response?.data?.detail || '완료 처리 실패')
    } finally {
      setCompleting(null)
    }
  }

  const pending = releases.filter((release) => release.status === '생산중')
  const completed = releases
    .filter((release) => release.status === '출고완료')
    .filter((release) => inRange(release.release_date, searched))

  useEffect(() => {
    const visibleIds = new Set(completed.map((release) => release.id))
    setCheckedCompleted((prev) => {
      const next = new Set([...prev].filter((id) => visibleIds.has(id)))
      if (next.size === prev.size) {
        let same = true
        for (const id of next) {
          if (!prev.has(id)) {
            same = false
            break
          }
        }
        if (same) return prev
      }
      return next
    })
  }, [searched, releases])

  const toggleCompletedOne = (id) => {
    setCheckedCompleted((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleCompletedAll = () => {
    if (completed.length === 0) return
    setCheckedCompleted((prev) => {
      if (completed.every((release) => prev.has(release.id))) {
        return new Set()
      }
      return new Set(completed.map((release) => release.id))
    })
  }

  const handleDownloadPacking = async (format) => {
    const selectedIds = completed
      .filter((release) => checkedCompleted.has(release.id))
      .map((release) => release.id)

    if (selectedIds.length === 0) {
      alert('패킹리스트로 추출할 완료 항목을 먼저 체크하세요.')
      return
    }

    setDownloadingFormat(format)
    try {
      await downloadSelectedPackingList(selectedIds, format)
    } catch (err) {
      alert(err.response?.data?.detail || '패킹리스트 생성 실패')
    } finally {
      setDownloadingFormat(null)
    }
  }

  const completedWeightTotal = completed.reduce(
    (sum, release) => sum + Number(release.product_weight_kg || 0),
    0,
  )
  const selectedCompleted = completed.filter((release) => checkedCompleted.has(release.id))
  const selectedCompletedWeightTotal = selectedCompleted.reduce(
    (sum, release) => sum + Number(release.product_weight_kg || 0),
    0,
  )
  const allCompletedChecked = completed.length > 0 && completed.every((release) => checkedCompleted.has(release.id))
  const downloadDisabled = checkedCompleted.size === 0 || downloadingFormat !== null

  return (
    <div className="space-y-5">
      <section>
        <h3 className="mb-2 text-base font-semibold">완료 처리</h3>
        <p className="mb-3 text-xs text-gray-400">
          완료 버튼을 누르면 재고 차감과 플랫폼 출고 신호 전송이 같이 처리됩니다.
        </p>

        {pending.length === 0 ? (
          <div className="rounded border bg-gray-50 py-6 text-center text-sm text-gray-400">
            완료 처리할 생산 주문이 없습니다.
          </div>
        ) : (
          <div className="grid gap-3">
            {pending.map((release) => {
              const dday = Math.ceil((new Date(release.due_date) - new Date()) / 86400000)
              return (
                <div
                  key={release.id}
                  className={`flex items-center justify-between rounded border px-4 py-3 ${
                    dday < 2
                      ? 'border-red-300 bg-red-50'
                      : dday < 5
                        ? 'border-yellow-300 bg-yellow-50'
                        : 'border-gray-200 bg-white'
                  }`}
                >
                  <div>
                    <span className="font-mono text-sm font-bold">{release.label_code}</span>
                    <span className="ml-3 text-xs text-gray-500">{release.release_qty.toLocaleString()}장</span>
                    <span className="ml-3 text-xs text-indigo-600">
                      출고중량 {toWeightText(release.product_weight_kg)}
                    </span>
                    <span
                      className={`ml-3 text-xs font-semibold ${
                        dday < 2 ? 'text-red-600' : dday < 5 ? 'text-yellow-700' : 'text-blue-600'
                      }`}
                    >
                      D-{dday}
                    </span>
                    <span className="ml-3 text-xs text-gray-400">납기 {release.due_date}</span>
                  </div>
                  <button
                    onClick={() => handleComplete(release.id)}
                    disabled={completing === release.id}
                    className="rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {completing === release.id ? '처리중...' : '완료'}
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-medium text-gray-600">
            출고완료 이력 ({completed.length}건 / 총 {completedWeightTotal.toLocaleString()} kg)
            {searched && (
              <span className="ml-2 text-xs font-normal text-blue-500">출고일 기준 필터 적용중</span>
            )}
            {checkedCompleted.size > 0 && (
              <span className="ml-2 text-xs font-normal text-indigo-600">
                선택 {checkedCompleted.size}건 / {selectedCompletedWeightTotal.toLocaleString()} kg
              </span>
            )}
          </p>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleDownloadPacking('csv')}
              disabled={downloadDisabled}
              className={`whitespace-nowrap rounded border px-4 py-1.5 text-xs transition-colors ${
                checkedCompleted.size > 0
                  ? 'border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700'
                  : 'cursor-not-allowed border-gray-300 bg-white text-gray-400'
              } disabled:opacity-50`}
            >
              {downloadingFormat === 'csv' ? 'CSV 생성중...' : `CSV 다운로드 (${checkedCompleted.size}건)`}
            </button>
            <button
              onClick={() => handleDownloadPacking('xlsx')}
              disabled={downloadDisabled}
              className={`whitespace-nowrap rounded border px-4 py-1.5 text-xs transition-colors ${
                checkedCompleted.size > 0
                  ? 'border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700'
                  : 'cursor-not-allowed border-gray-300 bg-white text-gray-400'
              } disabled:opacity-50`}
            >
              {downloadingFormat === 'xlsx' ? 'XLSX 생성중...' : `XLSX 다운로드 (${checkedCompleted.size}건)`}
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-gray-100 text-left text-gray-600">
                <th className="w-12 border px-4 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={allCompletedChecked}
                    onChange={toggleCompletedAll}
                    className="cursor-pointer"
                  />
                </th>
                <th className="border px-4 py-2">라벨코드</th>
                <th className="border px-4 py-2">출고수량</th>
                <th className="border px-4 py-2">완료중량(kg)</th>
                <th className="border px-4 py-2">납기일</th>
                <th className="border px-4 py-2">출고일</th>
                <th className="border px-4 py-2">생산 시작</th>
                <th className="border px-4 py-2">생산 완료</th>
                <th className="border px-4 py-2">상태</th>
              </tr>
            </thead>
            <tbody>
              {completed.length === 0 && (
                <tr>
                  <td colSpan={9} className="border px-4 py-6 text-center text-gray-400">
                    {searched ? '해당 기간 출고완료 이력이 없습니다.' : '출고완료 이력이 없습니다.'}
                  </td>
                </tr>
              )}
              {completed.map((release) => {
                const isFutureShipment = release.release_date && release.release_date > today()
                return (
                  <tr
                    key={release.id}
                    onClick={() => toggleCompletedOne(release.id)}
                    className={`cursor-pointer hover:bg-gray-50 ${
                      checkedCompleted.has(release.id) ? 'bg-indigo-50' : ''
                    }`}
                  >
                    <td className="border px-4 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={checkedCompleted.has(release.id)}
                        onChange={() => toggleCompletedOne(release.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="cursor-pointer"
                      />
                    </td>
                    <td className="border px-4 py-2 font-mono font-semibold">{release.label_code}</td>
                    <td className="border px-4 py-2">{release.release_qty.toLocaleString()}장</td>
                    <td className="border px-4 py-2 font-medium text-indigo-700">
                      {toWeightText(release.product_weight_kg)}
                    </td>
                    <td className="border px-4 py-2">{release.due_date}</td>
                    <td className="border px-4 py-2 font-medium text-green-700">{release.release_date || '-'}</td>
                    <td className="border px-4 py-2 text-xs text-gray-500">
                      {release.started_at ? fmtDateTime(release.started_at) : '-'}
                    </td>
                    <td className="border px-4 py-2 text-xs">
                      {release.finished_at ? (
                        <span className="font-medium text-blue-600">{fmtDateTime(release.finished_at)}</span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="border px-4 py-2">
                      {isFutureShipment ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                          출고대기
                        </span>
                      ) : (
                        <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">
                          출고완료
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
