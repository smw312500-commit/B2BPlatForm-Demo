import React, { startTransition, useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';
import DriverTab from './pages/DriverTab';
import CargoTab from './pages/CargoTab';
import OtherTab from './pages/OtherTab';
import { getDrivers } from './api/api';

const SIDEBAR_REFRESH_EVENT = 'logistics:refresh-sidebar';

const TAB_META = {
  기사관리: {
    eyebrow: 'driver dm',
    title: '기사 DM',
    subtitle: '기사 쓰레드를 열면 AI가 배차-센터 지시를 기사용 채팅으로 전달합니다.',
  },
  '화물관리/배차관리': {
    eyebrow: 'dispatch center',
    title: '# 배차-센터',
    subtitle: '플랫폼이 생산회사 보고를 집계해 물류에 지시하며, 기사 정보와 차량 정보는 별도 DB 동기화로 전달됩니다.',
  },
  기타: {
    eyebrow: 'ops config',
    title: '운영 설정',
    subtitle: '이동시간 기준과 내부 운영 메모를 정리하는 영역입니다.',
  },
};

const TAB_LINKS = [
  { tab: '화물관리/배차관리', label: '# 배차-센터', hint: '플랫폼 ↔ 물류 지시 채널' },
  { tab: '기사관리', label: '@ 기사 DM', hint: 'AI ↔ 기사 전달 채널' },
  { tab: '기타', label: '= 운영 설정', hint: '기준값과 정책' },
];

const STATUS_TONE = {
  가용: 'bg-emerald-400',
  운행중: 'bg-sky-400',
  휴무: 'bg-slate-500',
};

function formatNow(now) {
  const date = now.toLocaleDateString('ko-KR', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  });
  const time = now.toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
  });
  return `${date} ${time}`;
}

function DriverThreadList({ drivers, selectedDriverId, onOpenDriver }) {
  return (
    <div className="min-h-0 flex-1 overflow-auto px-2 pb-3">
      <div className="mb-3 flex items-center justify-between px-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">기사 DM</span>
        <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-slate-400">{drivers.length}</span>
      </div>

      <div className="space-y-1.5">
        {drivers.map((driver) => {
          const active = selectedDriverId === driver.id;
          return (
            <button
              key={driver.id}
              onClick={() => onOpenDriver(driver.id)}
              className={`flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition ${
                active
                  ? 'bg-[#202534] text-white shadow-[0_16px_32px_rgba(0,0,0,0.24)]'
                  : 'text-slate-300 hover:bg-white/[0.04]'
              }`}
            >
              <div className="relative shrink-0">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-slate-600 to-slate-800 text-sm font-bold text-white">
                  {driver.name?.slice(0, 1) || '?'}
                </div>
                <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-[#151923] ${STATUS_TONE[driver.status] || 'bg-slate-500'}`} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{driver.name}</div>
                <div className="truncate text-xs text-slate-400">
                  {driver.location_si || driver.base_region || '위치 미등록'} · {driver.vehicle_plate || '차량 미연결'}
                </div>
              </div>
            </button>
          );
        })}

        {drivers.length === 0 && (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-sm text-slate-500">
            표시할 기사 DM이 없습니다.
          </div>
        )}
      </div>
    </div>
  );
}

function NavigationSidebar({
  activeTab,
  onSelectTab,
  drivers,
  search,
  setSearch,
  selectedDriverId,
  onOpenDriver,
}) {
  const counts = useMemo(() => ({
    available: drivers.filter((driver) => driver.status === '가용').length,
    driving: drivers.filter((driver) => driver.status === '운행중').length,
    off: drivers.filter((driver) => driver.status === '휴무').length,
  }), [drivers]);

  return (
    <aside className="flex shrink-0 flex-col overflow-hidden rounded-[28px] border border-white/10 bg-[#141923]/90 shadow-[0_24px_60px_rgba(0,0,0,0.38)] lg:w-[320px]">
      <div className="border-b border-white/[0.06] px-4 pb-4 pt-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-[0.28em] text-slate-500">logistics relay</div>
            <div className="mt-1 text-lg font-semibold text-white">물류 커뮤니케이션</div>
          </div>
          <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-[11px] font-semibold text-emerald-300">
            live
          </div>
        </div>

        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="기사 또는 차량 검색"
          className="w-full rounded-2xl border border-white/[0.08] bg-[#0d1118] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-sky-400/40"
        />
      </div>

      <div className="grid grid-cols-3 gap-2 px-4 py-4">
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-3 py-3">
          <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">가용</div>
          <div className="mt-2 text-xl font-semibold text-white">{counts.available}</div>
        </div>
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-3 py-3">
          <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">운행</div>
          <div className="mt-2 text-xl font-semibold text-white">{counts.driving}</div>
        </div>
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-3 py-3">
          <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">휴무</div>
          <div className="mt-2 text-xl font-semibold text-white">{counts.off}</div>
        </div>
      </div>

      <div className="px-2 pb-3">
        <div className="mb-2 px-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">채널</div>
        <div className="space-y-1 px-2">
          {TAB_LINKS.map((link) => (
            <button
              key={link.tab}
              onClick={() => onSelectTab(link.tab)}
              className={`flex w-full items-center justify-between gap-3 rounded-2xl px-3 py-2.5 text-left transition ${
                activeTab === link.tab
                  ? 'bg-white/[0.07] text-white'
                  : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="truncate whitespace-nowrap text-sm font-semibold">{link.label}</div>
                <div className="truncate whitespace-nowrap text-xs text-slate-500">{link.hint}</div>
              </div>
              <span className="shrink-0 text-slate-500">&gt;</span>
            </button>
          ))}
        </div>
      </div>

      <DriverThreadList drivers={drivers} selectedDriverId={selectedDriverId} onOpenDriver={onOpenDriver} />
    </aside>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState('화물관리/배차관리');
  const [selectedDriverId, setSelectedDriverId] = useState(null);
  const [drivers, setDrivers] = useState([]);
  const [search, setSearch] = useState('');
  const [now, setNow] = useState(new Date());
  const deferredSearch = useDeferredValue(search);

  const loadDrivers = useCallback(async () => {
    try {
      const response = await getDrivers();
      setDrivers(response.data || []);
    } catch {
      setDrivers([]);
    }
  }, []);

  useEffect(() => {
    loadDrivers();
    const clock = setInterval(() => setNow(new Date()), 1000);
    const reloadTimer = setInterval(loadDrivers, 30000);
    const handleRefresh = () => loadDrivers();
    window.addEventListener(SIDEBAR_REFRESH_EVENT, handleRefresh);

    return () => {
      clearInterval(clock);
      clearInterval(reloadTimer);
      window.removeEventListener(SIDEBAR_REFRESH_EVENT, handleRefresh);
    };
  }, [loadDrivers]);

  const filteredDrivers = useMemo(() => {
    const keyword = deferredSearch.trim().toLowerCase();
    const ordered = [...drivers].sort((left, right) => {
      const statusRank = { 가용: 0, 운행중: 1, 휴무: 2 };
      return (statusRank[left.status] ?? 9) - (statusRank[right.status] ?? 9);
    });

    if (!keyword) {
      return ordered;
    }

    return ordered.filter((driver) => (
      [driver.name, driver.location_si, driver.base_region, driver.phone, driver.status, driver.vehicle_plate]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(keyword))
    ));
  }, [deferredSearch, drivers]);

  const activeDriver = drivers.find((driver) => driver.id === selectedDriverId) || null;
  const meta = TAB_META[activeTab];

  const handleSelectTab = (tab) => {
    startTransition(() => {
      setActiveTab(tab);
      if (tab !== '기사관리') {
        setSelectedDriverId(null);
      }
    });
  };

  const handleOpenDriver = (driverId) => {
    startTransition(() => {
      setSelectedDriverId(driverId);
      setActiveTab('기사관리');
    });
  };

  const renderTab = () => {
    if (activeTab === '기사관리' && selectedDriverId) {
      return <CargoTab selectedDriverId={selectedDriverId} />;
    }
    if (activeTab === '기사관리') {
      return <DriverTab selectedDriverId={selectedDriverId} />;
    }
    if (activeTab === '화물관리/배차관리') {
      return <CargoTab />;
    }
    return <OtherTab />;
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.12),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(251,191,36,0.12),transparent_24%),linear-gradient(180deg,#0a0d13_0%,#0f131a_52%,#0b0e14_100%)] px-3 py-3 text-slate-100">
      <div className="flex min-h-[calc(100vh-24px)] flex-col gap-3 lg:flex-row">
        <NavigationSidebar
          activeTab={activeTab}
          onSelectTab={handleSelectTab}
          drivers={filteredDrivers}
          search={search}
          setSearch={setSearch}
          selectedDriverId={selectedDriverId}
          onOpenDriver={handleOpenDriver}
        />

        <main className="flex min-h-[520px] min-w-0 flex-1 flex-col overflow-hidden rounded-[30px] border border-white/10 bg-[#121722]/92 shadow-[0_26px_60px_rgba(0,0,0,0.4)]">
          <div className="border-b border-white/[0.06] px-5 pb-4 pt-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">{meta.eyebrow}</div>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <h1 className="text-2xl font-semibold tracking-tight text-white">{meta.title}</h1>
                  {activeDriver && (
                    <span className="rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1 text-xs font-semibold text-sky-300">
                      {activeDriver.name} 기사 채팅
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm text-slate-400">
                  {activeDriver
                    ? `${activeDriver.location_si || activeDriver.base_region || '위치 미등록'} / ${activeDriver.vehicle_plate || '차량 미연결'} / 상태 ${activeDriver.status}`
                    : meta.subtitle}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-right">
                  <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">ops clock</div>
                  <div className="mt-1 text-sm font-semibold text-white">{formatNow(now)}</div>
                </div>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-hidden">
            {renderTab()}
          </div>
        </main>
      </div>
    </div>
  );
}
