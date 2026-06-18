import React, { useState, useEffect } from 'react';
import './Header.css';

export default function Header() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const fmt = (d) =>
    `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} `+
    `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;

  return (
    <header className="header">
      <div className="header-title">
        <span className="header-company">옷감회사</span>
        <span className="header-badge">AI Agent</span>
      </div>
      <div className="header-time">{fmt(now)}</div>
    </header>
  );
}
