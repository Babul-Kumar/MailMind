import React from 'react';

export function PriorityTabs({
  activeFilter,
  onSelectFilter,
  stats,
  totalCount,
  sortBy,
  onSortChange,
}) {
  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };

  const tabs = [
    { key: 'ALL', label: 'All', count: totalCount },
    { key: 'P1', label: 'Critical', count: counts.P1 || 0, dotColor: 'var(--p1-color)' },
    { key: 'P2', label: 'Important', count: counts.P2 || 0, dotColor: 'var(--p2-color)' },
    { key: 'P3', label: 'Routine', count: counts.P3 || 0, dotColor: 'var(--p3-color)' },
    { key: 'P4', label: 'Low', count: counts.P4 || 0, dotColor: 'var(--p4-color)' },
  ];

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.8rem',
        padding: '0.75rem 0',
      }}
    >
      {/* Priority Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', overflowX: 'auto' }}>
        {tabs.map((tab) => {
          const isActive = activeFilter === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => onSelectFilter(tab.key)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                padding: '0.4rem 0.8rem',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.82rem',
                fontWeight: isActive ? 600 : 500,
                backgroundColor: isActive ? 'var(--bg-surface-selected)' : 'transparent',
                color: isActive ? 'var(--text-main)' : 'var(--text-muted)',
                border: `1px solid ${isActive ? 'var(--border-subtle)' : 'transparent'}`,
                transition: 'all var(--transition-fast)',
              }}
            >
              {tab.dotColor && (
                <span
                  style={{
                    width: '7px',
                    height: '7px',
                    borderRadius: '50%',
                    backgroundColor: tab.dotColor,
                  }}
                />
              )}
              <span>{tab.label}</span>
              <span
                style={{
                  fontSize: '0.72rem',
                  padding: '0.08rem 0.4rem',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--badge-bg)',
                  color: 'var(--text-secondary)',
                }}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Sort Select */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Sort by:</span>
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value)}
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-secondary)',
            fontSize: '0.78rem',
            padding: '0.28rem 0.6rem',
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          <option value="date_desc">Newest</option>
          <option value="date_asc">Oldest</option>
          <option value="priority_desc">Highest priority</option>
          <option value="confidence_desc">Confidence</option>
        </select>
      </div>
    </div>
  );
}
