import React, { useCallback, useEffect, useState } from 'react';
import { getAIPanel, getPlatformChannel } from '../api/api';

const PANEL_REFRESH_EVENT = 'logistics:refresh-panel';

const TYPE_STYLE = {
  error: 'border-red-500/20 bg-red-500/10 text-red-100',
  warning: 'border-amber-400/20 bg-amber-400/10 text-amber-100',
  info: 'border-sky-400/20 bg-sky-400/10 text-sky-100',
  success: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100',
};

const STATUS_STYLE = {
  수신완료: 'bg-slate-200 text-slate-700',
  배차검토중: 'bg-amber-200 text-amber-900',
  배차완료: 'bg-sky-200 text-sky-900',
  귀로배정연결완료: 'bg-emerald-200 text-emerald-900',
  '귀로배정 연결완료': 'bg-emerald-200 text-emerald-900',
  빈차귀환: 'bg-rose-200 text-rose-900',
  '빈차 귀환': 'bg-rose-200 text-rose-900',
  배송완료: 'bg-green-200 text-green-900',
  '플랫폼 보고 대기': 'bg-orange-200 text-orange-900',
};

function formatDateTime(value) {
  if (!value) {
    return '';
  }
  return String(value).replace('T', ' ').slice(0, 16);
}

function normalizeStatus(status) {
  if (!status) {
    return '';
  }
  if (status.includes('귀로') && status.includes('연결완료')) {
    return '귀로배정연결완료';
  }
  return status;
}

function ReportBubble({ message }) {
  const outbound = message.direction === 'outbound';
  const normalizedStatus = normalizeStatus(message.status);

  return (
    <div className={`flex ${outbound ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[92%] rounded-3xl border px-4 py-3 shadow-[0_16px_32px_rgba(0,0,0,0.24)] ${
          outbound
            ? 'border-sky-500/20 bg-sky-500/10 text-sky-50'
            : 'border-white/[0.08] bg-[#151b27] text-slate-100'
        }`}
      >
        <div className="mb-2 flex items-center gap-2 text-[11px] text-slate-400">
          <span className="font-semibold">{outbound ? '물류 -> 플랫폼' : '플랫폼 -> 물류'}</span>
          <span className={`rounded-full px-2 py-0.5 font-semibold ${STATUS_STYLE[normalizedStatus] || 'bg-slate-200 text-slate-700'}`}>
            {message.status}
          </span>
          <span className="ml-auto text-[10px]">{formatDateTime(message.created_at)}</span>
        </div>
        <p className="text-sm font-semibold text-white">{message.title}</p>
        <p className="mt-1 text-sm leading-5 text-slate-300">{message.summary}</p>
      </div>
    </div>
  );
}

function FeedCard({ title, eyebrow, count, children, loading, onRefresh, grow = 'flex-1' }) {
  return (
    <section className={`flex min-h-0 flex-col rounded-[28px] border border-white/10 bg-[#141923]/92 ${grow}`}>
      <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 pb-3 pt-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{eyebrow}</div>
          <div className="mt-1 text-sm font-semibold text-white">{title}</div>
        </div>
        {typeof count === 'number' && (
          <span className="ml-auto rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-slate-400">
            {count}
          </span>
        )}
        {onRefresh && (
          <button onClick={onRefresh} className="text-xs text-slate-500 transition hover:text-slate-200">
            새로고침
          </button>
        )}
      </div>
      {loading && (
        <div className="px-4 pt-2 text-xs text-slate-500">업데이트 중...</div>
      )}
      <div className="min-h-0 flex-1 overflow-auto px-3 py-3">
        {children}
      </div>
    </section>
  );
}

export default function AIPanel({ layout = 'sidebar' }) {
  const [messages, setMessages] = useState([]);
  const [channel, setChannel] = useState({ channel: '물류 - 플랫폼', messages: [] });
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);

    const [aiResult, channelResult] = await Promise.allSettled([
      getAIPanel(),
      getPlatformChannel(24),
    ]);

    if (aiResult.status === 'fulfilled') {
      setMessages(aiResult.value.data.messages || []);
    } else {
      setMessages([{ type: 'error', icon: 'ERR', text: 'AI 패널 로드 실패' }]);
    }

    if (channelResult.status === 'fulfilled') {
      setChannel(channelResult.value.data || { channel: '물류 - 플랫폼', messages: [] });
    } else {
      setChannel({
        channel: '물류 - 플랫폼',
        messages: [{
          id: 'channel-error',
          direction: 'inbound',
          title: '플랫폼 보고 채널',
          summary: '채널 로드 실패. 백엔드 연결 상태를 확인하세요.',
          status: '플랫폼 보고 대기',
          created_at: null,
        }],
      });
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    const handleRefresh = () => load();
    window.addEventListener(PANEL_REFRESH_EVENT, handleRefresh);

    return () => {
      clearInterval(timer);
      window.removeEventListener(PANEL_REFRESH_EVENT, handleRefresh);
    };
  }, [load]);

  return (
    <div className={`flex h-full min-h-0 flex-col gap-3 rounded-[30px] border border-white/10 bg-[#101520]/92 p-3 shadow-[0_26px_60px_rgba(0,0,0,0.4)] ${
      layout === 'sidebar' ? '' : ''
    }`}
    >
      <div className="rounded-[24px] border border-white/[0.08] bg-[linear-gradient(135deg,rgba(56,189,248,0.14),rgba(15,23,42,0.2))] px-4 py-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">ops relay</div>
        <div className="mt-2 text-lg font-semibold text-white">AI 지시 + 플랫폼 보고</div>
        <div className="mt-1 text-sm text-slate-400">
          배차 판단, 납기 경고, 플랫폼 보고 타임라인을 같은 흐름으로 본다.
        </div>
      </div>

      <FeedCard
        title="AI 지시 피드"
        eyebrow="ai feed"
        count={messages.length}
        loading={loading}
        onRefresh={load}
        grow="flex-[0.95]"
      >
        <div className="space-y-2">
          {messages.map((message, index) => (
            <div
              key={`${message.type}-${index}`}
              className={`rounded-3xl border px-3 py-3 text-sm ${TYPE_STYLE[message.type] || 'border-white/10 bg-white/[0.03] text-slate-100'}`}
            >
              <div className="flex items-start gap-3">
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] font-bold tracking-[0.18em] text-slate-300">
                  {message.icon}
                </span>
                <span className="leading-6">{message.text}</span>
              </div>
            </div>
          ))}
        </div>
      </FeedCard>

      <FeedCard
        title={channel.channel}
        eyebrow="platform relay"
        count={channel.messages?.length || 0}
        grow="flex-[1.15]"
      >
        <div className="space-y-3">
          {channel.messages?.length ? (
            channel.messages.map((message) => (
              <ReportBubble key={message.id} message={message} />
            ))
          ) : (
            <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-6 text-sm text-slate-500">
              아직 표시할 플랫폼 보고 이벤트가 없습니다.
            </div>
          )}
        </div>
      </FeedCard>
    </div>
  );
}
