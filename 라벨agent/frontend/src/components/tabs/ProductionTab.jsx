import { useEffect, useRef, useState } from 'react'
import * as XLSX from 'xlsx'
import {
  createRelease,
  deleteReleasesBulk,
  getAgentStatus,
  getMachines,
  getReleases,
  machineAction,
  validateLabelCode,
} from '../../services/api'
import MachineLayout from '../MachineLayout'

function today() { return new Date().toISOString().split('T')[0] }

function inRange(dateStr, searched) {
  if (!searched || !dateStr) return true
  const d = new Date(dateStr)
  return d >= new Date(searched.from) && d <= new Date(searched.to + 'T23:59:59')
}

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
    const cleaned = val.replace(/\//g, '-').trim()
    if (/^\d{4}-\d{2}-\d{2}$/.test(cleaned)) return cleaned
  }
  return null
}

const BRAND = new Set(['W'])
const SEASON = new Set(['1','2','3','4'])
const GENDER = new Set(['W','M'])
const ITEM = new Set(['T','P','J','D'])
const FABRIC = new Set(['C','P','L','W','M'])
const COLOR = new Set(['BK','WH','NV','GY','BE','RD'])

function validateCode(code) {
  if (!code || code.length !== 9) return '9자리가 아님'
  if (!BRAND.has(code[0])) return `브랜드코드 오류: ${code[0]}`
  if (!SEASON.has(code[1])) return `계절코드 오류: ${code[1]}`
  if (!GENDER.has(code[2])) return `성별코드 오류: ${code[2]}`
  if (!ITEM.has(code[3])) return `품목코드 오류: ${code[3]}`
  if (!FABRIC.has(code[4])) return `원단코드 오류: ${code[4]}`
  if (!/^\d{2}$/.test(code.slice(5,7))) return `스타일번호 오류: ${code.slice(5,7)}`
  if (!COLOR.has(code.slice(7,9))) return `컬러코드 오류: ${code.slice(7,9)}`
  return null
}

function validateRow(row, idx) {
  const errors = []
  const codeErr = validateCode(row.label_code)
  if (codeErr) errors.push(`${idx+1}행: 라벨코드 ${codeErr}`)
  if (!row.release_qty || isNaN(Number(row.release_qty)) || Number(row.release_qty) <= 0) {
    errors.push(`${idx+1}행: 주문량이 올바르지 않습니다`)
  }
  if (!row.due_date) errors.push(`${idx+1}행: 납기일 형식 오류 (YYYY-MM-DD)`)
  return errors
}

function downloadTemplate() {
  const ws = XLSX.utils.aoa_to_sheet([
    ['라벨코드', '주문량(장)', '납기일'],
    ['W3MJW01NV', 5000, '2026-06-10'],
    ['W1WTC01BK', 3000, '2026-06-15'],
  ])
  ws['!cols'] = [{ wch: 14 }, { wch: 12 }, { wch: 14 }]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '생산등록')
  XLSX.writeFile(wb, '생산등록_양식.xlsx')
}

const SPEED = 800 / 3600

function getApplicableRecommendationPlans(recommendations = []) {
  return recommendations
    .filter((item) => item.apply_required)
    .filter((item) => {
      const releaseIds = item.apply_release_ids || []
      return releaseIds.length > 0 || (item.queue_release_ids || []).length > 0
    })
}

function advanceMachine(machine) {
  if (machine.status !== '가동중' || !machine.running_started_at || machine.total_qty <= 0) return machine
  const next = Math.min(Number(machine.produced_qty) + SPEED, machine.total_qty)
  if (next >= machine.total_qty) {
    return {
      ...machine,
      produced_qty: machine.total_qty,
      remaining_qty: 0,
      status: '완료',
      running_started_at: null,
      finished_at: new Date().toISOString(),
      estimated_completion_at: new Date().toISOString(),
    }
  }
  return {
    ...machine,
    produced_qty: next,
    remaining_qty: Math.max(machine.total_qty - next, 0),
  }
}

export default function ProductionTab({ searched, onAgentStatusSync }) {
  const [releases, setReleases] = useState([])
  const [machines, setMachines] = useState([])
  const [agentStatus, setAgentStatus] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [showExcel, setShowExcel] = useState(false)
  const [form, setForm] = useState({ label_code: '', release_qty: '', due_date: '' })
  const [validation, setValidation] = useState(null)
  const [previewRows, setPreviewRows] = useState([])
  const [excelErrors, setExcelErrors] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [checked, setChecked] = useState(new Set())
  const [deleting, setDeleting] = useState(false)
  const [selMachine, setSelMachine] = useState(null)
  const [machineBusy, setMachineBusy] = useState(false)
  const fileRef = useRef(null)
  const autoCompletingRef = useRef(new Set())

  const fetchAll = async () => {
    const [releaseRes, machineRes, statusRes] = await Promise.all([
      getReleases(),
      getMachines(),
      getAgentStatus(),
    ])
    setReleases(releaseRes.data.filter((r) => r.status === '생산중'))
    setMachines(machineRes.data)
    setAgentStatus(statusRes.data)
    onAgentStatusSync?.(statusRes.data)
  }

  const syncSnapshotToState = (snapshot) => {
    setReleases(snapshot.releases)
    setMachines(snapshot.machines)
    setAgentStatus(snapshot.agentStatus)
    onAgentStatusSync?.(snapshot.agentStatus)
  }

  const fetchAllSnapshot = async () => {
    const [releaseRes, machineRes, statusRes] = await Promise.all([
      getReleases(),
      getMachines(),
      getAgentStatus(),
    ])

    return {
      releases: releaseRes.data.filter((r) => !r.finished_at),
      machines: machineRes.data,
      agentStatus: statusRes.data,
    }
  }

  useEffect(() => {
    fetchAll()
  }, [])

  useEffect(() => {
    const timer = setInterval(() => {
      setMachines((prev) => prev.map(advanceMachine))
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (machineBusy) {
      return
    }

    const activeKeys = new Set()
    let pendingMachine = null

    machines.forEach((machine) => {
      const completionKey = `${machine.id}:${machine.release_id}`
      if (machine.status === '완료' && machine.release_id && machine.total_qty > 0) {
        activeKeys.add(completionKey)
        if (!pendingMachine && !autoCompletingRef.current.has(completionKey)) {
          autoCompletingRef.current.add(completionKey)
          pendingMachine = machine
        }
      }
    })

    autoCompletingRef.current.forEach((key) => {
      if (!activeKeys.has(key)) {
        autoCompletingRef.current.delete(key)
      }
    })

    if (pendingMachine) {
      runMachineAction(pendingMachine.id, { action: 'complete' })
    }
  }, [machineBusy, machines])

  const filtered = searched ? releases.filter((r) => inRange(r.due_date, searched)) : releases

  const toggleOne = (id) => setChecked((prev) => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })

  const toggleAll = () => {
    if (checked.size === filtered.length) setChecked(new Set())
    else setChecked(new Set(filtered.map((r) => r.id)))
  }

  const handleDelete = async () => {
    if (checked.size === 0) return
    if (!confirm(`선택한 ${checked.size}건을 삭제하시겠습니까?`)) return
    setDeleting(true)
    try {
      await deleteReleasesBulk([...checked])
      setChecked(new Set())
      await fetchAll()
    } catch (err) {
      alert(err.response?.data?.detail || '삭제 실패')
    } finally {
      setDeleting(false)
    }
  }

  const handleValidate = async () => {
    if (!form.label_code) return
    try {
      const res = await validateLabelCode(form.label_code)
      setValidation(res.data)
    } catch {
      setValidation({ valid: false, message: '서버 오류' })
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await createRelease({ ...form, release_qty: Number(form.release_qty) })
      setForm({ label_code: '', release_qty: '', due_date: '' })
      setValidation(null)
      setShowForm(false)
      await fetchAll()
    } catch (err) {
      alert(err.response?.data?.detail || '등록 실패')
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploadResult(null)
    const reader = new FileReader()
    reader.onload = (evt) => {
      const wb = XLSX.read(evt.target.result, { type: 'array', cellDates: true })
      const ws = wb.Sheets[wb.SheetNames[0]]
      const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
      const dataRows = raw.slice(1).filter((r) => r.some((c) => c !== ''))
      const rows = dataRows.map((r) => ({
        label_code: String(r[0] ?? '').trim().toUpperCase(),
        release_qty: r[1],
        due_date: excelDateToISO(r[2]),
      }))
      const errors = rows.flatMap((row, i) => validateRow(row, i))
      setPreviewRows(rows)
      setExcelErrors(errors)
    }
    reader.readAsArrayBuffer(file)
  }

  const handleUpload = async () => {
    if (excelErrors.length > 0 || previewRows.length === 0) return
    setUploading(true)
    let success = 0
    const failDetails = []
    for (const [i, row] of previewRows.entries()) {
      try {
        await createRelease({ ...row, release_qty: Number(row.release_qty) })
        success++
      } catch (err) {
        const msg = err.response?.data?.detail || err.message || '알 수 없는 오류'
        failDetails.push(`${i+1}행 (${row.label_code}): ${msg}`)
      }
    }
    setUploading(false)
    setUploadResult({ success, fail: failDetails.length, failDetails })
    if (failDetails.length === 0) {
      setPreviewRows([])
      setExcelErrors([])
      if (fileRef.current) fileRef.current.value = ''
    }
    await fetchAll()
  }

  const handleExcelClose = () => {
    setShowExcel(false)
    setPreviewRows([])
    setExcelErrors([])
    setUploadResult(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const runMachineAction = async (id, payload) => {
    setMachineBusy(true)
    try {
      await machineAction(id, payload)
      await fetchAll()
    } catch (err) {
      alert(err.response?.data?.detail || '기계 상태 변경 실패')
    } finally {
      setMachineBusy(false)
    }
  }

  const machineHandlers = {
    onStart: (id) => runMachineAction(id, { action: 'start' }),
    onStop: (id) => runMachineAction(id, { action: 'stop' }),
    onComplete: (id) => runMachineAction(id, { action: 'complete' }),
    onAssign: (id, releaseId) => runMachineAction(id, {
      action: 'assign',
      release_id: releaseId ? Number(releaseId) : null,
    }),
    onStatusChange: (id, st) => runMachineAction(id, { action: 'status_change', status: st }),
    onSelectToggle: (id) => setSelMachine((prev) => (prev === id ? null : id)),
  }

  const machineRecommendations = agentStatus?.machine_recommendations || []
  const applicableRecommendations = machineRecommendations.filter((item) => {
    if (!item.recommended_release_id) return false
    if (item.machine_status !== '대기중') return false
    const machine = machines.find((m) => m.id === item.machine_id)
    if (!machine) return false
    return machine.release_id !== item.recommended_release_id
  })

  const applyRecommendedAssignments = async () => {
    if (applicableRecommendations.length === 0) return
    setMachineBusy(true)
    try {
      await Promise.all(
        applicableRecommendations.map((item) =>
          machineAction(item.machine_id, {
            action: 'assign',
            release_id: item.recommended_release_id,
          })
        )
      )
      await fetchAll()
    } catch (err) {
      alert(err.response?.data?.detail || '기계배정 적용 실패')
    } finally {
      setMachineBusy(false)
    }
  }

  const applicableRecommendationPlans = machineRecommendations
    .filter((item) => item.apply_required)
    .filter((item) => {
      const releaseIds = item.apply_release_ids || []
      return releaseIds.length > 0 || (item.queue_release_ids || []).length > 0
    })

  const applyRecommendedAssignmentPlans = async () => {
    if (applicableRecommendationPlans.length === 0) return
    setMachineBusy(true)
    try {
      for (const item of applicableRecommendationPlans) {
        await machineAction(item.machine_id, {
          action: 'apply_plan',
          release_ids: item.apply_release_ids || [],
        })
      }
      await fetchAll()
    } catch (err) {
      alert(err.response?.data?.detail || '湲곌퀎諛곗젙 ?곸슜 ?ㅽ뙣')
    } finally {
      setMachineBusy(false)
    }
  }

  const handleAutoAssign = async () => {
    setMachineBusy(true)
    try {
      const snapshot = await fetchAllSnapshot()
      syncSnapshotToState(snapshot)

      const freshPlans = getApplicableRecommendationPlans(
        snapshot.agentStatus?.machine_recommendations || []
      )

      if (freshPlans.length === 0) {
        alert('?꾩옱 ?곹깭湲곗?濡?異붽? 諛곗젙???놁뒿?덈떎.')
        return
      }

      for (const item of freshPlans) {
        await machineAction(item.machine_id, {
          action: 'apply_plan',
          release_ids: item.apply_release_ids || [],
        })
      }

      await fetchAll()
    } catch (err) {
      alert(err.response?.data?.detail || '?먮룞諛곗꽕 ?ㅽ뙣')
    } finally {
      setMachineBusy(false)
    }
  }

  const findReleaseAssignment = (releaseId) => {
    for (const machine of machines) {
      if (machine.release_id === releaseId) {
        return {
          machine,
          isCurrent: true,
          queueSequence: null,
        }
      }

      const queueIndex = (machine.queue_items || []).findIndex((item) => item.release_id === releaseId)
      if (queueIndex >= 0) {
        return {
          machine: {
            ...machine,
            status: `대기열 ${queueIndex + 1}순위`,
            total_qty: 0,
            produced_qty: 0,
          },
          isCurrent: false,
          queueSequence: queueIndex + 1,
        }
      }
    }

    return null
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">
          라벨 생산
          {searched && <span className="ml-2 text-xs text-blue-500 font-normal">납기일 기준 필터 적용중</span>}
        </h3>
        <div className="flex gap-2">
          <button onClick={() => { setShowExcel(!showExcel); setShowForm(false) }}
            className={`text-sm px-4 py-1.5 rounded border transition-colors ${
              showExcel ? 'bg-green-600 text-white border-green-600' : 'bg-white text-green-700 border-green-400 hover:bg-green-50'
            }`}>
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
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-500">라벨코드 (9자리)</label>
              <div className="flex gap-1 mt-1">
                <input type="text" required maxLength={9} value={form.label_code}
                  onChange={(e) => { setForm({ ...form, label_code: e.target.value.toUpperCase() }); setValidation(null) }}
                  className="flex-1 border rounded px-2 py-1.5 font-mono uppercase" placeholder="W3MJW01NV" />
                <button type="button" onClick={handleValidate}
                  className="text-xs bg-gray-200 px-2 rounded hover:bg-gray-300">검증</button>
              </div>
              {validation && (
                <p className={`text-xs mt-1 ${validation.valid ? 'text-green-600' : 'text-red-600'}`}>
                  {validation.valid ? '✅ ' : '❌ '}{validation.message}
                </p>
              )}
            </div>
            <div>
              <label className="text-xs text-gray-500">주문량 (장)</label>
              <input type="number" required value={form.release_qty}
                onChange={(e) => setForm({ ...form, release_qty: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" placeholder="수량" />
            </div>
            <div>
              <label className="text-xs text-gray-500">납기일</label>
              <input type="date" required value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                className="w-full border rounded px-2 py-1.5 mt-1" />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => { setShowForm(false); setValidation(null) }}
              className="text-xs text-gray-500 hover:underline">취소</button>
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
                <p>• 라벨코드: <span className="font-mono font-medium text-gray-600">9자리</span> (예: W3MJW01NV)</p>
                <p>• 주문량: 숫자 (장)</p>
                <p>• 납기일: <span className="font-medium text-gray-600">YYYY-MM-DD</span> 형식</p>
              </div>
            </div>
            <button onClick={downloadTemplate}
              className="text-xs bg-white border border-gray-300 text-gray-600 px-3 py-2 rounded hover:bg-gray-100 whitespace-nowrap">
              ⬇ 양식 다운로드
            </button>
          </div>

          <div className="flex items-center gap-3">
            <label className="cursor-pointer bg-white border border-dashed border-gray-400 rounded px-4 py-2 text-xs text-gray-500 hover:bg-gray-50 hover:border-green-400 transition-colors">
              📄 파일 선택 (.xlsx, .xls)
              <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFileChange} />
            </label>
            {previewRows.length > 0 && (
              <span className="text-xs text-green-600">{previewRows.length}행 인식됨</span>
            )}
          </div>

          {excelErrors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded p-3 space-y-1">
              <p className="text-xs font-semibold text-red-700">❌ 아래 오류를 수정 후 다시 업로드하세요</p>
              {excelErrors.map((e, i) => <p key={i} className="text-xs text-red-600">{e}</p>)}
            </div>
          )}

          {previewRows.length > 0 && excelErrors.length === 0 && (
            <div>
              <p className="text-xs font-medium text-gray-600 mb-2">미리보기 (총 {previewRows.length}건)</p>
              <div className="overflow-x-auto max-h-48 overflow-y-auto border rounded">
                <table className="w-full text-xs border-collapse">
                  <thead className="sticky top-0 bg-gray-100">
                    <tr>
                      {['라벨코드', '주문량', '납기일'].map((h) => (
                        <th key={h} className="px-3 py-1.5 border text-gray-600 text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewRows.map((r, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-1.5 border font-mono font-semibold">{r.label_code}</td>
                        <td className="px-3 py-1.5 border">{Number(r.release_qty).toLocaleString()}장</td>
                        <td className="px-3 py-1.5 border">{r.due_date}</td>
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
            <button onClick={handleUpload}
              disabled={uploading || previewRows.length === 0 || excelErrors.length > 0}
              className="text-xs bg-green-600 text-white px-4 py-1.5 rounded hover:bg-green-700 disabled:opacity-40">
              {uploading ? '업로드 중...' : `${previewRows.length}건 업로드`}
            </button>
          </div>
        </div>
      )}

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
                <th className="px-3 py-2 border w-10">
                  <input type="checkbox"
                    checked={filtered.length > 0 && checked.size === filtered.length}
                    onChange={toggleAll} className="cursor-pointer" />
                </th>
                <th className="px-4 py-2 border">라벨코드</th>
                <th className="px-4 py-2 border">주문량</th>
                <th className="px-4 py-2 border">납기일</th>
                <th className="px-4 py-2 border">D-day</th>
                <th className="px-4 py-2 border">배정 기계</th>
                <th className="px-4 py-2 border">시작 시간</th>
                <th className="px-4 py-2 border">완료 시간</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-4 text-center text-gray-400">생산중인 주문 없음</td></tr>
              )}
              {filtered.map((r) => {
                const d = Math.ceil((new Date(r.due_date) - new Date(today())) / 86400000)
                const assignment = findReleaseAssignment(r.id)
                const mach = assignment?.machine || null
                const isCurrentMachineJob = assignment?.isCurrent || false
                const produced = isCurrentMachineJob && mach ? Math.floor(mach.produced_qty) : 0
                const total = r.release_qty
                const pct = total > 0 ? Math.min((produced / total) * 100, 100) : 0
                return (
                  <tr key={r.id} onClick={() => toggleOne(r.id)}
                    className={`cursor-pointer hover:bg-gray-50 ${checked.has(r.id) ? 'bg-red-50' : ''}`}>
                    <td className="px-3 py-2 border text-center">
                      <input type="checkbox" checked={checked.has(r.id)} onChange={() => toggleOne(r.id)}
                        onClick={(e) => e.stopPropagation()} className="cursor-pointer" />
                    </td>
                    <td className="px-4 py-2 border font-mono font-semibold">{r.label_code}</td>
                    <td className="px-4 py-2 border">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm">
                          <span className={mach?.status === '가동중' ? 'text-green-700 font-semibold' : 'text-gray-700'}>
                            {produced.toLocaleString()} / {total.toLocaleString()}장
                          </span>
                        </div>
                        {mach && mach.total_qty > 0 && (
                          <div className="w-full bg-gray-200 rounded-full h-1.5">
                            <div className={`h-1.5 rounded-full ${mach.status === '완료' ? 'bg-blue-500' : 'bg-green-500'}`}
                              style={{ width: `${pct}%` }} />
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2 border">{r.due_date}</td>
                    <td className="px-4 py-2 border">
                      <span className={`font-bold text-xs px-2 py-0.5 rounded-full ${
                        d < 2 ? 'bg-red-100 text-red-700' : d < 5 ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'
                      }`}>D-{d}</span>
                    </td>
                    <td className="px-4 py-2 border text-xs">
                      {mach ? (
                        <div className="space-y-0.5">
                          <p className="font-medium text-gray-700">{mach.name}</p>
                          <p className="text-gray-500">{mach.status}</p>
                        </div>
                      ) : <span className="text-gray-400">미배정</span>}
                    </td>
                    <td className="px-4 py-2 border text-xs text-gray-500">
                      {r.started_at ? new Date(r.started_at).toLocaleString('ko-KR') : '-'}
                    </td>
                    <td className="px-4 py-2 border text-xs">
                      {r.finished_at
                        ? <span className="text-blue-600 font-medium">{new Date(r.finished_at).toLocaleString('ko-KR')}</span>
                        : <span className="text-gray-400">-</span>
                      }
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border rounded-xl p-5 bg-gray-50 space-y-4">
        <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3">
          <p className="text-sm font-semibold text-blue-900 mb-2">오늘 기계배정 추천</p>
          {machineRecommendations.length === 0 ? (
            <p className="text-xs text-blue-700">추천할 기계 배정이 없습니다.</p>
          ) : (
            <div className="space-y-1.5">
              {machineRecommendations.map((item) => (
                <p key={item.machine_id} className="text-xs text-blue-900">{item.summary}</p>
              ))}
            </div>
          )}
          <p className="text-[11px] text-blue-500 mt-2">자동 갱신 없음 · 생산 등록/기계 조작 후에만 서버 상태를 다시 조회합니다.</p>
        </div>

        <MachineLayout
          machines={machines}
          releases={filtered}
          selected={selMachine}
          recommendations={machineRecommendations}
          busy={machineBusy}
          onAutoAssign={handleAutoAssign}
          canAutoAssign={releases.length > 0}
          onApplyRecommendations={applyRecommendedAssignmentPlans}
          canApplyRecommendations={applicableRecommendationPlans.length > 0}
          {...machineHandlers}
        />
      </div>
    </div>
  )
}
