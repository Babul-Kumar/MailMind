import React, { useState, useRef, useEffect } from 'react';
import { RefreshCw, Sun, Moon, Settings, Menu, Check, User, LogOut, RefreshCcw, ShieldCheck, Sparkles } from 'lucide-react';
import { SearchBar } from '../inbox/SearchBar';
import { AIProcessingState } from '../ai/AIProcessingState';
import { MailMindLogo } from '../brand/MailMindLogo';

function TopBarComponent({
  searchQuery,
  onSearchChange,
  matchCount,
  isLoading,
  isRefreshing,
  isJustUpdated,
  loadingStep,
  profile,
  stats,
  auth,
  onRefresh,
  scanStatus,
  isScanning,
  onStartScan,
  onCancelScan,
  onRescan,
  theme,
  onToggleTheme,
  onOpenSettings,
  onToggleMobileMenu,
}) {
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef(null);

  // Close account menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (accountMenuRef.current && !accountMenuRef.current.contains(e.target)) {
        setAccountMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const userEmail = auth?.user?.email || profile?.email_address;
  const isAuthenticated = auth?.isAuthenticated || Boolean(userEmail);
  const authError = auth?.error;

  return (
    <header className="topbar-header">
      {/* 1. Dedicated Mobile Header: Row 1 (<= 640px) */}
      <div className="topbar-mobile-row-1">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <button
            onClick={onToggleMobileMenu}
            className="mobile-menu-btn"
            aria-label="Toggle navigation menu"
            style={{ display: 'inline-flex' }}
          >
            <Menu size={22} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <MailMindLogo size={24} isScanning={isScanning} />
            <span style={{ fontSize: '1.05rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-main)', lineHeight: 1 }}>
              MailMind
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <AIProcessingState isLoading={isLoading} stepText={loadingStep} />

          {isAuthenticated ? (
            <button
              onClick={onToggleMobileMenu}
              title={userEmail ? `Connected: ${userEmail}` : 'Account options'}
              aria-label="Open account navigation"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.35rem 0.55rem',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--bg-surface-hover)',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.74rem',
                color: 'var(--text-secondary)',
                minHeight: '38px',
                cursor: 'pointer',
              }}
            >
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  backgroundColor: '#22c55e',
                  boxShadow: '0 0 6px rgba(34, 197, 94, 0.5)',
                }}
              />
              <User size={14} />
            </button>
          ) : authError ? (
            <button
              onClick={() => auth?.login?.()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                padding: '0.35rem 0.65rem',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--p1-color)',
                fontSize: '0.75rem',
                fontWeight: 600,
                minHeight: '38px',
                cursor: 'pointer',
              }}
            >
              <span>Reconnect</span>
            </button>
          ) : (
            <button
              onClick={() => auth?.login?.()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.38rem 0.8rem',
                backgroundColor: 'var(--accent)',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                color: '#ffffff',
                fontSize: '0.78rem',
                fontWeight: 600,
                minHeight: '38px',
                cursor: 'pointer',
              }}
              aria-label="Sign in with Google"
            >
              <span>Sign in</span>
            </button>
          )}

          <button
            onClick={onToggleTheme}
            style={{
              padding: '0.4rem',
              color: 'var(--text-secondary)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minWidth: '38px',
              minHeight: '38px',
              cursor: 'pointer',
            }}
            title="Appearance"
            aria-label={`Appearance: switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>
      </div>

      {/* 2. Dedicated Mobile Header: Row 2 Full-Width Search (<= 640px) */}
      <div className="topbar-mobile-row-2">
        <SearchBar value={searchQuery} onChange={onSearchChange} matchCount={matchCount} />
      </div>

      {/* 3. Desktop Single-Row Layout (> 640px) */}
      <div className="topbar-desktop-row">
        {/* Brand & Mobile Hamburger */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={onToggleMobileMenu}
            className="mobile-menu-btn"
            aria-label="Toggle navigation menu"
          >
            <Menu size={20} />
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <MailMindLogo size={28} isScanning={isScanning} />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span className="topbar-brand-title" style={{ fontSize: '1.02rem', fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                MailMind
              </span>
              <span className="topbar-brand-sub topbar-brand-subtitle" style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Intelligent inbox</span>
            </div>
          </div>
        </div>

        {/* Central Search Bar */}
        <SearchBar value={searchQuery} onChange={onSearchChange} matchCount={matchCount} />

        {/* Right Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <AIProcessingState isLoading={isLoading} stepText={loadingStep} />

          {/* Account UI */}
          {isAuthenticated ? (
            <div style={{ position: 'relative' }} ref={accountMenuRef}>
              <button
                onClick={() => setAccountMenuOpen((prev) => !prev)}
                title={userEmail ? `Connected as ${userEmail} (Read-Only)` : 'Gmail connected'}
                aria-label="Account options menu"
                aria-expanded={accountMenuOpen}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  fontSize: '0.78rem',
                  color: 'var(--text-secondary)',
                  padding: '0.35rem 0.65rem',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: accountMenuOpen ? 'var(--bg-surface-hover)' : 'transparent',
                  border: '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: '#22c55e',
                    boxShadow: '0 0 8px rgba(34, 197, 94, 0.4)',
                  }}
                />
                <span className="desktop-status-label" style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {userEmail || 'Connected'}
                </span>
              </button>

              {/* Account Dropdown Menu */}
              {accountMenuOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 6px)',
                    right: 0,
                    width: '240px',
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    boxShadow: 'var(--shadow-md)',
                    padding: '0.5rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.25rem',
                    zIndex: 100,
                    animation: 'fadeIn 0.15s ease',
                  }}
                >
                  <div style={{ padding: '0.5rem 0.65rem', borderBottom: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                      Google Account
                    </div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)', wordBreak: 'break-all' }}>
                      {userEmail}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem', color: '#22c55e', marginTop: '0.2rem' }}>
                      <ShieldCheck size={12} />
                      <span>Read-Only Session</span>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setAccountMenuOpen(false);
                      onRescan?.({ scope: 'mailbox' });
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.45rem 0.65rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.8rem',
                      color: 'var(--text-main)',
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                      transition: 'background-color var(--transition-fast)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <RefreshCw size={14} color="var(--accent)" />
                    <span>Full Mailbox Rescan</span>
                  </button>

                  <button
                    onClick={() => {
                      setAccountMenuOpen(false);
                      auth?.switchAccount?.();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.45rem 0.65rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.8rem',
                      color: 'var(--text-main)',
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                      transition: 'background-color var(--transition-fast)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <RefreshCcw size={14} color="var(--accent)" />
                    <span>Switch Google account</span>
                  </button>

                  <button
                    onClick={() => {
                      setAccountMenuOpen(false);
                      auth?.logout?.();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.45rem 0.65rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.8rem',
                      color: 'var(--p1-color)',
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                      transition: 'background-color var(--transition-fast)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.08)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <LogOut size={14} />
                    <span>Disconnect</span>
                  </button>
                </div>
              )}
            </div>
          ) : authError ? (
            <button
              onClick={() => auth?.login?.()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.35rem 0.75rem',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--p1-color)',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <span>Reconnect</span>
            </button>
          ) : (
            <button
              onClick={() => auth?.login?.()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                padding: '0.35rem 0.75rem',
                backgroundColor: 'var(--accent)',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                color: '#ffffff',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <span>Continue with Google</span>
            </button>
          )}

          {/* Live Background Scan Progress Banner / Pill */}
          {scanStatus && ['QUEUED', 'SCANNING', 'ANALYZING', 'FINALIZING'].includes(scanStatus.status) && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                padding: '0.35rem 0.75rem',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'rgba(99, 102, 241, 0.12)',
                border: '1px solid rgba(99, 102, 241, 0.25)',
                fontSize: '0.78rem',
                color: 'var(--accent)',
                fontWeight: 600,
              }}
            >
              <RefreshCw size={13} className="animate-spin" />
              <span>
                {scanStatus.status === 'SCANNING'
                  ? `Scanning Gmail... ${scanStatus.discovered?.toLocaleString() || 0} discovered`
                  : scanStatus.status === 'ANALYZING'
                  ? `Analyzing: ${scanStatus.analyzed?.toLocaleString() || 0} / ${scanStatus.total?.toLocaleString() || 0} (${scanStatus.progress_percent || 0}%)`
                  : 'Finalizing Mailbox...'}
              </span>
            </div>
          )}

          {/* Subtle Compact Sync Status */}
          {isAuthenticated && !isScanning && (stats?.total_analyzed > 0 || profile?.messages_total > 0) && (
            <div
              className="desktop-sync-status"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                padding: '0.24rem 0.5rem',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--badge-bg)',
                fontSize: '0.74rem',
                color: 'var(--text-muted)',
                fontWeight: 500,
                whiteSpace: 'nowrap',
              }}
              title={`${(stats?.total_analyzed || profile?.messages_total || 0).toLocaleString()} messages synchronized`}
            >
              <span style={{ color: '#22c55e', fontWeight: 700 }}>✓</span>
              <span>Synced</span>
            </div>
          )}

          {/* Primary Mailbox Sync Action Button */}
          <button
            onClick={() => {
              if (isScanning) {
                onCancelScan?.();
              } else if (!scanStatus || scanStatus.total === 0) {
                onStartScan?.({ scope: 'mailbox', mode: 'full' });
              } else {
                onStartScan?.({ scope: 'mailbox', mode: 'incremental' });
              }
            }}
            disabled={!isAuthenticated}
            className="topbar-sync-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.45rem',
              padding: '0.42rem 0.85rem',
              minWidth: '150px',
              backgroundColor: isScanning
                ? 'rgba(239, 68, 68, 0.08)'
                : isJustUpdated
                ? 'var(--accent-light)'
                : 'var(--accent)',
              border: `1px solid ${isScanning ? 'rgba(239, 68, 68, 0.25)' : 'transparent'}`,
              borderRadius: 'var(--radius-md)',
              color: isScanning ? 'var(--p1-color)' : isJustUpdated ? 'var(--accent)' : '#ffffff',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: !isAuthenticated ? 'default' : 'pointer',
              opacity: !isAuthenticated ? 0.5 : 1,
              transition: 'all var(--transition-fast)',
              whiteSpace: 'nowrap',
            }}
            title={isScanning ? 'Click to cancel current scan' : 'Scan for new and changed messages'}
            aria-label="Mailbox synchronization"
          >
            {isScanning ? (
              <>
                <RefreshCw size={13} className="animate-spin" />
                <span className="topbar-sync-text">Syncing...</span>
              </>
            ) : isJustUpdated ? (
              <>
                <Check size={13} />
                <span className="topbar-sync-text">Updated</span>
              </>
            ) : !scanStatus || scanStatus.total === 0 ? (
              <>
                <Sparkles size={13} />
                <span className="topbar-sync-text">Scan Complete Gmail</span>
              </>
            ) : (
              <>
                <RefreshCw size={13} />
                <span className="topbar-sync-text">Sync New &amp; Changed</span>
              </>
            )}
          </button>

          {/* Theme Toggle Button */}
          <button
            onClick={onToggleTheme}
            style={{
              padding: '0.45rem',
              color: 'var(--text-secondary)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
            }}
            title="Appearance"
            aria-label={`Appearance: switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>

          {/* Settings Button */}
          <button
            onClick={onOpenSettings}
            style={{
              padding: '0.45rem',
              color: 'var(--text-secondary)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
            }}
            title="Settings"
            aria-label="Settings"
          >
            <Settings size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}

export const TopBar = React.memo(TopBarComponent);

