export default function Header() {
  return (
    <header className="bg-gradient-to-r from-blue-700 to-blue-900 text-white px-6 py-3 flex items-center justify-between shadow-md">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center text-lg">⬡</div>
        <div>
          <h1 className="text-base font-bold leading-tight">B2B 플랫폼 에이전트</h1>
          <p className="text-xs text-blue-200">부자재 공급망 통합 관리 시스템</p>
        </div>
      </div>
      <div className="text-xs text-blue-200">PORT 8000 · 5174</div>
    </header>
  )
}
