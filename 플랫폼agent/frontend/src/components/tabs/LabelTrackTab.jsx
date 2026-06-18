import { useState } from 'react'
import { getLabelCodeStatus } from '../../api'

function CompanyCard({ name, data }) {
  const done = data?.status === '출고완료'
  return (
    <div className={`flex-1 border-2 rounded-xl p-4 text-center transition-all ${done ? 'border-green-400 bg-green-50' : 'border-gray-200 bg-white'}`}>
      <p className="text-sm font-bold text-gray-700 mb-2">{name}</p>
      {data?.item_name ? (
        <>
          <p className="font-mono text-xs text-gray-500 mb-1">{data.item_name}</p>
          {data.qty != null && <p className="text-xs text-gray-400 mb-2">{data.qty} 개/야드/장</p>}
        </>
      ) : (
        <p className="text-xs text-gray-300 mb-2 italic">데이터 없음</p>
      )}
      <div className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold ${
        done ? 'bg-green-200 text-green-800' : 'bg-gray-100 text-gray-500'
      }`}>
        {done ? '✅ 출고완료' : data?.status ? `⏳ ${data.status}` : '미등록'}
      </div>
    </div>
  )
}

export default function LabelTrackTab() {
  const [code, setCode] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSearch = async () => {
    const trimmed = code.trim().toUpperCase()
    if (trimmed.length !== 9) { setError('라벨코드는 9자리여야 합니다'); return }
    setError('')
    setLoading(true)
    setResult(null)
    try {
      const res = await getLabelCodeStatus(trimmed)
      setResult(res.data)
    } catch {
      setError('조회 실패 — 서버를 확인하세요')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="bg-white rounded-xl shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">라벨코드 추적</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={code}
            maxLength={9}
            onChange={e => setCode(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="W3MJW01NV"
            className="flex-1 border rounded-lg px-3 py-2 font-mono text-sm uppercase focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? '조회중...' : '조회'}
          </button>
        </div>
        {error && <p className="text-red-500 text-xs mt-2">{error}</p>}
      </div>

      {result && (
        <div className="space-y-4">
          {/* 3사 현황 카드 */}
          <div className="flex gap-3">
            <CompanyCard name="옷감사"    data={result.옷감사} />
            <CompanyCard name="라벨사"    data={result.라벨사} />
            <CompanyCard name="지퍼단추사" data={result.지퍼단추사} />
          </div>

          {/* 완료 배너 */}
          {result.all_complete ? (
            <div className="bg-green-500 text-white rounded-xl p-4 text-center font-semibold shadow-lg">
              ✅ 전사 출고 완료 — 물류 배차 자동 생성됨
            </div>
          ) : (
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 text-center text-sm text-yellow-700">
              ⏳ 일부 회사 출고 미완료
            </div>
          )}
        </div>
      )}
    </div>
  )
}
