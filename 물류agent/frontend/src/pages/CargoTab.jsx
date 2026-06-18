import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  assignDriver,
  autoDispatch,
  completeDelivery,
  createDelivery,
  getAIPanel,
  getDeliveries,
  getDrivers,
  getPlatformChannel,
  getVehicles,
} from '../api/api';

const PANEL_REFRESH_EVENT = 'logistics:refresh-panel';
const SIDEBAR_REFRESH_EVENT = 'logistics:refresh-sidebar';

const STATUS_COLOR = {
  배차대기: 'bg-amber-400/[0.15] text-amber-300 ring-1 ring-amber-400/20',
  운행중: 'bg-sky-400/[0.15] text-sky-300 ring-1 ring-sky-400/20',
  완료: 'bg-emerald-400/[0.15] text-emerald-300 ring-1 ring-emerald-400/20',
};

const EMPTY_COLOR = {
  연결완료: 'text-emerald-300',
  '빈차 귀환': 'text-rose-300',
  미정: 'text-slate-500',
};

function triggerWorkspaceRefresh() {
  window.dispatchEvent(new Event(PANEL_REFRESH_EVENT));
  window.dispatchEvent(new Event(SIDEBAR_REFRESH_EVENT));
}

function formatDateTime(value) {
  if (!value) {
    return '';
  }
  return String(value).replace('T', ' ').slice(0, 16);
}

function formatDate(value) {
  if (!value) {
    return '-';
  }
  return String(value).slice(0, 10);
}

function ChatBubble({ item }) {
  const style = item.role === 'platform'
    ? 'border-white/[0.08] bg-[#161c28] text-slate-100'
    : item.role === 'logistics'
      ? 'border-sky-500/20 bg-sky-500/10 text-sky-50'
      : item.role === 'ai'
        ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-50'
        : 'border-white/[0.08] bg-white/[0.04] text-slate-100';

  const align = item.role === 'logistics' ? 'justify-end' : 'justify-start';

  return (
    <div className={`flex ${align}`}>
      <div className={`max-w-[88%] rounded-[26px] border px-4 py-3 shadow-[0_16px_32px_rgba(0,0,0,0.22)] ${style}`}>
        <div className="mb-2 flex items-center gap-2 text-[11px] text-slate-400">
          <span className="font-semibold">{item.sender}</span>
          {item.badge && (
            <span className="rounded-full border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[10px] font-semibold text-slate-300">
              {item.badge}
            </span>
          )}
          <span className="ml-auto text-[10px]">{item.time}</span>
        </div>
        <p className="text-sm font-semibold text-white">{item.title}</p>
        <p className="mt-1 text-sm leading-6 text-slate-300">{item.body}</p>
        {item.detailRows?.length ? (
          <div className="mt-3 grid gap-2 rounded-2xl border border-white/[0.06] bg-[#0f141d] p-3 sm:grid-cols-2">
            {item.detailRows.map(([label, value]) => (
              <div key={`${item.id}-${label}`} className="rounded-xl bg-white/[0.03] px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{label}</p>
                <p className="mt-1 text-sm font-medium leading-6 text-slate-200">{value}</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-3 border-t border-white/[0.06] py-2 first:border-t-0 first:pt-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-right text-sm text-slate-200">{value || '-'}</span>
    </div>
  );
}

function DeliveryForm({ onSave, onCancel }) {
  const [form, setForm] = useState({
    company_name: '',
    origin_si: '',
    destination: '인천항',
    cargo_detail: '',
    weight_kg: '',
    due_date: '',
  });

  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="rounded-[24px] border border-amber-400/[0.15] bg-amber-400/[0.08] p-4">
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-300">new cargo</div>
      <div className="grid gap-3 lg:grid-cols-2">
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="출발 회사명" value={form.company_name} onChange={(e) => set('company_name', e.target.value)} />
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="출발지 (시)" value={form.origin_si} onChange={(e) => set('origin_si', e.target.value)} />
        <select className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white" value={form.destination} onChange={(e) => set('destination', e.target.value)}>
          <option>인천항</option>
          <option>부산항</option>
        </select>
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="화물 내용" value={form.cargo_detail} onChange={(e) => set('cargo_detail', e.target.value)} />
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="무게 (kg)" type="number" value={form.weight_kg} onChange={(e) => set('weight_kg', e.target.value)} />
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white" type="date" value={form.due_date} onChange={(e) => set('due_date', e.target.value)} />
      </div>
      <div className="mt-4 flex gap-2">
        <button className="rounded-2xl bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-amber-400" onClick={() => onSave(form)}>화물 등록</button>
        <button className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.08]" onClick={onCancel}>취소</button>
      </div>
    </div>
  );
}

function AssignmentForm({ delivery, drivers, vehicles, onSave, onCancel }) {
  const availableDrivers = useMemo(() => drivers.filter((driver) => driver.status === '가용' || driver.id === delivery.driver_id), [delivery.driver_id, drivers]);
  const [driverId, setDriverId] = useState(() => {
    if (delivery.driver_id) {
      return String(delivery.driver_id);
    }
    return availableDrivers[0] ? String(availableDrivers[0].id) : '';
  });
  const [vehicleId, setVehicleId] = useState('');
  const [pickupDate, setPickupDate] = useState(delivery.pickup_date || '');

  const filteredVehicles = useMemo(() => {
    if (!driverId) {
      return [];
    }
    return vehicles.filter((vehicle) => String(vehicle.driver_id) === String(driverId));
  }, [driverId, vehicles]);

  useEffect(() => {
    if (delivery.driver_id) {
      setDriverId(String(delivery.driver_id));
    } else if (availableDrivers[0]) {
      setDriverId(String(availableDrivers[0].id));
    }
  }, [availableDrivers, delivery.driver_id]);

  useEffect(() => {
    if (!filteredVehicles.length) {
      setVehicleId('');
      return;
    }

    const hasSelectedVehicle = filteredVehicles.some((vehicle) => String(vehicle.id) === String(vehicleId));
    if (!hasSelectedVehicle) {
      setVehicleId(String(filteredVehicles[0].id));
    }
  }, [filteredVehicles, vehicleId]);

  return (
    <div className="rounded-[22px] border border-indigo-400/[0.15] bg-indigo-400/[0.08] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-indigo-300">manual dispatch</div>
          <div className="mt-1 text-sm font-semibold text-white">
            {delivery.company_name || '미지정 업체'} / {delivery.origin_si || '-'} {'->'} {delivery.destination || '-'}
          </div>
        </div>
        <button className="text-xs text-slate-400 hover:text-white" onClick={onCancel}>닫기</button>
      </div>

      <div className="grid gap-3">
        <select className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white" value={driverId} onChange={(e) => setDriverId(e.target.value)}>
          {availableDrivers.map((driver) => (
            <option key={driver.id} value={driver.id}>
              {driver.name} · {driver.location_si || driver.base_region || '위치없음'} · {driver.status}
            </option>
          ))}
        </select>

        <select className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white" value={vehicleId} onChange={(e) => setVehicleId(e.target.value)}>
          {filteredVehicles.map((vehicle) => (
            <option key={vehicle.id} value={vehicle.id}>
              {vehicle.plate_no} · {vehicle.vehicle_type || '차종 미정'}
            </option>
          ))}
        </select>

        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white" type="date" value={pickupDate} onChange={(e) => setPickupDate(e.target.value)} />
      </div>

      <div className="mt-4 flex gap-2">
        <button className="rounded-2xl bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400" onClick={() => onSave({ driverId, vehicleId, pickupDate })} disabled={!driverId || !vehicleId}>
          배정 확정
        </button>
        <button className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.08]" onClick={onCancel}>
          취소
        </button>
      </div>
    </div>
  );
}

function DeliveryActionCard({
  delivery,
  drivers,
  vehicles,
  assigning,
  onToggleAssign,
  onAssign,
  onCloseAssign,
  onAutoDispatch,
  onComplete,
  dDay,
}) {
  return (
    <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-white">{delivery.company_name || '미지정 업체'}</div>
          <div className="mt-1 text-xs text-slate-400">
            {delivery.origin_si || '-'} {'->'} {delivery.destination || '-'}
          </div>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_COLOR[delivery.status] || 'bg-slate-500/20 text-slate-300'}`}>
          {delivery.status}
        </span>
      </div>

      <div className="mt-3 space-y-1 text-xs text-slate-400">
        <div>납기 {formatDate(delivery.due_date)} · {dDay}</div>
        <div>귀로 {delivery.empty_return || '미정'}</div>
        <div>기사 {delivery.driver_name || '미배정'}</div>
      </div>

      {delivery.status !== '완료' && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="rounded-2xl bg-indigo-500/[0.15] px-3 py-1.5 text-xs font-semibold text-indigo-200 ring-1 ring-indigo-400/20 hover:bg-indigo-500/25" onClick={() => onAutoDispatch(delivery.id)}>
            AI 배차
          </button>
          <button className="rounded-2xl bg-white/[0.05] px-3 py-1.5 text-xs font-semibold text-slate-200 ring-1 ring-white/10 hover:bg-white/[0.09]" onClick={() => onToggleAssign(delivery.id)}>
            {assigning ? '닫기' : '수동 배정'}
          </button>
          <button className="rounded-2xl bg-emerald-500/[0.15] px-3 py-1.5 text-xs font-semibold text-emerald-200 ring-1 ring-emerald-400/20 hover:bg-emerald-500/25" onClick={() => onComplete(delivery.id)}>
            완료
          </button>
        </div>
      )}

      {assigning && delivery.status !== '완료' && (
        <div className="mt-4">
          <AssignmentForm
            delivery={delivery}
            drivers={drivers}
            vehicles={vehicles}
            onSave={onAssign}
            onCancel={onCloseAssign}
          />
        </div>
      )}
    </div>
  );
}

function buildDispatchMessages(channelMessages) {
  return channelMessages.map((message) => ({
    id: `platform-${message.id}`,
    role: message.direction === 'outbound' ? 'logistics' : 'platform',
    sender: message.direction === 'outbound' ? '물류 운영자' : '플랫폼',
    badge: `${message.event_type} · ${message.status}`,
    time: formatDateTime(message.created_at),
    title: message.title,
    body: message.summary,
    detailRows: buildPlatformDetailRows(message),
  }));
}

function buildPlatformDetailRows(message) {
  const payload = message.payload || {};

  if (message.event_type === 'dispatch_confirmed') {
    return [
      ['기사', payload.driver_name || '-'],
      ['기사 ID', payload.driver_id != null ? String(payload.driver_id) : '-'],
      ['차량', payload.vehicle_plate || '-'],
      ['차량 ID', payload.vehicle_id != null ? String(payload.vehicle_id) : '-'],
      ['픽업일', payload.pickup_date || '-'],
      ['이동시간', payload.travel || '-'],
    ];
  }

  if (message.event_type === 'dispatch_review') {
    return [
      ['화물 ID', payload.delivery_id != null ? String(payload.delivery_id) : '-'],
      ['목표 픽업', payload.pickup_date || '-'],
      ['이동시간', payload.travel || '-'],
    ];
  }

  if (message.event_type === 'platform_signal' || message.event_type === 'schedule' || message.event_type === 'dispatch' || message.event_type === 'reschedule') {
    return [
      ['업체', payload.company_name || '-'],
      ['출발지', payload.origin_si || '-'],
      ['도착지', payload.destination || '-'],
      ['납기', payload.due_date || '-'],
      ['픽업일', payload.pickup_date || '-'],
      ['화물', payload.cargo_detail || payload.item || payload.label_code || '-'],
    ];
  }

  if (message.event_type === 'delivery_complete') {
    return [
      ['화물 ID', payload.delivery_id != null ? String(payload.delivery_id) : '-'],
      ['업체 ID', payload.company_id != null ? String(payload.company_id) : '-'],
      ['도착지', payload.destination || '-'],
      ['완료일', payload.complete_date || '-'],
    ];
  }

  if (message.event_type === 'round_trip_result') {
    return [
      ['화물 ID', payload.delivery_id != null ? String(payload.delivery_id) : '-'],
      ['귀로 결과', payload.empty_return || '-'],
    ];
  }

  return [];
}

function buildDriverMessages(driver, deliveries, channelMessages) {
  const driverDeliveries = deliveries
    .filter((delivery) => delivery.driver_id === driver.id)
    .sort((left, right) => String(left.due_date || '').localeCompare(String(right.due_date || '')));

  const messages = [];
  const latestPlatform = channelMessages.filter((message) => message.direction === 'inbound').slice(-2);

  messages.push({
    id: `driver-${driver.id}-intro`,
    role: 'system',
    sender: 'DM 시스템',
    badge: '동기화',
    time: formatDateTime(new Date().toISOString()),
    title: `${driver.name} 기사 DM`,
    body: '배차-센터에서 들어온 지시를 AI가 기사용 문장으로 재구성해 전달합니다.',
  });

  latestPlatform.forEach((message) => {
    messages.push({
      id: `driver-${driver.id}-platform-${message.id}`,
      role: 'system',
      sender: '배차-센터',
      badge: '원본 지시',
      time: formatDateTime(message.created_at),
      title: message.title,
      body: message.summary,
    });
  });

  if (!driverDeliveries.length) {
    messages.push({
      id: `driver-${driver.id}-idle`,
      role: 'ai',
      sender: 'AI 배차봇',
      badge: '대기',
      time: formatDateTime(new Date().toISOString()),
      title: '현재 전달할 신규 배차 없음',
      body: `${driver.name} 기사님에게 아직 배차-센터에서 넘길 활성 지시가 없습니다. 상태와 위치만 유지합니다.`,
    });
    return messages;
  }

  driverDeliveries.forEach((delivery) => {
    messages.push({
      id: `driver-${driver.id}-job-${delivery.id}`,
      role: 'ai',
      sender: 'AI 배차봇',
      badge: delivery.status,
      time: formatDate(delivery.pickup_date || delivery.due_date),
      title: `${delivery.company_name || '생산회사'} 화물 지시 전달`,
      body: `${driver.name} 기사님, ${delivery.origin_si || '-'}에서 ${delivery.destination || '-'}로 이동 예정입니다. 픽업일 ${formatDate(delivery.pickup_date)}, 납기 ${formatDate(delivery.due_date)} 기준으로 준비해주세요.`,
    });

    messages.push({
      id: `driver-${driver.id}-vehicle-${delivery.id}`,
      role: 'system',
      sender: '차량/운행 정보',
      badge: delivery.empty_return || '운행',
      time: formatDate(delivery.pickup_date || delivery.due_date),
      title: `${driver.vehicle_plate || '차량 미연결'} / ${driver.vehicle_type || '차종 미정'}`,
      body: `차량 ID ${driver.vehicle_id || '-'} · 적재중량 ${driver.vehicle_max_weight ? `${driver.vehicle_max_weight} kg` : '-'} · 현재 상태 ${driver.status}`,
    });
  });

  return messages;
}

export default function CargoTab({ selectedDriverId = null }) {
  const [deliveries, setDeliveries] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [driverPanels, setDriverPanels] = useState([]);
  const [channelMessages, setChannelMessages] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [assigningId, setAssigningId] = useState(null);

  const load = useCallback(async () => {
    try {
      const [deliveryResult, driverResult, vehicleResult, panelResult, channelResult] = await Promise.all([
        getDeliveries(),
        getDrivers(),
        getVehicles(),
        getAIPanel(),
        getPlatformChannel(40),
      ]);

      setDeliveries(deliveryResult.data || []);
      setDrivers(driverResult.data || []);
      setVehicles(vehicleResult.data || []);
      setDriverPanels(panelResult.data.driver_panels || []);
      setChannelMessages(channelResult.data?.messages || []);
    } catch {
      setDeliveries([]);
      setDrivers([]);
      setVehicles([]);
      setDriverPanels([]);
      setChannelMessages([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selectedDriver = useMemo(
    () => drivers.find((driver) => driver.id === selectedDriverId) || null,
    [drivers, selectedDriverId],
  );
  const selectedPanel = useMemo(
    () => driverPanels.find((panel) => panel.driver_id === selectedDriverId) || null,
    [driverPanels, selectedDriverId],
  );

  const dispatchMessages = useMemo(
    () => buildDispatchMessages(channelMessages),
    [channelMessages],
  );
  const driverMessages = useMemo(
    () => (selectedDriver ? buildDriverMessages(selectedDriver, deliveries, channelMessages) : []),
    [channelMessages, deliveries, selectedDriver],
  );

  const today = new Date().toISOString().split('T')[0];
  const pendingDeliveries = useMemo(
    () => deliveries.filter((delivery) => delivery.status !== '완료').sort((left, right) => String(left.due_date || '').localeCompare(String(right.due_date || ''))),
    [deliveries],
  );

  const driverJobs = useMemo(
    () => deliveries.filter((delivery) => delivery.driver_id === selectedDriverId),
    [deliveries, selectedDriverId],
  );

  const stats = useMemo(() => {
    const pending = deliveries.filter((delivery) => delivery.status === '배차대기').length;
    const driving = deliveries.filter((delivery) => delivery.status === '운행중').length;
    const done = deliveries.filter((delivery) => delivery.status === '완료').length;
    const risky = deliveries.filter((delivery) => {
      if (!delivery.due_date || delivery.status === '완료') {
        return false;
      }
      const diff = Math.ceil((new Date(delivery.due_date) - new Date(today)) / 86400000);
      return diff <= 1;
    }).length;
    return { pending, driving, done, risky };
  }, [deliveries, today]);

  const handleCreate = async (form) => {
    if (!form.due_date) {
      alert('납기일을 입력하세요');
      return;
    }

    try {
      await createDelivery({ ...form, weight_kg: parseFloat(form.weight_kg) || null });
      setShowForm(false);
      await load();
      triggerWorkspaceRefresh();
    } catch (error) {
      alert(`등록 실패: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleComplete = async (id) => {
    if (!window.confirm('배송 완료 처리 하시겠습니까?')) {
      return;
    }

    try {
      await completeDelivery(id);
      await load();
      triggerWorkspaceRefresh();
    } catch (error) {
      alert(`완료 처리 실패: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleAutoDispatch = async (id) => {
    try {
      const response = await autoDispatch(id);
      alert(response.data.message);
      await load();
      triggerWorkspaceRefresh();
    } catch (error) {
      alert(`자동 배차 실패: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleManualAssign = async (deliveryId, form) => {
    if (!form.driverId) {
      alert('기사를 선택하세요');
      return;
    }
    if (!form.vehicleId) {
      alert('차량을 선택하세요');
      return;
    }

    try {
      await assignDriver(deliveryId, Number(form.driverId), Number(form.vehicleId), form.pickupDate || undefined);
      setAssigningId(null);
      await load();
      triggerWorkspaceRefresh();
    } catch (error) {
      alert(`수동 배정 실패: ${error.response?.data?.detail || error.message}`);
    }
  };

  const getDDayLabel = (dueDate) => {
    if (!dueDate) {
      return '납기 미정';
    }

    const diff = Math.ceil((new Date(dueDate) - new Date(today)) / 86400000);
    if (diff < 0) {
      return `D+${Math.abs(diff)} 초과`;
    }
    if (diff === 0) {
      return 'D-Day';
    }
    return `D-${diff}`;
  };

  const chatItems = selectedDriver ? driverMessages : dispatchMessages;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden p-4">
      <div className="grid shrink-0 gap-3 md:grid-cols-4">
        <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.03] px-4 py-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">배차대기</div>
          <div className="mt-2 text-2xl font-semibold text-amber-300">{stats.pending}</div>
        </div>
        <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.03] px-4 py-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">운행중</div>
          <div className="mt-2 text-2xl font-semibold text-sky-300">{stats.driving}</div>
        </div>
        <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.03] px-4 py-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">완료</div>
          <div className="mt-2 text-2xl font-semibold text-emerald-300">{stats.done}</div>
        </div>
        <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.03] px-4 py-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">납기위험</div>
          <div className="mt-2 text-2xl font-semibold text-rose-300">{stats.risky}</div>
        </div>
      </div>

      <div className="mt-4 grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1.55fr)_360px]">
        <section className="flex min-h-0 flex-col overflow-hidden rounded-[28px] border border-white/10 bg-[#151b27]">
          <div className="border-b border-white/[0.06] px-5 py-4">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {selectedDriver ? 'driver dm relay' : 'platform dispatch chat'}
                </div>
                <h2 className="mt-1 text-lg font-semibold text-white">
                  {selectedDriver ? `@ ${selectedDriver.name}` : '# 배차-센터'}
                </h2>
                <p className="mt-1 text-sm text-slate-400">
                  {selectedDriver
                    ? 'AI가 배차-센터 지시를 기사에게 전달하는 채팅창입니다.'
                    : '플랫폼에서 생산회사 보고를 바탕으로 보내는 지시와 물류 응답 로그를 채팅처럼 확인합니다. 기사 정보는 별도 DB 동기화로 전달됩니다.'}
                </p>
              </div>
              {!selectedDriver && (
                <div className="flex flex-wrap gap-2">
                  <button className="rounded-2xl bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-amber-400" onClick={() => setShowForm((prev) => !prev)}>
                    + 화물 등록
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-auto px-4 py-4">
            <div className="space-y-3">
              {chatItems.length ? (
                chatItems.map((item) => <ChatBubble key={item.id} item={item} />)
              ) : (
                <div className="rounded-[24px] border border-dashed border-white/10 bg-white/[0.02] px-4 py-8 text-sm text-slate-500">
                  표시할 채팅 이벤트가 없습니다.
                </div>
              )}
            </div>
          </div>

          <div className="border-t border-white/[0.06] px-4 py-4">
            {selectedDriver ? (
              <div className="rounded-[22px] border border-emerald-400/15 bg-emerald-400/8 px-4 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-300">ai relay</div>
                <div className="mt-1 text-sm text-slate-200">
                  배차-센터에서 들어온 지시를 기사용 문장으로 재정리해 전달하는 전용 DM입니다. 현재 답장 입력은 아직 연동하지 않았습니다.
                </div>
              </div>
            ) : (
              <div className="rounded-[22px] border border-sky-400/15 bg-sky-400/8 px-4 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-sky-300">dispatch note</div>
                <div className="mt-1 text-sm text-slate-200">
                  이 채널의 지시를 기반으로 AI가 기사 DM으로 전달합니다. 기사 기본 정보와 차량 정보는 채팅이 아니라 플랫폼 DB로 직접 동기화됩니다.
                </div>
              </div>
            )}
          </div>
        </section>

        <aside className="min-h-0 overflow-auto rounded-[28px] border border-white/10 bg-[#151b27] p-4">
          {selectedDriver ? (
            <div className="space-y-4">
              <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.03] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">driver profile</div>
                <h3 className="mt-2 text-lg font-semibold text-white">{selectedDriver.name}</h3>
                <div className="mt-4">
                  <InfoRow label="기사 ID" value={selectedDriver.id} />
                  <InfoRow label="가용상태" value={selectedDriver.status} />
                  <InfoRow label="현재 위치" value={selectedDriver.location_si || '-'} />
                  <InfoRow label="소속 지역" value={selectedDriver.base_region || '-'} />
                  <InfoRow label="차량 ID" value={selectedDriver.vehicle_id || '-'} />
                  <InfoRow label="번호판" value={selectedDriver.vehicle_plate || '-'} />
                  <InfoRow label="적재중량" value={selectedDriver.vehicle_max_weight ? `${selectedDriver.vehicle_max_weight} kg` : '-'} />
                  <InfoRow label="차종" value={selectedDriver.vehicle_type || '-'} />
                </div>
              </div>

              <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.03] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">today jobs</div>
                <h3 className="mt-2 text-lg font-semibold text-white">기사 배정 현황</h3>
                <div className="mt-4 space-y-3">
                  {driverJobs.length ? (
                    driverJobs.map((job) => (
                      <div key={job.id} className="rounded-[20px] border border-white/[0.06] bg-[#10151f] p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-semibold text-white">{job.company_name || '생산회사'}</div>
                          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_COLOR[job.status] || 'bg-slate-500/20 text-slate-300'}`}>
                            {job.status}
                          </span>
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          {job.origin_si || '-'} {'->'} {job.destination || '-'}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          픽업 {formatDate(job.pickup_date)} · 납기 {formatDate(job.due_date)}
                        </div>
                        <div className={`mt-1 text-xs font-semibold ${EMPTY_COLOR[job.empty_return] || 'text-slate-500'}`}>
                          {job.empty_return || '미정'}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-[20px] border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-sm text-slate-500">
                      현재 연결된 화물이 없습니다.
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.03] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">panel sync</div>
                <h3 className="mt-2 text-lg font-semibold text-white">AI 패널 요약</h3>
                <div className="mt-3 text-sm text-slate-300">
                  {selectedPanel?.today_jobs?.length
                    ? `${selectedPanel.driver_name} 기사에게 오늘 ${selectedPanel.today_jobs.length}건 전달 예정`
                    : '오늘 배정된 작업이 없습니다.'}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.03] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">dispatch actions</div>
                    <h3 className="mt-2 text-lg font-semibold text-white">대기 화물</h3>
                  </div>
                </div>
                <div className="mt-4 space-y-3">
                  {showForm && (
                    <DeliveryForm onSave={handleCreate} onCancel={() => setShowForm(false)} />
                  )}

                  {pendingDeliveries.length ? (
                    pendingDeliveries.slice(0, 8).map((delivery) => (
                      <DeliveryActionCard
                        key={delivery.id}
                        delivery={delivery}
                        drivers={drivers}
                        vehicles={vehicles}
                        assigning={assigningId === delivery.id}
                        onToggleAssign={(deliveryId) => setAssigningId((current) => (current === deliveryId ? null : deliveryId))}
                        onAssign={(form) => handleManualAssign(delivery.id, form)}
                        onCloseAssign={() => setAssigningId(null)}
                        onAutoDispatch={handleAutoDispatch}
                        onComplete={handleComplete}
                        dDay={getDDayLabel(delivery.due_date)}
                      />
                    ))
                  ) : (
                    <div className="rounded-[20px] border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-sm text-slate-500">
                      대기 화물이 없습니다.
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.03] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">driver summary</div>
                <h3 className="mt-2 text-lg font-semibold text-white">기사 브리핑</h3>
                <div className="mt-4 space-y-3">
                  {driverPanels.length ? (
                    driverPanels
                      .filter((panel) => panel.today_jobs.length)
                      .slice(0, 6)
                      .map((panel) => (
                        <div key={panel.driver_id} className="rounded-[20px] border border-white/[0.06] bg-[#10151f] p-3">
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-semibold text-white">{panel.driver_name}</div>
                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_COLOR[panel.status] || 'bg-slate-500/20 text-slate-300'}`}>
                              {panel.status}
                            </span>
                          </div>
                          <div className="mt-2 text-xs text-slate-400">
                            오늘 작업 {panel.today_jobs.length}건
                          </div>
                        </div>
                      ))
                  ) : (
                    <div className="rounded-[20px] border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-sm text-slate-500">
                      기사 브리핑 데이터가 없습니다.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
