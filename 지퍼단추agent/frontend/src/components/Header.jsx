import { useEffect, useState } from 'react'

export default function Header() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const dateStr = now.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' })
  const timeStr = now.toLocaleTimeString('ko-KR')

  return (
    <header className="bg-gray-800 text-white px-6 py-3 flex items-center justify-between shadow">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold">지퍼단추사</span>
        <span className="text-xs bg-indigo-600 px-2 py-0.5 rounded-full">AI Agent</span>
      </div>
      <span className="text-sm text-gray-300 tabular-nums">{dateStr} {timeStr}</span>
    </header>
  )
}
