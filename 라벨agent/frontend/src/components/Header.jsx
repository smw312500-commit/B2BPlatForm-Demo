import { useEffect, useState } from 'react'

export default function Header() {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const dateStr = now.toLocaleDateString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short',
  })
  const timeStr = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <header className="bg-blue-700 text-white px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold">케어라벨회사</span>
        <span className="text-blue-200 text-sm">AI Agent 업무자동화 시스템</span>
      </div>
      <div className="text-sm text-blue-100">
        {dateStr} {timeStr}
      </div>
    </header>
  )
}
