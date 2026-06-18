import React from 'react';
import './AIAgentPanel.css';

export default function AIAgentPanel({ status, onRefresh, onOpenReportChannel }) {
  const stockItems = status?.stock_summary?.items;
  const activeProductions = status?.active_productions || [];
  const riskItems = status?.risk_items || [];
  const nextActions = status?.next_actions || [];
  const platformStatus = status?.platform_report_status;

  return (
    <div className="agent-panel">
      <h2 className="agent-title">AI Agent</h2>

      {/* 원단 재고 판단 */}
      <div className="agent-section">
        <p className="agent-section-label">원단 재고 판단</p>
        {!status ? (
          <p className="agent-empty">불러오는 중...</p>
        ) : !stockItems || stockItems.length === 0 ? (
          <p className="agent-empty">재고 데이터 없음</p>
        ) : (
          <div className="stock-list">
            {stockItems.map(s => {
              const cls = s.status === '재고없음' ? 'danger' : s.status === '안전재고이하' ? 'warn' : '';
              const mark = s.status === '재고없음' ? ' ❌' : s.status === '안전재고이하' ? ' ⚠' : '';
              return (
                <div key={`${s.fabric_code}_${s.color_code}`} className={`stock-badge ${cls}`}>
                  <span className={`stock-name ${cls}`}>{s.material_name}</span>
                  <span className={`stock-qty ${cls}`}>
                    {s.current_qty.toLocaleString()} {s.unit}{mark}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 납기 현황 (출고 대기 건) */}
      <div className="agent-section">
        <p className="agent-section-label">납기 현황</p>
        {!status || status.active_orders?.length === 0 ? (
          <p className="agent-empty">진행 중인 주문 없음</p>
        ) : (
          status.active_orders.map(o => {
            const urgent = o.days_remaining < 2;
            const warn   = o.days_remaining < 5;
            return (
              <div key={o.id} className={`order-badge ${urgent ? 'urgent' : warn ? 'warn' : ''}`}>
                <div className="order-badge-top">
                  <span className="order-item-name">{o.item_name}</span>
                  <span className={`d-badge ${urgent ? 'urgent' : warn ? 'warn' : ''}`}>D-{o.days_remaining}</span>
                </div>
                <div className="order-badge-sub">
                  {o.release_qty.toLocaleString()}야드 · 납기 {o.due_date}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 진행중 생산단계 */}
      <div className="agent-section">
        <p className="agent-section-label">진행중 생산단계</p>
        {!status ? (
          <p className="agent-empty">불러오는 중...</p>
        ) : activeProductions.length === 0 ? (
          <p className="agent-empty">진행중인 생산 항목 없음</p>
        ) : (
          <div className="production-list">
            {activeProductions.map(p => {
              const cls = p.deadline_status === '납기불가' ? 'danger' : p.deadline_status === '납기위험' ? 'warn' : '';
              return (
                <div key={p.id} className={`production-badge ${cls}`}>
                  <div className="production-badge-top">
                    <span className="production-item-name">{p.item_name}</span>
                    <span className={`stage-pill ${p.stage === '완성' ? 'done' : ''}`}>{p.stage}</span>
                  </div>
                  <div className="production-badge-sub">{p.summary}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 납기 위험 원단 */}
      <div className="agent-section">
        <p className="agent-section-label">납기 위험 원단</p>
        {!status ? (
          <p className="agent-empty">불러오는 중...</p>
        ) : riskItems.length === 0 ? (
          <p className="agent-empty">납기 위험 원단 없음 — 모두 정상</p>
        ) : (
          <div className="instructions-list">
            {riskItems.map(r => (
              <p key={r.id} className={`instruction-item ${r.deadline_status === '납기불가' ? 'danger' : 'warn'}`}>
                {r.summary}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* 오늘 작업 우선순위 */}
      <div className="agent-section">
        <p className="agent-section-label">오늘 작업 우선순위</p>
        {!status || nextActions.length === 0 ? (
          <p className="agent-empty">표시할 지시사항 없음</p>
        ) : (
          <div className="instructions-list">
            {nextActions.map((a, i) => {
              const cls = a.startsWith('❌') ? 'danger' : a.startsWith('⚠') ? 'warn' : 'ok';
              return <p key={i} className={`instruction-item ${cls}`}>{a}</p>;
            })}
          </div>
        )}
      </div>

      {/* 플랫폼 보고 상태 */}
      <div className="agent-section">
        <p className="agent-section-label">플랫폼 보고 상태</p>
        {!platformStatus ? (
          <p className="agent-empty">불러오는 중...</p>
        ) : (
          <div className="platform-status-box">
            <p className="platform-status-summary">{platformStatus.summary}</p>
            <div className="platform-status-counts">
              <span className="platform-count ok">전송완료 {platformStatus.success_count}</span>
              <span className="platform-count waiting">대기 {platformStatus.waiting_count}</span>
            </div>
            {onOpenReportChannel && (
              <button className="platform-channel-link" onClick={onOpenReportChannel}>
                플랫폼 보고 채널 열기 →
              </button>
            )}
          </div>
        )}
      </div>

      <button onClick={onRefresh} className="refresh-btn">새로고침</button>
    </div>
  );
}
