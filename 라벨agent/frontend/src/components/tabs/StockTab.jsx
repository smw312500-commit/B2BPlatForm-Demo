import { useEffect, useState } from 'react'
import { deleteStockBulk, getStock } from '../../services/api'

export default function StockTab() {
  const [stocks, setStocks] = useState([])
  const [checked, setChecked] = useState(new Set())
  const [deleting, setDeleting] = useState(false)
  const [loading, setLoading] = useState(true)

  const fetchStock = async () => {
    try {
      const res = await getStock()
      setStocks(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStock()
  }, [])

  const toggleOne = (id) => {
    setChecked((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (checked.size === stocks.length) setChecked(new Set())
    else setChecked(new Set(stocks.map((stock) => stock.id)))
  }

  const handleDelete = async () => {
    if (checked.size === 0) return
    if (!confirm(`선택한 ${checked.size}건을 삭제하시겠습니까?`)) return

    setDeleting(true)
    try {
      await deleteStockBulk([...checked])
      setChecked(new Set())
      await fetchStock()
    } catch (err) {
      alert(err.response?.data?.detail || '삭제 실패')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-base font-semibold">재고 현황</h3>
        {checked.size > 0 && (
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="rounded bg-red-500 px-4 py-1.5 text-sm text-white hover:bg-red-600 disabled:opacity-50"
          >
            {deleting ? '삭제 중..' : `선택 삭제 (${checked.size}건)`}
          </button>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">불러오는 중..</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-gray-100 text-left text-gray-600">
                <th className="w-10 border px-3 py-2">
                  <input
                    type="checkbox"
                    checked={stocks.length > 0 && checked.size === stocks.length}
                    onChange={toggleAll}
                    className="cursor-pointer"
                  />
                </th>
                <th className="border px-4 py-2">항목명</th>
                <th className="border px-4 py-2">단위</th>
                <th className="border px-4 py-2">현재 재고</th>
                <th className="border px-4 py-2">환산중량(kg)</th>
                <th className="border px-4 py-2">최종 업데이트</th>
              </tr>
            </thead>
            <tbody>
              {stocks.length === 0 && (
                <tr>
                  <td colSpan={6} className="border px-4 py-4 text-center text-gray-400">
                    재고 데이터 없음
                  </td>
                </tr>
              )}
              {stocks.map((stock) => (
                <tr
                  key={stock.id}
                  onClick={() => toggleOne(stock.id)}
                  className={`cursor-pointer hover:bg-gray-50 ${checked.has(stock.id) ? 'bg-red-50' : ''}`}
                >
                  <td className="border px-3 py-2 text-center">
                    <input
                      type="checkbox"
                      checked={checked.has(stock.id)}
                      onChange={() => toggleOne(stock.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="cursor-pointer"
                    />
                  </td>
                  <td className="border px-4 py-2 font-medium">{stock.material_name}</td>
                  <td className="border px-4 py-2 text-gray-500">{stock.unit}</td>
                  <td className="border px-4 py-2">
                    <span
                      className={`font-semibold ${
                        Number(stock.stock_qty) <= (stock.material_name === '라벨원단' ? 500 : 5)
                          ? 'text-red-600'
                          : 'text-gray-800'
                      }`}
                    >
                      {Number(stock.stock_qty).toLocaleString()} {stock.unit}
                    </span>
                  </td>
                  <td className="border px-4 py-2 text-gray-600">
                    {typeof stock.weight_kg === 'number' ? `${stock.weight_kg.toLocaleString()} kg` : '-'}
                  </td>
                  <td className="border px-4 py-2 text-xs text-gray-400">
                    {stock.updated_at ? new Date(stock.updated_at).toLocaleString('ko-KR') : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 rounded border border-blue-200 bg-blue-50 p-3 text-xs text-blue-700">
        안전재고 기준: 라벨원단 500m / 잉크 5통 이하 시 AI Agent 발주 권고 표시
        <br />
        무게 환산 규칙: 완제품 라벨 1,000장 = 1kg / 라벨원단 1,000장 생산분 = 1kg / 잉크 10통 = 1kg
      </div>
    </div>
  )
}
