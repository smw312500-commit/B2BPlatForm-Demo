import { useEffect, useRef, useState } from 'react'
import * as XLSX from 'xlsx'
import { getReleases, createRelease, validateItem, deleteReleasesBulk } from '../../services/api'
import MachineLayout from '../MachineLayout'

function today() { return new Date().toISOString().split('T')[0] }

function inRange(dateStr, searched) {
  if (!searched || !dateStr) return true
  const d = new Date(dateStr)
  return d >= new Date(searched.from) && d <= new Date(searched.to + 'T23:59:59')
}

function excelDateToISO(val) {
  if (!val && val !== 0) return null
  if (val instanceof Date)
    return `${val.getFullYear()}-${String(val.getMonth()+1).padStart(2,'0')}-${String(val.getDate()).padStart(2,'0')}`
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

const ITEM_OPTIONS = [
  'WOOD_BR','WOOD_BK','PLASTIC_BK','PLASTIC_WH','METAL_SV','METAL_BK','ZIPPER_S','ZIPPER_M','ZIPPER_L',
]

// 품목 타입 → 선택 가능한 컬러/사이즈
const ITEM_TYPES = [
  { code: 'WOOD',    label: '원목단추' },
  { code: 'PLASTIC', label: '플라스틱단추' },
  { code: 'METAL',   label: '금속단추' },
  { code: 'ZIPPER',  label: '지퍼' },
]
const COLOR_OPTIONS = {
  WOOD:    [{ code: 'BR', label: '브라운' }, { code: 'BK', label: '블랙' }],
  PLASTIC: [{ code: 'BK', label: '블랙' },  { code: 'WH', label: '화이트' }],
  METAL:   [{ code: 'SV', label: '실버' },  { code: 'BK', label: '블랙' }],
  ZIPPER:  [{ code: 'S',  label: '소형' },  { code: 'M',  label: '중형' }, { code: 'L', label: '대형' }],
}

function getItemType(itemName) {
  const p = itemName.toUpperCase().split('_')
  if (p[0] === 'ZIPPER') return '지퍼'
  return { WOOD: '원목단추', PLASTIC: '플라스틱단추', METAL: '금속단추' }[p[0]] || itemName
}

function getItemLabel(itemName) {
  const p = itemName.toUpperCase().split('_')
  const typeLabel = { WOOD: '원목단추', PLASTIC: '플라스틱단추', METAL: '금속단추', ZIPPER: '지퍼' }[p[0]] || p[0]
  if (p[0] === 'ZIPPER') {
    const sizeLabel = { S: '소형', M: '중형', L: '대형' }[p[1]] || p[1]
    return `${typeLabel} (${sizeLabel})`
  }
  const colorLabel = { BR: '브라운', BK: '블랙', WH: '화이트', SV: '실버', NV: '네이비', GY: '그레이' }[p[1]] || p[1]
  return `${typeLabel} / ${colorLabel}`
}

// 기계 기본값: 8대 (4종 × 2대)
const LS_KEY       = 'zipper_machines_v1'
const PROD_LOG_KEY = 'zipper_prod_log_v1'

const SPEED_PER_SEC = {
  원목단추:     (20 * 2)  / 3600,
  플라스틱단추: (300 * 2) / 3600,
  금속단추:     (150 * 2) / 3600,
  지퍼:         (200 * 2) / 3600,
}

const MACHINE_INIT = [
  { id: 1, name: '목공 성형기 1호', itemType: '원목단추' },
  { id: 2, name: '목공 성형기 2호', itemType: '원목단추' },
  { id: 3, name: '사출 성형기 1호', itemType: '플라스틱단추' },
  { id: 4, name: '사출 성형기 2호', itemType: '플라스틱단추' },
  { id: 5, name: '금속 프레스기 1호', itemType: '금속단추' },
  { id: 6, name: '금속 프레스기 2호', itemType: '금속단추' },
  { id: 7, name: '지퍼 조립기 1호', itemType: '지퍼' },
  { id: 8, name: '지퍼 조립기 2호', itemType: '지퍼' },
].map((m) => ({ ...m, status: '대기중', releaseId: null, item_name: null, total: 0, produced: 0, started_at: null, finished_at: null }))

function saveProdLog(releaseId, patch) {
  try {
    const log = JSON.parse(localStorage.getItem(PROD_LOG_KEY) || '{}')
    log[releaseId] = { ...(log[releaseId] || {}), ...patch }
    localStorage.setItem(PROD_LOG_KEY, JSON.stringify(log))
  } catch {}
}

function loadMachines() {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return MACHINE_INIT
    return JSON.parse(raw).map((m) => {
      const started  = m.started_at  ? new Date(m.started_at)  : null
      const finished = m.finished_at ? new Date(m.finished_at) : null
      if (m.status === '가동중' && started) {
        const speed   = SPEED_PER_SEC[m.itemType] ?? 1
        const elapsed = (Date.now() - started.getTime()) / 1000
        const next    = Math.min(m.produced + elapsed * speed, m.total)
        if (next >= m.total) {
          const finAt = new Date()
          if (m.releaseId) saveProdLog(m.releaseId, { finished_at: finAt.toISOString() })
          return { ...m, produced: m.total, status: '완료', started_at: started, finished_at: finAt }
        }
        return { ...m, produced: next, started_at: started, finished_at: null }
      }
      return { ...m, started_at: started, finished_at: finished }
    })
  } catch { return MACHINE_INIT }
}

// 한글 → 코드 매핑 (엑셀 업로드용)
const TYPE_MAP  = { '원목단추': 'WOOD', '플라스틱단추': 'PLASTIC', '금속단추': 'METAL', '지퍼': 'ZIPPER' }
const COLOR_MAP = { '브라운': 'BR', '블랙': 'BK', '화이트': 'WH', '실버': 'SV', '네이비': 'NV', '그레이': 'GY', '소형': 'S', '중형': 'M', '대형': 'L' }

function parseExcelItemName(typeRaw, colorRaw) {
  const typeCode  = TYPE_MAP[String(typeRaw).trim()]  || String(typeRaw).trim().toUpperCase()
  const colorCode = COLOR_MAP[String(colorRaw).trim()] || String(colorRaw).trim().toUpperCase()
  return `${typeCode}_${colorCode}`
}

function validateRow(row, idx) {
  const errors = []
  if (!ITEM_OPTIONS.includes(row.item_name?.toUpperCase()))
    errors.push(`${idx+1}행: 품목 오류 — "${row.item_name}" (원목단추/플라스틱단추/금속단추/지퍼 + 컬러/사이즈)`)
  if (!row.release_qty || isNaN(Number(row.release_qty)) || Number(row.release_qty) <= 0)
    errors.push(`${idx+1}행: 주문량이 올바르지 않습니다`)
  if (!row.due_date)
    errors.push(`${idx+1}행: 납기일 형식 오류 (YYYY-MM-DD)`)
  return errors
}

function downloadTemplate() {
  const ws = XLSX.utils.aoa_to_sheet([
    ['품목', '컬러/사이즈', '주문량(개)', '납기일'],
    ['원목단추',     '브라운', 500,  '2026-06-10'],
    ['플라스틱단추', '블랙',   2000, '2026-06-12'],
    ['금속단추',     '실버',   800,  '2026-06-15'],
    ['지퍼',         '중형',   350,  '2026-06-18'],
  ])
  ws['!cols'] = [{ wch: 14 }, { wch: 12 }, { wch: 12 }, { wch: 14 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '생산등록')
  XLSX.writeFile(wb, '생산등록_양식.xlsx')
}

export default function ProductionTab({ searched }) {
  const [releases, setReleases]     = useState([])
  const [showForm, setShowForm]     = useState(false)
  const [showExcel, setShowExcel]   = useState(false)
  const [form, setForm]             = useState({ item_type: 'WOOD', item_color: 'BR', release_qty: '', due_date: '' })
  const [validation, setValidation] = useState(null)
  const [previewRows, setPreviewRows]   = useState([])
  const [excelErrors, setExcelErrors]   = useState([])
  const [uploading, setUploading]       = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const fileRef = useRef(null)
  const [checked, setChecked]   = useState(new Set())
  const [deleting, setDeleting] = useState(false)

  const [machines, setMachines] = useState(loadMachines)
  const [selMachine, setSelMachine] = useState(null)
  const timers = useRef({})

  useEffect(() => {
    localStorage.setItem(LS_KEY, JSON.stringify(machines))
  }, [machines])

  useEffect(() => {
    machines.forEach((m) => {
      if (m.status === '가동중' && m.produced < m.total) _startTimer(m.id)
      if (m.status === '완료' && m.releaseId) {
        saveProdLog(m.releaseId, {
          ...(m.started_at  ? { started_at:  new Date(m.started_at).toISOString()  } : {}),
          ...(m.finished_at ? { finished_at: new Date(m.finished_at).toISOString() } : {}),
        })
      }
    })
    return () => Object.values(timers.current).forEach(clearInterval)
  }, []) // eslint-disable-line

  const _startTimer = (id) => {
    if (timers.current[id]) return
    timers.current[id] = setInterval(() => {
      setMachines((prev) => prev.map((m) => {
        if (m.id !== id) return m
        const speed = SPEED_PER_SEC[m.itemType] ?? 1
        const next  = Math.min(m.produced + speed, m.total)
        if (next >= m.total) {
          clearInterval(timers.current[id]); delete timers.current[id]
          const finAt = new Date()
          if (m.releaseId) saveProdLog(m.releaseId, { finished_at: finAt.toISOString() })
          return { ...m, produced: m.total, status: '완료', finished_at: finAt }
        }
        return { ...m, produced: next }
      }))
    }, 1000)
  }

  const machineHandlers = {
    onStart: (id) => {
      const startTime = new Date()
      setMachines((prev) => {
        const m = prev.find((x) => x.id === id)
        if (m?.releaseId) saveProdLog(m.releaseId, { started_at: startTime.toISOString(), finished_at: null })
        return prev.map((x) => x.id === id ? { ...x, status: '가동중', started_at: startTime, finished_at: null } : x)
      })
      _startTimer(id)
    },
    onStop: (id) => {
      if (timers.current[id]) { clearInterval(timers.current[id]); delete timers.current[id] }
      setMachines((prev) => prev.map((m) => m.id === id ? { ...m, status: '대기중' } : m))
    },
    onReset: (id) => {
      if (timers.current[id]) { clearInterval(timers.current[id]); delete timers.current[id] }
      setMachines((prev) => prev.map((m) => m.id === id
        ? { ...m, produced: 0, status: '대기중', releaseId: null, item_name: null, total: 0, started_at: null, finished_at: null } : m))
    },
    onAssign: (id, releaseId) => {
      if (timers.current[id]) { clearInterval(timers.current[id]); delete timers.current[id] }
      const rel = releases.find((r) => r.id === releaseId)
      setMachines((prev) => prev.map((m) => m.id === id ? {
        ...m, releaseId: releaseId || null,
        item_name: rel?.item_name || null,
        total: rel ? rel.release_qty : 0,
        produced: 0, status: '대기중', started_at: null, finished_at: null,
      } : m))
      setSelMachine(null)
    },
    onStatusChange: (id, st) => {
      if (timers.current[id]) { clearInterval(timers.current[id]); delete timers.current[id] }
      setMachines((prev) => prev.map((m) => m.id === id ? { ...m, status: st, releaseId: st === '점검중' ? null : m.releaseId } : m))
      setSelMachine(null)
    },
    onSelectToggle: (id) => setSelMachine((prev) => prev === id ? null : id),
  }

  const fetchReleases = async () => {
    const res = await getReleases()
    setReleases(res.data.filter((r) => r.status === '생산중'))
  }
  useEffect(() => { fetchReleases() }, [])

  const toggleOne = (id) => setChecked((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  const toggleAll = () => { if (checked.size === filtered.length) setChecked(new Set()); else setChecked(new Set(filtered.map((r) => r.id))) }
  const handleDelete = async () => {
    if (checked.size === 0) return
    if (!confirm(`선택한 ${checked.size}건을 삭제하시겠습니까?`)) return
    setDeleting(true)
    try { await deleteReleasesBulk([...checked]); setChecked(new Set()); fetchReleases() }
    catch (err) { alert(err.response?.data?.detail || '삭제 실패') }
    finally { setDeleting(false) }
  }

  const getItemName = () => `${form.item_type}_${form.item_color}`

  const handleValidate = async () => {
    const name = getItemName()
    try { const res = await validateItem(name); setValidation(res.data) }
    catch { setValidation({ valid: false, message: '서버 오류' }) }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await createRelease({ item_name: getItemName(), release_qty: Number(form.release_qty), due_date: form.due_date })
      setForm({ item_type: 'WOOD', item_color: 'BR', release_qty: '', due_date: '' })
      setValidation(null); setShowForm(false); fetchReleases()
    } catch (err) { alert(err.response?.data?.detail || '등록 실패') }
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]; if (!file) return
    setUploadResult(null)
    const reader = new FileReader()
    reader.onload = (evt) => {
      const wb  = XLSX.read(evt.target.result, { type: 'array', cellDates: true })
      const ws  = wb.Sheets[wb.SheetNames[0]]
      const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
      const rows = raw.slice(1).filter((r) => r.some((c) => c !== '')).map((r) => ({
        item_name:   parseExcelItemName(r[0], r[1]),
        release_qty: r[2],
        due_date:    excelDateToISO(r[3]),
      }))
      setPreviewRows(rows); setExcelErrors(rows.flatMap((row, i) => validateRow(row, i)))
    }
    reader.readAsArrayBuffer(file)
  }

  const handleUpload = async () => {
    if (excelErrors.length > 0 || previewRows.length === 0) return
    setUploading(true)
    let success = 0; const failDetails = []
    for (const [i, row] of previewRows.entries()) {
      try { await createRelease({ ...row, release_qty: Number(row.release_qty) }); success++ }
      catch (err) { failDetails.push(`${i+1}행 (${row.item_name}): ${err.response?.data?.detail || err.message}`) }
    }
    setUploading(false)
    setUploadResult({ success, fail: failDetails.length, failDetails })
    if (failDetails.length === 0) { setPreviewRows([]); setExcelErrors([]); if (fileRef.current) fileRef.current.value = '' }
    fetchReleases()
  }

  const handleExcelClose = () => {
    setShowExcel(false); setPreviewRows([]); setExcelErrors([]); setUploadResult(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const filtered = searched ? releases.filter((r) => inRange(r.due_date, searched)) : releases

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">
          지퍼/단추 생산
          {searched && <span className="ml-2 text-xs text-blue-500 font-normal">납기일 기준 필터 적용중</span>}
        </h3>
        <div className="flex gap-2">
          <button onClick={() => { setShowExcel(!showExcel); setShowForm(false) }}
            className={`text-sm px-4 py-1.5 rounded border transition-colors ${showExcel ? 'bg-green-600 text-white border-green-600' : 'bg-white text-green-700 border-green-400 hover:bg-green-50'}`}>
            📂 엑셀 업로드
          </button>
          <button onClick={() => { setShowForm(!showForm); setShowExcel(false) }}
            className="text-sm bg-green-600 text-white px-4 py-1.5 rounded hover:bg-green-700">
            + 생산 등록
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-50 border rounded p-4 space-y-4 text-sm">
          <div className="grid grid-cols-4 gap-3">
            {/* 품목 */}
            <div>
              <label className="text-xs text-gray-500">품목</label>
              <select value={form.item_type}
                onChange={(e) => {
                  const t = e.target.value
                  setForm({ ...form, item_type: t, item_color: COLOR_OPTIONS[t][0].code })
                  setValidation(null)
                }}
                className="w-full border rounded px-2 py-1.5 mt-1 text-sm">
                {ITEM_TYPES.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
              </select>
            </div>
            {/* 컬러 / 사이즈 */}
            <div>
              <label className="text-xs text-gray-500">
                {form.item_type === 'ZIPPER' ? '사이즈' : '컬러'}
              </label>
              <div className="flex gap-1 mt-1">
                <select value={form.item_color}
                  onChange={(e) => { setForm({ ...form, item_color: e.target.value }); setValidation(null) }}
                  className="flex-1 border rounded px-2 py-1.5 text-sm">
                  {COLOR_OPTIONS[form.item_type].map((c) => (
                    <option key={c.code} value={c.code}>{c.label}</option>
                  ))}
                </select>
                <button type="button" onClick={handleValidate}
                  className="text-xs bg-gray-200 px-2 rounded hover:bg-gray-300">검증</button>
              </div>
              {validation && (
                <p className={`text-xs mt-1 ${validation.valid ? 'text-green-600' : 'text-red-600'}`}>
                  {validation.message}
                </p>
              )}
              <p className="text-xs text-gray-400 mt-0.5 font-mono">{getItemName()}</p>
            </div>
            {/* 주문량 */}
            <div>
              <label className="text-xs text-gray-500">주문량 (개)</label>
              <input type="number" required value={form.release_qty}
                onChange={(e) => setForm({ ...form, release_qty: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" placeholder="수량" />
            </div>
            {/* 납기일 */}
            <div>
              <label className="text-xs text-gray-500">납기일</label>
              <input type="date" required value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => { setShowForm(false); setValidation(null) }} className="text-xs text-gray-500 hover:underline">취소</button>
            <button type="submit" className="text-xs bg-green-600 text-white px-4 py-1.5 rounded hover:bg-green-700">등록</button>
          </div>
        </form>
      )}

      {showExcel && (
        <div className="border rounded p-4 bg-gray-50 space-y-4 text-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium text-gray-700 mb-1">엑셀 일괄 생산 등록</p>
              <div className="text-xs text-gray-400 space-y-0.5 mt-1">
                <p>• 품목코드: WOOD_BR / PLASTIC_BK / METAL_SV / ZIPPER_M 등</p>
                <p>• 납기일: YYYY-MM-DD 형식</p>
              </div>
            </div>
            <button onClick={downloadTemplate} className="text-xs bg-white border border-gray-300 text-gray-600 px-3 py-2 rounded hover:bg-gray-100 whitespace-nowrap">
              ⬇ 양식 다운로드
            </button>
          </div>
          <div className="flex items-center gap-3">
            <label className="cursor-pointer bg-white border border-dashed border-gray-400 rounded px-4 py-2 text-xs text-gray-500 hover:bg-gray-50 hover:border-green-400 transition-colors">
              📄 파일 선택 (.xlsx, .xls)
              <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFileChange} />
            </label>
            {previewRows.length > 0 && <span className="text-xs text-green-600">{previewRows.length}행 인식됨</span>}
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
                    <tr>{['품목','컬러/사이즈','주문량','납기일'].map((h) => <th key={h} className="px-3 py-1.5 border text-gray-600 text-left">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {previewRows.map((r, i) => {
                      const [type, color] = r.item_name.split('_')
                      return (
                        <tr key={i} className="hover:bg-gray-50">
                          <td className="px-3 py-1.5 border font-semibold">{getItemType(r.item_name)}</td>
                          <td className="px-3 py-1.5 border text-gray-600">{color}</td>
                          <td className="px-3 py-1.5 border">{Number(r.release_qty).toLocaleString()}개</td>
                          <td className="px-3 py-1.5 border">{r.due_date}</td>
                        </tr>
                      )
                    })}
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

      {/* 생산중 목록 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-600">생산중 목록 ({filtered.length}건)</p>
          {checked.size > 0 && (
            <button onClick={handleDelete} disabled={deleting}
              className="text-sm bg-red-500 text-white px-4 py-1.5 rounded hover:bg-red-600 disabled:opacity-50">
              {deleting ? '삭제 중...' : `선택 삭제 (${checked.size}건)`}
            </button>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 text-gray-600 text-left">
                <th className="px-3 py-2 border w-10"><input type="checkbox" checked={filtered.length > 0 && checked.size === filtered.length} onChange={toggleAll} /></th>
                <th className="px-4 py-2 border">품목</th>
                <th className="px-4 py-2 border">컬러/사이즈</th>
                <th className="px-4 py-2 border">주문량</th>
                <th className="px-4 py-2 border">납기일</th>
                <th className="px-4 py-2 border">D-day</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan={6} className="px-4 py-4 text-center text-gray-400">생산중인 주문 없음</td></tr>}
              {filtered.map((r) => {
                const d = Math.ceil((new Date(r.due_date) - new Date(today())) / 86400000)
                const mach = machines.find((m) => m.releaseId === r.id)
                const produced = mach ? Math.floor(mach.produced) : 0
                const pct = r.release_qty > 0 ? Math.min((produced / r.release_qty) * 100, 100) : 0
                return (
                  <tr key={r.id} onClick={() => toggleOne(r.id)}
                    className={`cursor-pointer hover:bg-gray-50 ${checked.has(r.id) ? 'bg-red-50' : ''}`}>
                    <td className="px-3 py-2 border text-center">
                      <input type="checkbox" checked={checked.has(r.id)} onChange={() => toggleOne(r.id)} onClick={(e) => e.stopPropagation()} />
                    </td>
                    <td className="px-4 py-2 border font-semibold">{getItemType(r.item_name)}</td>
                    <td className="px-4 py-2 border text-gray-600 text-xs">{getItemLabel(r.item_name).split(/[\/()]/).pop()?.trim() || r.item_name}</td>
                    <td className="px-4 py-2 border">
                      <div className="space-y-1">
                        <span className={mach?.status === '가동중' ? 'text-green-700 font-semibold' : 'text-gray-700'}>
                          {produced.toLocaleString()} / {r.release_qty.toLocaleString()}개
                        </span>
                        {mach && mach.total > 0 && (
                          <div className="w-full bg-gray-200 rounded-full h-1.5">
                            <div className={`h-1.5 rounded-full ${mach.status === '완료' ? 'bg-blue-500' : 'bg-green-500'}`} style={{ width: `${pct}%` }} />
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2 border">{r.due_date}</td>
                    <td className="px-4 py-2 border">
                      <span className={`font-bold text-xs px-2 py-0.5 rounded-full ${d < 2 ? 'bg-red-100 text-red-700' : d < 5 ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>
                        D-{d}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 기계 배치 */}
      <div className="border rounded-xl p-5 bg-gray-50">
        <MachineLayout
          machines={machines}
          releases={filtered}
          selected={selMachine}
          {...machineHandlers}
        />
      </div>
    </div>
  )
}
