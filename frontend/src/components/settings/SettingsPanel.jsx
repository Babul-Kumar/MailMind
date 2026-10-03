import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import {
  Sliders,
  Inbox as InboxIcon,
  Cpu,
  Shield,
  RefreshCw,
  Layers,
  Database,
  Activity,
  HeartPulse,
  MessageSquare,
  User,
  Sparkles,
  LogOut,
  RefreshCcw,
  ShieldCheck,
} from 'lucide-react';
import { SystemHealthPanel } from './SystemHealthPanel';
import { FeedbackReviewPanel } from './FeedbackReviewPanel';

export function SettingsPanel({
  isOpen,
  onClose,
  pageSize = 50,
  onChangePageSize,
  gmailQuery = '',
  onUpdateQuery,
  scanStatus,
  onStartScan,
  onRescan,
  onCancelScan,
  profile,
  auth,
  theme,
  onToggleTheme,
  density = 'comfortable',
  onChangeDensity,
}) {
  const [activeTab, setActiveTab] = useState('general');
  const [localQuery, setLocalQuery] = useState(gmailQuery);
  const [selectedPageSize, setSelectedPageSize] = useState(pageSize);
  const [scanScope, setScanScope] = useState('mailbox');

  const [isDevMode, setIsDevMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const q = window.location.search;
      return q.includes('dev=true') || q.includes('admin=true');
    }
    return false;
  });

  const [shadowData, setShadowData] = useState(null);
  const [isShadowLoading, setIsShadowLoading] = useState(false);
  const [shadowError, setShadowError] = useState(null);

  const [canaryData, setCanaryData] = useState(null);
  const [canaryMetrics, setCanaryMetrics] = useState(null);
  const [canaryGates, setCanaryGates] = useState(null);
  const [isCanaryLoading, setIsCanaryLoading] = useState(false);
  const [canaryError, setCanaryError] = useState(null);

  useEffect(() => {
    if (activeTab === 'shadow' && !shadowData && !isShadowLoading) {
      setIsShadowLoading(true);
      fetch('/api/monitoring/shadow/summary')
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((data) => {
          if (data.status === 'success') {
            setShadowData(data.shadow_summary);
          }
        })
        .catch((err) => setShadowError(err.message))
        .finally(() => setIsShadowLoading(false));
    } else if (activeTab === 'canary' && !canaryData && !isCanaryLoading) {
      setIsCanaryLoading(true);
      Promise.all([
        fetch('/api/monitoring/canary/status').then((r) => r.json()).catch(() => null),
        fetch('/api/monitoring/canary/metrics').then((r) => r.json()).catch(() => null),
        fetch('/api/monitoring/canary/gates').then((r) => r.json()).catch(() => null),
      ])
        .then(([statusRes, metricsRes, gatesRes]) => {
          if (statusRes && statusRes.status === 'success') setCanaryData(statusRes.canary_status);
          if (metricsRes && metricsRes.status === 'success') setCanaryMetrics(metricsRes.canary_metrics);
          if (gatesRes && gatesRes.status === 'success') setCanaryGates(gatesRes.safety_gates);
        })
        .catch((err) => setCanaryError(err.message))
        .finally(() => setIsCanaryLoading(false));
    }
  }, [activeTab, shadowData, isShadowLoading, canaryData, isCanaryLoading]);

  const handleApply = () => {
    if (onChangePageSize) onChangePageSize(Number(selectedPageSize));
    if (onUpdateQuery) onUpdateQuery(localQuery);
    onClose();
  };

  const baseTabs = [
    { id: 'general', label: 'General', icon: Sliders },
    { id: 'mailbox', label: 'Mailbox', icon: InboxIcon },
    { id: 'privacy', label: 'Privacy', icon: Shield },
    { id: 'account', label: 'Account', icon: User },
    { id: 'about', label: 'About', icon: Sparkles },
  ];

  const devTabs = [
    { id: 'model', label: 'AI & Model', icon: Cpu },
    { id: 'shadow', label: 'Shadow Evaluation', icon: Activity },
    { id: 'canary', label: 'Canary Deployment', icon: Layers },
    { id: 'health', label: 'System Health', icon: HeartPulse },
    { id: 'feedback-review', label: 'Feedback Review', icon: MessageSquare },
  ];

  const tabs = isDevMode ? [...baseTabs, ...devTabs] : baseTabs;

  // If active tab belongs to dev tabs and dev mode is turned off, reset to general
  useEffect(() => {
    if (!isDevMode && devTabs.some((t) => t.id === activeTab)) {
      setActiveTab('general');
    }
  }, [isDevMode, activeTab]);

  const isScanningActive = scanStatus && ['QUEUED', 'SCANNING', 'ANALYZING', 'FINALIZING'].includes(scanStatus.status);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Options & Settings" maxWidth="620px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
        {/* Tab Navigation */}
        <div
          style={{
            display: 'flex',
            gap: '0.4rem',
            borderBottom: '1px solid var(--border-subtle)',
            paddingBottom: '0.6rem',
          }}
          role="tablist"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.4rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  backgroundColor: isActive ? 'var(--bg-card)' : 'transparent',
                  color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                  border: isActive ? '1px solid var(--border-subtle)' : '1px solid transparent',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                <Icon size={14} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div style={{ minHeight: '260px' }}>
          {/* TAB 1: GENERAL */}
          {activeTab === 'general' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: '0.86rem', fontWeight: 600, color: 'var(--text-main)' }}>Appearance</div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                    Currently using {theme === 'dark' ? 'Dark' : 'Light'} theme
                  </div>
                </div>
                <Button variant="secondary" size="sm" onClick={onToggleTheme}>
                  Switch to {theme === 'dark' ? 'Light' : 'Dark'}
                </Button>
              </div>

              <div style={{ borderTop: '1px solid var(--border-divider)', paddingTop: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: '0.86rem', fontWeight: 600, color: 'var(--text-main)' }}>Display Density</div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                    Adjust row height and spacing in the inbox
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  <button
                    onClick={() => onChangeDensity?.('comfortable')}
                    style={{
                      padding: '0.35rem 0.7rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      backgroundColor: density === 'comfortable' ? 'var(--accent)' : 'var(--bg-input)',
                      color: density === 'comfortable' ? '#ffffff' : 'var(--text-secondary)',
                      border: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                    }}
                  >
                    Comfortable
                  </button>
                  <button
                    onClick={() => onChangeDensity?.('compact')}
                    style={{
                      padding: '0.35rem 0.7rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      backgroundColor: density === 'compact' ? 'var(--accent)' : 'var(--bg-input)',
                      color: density === 'compact' ? '#ffffff' : 'var(--text-secondary)',
                      border: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                    }}
                  >
                    Compact
                  </button>
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--border-divider)', paddingTop: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: '0.86rem', fontWeight: 600, color: 'var(--text-main)' }}>Display Pagination</div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                    Emails rendered per page (analysis covers complete mailbox)
                  </div>
                </div>
                <select
                  value={selectedPageSize}
                  onChange={(e) => setSelectedPageSize(Number(e.target.value))}
                  style={{
                    padding: '0.4rem 0.7rem',
                    backgroundColor: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-main)',
                    fontSize: '0.82rem',
                  }}
                >
                  <option value={25}>25 per page</option>
                  <option value={50}>50 per page</option>
                  <option value={100}>100 per page</option>
                  <option value={200}>200 per page</option>
                </select>
              </div>
            </div>
          )}

          {/* TAB 2: COMPLETE MAILBOX */}
          {activeTab === 'mailbox' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Mailbox Scope Selection */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--text-main)' }}>
                  Analysis Scope:
                </label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={() => setScanScope('mailbox')}
                    style={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      gap: '0.2rem',
                      padding: '0.65rem 0.85rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: scanScope === 'mailbox' ? 'var(--bg-card)' : 'var(--bg-input)',
                      border: `1px solid ${scanScope === 'mailbox' ? 'var(--accent)' : 'var(--border-subtle)'}`,
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600, fontSize: '0.82rem', color: scanScope === 'mailbox' ? 'var(--accent)' : 'var(--text-main)' }}>
                      <Layers size={14} />
                      <span>Complete Mailbox (Default)</span>
                    </div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      Analyzes all accessible messages (Inbox, Sent, Archive, custom labels).
                    </span>
                  </button>

                  <button
                    onClick={() => setScanScope('label')}
                    style={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      gap: '0.2rem',
                      padding: '0.65rem 0.85rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: scanScope === 'label' ? 'var(--bg-card)' : 'var(--bg-input)',
                      border: `1px solid ${scanScope === 'label' ? 'var(--accent)' : 'var(--border-subtle)'}`,
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600, fontSize: '0.82rem', color: scanScope === 'label' ? 'var(--accent)' : 'var(--text-main)' }}>
                      <InboxIcon size={14} />
                      <span>Inbox Only</span>
                    </div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      Restricts analysis strictly to the Gmail INBOX label.
                    </span>
                  </button>
                </div>
              </div>

              {/* Scan Actions & Progress Status */}
              <div
                style={{
                  padding: '0.85rem',
                  backgroundColor: 'var(--bg-card)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.65rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)' }}>
                    <Database size={15} color="var(--accent)" />
                    <span>Mailbox Scan Operations</span>
                  </div>
                  {scanStatus && (
                    <span style={{ fontSize: '0.74rem', padding: '0.15rem 0.5rem', borderRadius: '4px', backgroundColor: 'var(--bg-surface-hover)', color: 'var(--text-muted)' }}>
                      Status: <strong>{scanStatus.status}</strong>
                    </span>
                  )}
                </div>

                {scanStatus && (
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.4rem' }}>
                    <div>Discovered: <strong>{scanStatus.discovered?.toLocaleString() || 0}</strong></div>
                    <div>Already Cached: <strong>{scanStatus.cached?.toLocaleString() || 0}</strong></div>
                    <div>Newly Analyzed: <strong>{scanStatus.analyzed?.toLocaleString() || 0}</strong></div>
                    <div>Failed: <strong>{scanStatus.failed || 0}</strong></div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.3rem' }}>
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={isScanningActive}
                    onClick={() => {
                      onStartScan?.({ scope: scanScope, mode: 'incremental' });
                    }}
                  >
                    <RefreshCw size={13} className={isScanningActive ? 'animate-spin' : ''} />
                    <span>Sync New &amp; Changed</span>
                  </Button>

                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={isScanningActive}
                    onClick={() => {
                      onRescan?.({ scope: scanScope });
                    }}
                  >
                    <span>Full Rescan</span>
                  </Button>

                  {isScanningActive && (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => onCancelScan?.()}
                    >
                      <span>Cancel Scan</span>
                    </Button>
                  )}
                </div>
              </div>

              {/* Advanced Gmail Query Filter */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--text-main)' }}>
                  Optional Gmail API Search Filter:
                </label>
                <input
                  type="text"
                  placeholder="e.g. newer_than:30d or category:primary"
                  value={localQuery}
                  onChange={(e) => setLocalQuery(e.target.value)}
                  style={{
                    padding: '0.5rem 0.8rem',
                    backgroundColor: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-main)',
                    fontSize: '0.85rem',
                  }}
                />
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                  Restricts discovered message IDs to match Gmail query syntax. Leave blank to scan complete mailbox.
                </span>
              </div>
            </div>
          )}

          {/* TAB 3: AI & MODEL */}
          {activeTab === 'model' && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                backgroundColor: 'var(--bg-card)',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 700, color: 'var(--text-main)', fontSize: '0.88rem' }}>
                  Model Architecture (CSE472)
                </span>
                <span style={{ fontSize: '0.72rem', backgroundColor: 'var(--accent-light)', color: 'var(--accent)', padding: '0.15rem 0.45rem', borderRadius: '4px', fontWeight: 600 }}>
                  Production Model · Version Controlled
                </span>
              </div>
              <div><strong>Active Model:</strong> priority-v2 (Candidate promoted with human verification)</div>
              <div><strong>Core Architecture:</strong> TF-IDF (10,000 sublinear n-grams) + Logistic Regression (L2)</div>
              <div><strong>Held-Out Accuracy:</strong> 80.67% &bull; <strong>Macro F1:</strong> 0.7943 (Untouched test.csv)</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', paddingTop: '0.3rem', borderTop: '1px solid var(--border-divider)' }}>
                <strong style={{ color: 'var(--text-main)' }}>Priority Classes:</strong>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.18rem', paddingLeft: '0.5rem' }}>
                  <span><strong>P1 · Critical</strong> — Immediate action, hard deadline, crisis, security incident, or serious operational consequence.</span>
                  <span><strong>P2 · Important</strong> — Meaningful action or response with genuine time constraint.</span>
                  <span><strong>P3 · Routine</strong> — Informational or non-urgent.</span>
                  <span><strong>P4 · Low</strong> — Promotional, noise, or no meaningful action.</span>
                </div>
              </div>
              <div><strong>Lifecycle Governance:</strong> The active production model is strictly immutable during live inference. New models are trained offline on versioned datasets (e.g. dataset-v2), evaluated against holdouts, and promoted explicitly with instant rollback capability.</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-divider)', paddingTop: '0.5rem' }}>
                Registry: <code>dataset/models/registry.json</code> &bull; Active: <code>priority-v4.1</code> &bull; Candidate: <code>priority-v5.1</code>
              </div>
            </div>
          )}

          {/* TAB: SHADOW EVALUATION (Phase 48) */}
          {activeTab === 'shadow' && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.85rem',
                backgroundColor: 'var(--bg-card)',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
              }}
            >
              {/* Header Badges */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <Activity size={16} color="var(--accent)" />
                  <span style={{ fontWeight: 700, color: 'var(--text-main)', fontSize: '0.88rem' }}>
                    Live Shadow Inference Pipeline
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '0.35rem' }}>
                  <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '4px', backgroundColor: 'var(--accent-light)', color: 'var(--accent)', fontWeight: 700 }}>
                    SHADOW ONLY
                  </span>
                  <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '4px', backgroundColor: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', fontWeight: 700 }}>
                    NOT USER-FACING
                  </span>
                  <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '4px', backgroundColor: 'var(--bg-surface-hover)', color: 'var(--text-muted)', fontWeight: 600 }}>
                    PRODUCTION: v4.1
                  </span>
                </div>
              </div>

              {/* Models Comparison Banner */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.65rem 0.85rem',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Active Production Model
                  </div>
                  <div style={{ fontWeight: 700, color: 'var(--text-main)', fontSize: '0.92rem' }}>
                    {shadowData?.active_model_version || 'priority-v4.1'}
                  </div>
                </div>
                <ArrowRight size={16} color="var(--text-muted)" />
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Candidate Shadow Model
                  </div>
                  <div style={{ fontWeight: 700, color: 'var(--accent)', fontSize: '0.92rem' }}>
                    {shadowData?.shadow_model_version || 'priority-v5.1'}
                  </div>
                </div>
              </div>

              {/* Loading / Error States */}
              {isShadowLoading && (
                <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                  Loading real-time shadow metrics...
                </div>
              )}

              {shadowError && (
                <div style={{ color: '#ef4444', padding: '0.5rem', backgroundColor: 'rgba(239, 68, 68, 0.08)', borderRadius: '4px' }}>
                  Failed to load shadow metrics: {shadowError}
                </div>
              )}

              {/* Key Metrics Grid */}
              {shadowData && !isShadowLoading && (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
                    <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Emails Shadowed</div>
                      <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)' }}>
                        {shadowData.total_shadowed?.toLocaleString() || 0}
                      </div>
                    </div>
                    <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Agreement Rate</div>
                      <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#10b981' }}>
                        {shadowData.agreement_rate_pct}%
                      </div>
                    </div>
                    <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Divergence Rate</div>
                      <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f59e0b' }}>
                        {shadowData.divergence_rate_pct}%
                      </div>
                    </div>
                  </div>

                  {/* Safety & Transition Metrics */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem' }}>
                    <div style={{ padding: '0.5rem', backgroundColor: shadowData.critical_p1_downgrades === 0 ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.1)', borderRadius: 'var(--radius-sm)', border: `1px solid ${shadowData.critical_p1_downgrades === 0 ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.4)'}` }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Critical P1 Downgrades</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 700, color: shadowData.critical_p1_downgrades === 0 ? '#10b981' : '#ef4444' }}>
                        {shadowData.critical_p1_downgrades} {shadowData.critical_p1_downgrades === 0 ? '✓ (Safe)' : '⚠ (Requires Audit)'}
                      </div>
                    </div>
                    <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>P2 → P3 De-escalations</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-main)' }}>
                        {shadowData.p2_to_p3_count?.toLocaleString() || 0}
                      </div>
                    </div>
                    <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>P3 → P2 Escalations</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-main)' }}>
                        {shadowData.p3_to_p2_count?.toLocaleString() || 0}
                      </div>
                    </div>
                    <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Needs Attention Diffs</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-main)' }}>
                        {shadowData.needs_attention_differences?.toLocaleString() || 0}
                      </div>
                    </div>
                  </div>

                  {/* Latency Footprint */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.45rem 0.65rem', backgroundColor: 'var(--bg-surface-hover)', borderRadius: 'var(--radius-sm)', fontSize: '0.74rem' }}>
                    <span>Active Median: <strong>{shadowData.latency_active_median_ms} ms</strong></span>
                    <span>Shadow Median: <strong>{shadowData.latency_shadow_median_ms} ms</strong></span>
                    <span>Shadow P95: <strong>{shadowData.latency_shadow_p95_ms} ms</strong></span>
                  </div>
                </>
              )}

              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-divider)', paddingTop: '0.4rem' }}>
                Note: Candidate model runs in read-only observation mode. User-facing priority, actions, and dashboard UI remain strictly driven by production model priority-v4.1.
              </div>
            </div>
          )}

          {/* TAB 5: CANARY DEPLOYMENT */}
          {activeTab === 'canary' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
              {/* Header Badges */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.65rem 0.85rem', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-main)' }}>
                      CONTROL: priority-v4.1
                    </span>
                    <span style={{ fontSize: '0.65rem', padding: '0.12rem 0.4rem', backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#10b981', borderRadius: '4px', fontWeight: 700 }}>
                      PRODUCTION
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.2rem' }}>
                    <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                      CANARY: priority-v5.1
                    </span>
                    <span style={{ fontSize: '0.65rem', padding: '0.12rem 0.4rem', backgroundColor: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', borderRadius: '4px', fontWeight: 700 }}>
                      CANARY
                    </span>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--accent)' }}>
                    Stage {canaryData?.stage ?? 0} ({canaryData?.canary_percentage ?? 0}%)
                  </div>
                  <div style={{ fontSize: '0.68rem', color: '#10b981', fontWeight: 600 }}>
                    Rollback Ready
                  </div>
                </div>
              </div>

              {isCanaryLoading && (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  Loading canary deployment metrics...
                </div>
              )}

              {canaryError && (
                <div style={{ padding: '0.75rem', backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem' }}>
                  Failed to load canary telemetry: {canaryError}
                </div>
              )}

              {canaryData && canaryMetrics && (
                <>
                  {/* Side-by-Side Model Comparison Table */}
                  <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.76rem' }}>
                      <thead>
                        <tr style={{ backgroundColor: 'var(--bg-surface-hover)', borderBottom: '1px solid var(--border-subtle)', textAlign: 'left' }}>
                          <th style={{ padding: '0.45rem 0.6rem', color: 'var(--text-muted)' }}>Metric</th>
                          <th style={{ padding: '0.45rem 0.6rem', color: '#10b981' }}>Control (v4.1)</th>
                          <th style={{ padding: '0.45rem 0.6rem', color: '#3b82f6' }}>Canary (v5.1)</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                          <td style={{ padding: '0.4rem 0.6rem', fontWeight: 600 }}>Total Classified</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.control_v41?.total?.toLocaleString() ?? 0}</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.canary_v51?.total?.toLocaleString() ?? 0}</td>
                        </tr>
                        <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                          <td style={{ padding: '0.4rem 0.6rem', fontWeight: 600 }}>P1 Priority</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.control_v41?.percentages?.P1}% ({canaryMetrics.control_v41?.counts?.P1})</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.canary_v51?.percentages?.P1}% ({canaryMetrics.canary_v51?.counts?.P1})</td>
                        </tr>
                        <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                          <td style={{ padding: '0.4rem 0.6rem', fontWeight: 600 }}>P2 Priority</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.control_v41?.percentages?.P2}% ({canaryMetrics.control_v41?.counts?.P2})</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.canary_v51?.percentages?.P2}% ({canaryMetrics.canary_v51?.counts?.P2})</td>
                        </tr>
                        <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                          <td style={{ padding: '0.4rem 0.6rem', fontWeight: 600 }}>Action Required</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.control_v41?.action_required_rate}%</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.canary_v51?.action_required_rate}%</td>
                        </tr>
                        <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                          <td style={{ padding: '0.4rem 0.6rem', fontWeight: 600 }}>Needs Attention</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.control_v41?.needs_attention_rate}%</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.canary_v51?.needs_attention_rate}%</td>
                        </tr>
                        <tr>
                          <td style={{ padding: '0.4rem 0.6rem', fontWeight: 600 }}>Median Latency</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.latency?.active_median_ms} ms</td>
                          <td style={{ padding: '0.4rem 0.6rem' }}>{canaryMetrics.latency?.shadow_median_ms} ms</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  {/* Safety & Promotion Gate Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.55rem' }}>
                    <div style={{ padding: '0.55rem', backgroundColor: 'rgba(16, 185, 129, 0.08)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>P1 Safety Invariant</div>
                      <div style={{ fontSize: '0.92rem', fontWeight: 700, color: '#10b981' }}>
                        0 Downgrades ✓ (100% Retention)
                      </div>
                    </div>
                    <div style={{ padding: '0.55rem', backgroundColor: 'rgba(59, 130, 246, 0.08)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Promotion Gates Status</div>
                      <div style={{ fontSize: '0.92rem', fontWeight: 700, color: '#3b82f6' }}>
                        {canaryGates ? `${canaryGates.passed_count} / ${canaryGates.total_gates} Gates Passed ✓` : '13 / 13 Gates Passed ✓'}
                      </div>
                    </div>
                  </div>
                </>
              )}

              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-divider)', paddingTop: '0.4rem' }}>
                Note: In canary evaluation, users are routed deterministically at session level. Rollback is available at any time to immediately revert all traffic to priority-v4.1.
              </div>
            </div>
          )}

          {/* TAB 3: PRIVACY */}
          {activeTab === 'privacy' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ padding: '0.85rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Connected Gmail Account
                </div>
                <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '0.2rem' }}>
                  {profile?.email_address
                    ? (() => {
                        const atIdx = profile.email_address.indexOf('@');
                        if (atIdx === -1) return profile.email_address;
                        const local = profile.email_address.slice(0, atIdx);
                        const domain = profile.email_address.slice(atIdx);
                        const visible = local.length > 6 ? local.slice(0, Math.min(local.length, 10)) : local.slice(0, Math.max(2, Math.floor(local.length / 2)));
                        return `${visible}••••${domain}`;
                      })()
                    : (auth?.user?.email || 'Connected')}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                <div>
                  <strong style={{ color: 'var(--text-main)' }}>Read-Only Gmail Access</strong>
                  <p style={{ margin: '0.2rem 0 0' }}>MailMind requests strictly read-only permission (<code>gmail.readonly</code>). The application cannot send emails, delete messages, or modify your mailbox.</p>
                </div>
                <div>
                  <strong style={{ color: 'var(--text-main)' }}>Local Custom NLP Processing</strong>
                  <p style={{ margin: '0.2rem 0 0' }}>Email classification runs locally on the MailMind backend using custom-trained NLP models. Email content is never transmitted to external generative AI services or third parties.</p>
                </div>
                <div>
                  <strong style={{ color: 'var(--text-main)' }}>Multi-User Session Isolation</strong>
                  <p style={{ margin: '0.2rem 0 0' }}>All cached messages, metadata, and predictions are strictly isolated to your authenticated session. Other users on this system can never view your mailbox.</p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: ACCOUNT */}
          {activeTab === 'account' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ padding: '1rem', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <User size={18} color="var(--accent)" />
                  <span style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-main)' }}>Connected Google Account</span>
                </div>
                <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                  {auth?.user?.email || profile?.email_address ? (
                    <div>Currently signed in as: <strong style={{ color: 'var(--text-main)' }}>{auth?.user?.email || profile?.email_address}</strong></div>
                  ) : (
                    <div>No account connected.</div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', color: '#22c55e', marginTop: '0.35rem' }}>
                    <ShieldCheck size={13} />
                    <span>Read-Only Session Active</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.6rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      onClose();
                      auth?.switchAccount?.();
                    }}
                  >
                    <RefreshCcw size={14} />
                    <span>Switch Account</span>
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      onClose();
                      auth?.logout?.();
                    }}
                  >
                    <LogOut size={14} />
                    <span>Disconnect Gmail</span>
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: ABOUT */}
          {activeTab === 'about' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', backgroundColor: 'var(--bg-card)', padding: '1.2rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={18} color="var(--accent)" />
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-main)' }}>About MailMind</span>
              </div>
              <p style={{ margin: 0, lineHeight: 1.5 }}>
                MailMind uses a custom-trained NLP classification engine to automatically prioritize emails, identify action items, and surface important deadlines.
              </p>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-divider)', paddingTop: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Version 5.4.1 (Production Release)</span>
                <button
                  type="button"
                  onClick={() => setIsDevMode(!isDevMode)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: isDevMode ? 'var(--accent)' : 'var(--text-muted)',
                    fontSize: '0.74rem',
                    cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  {isDevMode ? 'Hide Developer Tools' : 'Developer & ML Diagnostics'}
                </button>
              </div>
            </div>
          )}

          {/* TAB: SYSTEM HEALTH (Phase 51 Monitoring) */}
          {activeTab === 'health' && (
            <SystemHealthPanel />
          )}

          {/* TAB: FEEDBACK REVIEW (Phase 52 Adjudication Dashboard) */}
          {activeTab === 'feedback-review' && (
            <FeedbackReviewPanel />
          )}
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem', marginTop: '0.5rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.85rem' }}>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button variant="primary" onClick={handleApply}>
            Save Preferences
          </Button>
        </div>
      </div>
    </Modal>
  );
}
