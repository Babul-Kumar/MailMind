import React from 'react';
import { Mail, Zap, X, Settings, RefreshCw, RefreshCcw, LogOut, ShieldCheck, User, Sun, Moon } from 'lucide-react';
import { MailMindLogo } from '../brand/MailMindLogo';

function SidebarComponent({
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
  auth,
  profile,
  onRescan,
  isScanning,
  scanStatus,
  theme,
  onToggleTheme,
}) {
  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };
  const effectiveAttentionCount = stats?.needs_attention_count ?? attentionCount;
  const userEmail = auth?.user?.email || profile?.email_address;
  const isAuthenticated = auth?.isAuthenticated || Boolean(userEmail);

  const mailboxItems = [
    {
      key: 'ALL',
      label: 'All Mail',
      icon: <Mail size={17} />,
      count: totalCount || 0,
      tooltip: `${(totalCount || 0).toLocaleString()} synchronized messages in mailbox`,
    },
    {
      key: 'NEEDS_ATTENTION',
      label: 'Needs Attention',
      icon: <Zap size={17} />,
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
    if (isOpenMobile) onCloseMobile?.();
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
      aria-label="Sidebar navigation"
    >
      {/* Mobile Drawer Header */}
      {isOpenMobile && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.25rem 0.4rem 0.85rem',
            borderBottom: '1px solid var(--border-subtle)',
            marginBottom: '0.85rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
            <MailMindLogo size={26} isScanning={isScanning} />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                MailMind
              </span>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Priority Intelligence</span>
            </div>
          </div>
          <button
            onClick={onCloseMobile}
            aria-label="Close navigation menu"
            className="mobile-sidebar-close-btn"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '0.45rem',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 'var(--radius-sm)',
              minWidth: '40px',
              minHeight: '40px',
            }}
          >
            <X size={20} />
          </button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', flex: 1 }}>
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
                className={`sidebar-nav-btn ${isActive ? 'is-active' : ''}`}
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
                    height: '22px',
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
            const isP4 = item.key === 'P4';
            const formattedCount = typeof item.count === 'number' ? item.count.toLocaleString() : (item.count || '0');
            return (
              <button
                key={item.key}
                onClick={() => handleSelect(item.key)}
                title={item.tooltip}
                className={`sidebar-nav-btn ${isActive ? 'is-active' : ''}`}
                style={{ opacity: isP4 ? 0.85 : 1 }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: item.dotColor }} />
                  <span style={{ color: isP4 && !isActive ? 'var(--text-muted)' : undefined }}>{item.label}</span>
                </div>
                <span
                  style={{
                    fontSize: '11px',
                    minWidth: '22px',
                    height: '22px',
                    padding: '0 0.45rem',
                    borderRadius: '999px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: isP1WithCount ? 'rgba(244, 63, 94, 0.12)' : 'var(--badge-bg)',
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

        {/* Mobile-Only Account & Operations Section */}
        {isOpenMobile && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)' }}>
            {isAuthenticated ? (
              <>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', padding: '0 0.65rem' }}>
                  Account
                </div>

                <div
                  style={{
                    padding: '0.65rem 0.75rem',
                    backgroundColor: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.25rem',
                  }}
                >
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)', wordBreak: 'break-all' }}>
                    {userEmail || 'Connected'}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.72rem', color: '#22c55e' }}>
                    <ShieldCheck size={12} />
                    <span>Read-Only Session</span>
                  </div>
                </div>

                <button
                  onClick={() => {
                    onCloseMobile?.();
                    onOpenSettings?.();
                  }}
                  className="sidebar-nav-btn"
                  style={{ minHeight: '44px' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <Settings size={16} color="var(--text-secondary)" />
                    <span>Settings &amp; Options</span>
                  </div>
                </button>

                <button
                  onClick={() => {
                    onCloseMobile?.();
                    onRescan?.({ scope: 'mailbox' });
                  }}
                  className="sidebar-nav-btn"
                  style={{ minHeight: '44px' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <RefreshCw size={16} color="var(--accent)" />
                    <span>Full Mailbox Rescan</span>
                  </div>
                </button>

                <button
                  onClick={() => {
                    onCloseMobile?.();
                    auth?.switchAccount?.();
                  }}
                  className="sidebar-nav-btn"
                  style={{ minHeight: '44px' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <RefreshCcw size={16} color="var(--accent)" />
                    <span>Switch Google Account</span>
                  </div>
                </button>

                <button
                  onClick={() => {
                    onCloseMobile?.();
                    auth?.logout?.();
                  }}
                  className="sidebar-nav-btn"
                  style={{ minHeight: '44px', color: 'var(--p1-color)' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <LogOut size={16} />
                    <span>Disconnect</span>
                  </div>
                </button>
              </>
            ) : (
              <button
                onClick={() => {
                  onCloseMobile?.();
                  auth?.login?.();
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  padding: '0.7rem 1rem',
                  backgroundColor: 'var(--accent)',
                  color: '#ffffff',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  minHeight: '44px',
                  cursor: 'pointer',
                  border: 'none',
                }}
              >
                <span>Continue with Google</span>
              </button>
            )}

            {/* Mobile Theme Toggle in Drawer Footer */}
            <button
              onClick={onToggleTheme}
              className="sidebar-nav-btn"
              style={{ minHeight: '44px', marginTop: '0.25rem' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
                <span>Appearance: {theme === 'dark' ? 'Dark Mode' : 'Light Mode'}</span>
              </div>
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

export const Sidebar = React.memo(SidebarComponent);

