import React, { useState, useEffect } from 'react';
import { orderApi } from '../api';

function periodStr(start, end) {
  if (!start || !end) return '-';
  return `${start} ~ ${end}`;
}

export default function CancelTab({ onRefreshAgent }) {
  const [orders, setOrders] = useState([]);

  const load = async () => {
    try {
      const res = await orderApi.getActive();
      setOrders(res.data);
    } catch {}
  };

  useEffect(() => { load(); }, []);

  const handleCancel = async (id, name) => {
    if (!window.confirm(`[${name}] 발주를 취소하시겠습니까?`)) return;
    try {
      await orderApi.cancel(id);
      await load();
      onRefreshAgent();
    } catch (err) {
      alert(err.response?.data?.detail || '취소 실패');
    }
  };

  return (
    <div>
      <div className="section-title">발주 취소</div>
      <p style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
        대기중 상태의 발주만 취소 가능합니다.
      </p>

      {/* 표준 컬럼: 발주처 | 날짜 | 기간 | 수량 | 비고 | 취소버튼 */}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>품목</th>
              <th>발주처</th>
              <th>날짜</th>
              <th>기간 (발주 ~ 납기)</th>
              <th>수량 (kg)</th>
              <th>비고</th>
              <th>취소</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', color: '#9ca3af' }}>
                  취소 가능한 발주 없음
                </td>
              </tr>
            ) : orders.map(o => (
              <tr key={o.id}>
                <td style={{ fontWeight: 600 }}>{o.material_name}</td>
                <td>{o.supplier}</td>
                <td style={{ whiteSpace: 'nowrap' }}>{o.order_date}</td>
                <td style={{ fontSize: 12, color: '#374151', whiteSpace: 'nowrap' }}>
                  {periodStr(o.order_date, o.due_date)}
                </td>
                <td style={{ textAlign: 'right' }}>{parseFloat(o.order_qty).toLocaleString()}</td>
                <td style={{ fontSize: 12, color: '#6b7280' }}>{o.note || '—'}</td>
                <td>
                  <button className="btn btn-danger" style={{ padding: '4px 12px' }}
                    onClick={() => handleCancel(o.id, o.material_name)}>
                    취소
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
