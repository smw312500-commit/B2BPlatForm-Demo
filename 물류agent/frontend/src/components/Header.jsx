import React, { useState, useEffect } from 'react';

export default function Header({ activeTab, setActiveTab }) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const tabs = ['기사관리', '화물관리/배차관리', '기타'];

  const dateStr = now.toLocaleDateString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short',
  });
  const timeStr = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  return (
    <div className="bg-gray-800 text-white">
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-700">
        <h1 className="text-xl font-bold tracking-wide">물류 Agent</h1>
        <span className="text-sm text-gray-300">{dateStr} {timeStr}</span>
      </div>
      <div className="flex px-6">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-blue-400 text-blue-300'
                : 'border-transparent text-gray-400 hover:text-white'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>
    </div>
  );
}
