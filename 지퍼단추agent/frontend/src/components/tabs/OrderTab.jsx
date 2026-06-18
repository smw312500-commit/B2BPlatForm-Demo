import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import * as XLSX from 'xlsx'
import { getOrders, createOrder, cancelOrder, receiveOrder } from '../../services/api'

const STATUS_COLOR = {
  대기중:   'bg-yellow-100 text-yellow-800',
  입고완료: 'bg-green-100 text-green-700',
  취소:     'bg-gray-100 text-gray-400',
}

const MATERIAL_INFO = {
  원목:        { unit: 'kg', hint: '1kg → 원목단추 50개' },
  플라스틱원료: { unit: 'kg', hint: '1kg → 플라스틱단추 200개' },
  금속원료:    { unit: 'kg', hint: '1kg → 금속단추 150개' },
  지퍼테이프:  { unit: 'm',  hint: '1m → 지퍼 1개' },
}

const VALID_MATERIALS = Object.keys(MATERIAL_INFO)

function excelDateToISO(val) {
  if (!val && val !== 0) return null
  if (val instanceof Date) {
    return `${val.getFullYear()}-${String(val.getMonth()+1).padStart(2,'0')}-${String(val.getDate()).padStart(2,'0')}`
  }
  if (typeof val === 'number') {
    const date = new Date(Math.round((val - 25569) * 86400 * 1000))
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth()+1).padStart(2,'0')}-${String(date.getUTCDate()).padStart(2,'0')}`
  }
  if (typeof val === 'string') {
    const c = val.replace(/\//g, '-').trim()
    if (/^\d{4}-\d{2}-\d{2}$/.test(c)) return c
  }
  return null
}

function today() { return new Date().toISOString().split('T')[0] }

function inRange(dateStr, searched) {
  if (!searched || !dateStr) return true
  const d = new Date(dateStr)
  return d >= new Date(searched.from) && d <= new Date(searched.to + 'T23:59:59')
}

function downloadTemplate() {
  const ws = XLSX.utils.aoa_to_sheet([
    ['품목', '발주량', '발주처', '발주일', '납기요청일', '비고'],
    ['원목', 100, '원목공급사A', '2026-05-22', '2026-06-01', ''],
    ['지퍼테이프', 500, '부자재사B', '2026-05-22', '2026-06-01', ''],
  ])
  ws['!cols'] = [{ wch: 14 }, { wch: 10 }, { wch: 16 }, { wch: 14 }, { wch: 14 }, { wch: 16 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '발주등록')
  XLSX.writeFile(wb, '발주등록_양식.xlsx')
}

function validateRow(row, idx) {
  const errors = []
  if (!VALID_MATERIALS.includes(row.material_name))
    errors.push(`${idx+1}행: 품목은 ${VALID_MATERIALS.join(' / ')} 중 하나`)
  if (!row.order_qty || isNaN(Number(row.order_qty)) || Number(row.order_qty) <= 0)
    errors.push(`${idx+1}행: 발주량이 올바르지 않습니다`)
  if (!row.order_date) errors.push(`${idx+1}행: 발주일 형식 오류`)
  if (!row.due_date)   errors.push(`${idx+1}행: 납기요청일 형식 오류`)
  return errors
}

export default function OrderTab({ searched }) {
  const [orders, setOrders]       = useState([])
  const [showForm, setShowForm]   = useState(false)
  const [showExcel, setShowExcel] = useState(false)
  const [canceling, setCanceling]   = useState(null)
  const [receiving, setReceiving]   = useState(null)
  const [form, setForm] = useState({
    material_name: '원목', order_qty: '', supplier: '',
    order_date: today(), due_date: '', note: '',
  })
  const [previewRows, setPreviewRows]   = useState([])
  const [excelErrors, setExcelErrors]   = useState([])
  const [uploading, setUploading]       = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const fileRef    = useRef(null)
  // BL 업로드
  const [showBL, setShowBL]         = useState(false)
  const [blParsing, setBlParsing]   = useState(false)
  const [blResult, setBlResult]     = useState(null)
  const blFileRef  = useRef(null)

  const fetchOrders = async () => {
    const res = await getOrders()
    setOrders(res.data)
  }
  useEffect(() => { fetchOrders() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    await createOrder({ ...form, order_qty: Number(form.order_qty) })
    setForm({ material_name: '원목', order_qty: '', supplier: '', order_date: today(), due_date: '', note: '' })
    setShowForm(false); fetchOrders()
  }

  const handleCancel = async (id) => {
    if (!confirm('이 발주를 취소하시겠습니까?')) return
    setCanceling(id)
    try { await cancelOrder(id); fetchOrders() }
    catch (err) { alert(err.response?.data?.detail || '취소 실패') }
    finally { setCanceling(null) }
  }

  const handleReceive = async (id, materialName, qty) => {
    if (!confirm(`${materialName} ${Number(qty).toLocaleString()}${''} 입고 처리하면 재고에 자동으로 추가됩니다.\n진행하시겠습니까?`)) return
    setReceiving(id)
    try { await receiveOrder(id); fetchOrders() }
    catch (err) { alert(err.response?.data?.detail || '입고 처리 실패') }
    finally { setReceiving(null) }
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]; if (!file) return
    setUploadResult(null)
    const reader = new FileReader()
    reader.onload = (evt) => {
      const wb  = XLSX.read(evt.target.result, { type: 'array', cellDates: true })
      const ws  = wb.Sheets[wb.SheetNames[0]]
      const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
      const dataRows = raw.slice(1).filter((r) => r.some((c) => c !== ''))
      const rows = dataRows.map((r) => ({
        material_name: String(r[0] ?? '').trim(),
        order_qty:     r[1],
        supplier:      String(r[2] ?? '').trim(),
        order_date:    excelDateToISO(r[3]),
        due_date:      excelDateToISO(r[4]),
        note:          String(r[5] ?? '').trim(),
      }))
      setPreviewRows(rows)
      setExcelErrors(rows.flatMap((row, i) => validateRow(row, i)))
    }
    reader.readAsArrayBuffer(file)
  }

  const handleUpload = async () => {
    if (excelErrors.length > 0 || previewRows.length === 0) return
    setUploading(true)
    let success = 0; const failDetails = []
    for (const [i, row] of previewRows.entries()) {
      try { await createOrder({ ...row, order_qty: Number(row.order_qty) }); success++ }
      catch (err) { failDetails.push(`${i+1}행 (${row.material_name}): ${err.response?.data?.detail || err.message}`) }
    }
    setUploading(false)
    setUploadResult({ success, fail: failDetails.length, failDetails })
    if (failDetails.length === 0) { setPreviewRows([]); setExcelErrors([]); if (fileRef.current) fileRef.current.value = '' }
    fetchOrders()
  }

  const handleExcelClose = () => {
    setShowExcel(false); setPreviewRows([]); setExcelErrors([]); setUploadResult(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleBLUpload = async (e) => {
    const file = e.target.files[0]; if (!file) return
    setBlParsing(true); setBlResult(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await axios.post('http://localhost:8010/parse-bl', formData,
        { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 15000 })
      setBlResult({ ok: true, data: res.data })
    } catch (err) {
      const msg = err.code === 'ECONNREFUSED' || err.code === 'ERR_NETWORK'
        ? 'BL 파서 서비스(포트 8010)에 연결할 수 없습니다.'
        : (err.response?.data?.detail || err.message)
      setBlResult({ ok: false, msg })
    } finally { setBlParsing(false); if (blFileRef.current) blFileRef.current.value = '' }
  }

  const handleBLClose = () => { setShowBL(false); setBlResult(null) }

  const filtered = searched ? orders.filter((o) => inRange(o.order_date, searched)) : orders
  const active  = filtered.filter((o) => o.status === '대기중')
  const history = filtered.filter((o) => o.status !== '대기중')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">
          원자재 발주
          {searched && <span className="ml-2 text-xs text-blue-500 font-normal">발주일 기준 필터 적용중</span>}
        </h3>
        <div className="flex gap-2">
          <button onClick={() => { setShowBL(!showBL); setShowExcel(false); setShowForm(false) }}
            className={`text-sm px-4 py-1.5 rounded border transition-colors ${showBL ? 'bg-purple-600 text-white border-purple-600' : 'bg-white text-purple-700 border-purple-400 hover:bg-purple-50'}`}>
            📋 BL 업로드
          </button>
          <button onClick={() => { setShowExcel(!showExcel); setShowForm(false); setShowBL(false) }}
            className={`text-sm px-4 py-1.5 rounded border transition-colors ${showExcel ? 'bg-green-600 text-white border-green-600' : 'bg-white text-green-700 border-green-400 hover:bg-green-50'}`}>
            📂 엑셀 업로드
          </button>
          <button onClick={() => { setShowForm(!showForm); setShowExcel(false); setShowBL(false) }}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700">
            + 발주 등록
          </button>
        </div>
      </div>

      {showBL && (
        <div className="border rounded p-4 bg-purple-50 space-y-3 text-sm border-purple-200">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium text-purple-800 mb-1">BL(선하증권) 파서 연결</p>
              <p className="text-xs text-gray-500">BL 파일을 업로드하면 포트 8010 파서 서비스로 전송합니다.</p>
            </div>
            <button onClick={handleBLClose} className="text-xs text-gray-400 hover:text-gray-600">닫기</button>
          </div>
          <label className={`cursor-pointer inline-flex items-center gap-2 bg-white border border-dashed rounded px-4 py-2 text-xs transition-colors ${blParsing ? 'opacity-50 pointer-events-none' : 'border-purple-400 text-purple-700 hover:bg-purple-50'}`}>
            {blParsing ? '⏳ 파싱 중...' : '📄 BL 파일 선택'}
            <input ref={blFileRef} type="file" accept=".pdf,.xlsx,.xls,.csv" className="hidden"
              onChange={handleBLUpload} disabled={blParsing} />
          </label>
          {blResult && (
            blResult.ok
              ? (
                <div className="bg-white border border-purple-200 rounded p-3 space-y-1">
                  <p className="text-xs font-semibold text-purple-700 mb-2">✅ 파싱 완료</p>
                  <pre className="text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap max-h-48">
                    {typeof blResult.data === 'object'
                      ? JSON.stringify(blResult.data, null, 2)
                      : String(blResult.data)}
                  </pre>
                </div>
              ) : (
                <div className="bg-red-50 border border-red-200 rounded p-3">
                  <p className="text-xs font-semibold text-red-700">❌ 오류</p>
                  <p className="text-xs text-red-600 mt-1">{blResult.msg}</p>
                </div>
              )
          )}
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 border rounded p-4 space-y-3 text-sm">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-500">품목</label>
              <select value={form.material_name} onChange={(e) => setForm({ ...form, material_name: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1">
                {VALID_MATERIALS.map((m) => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500">발주량 ({MATERIAL_INFO[form.material_name]?.unit})</label>
              <input type="number" required value={form.order_qty}
                onChange={(e) => setForm({ ...form, order_qty: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" placeholder="수량" />
              <p className="text-xs text-gray-400 mt-0.5">{MATERIAL_INFO[form.material_name]?.hint}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">발주처</label>
              <input type="text" value={form.supplier}
                onChange={(e) => setForm({ ...form, supplier: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" placeholder="발주처명" />
            </div>
            <div>
              <label className="text-xs text-gray-500">발주일</label>
              <input type="date" required value={form.order_date}
                onChange={(e) => setForm({ ...form, order_date: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" />
            </div>
            <div>
              <label className="text-xs text-gray-500">납기요청일</label>
              <input type="date" required value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" />
            </div>
            <div>
              <label className="text-xs text-gray-500">비고</label>
              <input type="text" value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" placeholder="비고" />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setShowForm(false)} className="text-xs text-gray-500 hover:underline">취소</button>
            <button type="submit" className="text-xs bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700">등록</button>
          </div>
        </form>
      )}

      {showExcel && (
        <div className="border rounded p-4 bg-gray-50 space-y-4 text-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium text-gray-700 mb-1">엑셀 일괄 발주 등록</p>
              <div className="text-xs text-gray-400 space-y-0.5 mt-1">
                <p>• 품목: {VALID_MATERIALS.join(' / ')}</p>
                <p>• 날짜: YYYY-MM-DD 형식</p>
              </div>
            </div>
            <button onClick={downloadTemplate}
              className="text-xs bg-white border border-gray-300 text-gray-600 px-3 py-2 rounded hover:bg-gray-100 whitespace-nowrap">
              ⬇ 양식 다운로드
            </button>
          </div>
          <div className="flex items-center gap-3">
            <label className="cursor-pointer bg-white border border-dashed border-gray-400 rounded px-4 py-2 text-xs text-gray-500 hover:bg-gray-50 hover:border-blue-400 transition-colors">
              📄 파일 선택 (.xlsx, .xls)
              <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFileChange} />
            </label>
            {previewRows.length > 0 && <span className="text-xs text-blue-600">{previewRows.length}행 인식됨</span>}
          </div>
          {excelErrors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded p-3 space-y-1">
              <p className="text-xs font-semibold text-red-700">❌ 오류를 수정 후 다시 업로드하세요</p>
              {excelErrors.map((e, i) => <p key={i} className="text-xs text-red-600">{e}</p>)}
            </div>
          )}
          {previewRows.length > 0 && excelErrors.length === 0 && (
            <div>
              <p className="text-xs font-medium text-gray-600 mb-2">미리보기 ({previewRows.length}건)</p>
              <div className="overflow-x-auto max-h-40 overflow-y-auto border rounded">
                <table className="w-full text-xs border-collapse">
                  <thead className="sticky top-0 bg-gray-100">
                    <tr>{['품목','발주량','발주처','발주일','납기요청일','비고'].map((h) => (
                      <th key={h} className="px-3 py-1.5 border text-gray-600 text-left">{h}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {previewRows.map((r, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-1.5 border font-medium">{r.material_name}</td>
                        <td className="px-3 py-1.5 border">{Number(r.order_qty).toLocaleString()} {MATERIAL_INFO[r.material_name]?.unit}</td>
                        <td className="px-3 py-1.5 border text-gray-500">{r.supplier || '-'}</td>
                        <td className="px-3 py-1.5 border">{r.order_date}</td>
                        <td className="px-3 py-1.5 border">{r.due_date}</td>
                        <td className="px-3 py-1.5 border text-gray-400">{r.note || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {uploadResult && (
            <div className={`rounded p-3 text-xs space-y-1 ${uploadResult.fail === 0 ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-yellow-50 border border-yellow-200 text-yellow-800'}`}>
              <p>✅ 등록 완료: {uploadResult.success}건{uploadResult.fail > 0 && ` / ❌ 실패: ${uploadResult.fail}건`}</p>
              {uploadResult.failDetails?.map((d, i) => <p key={i} className="text-red-600">• {d}</p>)}
            </div>
          )}
          <div className="flex gap-2 justify-end">
            <button onClick={handleExcelClose} className="text-xs text-gray-500 hover:underline">닫기</button>
            <button onClick={handleUpload} disabled={uploading || previewRows.length === 0 || excelErrors.length > 0}
              className="text-xs bg-green-600 text-white px-4 py-1.5 rounded hover:bg-green-700 disabled:opacity-40">
              {uploading ? '업로드 중...' : `${previewRows.length}건 업로드`}
            </button>
          </div>
        </div>
      )}

      <section>
        <p className="text-sm font-medium text-gray-600 mb-2">진행중 발주 ({active.length}건)</p>
        <OrderTable rows={active} onCancel={handleCancel} canceling={canceling} onReceive={handleReceive} receiving={receiving} showCancel />
      </section>
      <section>
        <p className="text-sm font-medium text-gray-600 mb-2">발주 이력 ({history.length}건)</p>
        <OrderTable rows={history} />
      </section>
    </div>
  )
}

function OrderTable({ rows, onCancel, canceling, onReceive, receiving, showCancel }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100 text-gray-600 text-left">
            <th className="px-3 py-2 border">품목</th>
            <th className="px-3 py-2 border">발주량</th>
            <th className="px-3 py-2 border">발주처</th>
            <th className="px-3 py-2 border">발주일</th>
            <th className="px-3 py-2 border">납기요청일</th>
            <th className="px-3 py-2 border">상태</th>
            <th className="px-3 py-2 border">비고</th>
            {showCancel && <th className="px-3 py-2 border" colSpan={2}>처리</th>}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={showCancel ? 9 : 7} className="px-4 py-4 text-center text-gray-400">내역 없음</td></tr>
          )}
          {rows.map((o) => (
            <tr key={o.id} className="hover:bg-gray-50">
              <td className="px-3 py-2 border font-medium">{o.material_name}</td>
              <td className="px-3 py-2 border">{Number(o.order_qty).toLocaleString()} {o.unit}</td>
              <td className="px-3 py-2 border text-gray-600">{o.supplier || '-'}</td>
              <td className="px-3 py-2 border">{o.order_date}</td>
              <td className="px-3 py-2 border">{o.due_date}</td>
              <td className="px-3 py-2 border">
                <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLOR[o.status] || ''}`}>{o.status}</span>
              </td>
              <td className="px-3 py-2 border text-gray-400 text-xs">{o.note || '-'}</td>
              {showCancel && (
                <>
                  <td className="px-2 py-2 border">
                    <button onClick={() => onReceive(o.id, o.material_name, o.order_qty)}
                      disabled={receiving === o.id}
                      className="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700 disabled:opacity-50 whitespace-nowrap">
                      {receiving === o.id ? '...' : '재고도착'}
                    </button>
                  </td>
                  <td className="px-2 py-2 border">
                    <button onClick={() => onCancel(o.id)} disabled={canceling === o.id}
                      className="text-xs bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 disabled:opacity-50">
                      {canceling === o.id ? '...' : '취소'}
                    </button>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
