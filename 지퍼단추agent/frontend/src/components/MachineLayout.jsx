// MachineLayout - props 기반 (state는 ProductionTab에서 관리)
const STATUS = {
  가동중: { bg: 'bg-green-100', border: 'border-green-400', dot: 'bg-green-500', text: 'text-green-700', badge: 'bg-green-500' },
  대기중: { bg: 'bg-gray-100',  border: 'border-gray-300',  dot: 'bg-gray-400',  text: 'text-gray-500',  badge: 'bg-gray-400'  },
  점검중: { bg: 'bg-red-100',   border: 'border-red-400',   dot: 'bg-red-500',   text: 'text-red-700',   badge: 'bg-red-500'   },
  완료:   { bg: 'bg-blue-100',  border: 'border-blue-400',  dot: 'bg-blue-500',  text: 'text-blue-700',  badge: 'bg-blue-500'  },
}

// 품목 타입 → 예상 잔여시간 계산용 속도 (개/초)
const SPEED_PER_SEC = {
  원목단추:     (20 * 2) / 3600,
  플라스틱단추: (300 * 2) / 3600,
  금속단추:     (150 * 2) / 3600,
  지퍼:         (200 * 2) / 3600,
}

function fmtDateTime(d) {
  if (!d) return '-'
  return new Date(d).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function MachineLayout({ machines, releases = [], selected, onSelectToggle, onStart, onStop, onReset, onAssign, onStatusChange }) {
  const activeCount  = machines.filter((m) => m.status === '가동중').length
  const standbyCount = machines.filter((m) => m.status === '대기중').length
  const repairCount  = machines.filter((m) => m.status === '점검중').length
  const doneCount    = machines.filter((m) => m.status === '완료').length

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-semibold text-gray-700">기계 현황</span>
        {activeCount  > 0 && <span className="text-xs bg-green-100 text-green-700 px-2.5 py-1 rounded-full font-medium">가동 {activeCount}대</span>}
        {standbyCount > 0 && <span className="text-xs bg-gray-100 text-gray-500 px-2.5 py-1 rounded-full font-medium">대기 {standbyCount}대</span>}
        {repairCount  > 0 && <span className="text-xs bg-red-100 text-red-700 px-2.5 py-1 rounded-full font-medium">점검 {repairCount}대</span>}
        {doneCount    > 0 && <span className="text-xs bg-blue-100 text-blue-700 px-2.5 py-1 rounded-full font-medium">완료 {doneCount}대</span>}
        <span className="text-xs text-gray-400 ml-auto">기계 클릭 → 작업 설정</span>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {machines.map((m) => {
          const s      = STATUS[m.status] ?? STATUS['대기중']
          const isOpen = selected === m.id
          const pct    = m.total > 0 ? Math.min((m.produced / m.total) * 100, 100) : 0
          const running = m.status === '가동중'
          const done    = m.status === '완료'
          const speed   = SPEED_PER_SEC[m.itemType] ?? 1
          const remaining = running && m.total > m.produced ? ((m.total - m.produced) / speed / 3600).toFixed(1) : null

          return (
            <div key={m.id} className="relative">
              <div className={`rounded-xl border-2 ${s.border} ${s.bg} p-4 transition-all ${running ? 'shadow-md' : ''}`}>

                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-gray-800 truncate">{m.name}</span>
                  <span className={`w-2.5 h-2.5 rounded-full ${s.dot} ${running ? 'animate-pulse' : ''}`} />
                </div>

                <div
                  className="flex items-center justify-center h-16 rounded-lg border-2 border-inherit bg-white/70 mb-2 cursor-pointer hover:bg-white/90"
                  onClick={() => onSelectToggle(m.id)}
                >
                  <svg className={`w-10 h-10 ${running ? 'text-green-500 animate-spin' : done ? 'text-blue-400' : m.status === '점검중' ? 'text-red-400' : 'text-gray-300'}`}
                    style={running ? { animationDuration: '3s' } : {}}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="3" strokeWidth="2"/>
                    <path strokeWidth="2" strokeLinecap="round"
                      d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/>
                  </svg>
                </div>

                <div className="flex items-center gap-1.5 mb-2">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full text-white ${s.badge}`}>{m.status}</span>
                  {m.releaseId && <span className="text-xs text-indigo-600 truncate font-mono">{m.item_name}</span>}
                </div>

                {m.total > 0 ? (
                  <div className="mb-2 space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className={`font-semibold ${done ? 'text-blue-600' : 'text-gray-700'}`}>
                        {Math.floor(m.produced).toLocaleString()} / {m.total.toLocaleString()}개
                      </span>
                      <span className="text-gray-400">{pct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-white/70 rounded-full h-1.5 border border-gray-200">
                      <div className={`h-1.5 rounded-full transition-all ${done ? 'bg-blue-500' : 'bg-green-500'}`} style={{ width: `${pct}%` }} />
                    </div>
                    {remaining && <p className="text-xs text-gray-400">약 {remaining}h 남음</p>}
                    <div className="space-y-0.5">
                      {m.started_at  && <p className="text-xs text-gray-500">🕐 {fmtDateTime(m.started_at)}</p>}
                      {m.finished_at && <p className="text-xs text-blue-600 font-medium">✅ {fmtDateTime(m.finished_at)}</p>}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 mb-2">작업 없음</p>
                )}

                <div className="flex gap-1">
                  {!done && m.total > 0 && !running && (
                    <button onClick={() => onStart(m.id)} className="flex-1 text-xs bg-green-600 text-white py-1.5 rounded hover:bg-green-700">▶ 시작</button>
                  )}
                  {running && (
                    <button onClick={() => onStop(m.id)} className="flex-1 text-xs bg-yellow-500 text-white py-1.5 rounded hover:bg-yellow-600">■ 정지</button>
                  )}
                  {(done || m.produced > 0) && (
                    <button onClick={() => onReset(m.id)} className="flex-1 text-xs bg-gray-200 text-gray-600 py-1.5 rounded hover:bg-gray-300">↺</button>
                  )}
                  {m.total === 0 && !done && (
                    <button onClick={() => onSelectToggle(m.id)} className="flex-1 text-xs bg-indigo-50 text-indigo-600 py-1.5 rounded hover:bg-indigo-100 border border-indigo-200">+ 할당</button>
                  )}
                </div>
              </div>

              {isOpen && (
                <div className="absolute left-0 top-full mt-1 z-20 bg-white border border-gray-200 rounded-xl shadow-2xl p-3 w-full space-y-2">
                  <p className="text-xs font-semibold text-gray-500">상태 변경</p>
                  <div className="flex gap-1">
                    {['대기중', '점검중'].map((st) => (
                      <button key={st} onClick={() => onStatusChange(m.id, st)}
                        className={`flex-1 text-xs py-1.5 rounded border font-medium ${m.status === st ? `${STATUS[st].bg} ${STATUS[st].border} ${STATUS[st].text}` : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'}`}>
                        {st}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs font-semibold text-gray-500">작업 할당</p>
                  <select value={m.releaseId || ''} onChange={(e) => onAssign(m.id, e.target.value ? Number(e.target.value) : null)}
                    className="w-full border rounded px-2 py-1.5 text-xs">
                    <option value="">— 작업 없음 —</option>
                    {releases.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.item_name} ({r.release_qty.toLocaleString()}개)
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
