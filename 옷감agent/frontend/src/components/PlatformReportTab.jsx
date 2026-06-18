import React from 'react';
import './PlatformReportTab.css';

const STATUS_CLASS = {
  '전송완료': 'status-ok',
  '수신확인': 'status-ok',
  '전송중': 'status-sending',
  '플랫폼 보고 대기': 'status-waiting',
  '실패': 'status-danger',
  '오류': 'status-danger',
};

function formatTime(iso) {
  if (!iso) return '-';
  return iso.replace('T', ' ');
}

const DECISION_CLASS = {
  정상: 'ok',
  주의: 'warn',
  긴급: 'danger',
};

function AiDecisionCard({ aiReport }) {
  if (!aiReport || (!aiReport.summary && !aiReport.decision)) return null;
  const tone = DECISION_CLASS[aiReport.decision_level] || 'ok';
  const analysisLabel = aiReport.uses_openai === false ? 'DB 규칙 기반' : 'AI 판단';

  return (
    <div className={`ai-decision-card ${tone}`}>
      <div className="ai-decision-top">
        <span className="ai-decision-tag">{analysisLabel}</span>
        {aiReport.decision_level && <span className="ai-decision-tag">{aiReport.decision_level}</span>}
      </div>
      <p className="ai-decision-summary">{aiReport.summary}</p>
      {aiReport.decision && aiReport.decision !== aiReport.summary && (
        <p className="ai-decision-detail">{aiReport.decision}</p>
      )}
    </div>
  );
}

export default function PlatformReportTab({ agentStatus, onRefresh }) {
  const platformStatus = agentStatus?.platform_report_status;
  // 채널 메시지는 최신순(위 → 아래)으로 표시: 백엔드는 오래된 순으로 주므로 역순 정렬
  const messages = [...(platformStatus?.channel_messages || [])].reverse();

  return (
    <div className="report-channel">
      <div className="report-channel-header">
        <div>
          <div className="section-title" style={{ marginBottom: 4 }}>플랫폼 보고 채널 — 옷감 ↔ 플랫폼</div>
          <p className="report-channel-summary">{platformStatus?.summary || '불러오는 중...'}</p>
        </div>
        <div className="report-channel-counts">
          <span className="badge badge-ok">전송완료 {platformStatus?.success_count ?? 0}</span>
          <span className="badge badge-warning">보고 대기 {platformStatus?.waiting_count ?? 0}</span>
          <button className="btn btn-secondary" onClick={onRefresh}>새로고침</button>
        </div>
      </div>

      <div className="report-channel-body">
        {messages.length === 0 ? (
          <p className="agent-empty">표시할 보고 내역이 없습니다.</p>
        ) : (
          messages.map(m => (
            <div key={m.id} className={`report-msg ${m.direction === 'outbound' ? 'out' : 'in'}`}>
              <div className="report-msg-meta">
                <span className="report-msg-sender">{m.sender} → {m.receiver}</span>
                <span className="report-msg-time">{formatTime(m.created_at)}</span>
              </div>
              <div className="report-msg-bubble">
                <div className="report-msg-top">
                  <span className="report-msg-type">{m.report_type_label}</span>
                  <span className={`report-msg-status ${STATUS_CLASS[m.status] || 'status-default'}`}>{m.status}</span>
                </div>
                <p className="report-msg-summary">{m.summary}</p>
                {m.report_type === 'release' && m.direction === 'outbound' && (
                  <AiDecisionCard aiReport={m.payload?.ai_report} />
                )}
                {m.payload && Object.keys(m.payload).length > 0 && (
                  <details className="report-msg-payload">
                    <summary>전송 데이터 보기</summary>
                    <pre>{JSON.stringify(m.payload, null, 2)}</pre>
                  </details>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {platformStatus?.recent_reports?.length > 0 && (
        <div className="report-channel-recent">
          <div className="section-title" style={{ fontSize: 13, marginBottom: 8 }}>최근 보고 이벤트</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>유형</th>
                  <th>대상</th>
                  <th>상태</th>
                  <th>report_id</th>
                  <th>갱신시각</th>
                </tr>
              </thead>
              <tbody>
                {platformStatus.recent_reports.map(r => (
                  <tr key={r.id}>
                    <td>{r.report_type_label}</td>
                    <td>{r.item_ref}</td>
                    <td><span className={`badge ${r.status === '전송완료' ? 'badge-ok' : 'badge-warning'}`}>{r.status}</span></td>
                    <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{r.report_id || '-'}</td>
                    <td>{formatTime(r.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
