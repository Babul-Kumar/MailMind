import React, { useState, useRef, useEffect } from 'react';
import { Sparkles, RefreshCw, Sun, Moon, Settings, Menu, Check, User, LogOut, RefreshCcw, ShieldCheck } from 'lucide-react';
import { SearchBar } from '../inbox/SearchBar';
import { AIProcessingState } from '../ai/AIProcessingState';

export function TopBar({
  searchQuery,
  onSearchChange,
  matchCount,
  isLoading,
  isRefreshing,
  isJustUpdated,
  loadingStep,
  profile,
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
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.75rem 1.5rem',
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        gap: '1rem',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Brand & Mobile Hamburger */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <button
          onClick={onToggleMobileMenu}
          style={{ display: 'none', color: 'var(--text-secondary)' }}
          className="mobile-menu-btn"
          aria-label="Toggle navigation menu"
        >
          <Menu size={20} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
            }}
          >
            <Sparkles size={16} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '1.05rem', fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.1 }}>
              MailMind
            </span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>AI-powered inbox</span>
          </div>
        </div>
      </div>

      {/* Central Search Bar */}
      <SearchBar value={searchQuery} onChange={onSearchChange} matchCount={matchCount} />

      {/* Right Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <AIProcessingState isLoading={isLoading} stepText={loadingStep} />

        {/* Phase 5: Account UI (Proper states: CONNECTED, NO ACCOUNT, ERROR) */}
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

        {/* Primary Mailbox Scan Action Button */}
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
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.45rem 0.85rem',
            backgroundColor: isScanning
              ? 'rgba(239, 68, 68, 0.1)'
              : isJustUpdated
              ? 'var(--accent-light)'
              : 'var(--accent)',
            border: `1px solid ${isScanning ? 'rgba(239, 68, 68, 0.3)' : 'transparent'}`,
            borderRadius: 'var(--radius-md)',
            color: isScanning ? 'var(--p1-color)' : isJustUpdated ? 'var(--accent)' : '#ffffff',
            fontSize: '0.82rem',
            fontWeight: 600,
            cursor: !isAuthenticated ? 'default' : 'pointer',
            opacity: !isAuthenticated ? 0.5 : 1,
            transition: 'all 150ms ease',
          }}
          title={isScanning ? 'Click to cancel current scan' : 'Scan for new and changed messages'}
          aria-label="Mailbox synchronization"
        >
          {isScanning ? (
            <>
              <RefreshCw size={13} className="animate-spin" />
              <span>Cancel Scan ({scanStatus?.progress_percent || 0}%)</span>
            </>
          ) : isJustUpdated ? (
            <>
              <Check size={14} />
              <span>Mailbox Synced</span>
            </>
          ) : !scanStatus || scanStatus.total === 0 ? (
            <>
              <Sparkles size={14} />
              <span>Scan Complete Gmail</span>
            </>
          ) : (
            <>
              <RefreshCw size={14} />
              <span>Sync New &amp; Changed</span>
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
    </header>
  );
}
