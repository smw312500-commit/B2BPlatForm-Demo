import React from 'react';
import './TabNav.css';

export default function TabNav({ tabs, activeTab, onTabChange }) {
  return (
    <nav className="tabnav">
      {tabs.map((tab) => (
        <button
          key={tab}
          className={`tabnav-btn ${activeTab === tab ? 'active' : ''}`}
          onClick={() => onTabChange(tab)}
        >
          {tab}
        </button>
      ))}
    </nav>
  );
}
