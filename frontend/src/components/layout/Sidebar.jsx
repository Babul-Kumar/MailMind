import React from 'react';
import { Mail, Zap } from 'lucide-react';

export function Sidebar({
  activeFilter,
  onSelectFilter,
  focusMode,
  onToggleFocusMode,
  stats,
  totalCount,
  attentionCount = 0,
  onOpenSettings,
  isOpenMobile,
  onCloseMobile,
}) {
  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };
  const importantCount = counts.P2 || 0;

  const primaryItems = [
    {
      key: 'ALL',
      label: 'Inbox',
      icon: <Mail size={16} />,
      count: totalCount,
      tooltip: `${totalCount} most recent emails scanned`,
    },
    {
      key: 'NEEDS_ATTENTION',
      label: 'Needs Attention',
      icon: <Zap size={16} />,
      count: attentionCount,
      color: 'var(--accent)',
      tooltip: 'Emails that require action or have a meaningful deadline.',
    },
  ];

  const priorityItems = [
    { key: 'P1', label: 'P1 · Critical', count: counts.P1 || 0, dotColor: 'var(--p1-color)', tooltip: 'Immediate action, hard deadline, or critical operational consequence.' },
    { key: 'P2', label: 'P2 · Important', count: counts.P2 || 0, dotColor: 'var(--p2-color)', tooltip: 'Emails the model classified as important.' },
    { key: 'P3', label: 'P3 · Routine', count: counts.P3 || 0, dotColor: 'var(--p3-color)', tooltip: 'Informational or non-urgent.' },
    { key: 'P4', label: 'P4 · Low', count: counts.P4 || 0, dotColor: 'var(--p4-color)', tooltip: 'Promotional, noise, or no meaningful action.' },
  ];

  const handleSelect = (key) => {
    onToggleFocusMode(false);
    onSelectFilter(key);
    if (isOpenMobile) onCloseMobile();
  };

  return (
    <aside
      className={`sidebar-container ${isOpenMobile ? 'mobile-open' : ''}`}
      style={{
        width: '220px',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.25rem 0.75rem',
        flexShrink: 0,
        overflowY: 'auto',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Primary Views */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', padding: '0 0.65rem 0.35rem' }}>
            Views
          </div>
          {primaryItems.map((item) => {
            const isActive = !focusMode && activeFilter === item.key;
            return (
              <button
                key={item.key}
                onClick={() => handleSelect(item.key)}
                title={item.tooltip}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.52rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.84rem',
                  fontWeight: isActive ? 600 : 500,
                  backgroundColor: isActive ? 'var(--bg-surface-selected)' : 'transparent',
                  color: isActive ? 'var(--text-main)' : 'var(--text-secondary)',
                  border: `1px solid ${isActive ? 'var(--border-subtle)' : 'transparent'}`,
                  transition: 'all var(--transition-fast)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  <span style={{ color: item.color || (isActive ? 'var(--accent)' : 'var(--text-muted)'), display: 'flex' }}>
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </div>
                <span
                  style={{
                    fontSize: '12px',
                    minWidth: '22px',
                    height: '22px',
                    padding: '0 0.45rem',
                    borderRadius: '999px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: item.key === 'NEEDS_ATTENTION' && item.count > 0 ? 'var(--accent-light)' : 'var(--badge-bg)',
                    color: item.key === 'NEEDS_ATTENTION' && item.count > 0 ? 'var(--accent)' : 'var(--text-muted)',
                    fontWeight: item.count > 0 ? 600 : 500,
                  }}
                >
                  {item.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Priority Filter Section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', padding: '0 0.65rem 0.35rem' }}>
            Priority
          </div>
          {priorityItems.map((item) => {
            const isActive = !focusMode && activeFilter === item.key;
            const isP1WithCount = item.key === 'P1' && item.count > 0;
            return (
              <button
                key={item.key}
                onClick={() => handleSelect(item.key)}
                title={item.tooltip}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.45rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.82rem',
                  fontWeight: isActive ? 600 : 500,
                  backgroundColor: isActive ? 'var(--bg-surface-selected)' : 'transparent',
                  color: isActive ? 'var(--text-main)' : 'var(--text-secondary)',
                  border: `1px solid ${isActive ? 'var(--border-subtle)' : 'transparent'}`,
                  transition: 'all var(--transition-fast)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: item.dotColor }} />
                  <span>{item.label}</span>
                </div>
                <span
                  style={{
                    fontSize: '12px',
                    minWidth: '22px',
                    height: '22px',
                    padding: '0 0.45rem',
                    borderRadius: '999px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: isP1WithCount ? 'rgba(239, 68, 68, 0.18)' : 'var(--badge-bg)',
                    color: isP1WithCount ? 'var(--p1-color)' : 'var(--text-muted)',
                    fontWeight: item.count > 0 ? 600 : 500,
                  }}
                >
                  {item.count}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
