import React from 'react';
import { Mail, Zap, History, X, Settings, RefreshCw, RefreshCcw, LogOut, ShieldCheck, User, Sun, Moon, Sparkles } from 'lucide-react';
import { MailMindLogo } from '../brand/MailMindLogo';

function SidebarComponent({
  activeFilter,
  onSelectFilter,
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
  const userEmail = auth?.user?.email || profile?.email_address;
  const isAuthenticated = auth?.isAuthenticated || Boolean(userEmail);

  const mailboxItems = [
    {
      key: 'ALL',
      label: 'All Mail',
      icon: <Mail size={16} />,
      count: totalCount || 0,
      tooltip: `${(totalCount || 0).toLocaleString()} emails in active analysis period`,
    },
    {
      key: 'HISTORY',
      label: 'All History',
      icon: <History size={16} />,
      count: stats?.total_emails || totalCount || 0,
      tooltip: 'Browse all older synchronized messages with date filtering',
    },
  ];

  const priorityItems = [
    { key: 'P1', label: 'P1 · Critical', count: counts.P1 || 0, dotColor: 'var(--p1-color)', glow: 'var(--p1-glow)', bg: 'rgba(255, 51, 102, 0.12)', activeBorder: 'rgba(255, 51, 102, 0.3)', activeBar: 'var(--p1-color)', tooltip: 'Immediate action, hard deadline, or critical operational consequence.' },
    { key: 'P2', label: 'P2 · Important', count: counts.P2 || 0, dotColor: 'var(--p2-color)', glow: 'var(--p2-glow)', bg: 'rgba(245, 158, 11, 0.12)', activeBorder: 'rgba(245, 158, 11, 0.3)', activeBar: 'var(--p2-color)', tooltip: 'Important emails classified by the model; not all require action.' },
    { key: 'P3', label: 'P3 · Routine', count: counts.P3 || 0, dotColor: 'var(--p3-color)', glow: 'var(--p3-glow)', bg: 'rgba(56, 189, 248, 0.12)', activeBorder: 'rgba(56, 189, 248, 0.25)', activeBar: 'var(--p3-color)', tooltip: 'Informational or routine operational correspondence.' },
    { key: 'P4', label: 'P4 · Low', count: counts.P4 || 0, dotColor: 'var(--p4-color)', glow: 'var(--p4-glow)', bg: 'rgba(148, 163, 184, 0.10)', activeBorder: 'rgba(148, 163, 184, 0.2)', activeBar: 'var(--p4-color)', tooltip: 'Promotional, bulk notifications, or low priority.' },
  ];

  const handleSelect = (key) => {
    onSelectFilter(key);
    if (isOpenMobile) onCloseMobile?.();
  };

  return (
    <aside
      className={`sidebar-container ${isOpenMobile ? 'mobile-open' : ''}`}
      style={{
        width: '235px',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.25rem 0.85rem',
        flexShrink: 0,
        overflowY: 'auto',
        boxShadow: '2px 0 16px rgba(0,0,0,0.08)',
      }}
      aria-label="Sidebar navigation"
    >
      {/* Mobile Drawer Header */}
      {isOpenMobile ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.25rem 0.4rem 0.85rem',
            borderBottom: '1px solid var(--border-divider)',
            marginBottom: '0.85rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
            <MailMindLogo size={26} isScanning={isScanning} />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.025em', lineHeight: 1.1 }}>
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
      ) : (
        /* Desktop Top Branding Header */
        <div
          className="sidebar-desktop-brand"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            padding: '0.25rem 0.45rem 1rem',
            borderBottom: '1px solid var(--border-divider)',
            marginBottom: '0.65rem',
          }}
        >
          <div
            style={{
              padding: '2px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(168, 85, 247, 0.25))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MailMindLogo size={28} isScanning={isScanning} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.025em', lineHeight: 1.15 }}>
              MailMind
            </span>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)', fontWeight: 500 }}>
              AI Priority Engine
            </span>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', flex: 1 }}>
        {/* Mailbox Section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <div style={{ fontSize: '0.70rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', padding: '0 0.65rem 0.35rem' }}>
            Mailbox
          </div>
          {mailboxItems.map((item) => {
            const isActive = activeFilter === item.key;
            const formattedCount = typeof item.count === 'number' ? item.count.toLocaleString() : (item.count || '0');
            return (
              <button
                key={item.key}
                onClick={() => handleSelect(item.key)}
                title={item.tooltip}
                className={`sidebar-nav-btn ${isActive ? 'is-active' : ''}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  transition: 'all var(--transition-fast)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  <span style={{ color: isActive ? 'var(--accent)' : 'var(--text-muted)', display: 'flex' }}>
                    {item.icon}
                  </span>
                  <span style={{ fontWeight: isActive ? 600 : 500 }}>{item.label}</span>
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
                    backgroundColor: isActive ? 'var(--accent-light)' : 'var(--badge-bg)',
                    color: isActive ? 'var(--accent)' : 'var(--text-muted)',
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
          <div style={{ fontSize: '0.70rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', padding: '0 0.65rem 0.35rem' }}>
            Priority Tiers
          </div>
          {priorityItems.map((item) => {
            const isActive = activeFilter === item.key;
            const isP1WithCount = item.key === 'P1' && item.count > 0;
            const isP4 = item.key === 'P4';
            const formattedCount = typeof item.count === 'number' ? item.count.toLocaleString() : (item.count || '0');
            return (
              <button
                key={item.key}
                onClick={() => handleSelect(item.key)}
                title={item.tooltip}
                className={`sidebar-nav-btn ${isActive ? 'is-active' : ''}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.52rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  opacity: isP4 ? 0.85 : 1,
                  transition: 'all var(--transition-fast)',
                  background: isActive ? `linear-gradient(90deg, ${item.bg} 0%, transparent 100%)` : undefined,
                  borderColor: isActive ? item.glow : undefined,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  <span
                    className={isP1WithCount ? 'animate-pulse-p1' : ''}
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: item.dotColor,
                      boxShadow: isActive ? `0 0 10px ${item.dotColor}, 0 0 4px ${item.dotColor}` : isP1WithCount ? `0 0 6px ${item.dotColor}` : 'none',
                      flexShrink: 0,
                      transition: 'box-shadow var(--transition-fast)',
                    }}
                  />
                  <span style={{
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? item.dotColor : isP4 && !isActive ? 'var(--text-muted)' : 'var(--text-secondary)',
                    transition: 'color var(--transition-fast)',
                  }}>
                    {item.label}
                  </span>
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
                    backgroundColor: isActive ? item.bg : isP1WithCount ? 'rgba(255, 51, 102, 0.15)' : 'var(--badge-bg)',
                    color: isActive || isP1WithCount ? item.dotColor : 'var(--text-muted)',
                    fontWeight: item.count > 0 ? 700 : 500,
                    border: isActive ? `1px solid ${item.glow}` : '1px solid transparent',
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  {formattedCount}
                </span>
              </button>
            );
          })}
        </div>

        {/* Desktop Sidebar Bottom Utilities */}
        <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border-divider)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          {isAuthenticated && userEmail && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.55rem',
                padding: '0.5rem 0.65rem',
                borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, var(--bg-card) 0%, rgba(99, 102, 241, 0.05) 100%)',
                border: '1px solid var(--border-subtle)',
                marginBottom: '0.35rem',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  flexShrink: 0,
                  boxShadow: '0 2px 8px rgba(99, 102, 241, 0.35)',
                }}
              >
                {userEmail.slice(0, 1).toUpperCase()}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 }}>
                <span style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {userEmail}
                </span>
                <span style={{ fontSize: '0.63rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '3px', fontWeight: 600 }}>
                  <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block', boxShadow: '0 0 6px rgba(16, 185, 129, 0.5)' }} />
                  Active · Read-Only
                </span>
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={onOpenSettings}
            className="sidebar-nav-btn"
            style={{
              padding: '0.45rem 0.65rem',
              fontSize: '0.8rem',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
              <Settings size={15} style={{ color: 'var(--text-muted)' }} />
              <span>Settings</span>
            </div>
          </button>

          <button
            type="button"
            onClick={onToggleTheme}
            className="sidebar-nav-btn"
            style={{
              padding: '0.45rem 0.65rem',
              fontSize: '0.8rem',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
              {theme === 'dark' ? <Sun size={15} style={{ color: '#f59e0b' }} /> : <Moon size={15} style={{ color: '#6366f1' }} />}
              <span>{theme === 'dark' ? 'Light Theme' : 'Dark Theme'}</span>
            </div>
          </button>
        </div>
      </div>
    </aside>
  );
}

export const Sidebar = React.memo(SidebarComponent);
export default Sidebar;
