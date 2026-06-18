import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createDriver, createVehicle, getDrivers, getVehicles, updateDriver } from '../api/api';

const SIDEBAR_REFRESH_EVENT = 'logistics:refresh-sidebar';

const STATUS_BADGE = {
  가용: 'bg-emerald-400/[0.15] text-emerald-300 ring-1 ring-emerald-400/20',
  운행중: 'bg-sky-400/[0.15] text-sky-300 ring-1 ring-sky-400/20',
  휴무: 'bg-slate-500/[0.15] text-slate-300 ring-1 ring-slate-400/20',
};

function triggerSidebarRefresh() {
  window.dispatchEvent(new Event(SIDEBAR_REFRESH_EVENT));
}

function RegisterForm({ onSave, onCancel }) {
  const [form, setForm] = useState({
    name: '',
    phone: '',
    location_si: '',
    base_region: '',
    status: '가용',
    plate_no: '',
    max_weight: '',
    vehicle_type: '',
  });

  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="mt-4 rounded-[28px] border border-sky-400/[0.15] bg-sky-400/[0.08] p-4">
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-sky-300">new driver thread</div>

      <div className="grid gap-3 lg:grid-cols-2">
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="기사명*" value={form.name} onChange={(e) => set('name', e.target.value)} />
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="연락처" value={form.phone} onChange={(e) => set('phone', e.target.value)} />
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="현재위치 (시)" value={form.location_si} onChange={(e) => set('location_si', e.target.value)} />
        <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="소속 지역" value={form.base_region} onChange={(e) => set('base_region', e.target.value)} />
        <select className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white" value={form.status} onChange={(e) => set('status', e.target.value)}>
          <option>가용</option>
          <option>운행중</option>
          <option>휴무</option>
        </select>
      </div>

      <div className="mt-4 border-t border-white/[0.08] pt-4">
        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">vehicle binding</div>
        <div className="grid gap-3 lg:grid-cols-2">
          <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="차량번호*" value={form.plate_no} onChange={(e) => set('plate_no', e.target.value)} />
          <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="최대 적재량 (kg)" type="number" value={form.max_weight} onChange={(e) => set('max_weight', e.target.value)} />
          <input className="rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white placeholder:text-slate-500 lg:col-span-2" placeholder="차량종류 (트럭/탑차/화물차 등)" value={form.vehicle_type} onChange={(e) => set('vehicle_type', e.target.value)} />
        </div>
      </div>

      <div className="mt-4 flex gap-2">
        <button className="rounded-2xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400" onClick={() => onSave(form)}>기사 등록</button>
        <button className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.08]" onClick={onCancel}>취소</button>
      </div>
    </div>
  );
}

function StatCard({ label, value, tone }) {
  return (
    <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.03] px-4 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

export default function DriverTab({ selectedDriverId = null }) {
  const [drivers, setDrivers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    try {
      const [driverResult, vehicleResult] = await Promise.all([getDrivers(), getVehicles()]);
      setDrivers(driverResult.data || []);
      setVehicles(vehicleResult.data || []);
    } catch {
      setDrivers([]);
      setVehicles([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const orderedDrivers = useMemo(() => {
    const list = [...drivers];
    if (!selectedDriverId) {
      return list;
    }

    return list.sort((left, right) => {
      if (left.id === selectedDriverId) return -1;
      if (right.id === selectedDriverId) return 1;
      return 0;
    });
  }, [drivers, selectedDriverId]);

  const stats = useMemo(() => ({
    total: drivers.length,
    available: drivers.filter((driver) => driver.status === '가용').length,
    driving: drivers.filter((driver) => driver.status === '운행중').length,
    vehicles: vehicles.length,
  }), [drivers, vehicles]);

  const handleSave = async (form) => {
    if (!form.name) {
      alert('기사명을 입력하세요');
      return;
    }
    if (!form.plate_no) {
      alert('차량번호를 입력하세요');
      return;
    }

    try {
      const driverResponse = await createDriver({
        name: form.name,
        phone: form.phone,
        location_si: form.location_si,
        base_region: form.base_region || form.location_si,
        status: form.status,
      });

      await createVehicle({
        driver_id: driverResponse.data.id,
        plate_no: form.plate_no,
        max_weight: parseFloat(form.max_weight) || null,
        vehicle_type: form.vehicle_type,
      });

      setShowForm(false);
      await load();
      triggerSidebarRefresh();
    } catch (error) {
      alert(`등록 실패: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleStatusChange = async (driver, status) => {
    try {
      await updateDriver(driver.id, { status });
      await load();
      triggerSidebarRefresh();
    } catch (error) {
      alert(`상태 변경 실패: ${error.response?.data?.detail || error.message}`);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-auto p-4">
      <div className="grid gap-3 md:grid-cols-4">
        <StatCard label="threads" value={stats.total} tone="text-white" />
        <StatCard label="ready" value={stats.available} tone="text-emerald-300" />
        <StatCard label="route" value={stats.driving} tone="text-sky-300" />
        <StatCard label="vehicle" value={stats.vehicles} tone="text-amber-300" />
      </div>

      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="min-h-0 overflow-auto rounded-[28px] border border-white/10 bg-[#151b27] p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">driver roster</div>
              <h2 className="mt-1 text-lg font-semibold text-white">기사 목록</h2>
            </div>
            <button className="rounded-2xl bg-sky-500 px-3 py-2 text-sm font-semibold text-white hover:bg-sky-400" onClick={() => setShowForm((value) => !value)}>
              + 기사 등록
            </button>
          </div>

          {showForm && <RegisterForm onSave={handleSave} onCancel={() => setShowForm(false)} />}

          <div className="mt-4 overflow-hidden rounded-[24px] border border-white/[0.08]">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.03] text-slate-400">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">기사ID</th>
                  <th className="px-4 py-3 text-left font-medium">기사명</th>
                  <th className="px-4 py-3 text-left font-medium">가용상태</th>
                  <th className="px-4 py-3 text-left font-medium">현재위치</th>
                  <th className="px-4 py-3 text-left font-medium">소속지역</th>
                  <th className="px-4 py-3 text-left font-medium">차량ID</th>
                  <th className="px-4 py-3 text-left font-medium">번호판</th>
                  <th className="px-4 py-3 text-left font-medium">적재중량</th>
                  <th className="px-4 py-3 text-left font-medium">차종</th>
                </tr>
              </thead>
              <tbody>
                {orderedDrivers.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-8 text-center text-slate-500">등록된 기사 없음</td>
                  </tr>
                )}
                {orderedDrivers.map((driver) => (
                  <tr
                    key={driver.id}
                    className={`border-t border-white/[0.06] transition hover:bg-white/[0.03] ${
                      driver.id === selectedDriverId ? 'bg-sky-400/[0.08]' : ''
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-slate-400">{driver.id}</td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-white">{driver.name}</div>
                      <div className="mt-1 text-xs text-slate-500">{driver.phone || '연락처 미등록'}</div>
                      {driver.id === selectedDriverId && (
                        <div className="mt-1 text-xs text-sky-300">현재 선택된 기사 쓰레드</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={driver.status}
                        onChange={(event) => handleStatusChange(driver, event.target.value)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_BADGE[driver.status] || ''}`}
                      >
                        <option>가용</option>
                        <option>운행중</option>
                        <option>휴무</option>
                      </select>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{driver.location_si || '-'}</td>
                    <td className="px-4 py-3 text-slate-300">{driver.base_region || '-'}</td>
                    <td className="px-4 py-3 font-mono text-slate-400">{driver.vehicle_id || '-'}</td>
                    <td className="px-4 py-3 font-mono text-white">{driver.vehicle_plate || '-'}</td>
                    <td className="px-4 py-3 text-slate-300">{driver.vehicle_max_weight ? `${driver.vehicle_max_weight} kg` : '-'}</td>
                    <td className="px-4 py-3 text-slate-300">{driver.vehicle_type || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="min-h-0 overflow-auto rounded-[28px] border border-white/10 bg-[#151b27] p-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">vehicle binding</div>
            <h2 className="mt-1 text-lg font-semibold text-white">차량 목록</h2>
          </div>

          <div className="mt-4 overflow-hidden rounded-[24px] border border-white/[0.08]">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.03] text-slate-400">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">차량번호</th>
                  <th className="px-4 py-3 text-left font-medium">최대적재</th>
                  <th className="px-4 py-3 text-left font-medium">차량종류</th>
                  <th className="px-4 py-3 text-left font-medium">기사명</th>
                </tr>
              </thead>
              <tbody>
                {vehicles.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-500">등록된 차량 없음</td>
                  </tr>
                )}
                {vehicles.map((vehicle) => (
                  <tr
                    key={vehicle.id}
                    className={`border-t border-white/[0.06] ${
                      vehicle.driver_id === selectedDriverId ? 'bg-sky-400/[0.06]' : 'hover:bg-white/[0.03]'
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-white">
                      <div>{vehicle.plate_no}</div>
                      <div className="mt-1 text-xs text-slate-500">차량ID {vehicle.id}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{vehicle.max_weight ? `${vehicle.max_weight} kg` : '-'}</td>
                    <td className="px-4 py-3 text-slate-300">{vehicle.vehicle_type || '-'}</td>
                    <td className="px-4 py-3 text-slate-300">{vehicle.driver_name || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
