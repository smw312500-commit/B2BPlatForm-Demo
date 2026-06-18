import React from 'react';

function ConfigCard({ label, helper, defaultValue }) {
  return (
    <div className="rounded-[26px] border border-white/10 bg-[#151b27] p-5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">setting</div>
      <h3 className="mt-2 text-base font-semibold text-white">{label}</h3>
      <p className="mt-1 text-sm text-slate-400">{helper}</p>
      <input
        type="number"
        defaultValue={defaultValue}
        className="mt-4 w-32 rounded-2xl border border-white/10 bg-[#0d1118] px-3 py-2 text-sm text-white"
      />
    </div>
  );
}

export default function OtherTab() {
  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-auto p-4">
      <div className="rounded-[30px] border border-white/10 bg-[linear-gradient(135deg,rgba(251,191,36,0.14),rgba(15,23,42,0.14))] p-5">
        <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-300">ops memo</div>
        <h2 className="mt-2 text-xl font-semibold text-white">운영 기준 설정</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-300">
          아직 백엔드 저장과 연결된 설정 화면은 아니지만, 운영자가 보는 기준값 패널은 디스코드식 운영 콘솔에 맞춰 정리해두는 편이 좋습니다.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <ConfigCard label="인천항 이동 기준" helper="인천항 도착 화물의 기본 이동시간 기준값입니다." defaultValue={1} />
        <ConfigCard label="부산항 이동 기준" helper="부산항 도착 화물의 기본 이동시간 기준값입니다." defaultValue={1} />
        <ConfigCard label="여유시간 기준" helper="픽업일 계산 시 추가로 빼는 운영 여유일입니다." defaultValue={1} />
      </div>

      <div className="rounded-[26px] border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-slate-400">
        픽업일 계산식: 납기일 - 이동시간 - 운영 여유시간
      </div>
    </div>
  );
}
