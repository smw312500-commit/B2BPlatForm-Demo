import { useState } from 'react'
import Header from './components/Header'
import DashboardTab from './components/tabs/DashboardTab'
import DispatchTab from './components/tabs/DispatchTab'
import InsightTab from './components/tabs/InsightTab'
import ReportChannelsTab from './components/tabs/ReportChannelsTab'
import AIChatPanel from './components/AIChatPanel'

const TABS = [
  { id: 'dashboard', label: '대시보드' },
  { id: 'dispatch',  label: '배차 현황' },
  { id: 'report',    label: '보고 채널' },
  { id: 'insight',   label: 'AI 인사이트' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Header />

      {/* 탭 바 */}
      <div className="bg-white border-b border-gray-200 px-4">
        <div className="flex gap-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 본문 */}
      <div className="flex flex-1 overflow-hidden">
        <main className="flex-1 overflow-y-auto p-5">
          {activeTab === 'dashboard' && <DashboardTab />}
          {activeTab === 'dispatch'  && <DispatchTab />}
          {activeTab === 'report'    && <ReportChannelsTab />}
          {activeTab === 'insight'   && <InsightTab />}
        </main>
      </div>

      {/* AI 채팅 플로팅 버튼 */}
      <button
        onClick={() => setChatOpen(true)}
        title="AI 인사이트 채팅"
        className="fixed bottom-6 right-6 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-slate-950 text-white shadow-lg transition-all hover:bg-slate-800 hover:scale-105 active:scale-95"
      >
        <span className="text-xl">🤖</span>
      </button>

      <AIChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  )
}
