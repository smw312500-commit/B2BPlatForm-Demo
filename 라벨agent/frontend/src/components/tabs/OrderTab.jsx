import { useEffect, useRef, useState } from 'react'
import * as XLSX from 'xlsx'
import { cancelOrder, createOrder, getOrders, parseBL, receiveOrder } from '../../services/api'

const STATUS_COLOR = {
  대기중: 'bg-yellow-100 text-yellow-800',
  입고완료: 'bg-green-100 text-green-700',
  취소: 'bg-gray-100 text-gray-400',
}

const MATERIAL_INFO = {
  '라벨 원단': { unit: 'm', hint: '1m 당 라벨 25장 생산분' },
  잉크: { unit: '통', hint: '1통 당 라벨 10,000장 생산분' },
}

const VALID_MATERIALS = ['라벨 원단', '잉크']

function today() {
  return new Date().toISOString().split('T')[0]
}

function parseOrderNote(note) {
  const segments = String(note || '')
    .split('/')
    .map((segment) => segment.trim())
    .filter(Boolean)

  let blNumber = null
  let portOfLoading = null
  let portOfDischarge = null
  const remaining = []

  for (const segment of segments) {
    if (segment.startsWith('BL ')) {
      blNumber = segment.slice(3).trim() || null
      continue
    }
    if (segment.startsWith('POL ')) {
      portOfLoading = segment.slice(4).trim() || null
      continue
    }
    if (segment.startsWith('POD ')) {
      portOfDischarge = segment.slice(4).trim() || null
      continue
    }
    remaining.push(segment)
  }

  return {
    blNumber,
    portOfLoading,
    portOfDischarge,
    displayNote: remaining.length > 0 ? remaining.join(' / ') : '-',
  }
}

function inRange(dateStr, searched) {
  if (!searched || !dateStr) return true
  const date = new Date(dateStr)
  return date >= new Date(searched.from) && date <= new Date(`${searched.to}T23:59:59`)
}

function excelDateToISO(value) {
  if (!value && value !== 0) return null

  if (value instanceof Date) {
    const year = value.getFullYear()
    const month = String(value.getMonth() + 1).padStart(2, '0')
    const day = String(value.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }

  if (typeof value === 'number') {
    const ms = Math.round((value - 25569) * 86400 * 1000)
    const date = new Date(ms)
    const year = date.getUTCFullYear()
    const month = String(date.getUTCMonth() + 1).padStart(2, '0')
    const day = String(date.getUTCDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }

  if (typeof value === 'string') {
    const cleaned = value.replace(/\//g, '-').trim()
    if (/^\d{4}-\d{2}-\d{2}$/.test(cleaned)) return cleaned
  }

  return null
}

function buildEmptyForm() {
  return {
    material_name: '라벨 원단',
    order_qty: '',
    supplier: '',
    order_date: today(),
    due_date: '',
    note: '',
  }
}

function validateRow(row, index) {
  const errors = []

  if (!VALID_MATERIALS.includes(row.material_name)) {
    errors.push(`${index + 1}행 품목은 '라벨 원단' 또는 '잉크'만 가능합니다.`)
  }
  if (!row.order_qty || Number.isNaN(Number(row.order_qty)) || Number(row.order_qty) <= 0) {
    errors.push(`${index + 1}행 발주수량이 올바르지 않습니다.`)
  }
  if (!row.order_date) {
    errors.push(`${index + 1}행 발주일 형식이 올바르지 않습니다. (YYYY-MM-DD)`)
  }
  if (!row.due_date) {
    errors.push(`${index + 1}행 납기요청일 형식이 올바르지 않습니다. (YYYY-MM-DD)`)
  }

  return errors
}

function normalizeBulkRows(rows) {
  return rows.map((row) => ({
    material_name: row.material_name,
    order_qty: Number(row.order_qty),
    supplier: row.supplier || '',
    order_date: row.order_date || today(),
    due_date: row.due_date || '',
    note: row.note || '',
  }))
}

function downloadTemplate() {
  const worksheet = XLSX.utils.aoa_to_sheet([
    ['품목', '발주수량', '발주처', '발주일', '납기요청일', '비고'],
    ['라벨 원단', 100, '원단공급처', '2026-05-22', '2026-06-01', ''],
    ['잉크', 5, '잉크공급처', '2026-05-22', '2026-06-01', '샘플'],
  ])
  worksheet['!cols'] = [{ wch: 12 }, { wch: 10 }, { wch: 16 }, { wch: 14 }, { wch: 14 }, { wch: 18 }]

  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, '발주등록')
  XLSX.writeFile(workbook, '발주등록_양식.xlsx')
}

export default function OrderTab({ searched, onReportRefresh }) {
  const [orders, setOrders] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [showExcelPicker, setShowExcelPicker] = useState(false)
  const [canceling, setCanceling] = useState(null)
  const [receiving, setReceiving] = useState(null)
  const [form, setForm] = useState(buildEmptyForm())

  const [bulkMode, setBulkMode] = useState(null)
  const [bulkRows, setBulkRows] = useState([])
  const [bulkErrors, setBulkErrors] = useState([])
  const [bulkUploading, setBulkUploading] = useState(false)
  const [bulkResult, setBulkResult] = useState(null)

  const [blParsing, setBlParsing] = useState(false)

  const excelFileRef = useRef(null)
  const blFileRef = useRef(null)

  const fetchOrders = async () => {
    const response = await getOrders()
    setOrders(response.data)
  }

  useEffect(() => {
    fetchOrders()
  }, [])

  const resetBulkPreview = () => {
    setBulkMode(null)
    setBulkRows([])
    setBulkErrors([])
    setBulkResult(null)
    if (excelFileRef.current) excelFileRef.current.value = ''
    if (blFileRef.current) blFileRef.current.value = ''
  }

  const openManualForm = (nextForm = buildEmptyForm()) => {
    resetBulkPreview()
    setShowExcelPicker(false)
    setForm(nextForm)
    setShowForm(true)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    await createOrder({ ...form, order_qty: Number(form.order_qty) })
    setForm(buildEmptyForm())
    setShowForm(false)
    await fetchOrders()
  }

  const handleCancel = async (id) => {
    if (!confirm('이 발주를 취소하시겠습니까?')) return
    setCanceling(id)
    try {
      await cancelOrder(id)
      await fetchOrders()
    } catch (error) {
      alert(error.response?.data?.detail || '취소 실패')
    } finally {
      setCanceling(null)
    }
  }

  const handleReceive = async (id, materialName, qty) => {
    if (!confirm(`'${materialName}' ${Number(qty).toLocaleString()} 입고 처리하시겠습니까?\n재고에 즉시 반영됩니다.`)) {
      return
    }

    setReceiving(id)
    try {
      await receiveOrder(id)
      await fetchOrders()
      await onReportRefresh?.()
    } catch (error) {
      alert(error.response?.data?.detail || '입고 처리 실패')
    } finally {
      setReceiving(null)
    }
  }

  const handleExcelFileChange = (event) => {
    const file = event.target.files[0]
    if (!file) return

    setBulkResult(null)

    const reader = new FileReader()
    reader.onload = (loadEvent) => {
      const workbook = XLSX.read(loadEvent.target.result, { type: 'array', cellDates: true })
      const worksheet = workbook.Sheets[workbook.SheetNames[0]]
      const rawRows = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' })
      const dataRows = rawRows.slice(1).filter((row) => row.some((cell) => cell !== ''))

      const rows = dataRows.map((row) => ({
        material_name: String(row[0] ?? '').trim(),
        order_qty: row[1],
        supplier: String(row[2] ?? '').trim(),
        order_date: excelDateToISO(row[3]),
        due_date: excelDateToISO(row[4]),
        note: String(row[5] ?? '').trim(),
      }))

      setShowForm(false)
      setShowExcelPicker(true)
      setBulkMode('excel')
      setBulkRows(rows)
      setBulkErrors(rows.flatMap((row, index) => validateRow(row, index)))
    }
    reader.readAsArrayBuffer(file)
  }

  const handleBulkUpload = async () => {
    if (bulkRows.length === 0 || bulkErrors.length > 0) return

    setBulkUploading(true)
    let successCount = 0
    const failDetails = []

    for (const [index, row] of bulkRows.entries()) {
      try {
        await createOrder({ ...row, order_qty: Number(row.order_qty) })
        successCount += 1
      } catch (error) {
        const message = error.response?.data?.detail || error.message || '알 수 없는 오류'
        failDetails.push(`${index + 1}행(${row.material_name}): ${message}`)
      }
    }

    setBulkUploading(false)
    setBulkResult({
      success: successCount,
      fail: failDetails.length,
      failDetails,
    })

    if (failDetails.length === 0) {
      resetBulkPreview()
    }

    await fetchOrders()
  }

  const handleBLUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setBlParsing(true)
    setBulkResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await parseBL(formData)
      const data = response.data

      const ordersFromBl = Array.isArray(data.orders) && data.orders.length > 0
        ? data.orders.map((item, index) => ({
            material_name: item.material_name || data.material_name || '라벨 원단',
            order_qty: item.order_qty ?? data.order_qty ?? '',
            supplier: data.supplier || data.shipper || '',
            order_date: data.order_date || today(),
            due_date: data.due_date || data.eta || '',
            note: [
              data.bl_number ? `BL ${data.bl_number}` : '',
              data.port_of_loading ? `POL ${data.port_of_loading}` : '',
              data.port_of_discharge ? `POD ${data.port_of_discharge}` : '',
              item.source_code ? `코드 ${item.source_code}` : '',
              index === 0 ? data.note || '' : '',
            ]
              .filter(Boolean)
              .join(' / '),
          }))
        : [
            {
              material_name: data.material_name || data.item || '라벨 원단',
              order_qty: data.order_qty ?? data.quantity ?? '',
              supplier: data.supplier || data.shipper || '',
              order_date: data.order_date || today(),
              due_date: data.due_date || data.eta || '',
              note: [
                data.bl_number ? `BL ${data.bl_number}` : '',
                data.port_of_loading ? `POL ${data.port_of_loading}` : '',
                data.port_of_discharge ? `POD ${data.port_of_discharge}` : '',
                data.note || data.remark || '',
              ]
                .filter(Boolean)
                .join(' / '),
            },
          ]

      const normalizedRows = normalizeBulkRows(ordersFromBl)
      const errors = normalizedRows.flatMap((row, index) => validateRow(row, index))

      if (normalizedRows.length === 1) {
        openManualForm({
          ...normalizedRows[0],
          order_qty: String(normalizedRows[0].order_qty),
        })
        alert('BL 파싱 완료. 발주 등록 폼을 자동으로 채웠습니다.')
        return
      }

      setShowForm(false)
      setShowExcelPicker(false)
      setBulkMode('bl')
      setBulkRows(normalizedRows)
      setBulkErrors(errors)
      alert(`BL 파싱 완료. ${normalizedRows.length}건 발주 미리보기를 확인하고 등록하세요.`)
    } catch (error) {
      alert(error.response?.data?.detail || 'BL 파싱 실패')
    } finally {
      setBlParsing(false)
      if (blFileRef.current) blFileRef.current.value = ''
    }
  }

  const filteredOrders = searched
    ? orders.filter((order) => inRange(order.order_date, searched))
    : orders

  const activeOrders = filteredOrders.filter((order) => order.status === '대기중')
  const historyOrders = filteredOrders.filter((order) => order.status !== '대기중')

  const bulkTitle = bulkMode === 'bl' ? 'BL 파싱 발주 미리보기' : '엑셀 일괄 발주 등록'
  const bulkButtonLabel = bulkMode === 'bl'
    ? `${bulkRows.length}건 BL 발주 등록`
    : `${bulkRows.length}건 업로드`

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">
          원자재 발주
          {searched && (
            <span className="ml-2 text-xs font-normal text-blue-500">발주일 기준 필터 적용중</span>
          )}
        </h3>

        <div className="flex gap-2">
          <label
            className={`cursor-pointer text-sm px-4 py-1.5 rounded border transition-colors ${
              blParsing
                ? 'opacity-50 pointer-events-none'
                : 'bg-white text-purple-700 border-purple-400 hover:bg-purple-50'
            }`}
          >
            {blParsing ? '파싱중..' : 'BL 업로드'}
            <input
              ref={blFileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleBLUpload}
            />
          </label>

          <button
            onClick={() => {
              resetBulkPreview()
              setShowForm(false)
              setShowExcelPicker((prev) => !prev)
            }}
            className={`text-sm px-4 py-1.5 rounded border transition-colors ${
              showExcelPicker
                ? 'bg-green-600 text-white border-green-600'
                : 'bg-white text-green-700 border-green-400 hover:bg-green-50'
            }`}
          >
            엑셀 업로드
          </button>

          <button
            onClick={() => openManualForm(buildEmptyForm())}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700"
          >
            + 발주 등록
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 border rounded p-4 space-y-3 text-sm">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-500">품목</label>
              <select
                value={form.material_name}
                onChange={(event) => setForm((prev) => ({ ...prev, material_name: event.target.value }))}
                className="w-full border rounded px-2 py-1.5 mt-1"
              >
                <option>라벨 원단</option>
                <option>잉크</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-gray-500">
                발주수량
                <span className="ml-1 text-blue-500 font-medium">
                  ({MATERIAL_INFO[form.material_name]?.unit})
                </span>
              </label>
              <div className="flex items-center gap-1 mt-1">
                <input
                  type="number"
                  required
                  value={form.order_qty}
                  onChange={(event) => setForm((prev) => ({ ...prev, order_qty: event.target.value }))}
                  className="flex-1 border rounded px-2 py-1.5"
                  placeholder="수량"
                />
                <span className="text-sm text-gray-500 whitespace-nowrap">
                  {MATERIAL_INFO[form.material_name]?.unit}
                </span>
              </div>
              {form.order_qty && (
                <p className="text-xs text-blue-600 mt-1">
                  예상 생산량{' '}
                  {form.material_name === '라벨 원단'
                    ? (Number(form.order_qty) * 25).toLocaleString()
                    : (Number(form.order_qty) * 10000).toLocaleString()}
                  장 생산 가능
                </p>
              )}
              <p className="text-xs text-gray-400 mt-0.5">{MATERIAL_INFO[form.material_name]?.hint}</p>
            </div>

            <div>
              <label className="text-xs text-gray-500">발주처</label>
              <input
                type="text"
                value={form.supplier}
                onChange={(event) => setForm((prev) => ({ ...prev, supplier: event.target.value }))}
                className="w-full border rounded px-2 py-1.5 mt-1"
                placeholder="발주처명"
              />
            </div>

            <div>
              <label className="text-xs text-gray-500">발주일</label>
              <input
                type="date"
                required
                value={form.order_date}
                onChange={(event) => setForm((prev) => ({ ...prev, order_date: event.target.value }))}
                className="w-full border rounded px-2 py-1.5 mt-1"
              />
            </div>

            <div>
              <label className="text-xs text-gray-500">납기요청일</label>
              <input
                type="date"
                required
                value={form.due_date}
                onChange={(event) => setForm((prev) => ({ ...prev, due_date: event.target.value }))}
                className="w-full border rounded px-2 py-1.5 mt-1"
              />
            </div>

            <div>
              <label className="text-xs text-gray-500">비고</label>
              <input
                type="text"
                value={form.note}
                onChange={(event) => setForm((prev) => ({ ...prev, note: event.target.value }))}
                className="w-full border rounded px-2 py-1.5 mt-1"
                placeholder="비고"
              />
            </div>
          </div>

          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setShowForm(false)} className="text-xs text-gray-500 hover:underline">
              취소
            </button>
            <button type="submit" className="text-xs bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700">
              등록
            </button>
          </div>
        </form>
      )}

      {showExcelPicker && !bulkMode && (
        <div className="border rounded p-4 bg-gray-50 space-y-4 text-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium text-gray-700 mb-1">엑셀 일괄 발주 등록</p>
              <p className="text-xs text-gray-500">양식을 내려받아 작성한 뒤 업로드하세요.</p>
              <div className="mt-1 text-xs text-gray-400 space-y-0.5">
                <p>품목은 `라벨 원단` 또는 `잉크`만 가능합니다.</p>
                <p>날짜는 `YYYY-MM-DD` 형식을 사용합니다.</p>
                <p>발주처와 비고는 선택 입력입니다.</p>
              </div>
            </div>
            <button
              onClick={downloadTemplate}
              className="text-xs bg-white border border-gray-300 text-gray-600 px-3 py-2 rounded hover:bg-gray-100 whitespace-nowrap"
            >
              양식 다운로드
            </button>
          </div>

          <div className="flex items-center gap-3">
            <label className="cursor-pointer bg-white border border-dashed border-gray-400 rounded px-4 py-2 text-xs text-gray-500 hover:bg-gray-50 hover:border-blue-400 transition-colors">
              파일 선택 (.xlsx, .xls)
              <input
                ref={excelFileRef}
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={handleExcelFileChange}
              />
            </label>
          </div>
        </div>
      )}

      {bulkMode && (
        <div className="border rounded p-4 bg-gray-50 space-y-4 text-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium text-gray-700 mb-1">{bulkTitle}</p>
              <p className="text-xs text-gray-500">
                {bulkMode === 'bl'
                  ? 'BL에서 파싱한 품목을 여러 건 발주로 등록합니다.'
                  : '엑셀에서 읽은 품목을 여러 건 발주로 등록합니다.'}
              </p>
            </div>
            <button onClick={resetBulkPreview} className="text-xs text-gray-500 hover:underline">
              닫기
            </button>
          </div>

          {bulkErrors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded p-3 space-y-1">
              <p className="text-xs font-semibold text-red-700">아래 오류를 수정한 뒤 다시 시도하세요.</p>
              {bulkErrors.map((error, index) => (
                <p key={`bulk-error-${index}`} className="text-xs text-red-600">
                  {error}
                </p>
              ))}
            </div>
          )}

          <div>
            <p className="text-xs font-medium text-gray-600 mb-2">미리보기 (총 {bulkRows.length}건)</p>
            <div className="overflow-x-auto max-h-56 overflow-y-auto border rounded">
              <table className="w-full text-xs border-collapse">
                <thead className="sticky top-0 bg-gray-100">
                  <tr>
                    {['품목', '발주수량', '발주처', '발주일', '납기요청일', '비고'].map((header) => (
                      <th key={header} className="px-3 py-1.5 border text-gray-600 text-left">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {bulkRows.map((row, index) => (
                    <tr key={`${row.material_name}-${index}`} className="hover:bg-gray-50">
                      <td className="px-3 py-1.5 border font-medium">{row.material_name}</td>
                      <td className="px-3 py-1.5 border">
                        {Number(row.order_qty).toLocaleString()} {MATERIAL_INFO[row.material_name]?.unit}
                      </td>
                      <td className="px-3 py-1.5 border text-gray-600">{row.supplier || '-'}</td>
                      <td className="px-3 py-1.5 border">{row.order_date}</td>
                      <td className="px-3 py-1.5 border">{row.due_date}</td>
                      <td className="px-3 py-1.5 border text-gray-500">{row.note || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {bulkResult && (
            <div
              className={`rounded p-3 text-xs space-y-1 ${
                bulkResult.fail === 0
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-yellow-50 border border-yellow-200 text-yellow-800'
              }`}
            >
              <p>
                등록 완료: {bulkResult.success}건
                {bulkResult.fail > 0 ? ` / 실패: ${bulkResult.fail}건` : ''}
              </p>
              {bulkResult.failDetails?.map((detail, index) => (
                <p key={`bulk-fail-${index}`} className="text-red-600">
                  {detail}
                </p>
              ))}
            </div>
          )}

          <div className="flex gap-2 justify-end">
            <button onClick={resetBulkPreview} className="text-xs text-gray-500 hover:underline">
              취소
            </button>
            <button
              onClick={handleBulkUpload}
              disabled={bulkUploading || bulkRows.length === 0 || bulkErrors.length > 0}
              className="text-xs bg-green-600 text-white px-4 py-1.5 rounded hover:bg-green-700 disabled:opacity-40"
            >
              {bulkUploading ? '등록중..' : bulkButtonLabel}
            </button>
          </div>
        </div>
      )}

      <section>
        <p className="text-sm font-medium text-gray-600 mb-2">진행중 발주 ({activeOrders.length}건)</p>
        <OrderTable
          rows={activeOrders}
          onCancel={handleCancel}
          canceling={canceling}
          onReceive={handleReceive}
          receiving={receiving}
          showActions
        />
      </section>

      <section>
        <p className="text-sm font-medium text-gray-600 mb-2">발주 이력 ({historyOrders.length}건)</p>
        <OrderTable rows={historyOrders} />
      </section>
    </div>
  )
}

function OrderTable({ rows, onCancel, canceling, onReceive, receiving, showActions = false }) {
  const colSpan = showActions ? 11 : 9

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100 text-gray-600 text-left">
            <th className="px-3 py-2 border">품목</th>
            <th className="px-3 py-2 border">발주수량</th>
            <th className="px-3 py-2 border">발주처</th>
            <th className="px-3 py-2 border">선적항</th>
            <th className="px-3 py-2 border">도착항</th>
            <th className="px-3 py-2 border">발주일</th>
            <th className="px-3 py-2 border">납기요청일</th>
            <th className="px-3 py-2 border">상태</th>
            <th className="px-3 py-2 border">비고</th>
            {showActions && (
              <>
                <th className="px-3 py-2 border">재고 입고</th>
                <th className="px-3 py-2 border">취소</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={colSpan} className="px-4 py-4 text-center text-gray-400">
                내역 없음
              </td>
            </tr>
          )}

          {rows.map((order) => {
            const route = parseOrderNote(order.note)

            return (
              <tr key={order.id} className="hover:bg-gray-50">
                <td className="px-3 py-2 border font-medium">{order.material_name}</td>
                <td className="px-3 py-2 border">{Number(order.order_qty).toLocaleString()}</td>
                <td className="px-3 py-2 border text-gray-600">{order.supplier || '-'}</td>
                <td className="px-3 py-2 border text-xs text-gray-600 whitespace-nowrap">
                  {route.portOfLoading || '-'}
                </td>
                <td className="px-3 py-2 border text-xs text-gray-600 whitespace-nowrap">
                  {route.portOfDischarge || '-'}
                </td>
                <td className="px-3 py-2 border">{order.order_date}</td>
                <td className="px-3 py-2 border">{order.due_date}</td>
                <td className="px-3 py-2 border">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLOR[order.status] || ''}`}>
                    {order.status}
                  </span>
                </td>
                <td className="px-3 py-2 border text-gray-400 text-xs">
                  {route.blNumber ? `BL ${route.blNumber}` : route.displayNote}
                </td>
                {showActions && (
                  <>
                    <td className="px-3 py-2 border">
                      <button
                        onClick={() => onReceive(order.id, order.material_name, order.order_qty)}
                        disabled={receiving === order.id}
                        className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap"
                      >
                        {receiving === order.id ? '처리중..' : '재고 입고'}
                      </button>
                    </td>
                    <td className="px-3 py-2 border">
                      <button
                        onClick={() => onCancel(order.id)}
                        disabled={canceling === order.id}
                        className="text-xs bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 disabled:opacity-50"
                      >
                        {canceling === order.id ? '...' : '취소'}
                      </button>
                    </td>
                  </>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
