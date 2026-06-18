import { useEffect, useState } from 'react'
import { getReleases, completeRelease, downloadPackingList } from '../../services/api'

const PROD_LOG_KEY = 'zipper_prod_log_v1'

function inRange(dateStr, searched) {
  if (!searched || !dateStr) return true
  const d = new Date(dateStr)
  return d >= new Date(searched.from) && d <= new Date(searched.to + 'T23:59:59')
}

function getProdLog() {
  try { return JSON.parse(localStorage.getItem(PROD_LOG_KEY) || '{}') }
  catch { return {} }
}

function fmtDT(d) {
  if (!d) return '-'
  return new Date(d).toLocaleString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function CompleteTab({ searched }) {
  const [releases, setReleases]       = useState([])
  const [completing, setCompleting]   = useState(null)
  const [downloading, setDownloading] = useState(false)

  const fetchReleases = async () => {
    const res = await getReleases()
    setReleases(res.data)
  }
  useEffect(() => { fetchReleases() }, [])

  const handleComplete = async (id) => {
    setCompleting(id)
    try {
      const log   = getProdLog()
      const times = log[id] || {}
      await completeRelease(id, {
        started_at:  times.started_at  || null,
        finished_at: times.finished_at || null,
      })
      await fetchReleases()
    } catch (err) {
      alert(err.response?.data?.detail || '완료 처리 실패')
    } finally { setCompleting(null) }
  }

  const handlePackingList = async () => {
    if (!searched) {
      alert('날짜 범위를 설정하세요.\n우측 상단 캘린더에서 기간을 선택한 후 다시 시도해주세요.')
      return
    }
    setDownloading(true)
    try {
      const res  = await downloadPackingList(searched.from, searched.to)
      const url  = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a    = document.createElement('a')
      a.href     = url
      a.download = `packing_list_${searched.from}_${searched.to}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      const msg = err.response?.status === 404
        ? '해당 기간 출고완료 건이 없습니다.'
        : (err.response?.data?.detail || '패킹리스트 생성 실패')
      alert(msg)
    } finally { setDownloading(false) }
  }

  const pending   = releases.filter((r) => r.status === '생산중')
  const completed = releases.filter((r) => r.status === '출고완료' && inRange(r.release_date, searched))

  return (
    <div className="space-y-5">

      {/* 완료 처리 */}
      <section>
        <h3 className="text-base font-semibold mb-2">완료 처리</h3>
        <p className="text-xs text-gray-400 mb-3">완료 버튼 클릭 시: 원자재 재고 자동 차감 → 플랫폼으로 출고 신호 전송</p>

        {pending.length === 0 ? (
          <div className="text-sm text-gray-400 py-6 text-center border rounded bg-gray-50">완료 처리할 생산 주문 없음</div>
        ) : (
          <div className="grid gap-3">
            {pending.map((r) => {
              const d = Math.ceil((new Date(r.due_date) - new Date()) / 86400000)
              return (
                <div key={r.id} className={`flex items-center justify-between border rounded px-4 py-3 ${
                  d < 2 ? 'border-red-300 bg-red-50' : d < 5 ? 'border-yellow-300 bg-yellow-50' : 'border-gray-200 bg-white'
                }`}>
                  <div>
                    <span className="font-mono font-bold text-sm">{r.item_name}</span>
                    <span className="text-gray-500 text-xs ml-3">{r.release_qty.toLocaleString()}개</span>
                    <span className={`ml-3 text-xs font-semibold ${d < 2 ? 'text-red-600' : d < 5 ? 'text-yellow-700' : 'text-blue-600'}`}>
                      D-{d}
                    </span>
                    <span className="text-gray-400 text-xs ml-3">납기 {r.due_date}</span>
                  </div>
                  <button onClick={() => handleComplete(r.id)} disabled={completing === r.id}
                    className="bg-blue-600 text-white text-sm px-5 py-2 rounded hover:bg-blue-700 disabled:opacity-50 font-medium">
                    {completing === r.id ? '처리중...' : '완료'}
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* 출고완료 이력 */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-600">
            출고완료 이력 ({completed.length}건)
            {searched && <span className="ml-2 text-xs text-blue-500 font-normal">출고일 기준 필터 적용중</span>}
          </p>
          <button
            onClick={handlePackingList}
            disabled={downloading}
            className="text-sm bg-indigo-600 text-white px-4 py-1.5 rounded hover:bg-indigo-700 disabled:opacity-50 whitespace-nowrap"
          >
            {downloading ? '생성중...' : '📄 패킹리스트 다운로드'}
          </button>
        </div>

        {searched && (
          <p className="text-xs text-gray-400 mb-2">
            기간: {searched.from} ~ {searched.to} 출고완료 건 합산 PDF 생성
          </p>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 text-gray-600 text-left">
                <th className="px-4 py-2 border">품목코드</th>
                <th className="px-4 py-2 border">출고량</th>
                <th className="px-4 py-2 border">납기일</th>
                <th className="px-4 py-2 border">출고일</th>
                <th className="px-4 py-2 border">생산 시작</th>
                <th className="px-4 py-2 border">생산 완료</th>
                <th className="px-4 py-2 border">상태</th>
              </tr>
            </thead>
            <tbody>
              {completed.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-400">
                  {searched ? '해당 기간 출고완료 이력 없음' : '출고완료 이력 없음'}
                </td></tr>
              )}
              {completed.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 border font-mono font-semibold">{r.item_name}</td>
                  <td className="px-4 py-2 border">{r.release_qty.toLocaleString()}개</td>
                  <td className="px-4 py-2 border">{r.due_date}</td>
                  <td className="px-4 py-2 border text-green-700 font-medium">{r.release_date || '-'}</td>
                  <td className="px-4 py-2 border text-xs text-gray-500">{r.started_at ? fmtDT(r.started_at) : '-'}</td>
                  <td className="px-4 py-2 border text-xs">
                    {r.finished_at
                      ? <span className="text-blue-600 font-medium">{fmtDT(r.finished_at)}</span>
                      : <span className="text-gray-400">-</span>}
                  </td>
                  <td className="px-4 py-2 border">
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">출고완료</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
