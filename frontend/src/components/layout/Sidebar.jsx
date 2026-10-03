import React from 'react';
import { Mail, Zap, X } from 'lucide-react';

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
  const effectiveAttentionCount = stats?.needs_attention_count ?? attentionCount;

  const mailboxItems = [
    {
      key: 'ALL',
      label: 'All Mail',
      icon: <Mail size={16} />,
      count: totalCount || 0,
      tooltip: `${(totalCount || 0).toLocaleString()} synchronized messages in mailbox`,
    },
    {
      key: 'NEEDS_ATTENTION',
      label: 'Needs Attention',
      icon: <Zap size={16} />,
      count: effectiveAttentionCount || 0,
      color: 'var(--accent)',
      tooltip: 'Emails that require action or have a meaningful deadline.',
    },
  ];

  const priorityItems = [
    { key: 'P1', label: 'P1 · Critical', count: counts.P1 || 0, dotColor: 'var(--p1-color)', tooltip: 'Immediate action, hard deadline, or critical operational consequence.' },
    { key: 'P2', label: 'P2 · Important', count: counts.P2 || 0, dotColor: 'var(--p2-color)', tooltip: 'Important emails classified by the model; not all require action.' },
    { key: 'P3', label: 'P3 · Routine', count: counts.P3 || 0, dotColor: 'var(--p3-color)', tooltip: 'Informational or routine operational correspondence.' },
    { key: 'P4', label: 'P4 · Low', count: counts.P4 || 0, dotColor: 'var(--p4-color)', tooltip: 'Promotional, bulk notifications, or low priority.' },
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
        width: '230px',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.25rem 0.75rem',
        flexShrink: 0,
        overflowY: 'auto',
      }}
    >
      {isOpenMobile && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 0.5rem 0.65rem', borderBottom: '1px solid var(--border-subtle)', marginBottom: '0.75rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>Navigation</span>
          <button
            onClick={onCloseMobile}
            aria-label="Close navigation menu"
            className="mobile-sidebar-close-btn"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '0.25rem',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <X size={18} />
          </button>
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}>
        {/* Mailbox Section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', padding: '0 0.65rem 0.35rem' }}>
            Mailbox
          </div>
          {mailboxItems.map((item) => {
            const isActive = !focusMode && activeFilter === item.key;
            const hasAttentionCount = item.key === 'NEEDS_ATTENTION' && item.count > 0;
            const formattedCount = typeof item.count === 'number' ? item.count.toLocaleString() : (item.count || '0');
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
                    fontSize: '11px',
                    minWidth: '22px',
                    height: '20px',
                    padding: '0 0.45rem',
                    borderRadius: '999px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: hasAttentionCount ? 'var(--accent-light)' : 'var(--badge-bg)',
                    color: hasAttentionCount ? 'var(--accent)' : 'var(--text-muted)',
                    fontWeight: item.count > 0 ? 600 : 500,
                  }}
                >
                  {formattedCount}
                </span>
              </button>
            );
          })}
        </div>

        {/* Priority Filter Section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', padding: '0 0.65rem 0.35rem' }}>
            Priority
          </div>
          {priorityItems.map((item) => {
            const isActive = !focusMode && activeFilter === item.key;
            const isP1WithCount = item.key === 'P1' && item.count > 0;
            const formattedCount = typeof item.count === 'number' ? item.count.toLocaleString() : (item.count || '0');
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
                    fontSize: '11px',
                    minWidth: '22px',
                    height: '20px',
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
                  {formattedCount}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
