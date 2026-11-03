import React, { useState } from 'react';
import { Shield, Lock, ArrowRight, Sparkles, Clock, AlertTriangle, CheckCircle2, Zap, Eye, ChevronRight } from 'lucide-react';
import { MailMindLogo } from '../brand/MailMindLogo';

const DEMO_EMAILS = {
  P1: {
    tier: 'P1 · Critical',
    color: 'var(--p1-color)',
    bg: 'var(--p1-bg)',
    border: 'var(--p1-border)',
    badgeGlow: 'var(--p1-glow)',
    sender: 'DevOps Alerting <alerts@cloud-infra.internal>',
    subject: 'URGENT: Production API cluster latency spike (>2.4s) — P1 Incident #4089',
    time: '4 mins ago',
    snippet: 'Automated health probe failed across us-east regions. Immediate failover required to restore customer gateway SLA.',
    confidence: '98.4%',
    signals: ['immediate failover', 'production api', 'p1 incident', 'latency spike'],
    deadline: 'Immediate Action Required',
  },
  P2: {
    tier: 'P2 · Important',
    color: 'var(--p2-color)',
    bg: 'var(--p2-bg)',
    border: 'var(--p2-border)',
    badgeGlow: 'var(--p2-glow)',
    sender: 'Sarah Jenkins <s.jenkins@clientgroup.com>',
    subject: 'Action Needed: Contract amendment review before 5:00 PM EST',
    time: '42 mins ago',
    snippet: 'Please review the highlighted indemnification terms in Section 4.2 and let us know if we can sign off today.',
    confidence: '92.1%',
    signals: ['action needed', 'review before', 'indemnification', 'sign off'],
    deadline: 'Due Today · 5:00 PM',
  },
  P3: {
    tier: 'P3 · Routine',
    color: 'var(--p3-color)',
    bg: 'var(--p3-bg)',
    border: 'var(--p3-border)',
    badgeGlow: 'var(--p3-glow)',
    sender: 'Engineering Weekly <updates@internal-digest.io>',
    subject: 'Sprint 44 Retrospective Summary & Q4 Roadmap Milestone Status',
    time: '3 hours ago',
    snippet: 'Here is the comprehensive digest of completed epics, documentation updates, and velocity metrics for the week.',
    confidence: '89.6%',
    signals: ['weekly digest', 'retrospective', 'milestone status', 'velocity'],
    deadline: 'No Deadline · Informational',
  },
  P4: {
    tier: 'P4 · Low / Noise',
    color: 'var(--p4-color)',
    bg: 'var(--p4-bg)',
    border: 'var(--p4-border)',
    badgeGlow: 'var(--p4-glow)',
    sender: 'SaaS Deals Newsletter <promotions@growthmarketing.co>',
    subject: '⚡ Exclusive 40% discount on team seats ends this Friday!',
    time: 'Yesterday',
    snippet: 'Upgrade your subscription plan to unlock unlimited collaboration seats and custom branding templates.',
    confidence: '96.2%',
    signals: ['exclusive discount', 'subscription plan', 'promo', 'unsubscribe'],
    deadline: 'Promotional / Deprioritized',
  },
};

export function ConnectAccountHero({ onLogin, isLoading, error }) {
  const [activeDemoTier, setActiveDemoTier] = useState('P1');
  const demoEmail = DEMO_EMAILS[activeDemoTier];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-start',
        width: '100%',
        minHeight: '100%',
        padding: 'clamp(1.5rem, 4vh, 3.5rem) clamp(1rem, 4vw, 2.5rem)',
        background: 'var(--ambient-gradient)',
        overflowY: 'auto',
      }}
    >
      <div
        style={{
          maxWidth: '860px',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '2rem',
        }}
      >
        {/* Top Product Badge */}
        <div
          className="animate-float"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.4rem 0.95rem',
            borderRadius: 'var(--radius-full)',
            background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15))',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            boxShadow: '0 2px 12px rgba(99, 102, 241, 0.15)',
            fontSize: '0.82rem',
            fontWeight: 600,
            color: 'var(--sparkle-color)',
          }}
        >
          <Sparkles size={15} />
          <span>Intelligent Gmail Triage · Powered by priority-v5.1 ML</span>
        </div>

        {/* Hero Title & Pitch */}
        <div style={{ textAlign: 'center', maxWidth: '700px' }}>
          <h1
            style={{
              fontSize: 'clamp(2rem, 5.5vw, 3.1rem)',
              fontWeight: 800,
              letterSpacing: '-0.035em',
              lineHeight: 1.15,
              margin: '0 0 1rem 0',
              color: 'var(--text-main)',
            }}
          >
            Master Your Inbox with{' '}
            <span
              style={{
                background: 'linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #f43f5e 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Machine Intelligence
            </span>
          </h1>
          <p
            style={{
              fontSize: 'clamp(0.95rem, 2.5vw, 1.12rem)',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
              margin: 0,
            }}
          >
            Connect Gmail with read-only security. MailMind parses thousands of emails, spots critical emergencies, tracks upcoming deadlines, and filters out noise in sub-millisecond speeds.
          </p>
        </div>

        {/* Primary CTA Box */}
        <div
          style={{
            width: '100%',
            maxWidth: '460px',
            backgroundColor: 'var(--glass-bg)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: '1px solid var(--border-glow)',
            borderRadius: 'var(--radius-xl)',
            padding: '1.75rem',
            boxShadow: 'var(--shadow-lg), 0 0 30px rgba(99, 102, 241, 0.12)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '1rem',
            textAlign: 'center',
          }}
        >
          {error && (
            <div
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--p1-color)',
                fontSize: '0.84rem',
                textAlign: 'left',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <AlertTriangle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {/* Continue with Google button */}
          <button
            onClick={onLogin}
            disabled={isLoading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.85rem',
              width: '100%',
              padding: '0.85rem 1.4rem',
              minHeight: '52px',
              backgroundColor: '#ffffff',
              color: '#0f172a',
              border: '1px solid rgba(255, 255, 255, 0.9)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.98rem',
              fontWeight: 700,
              cursor: isLoading ? 'default' : 'pointer',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.15)',
              transition: 'all var(--transition-fast)',
              opacity: isLoading ? 0.75 : 1,
            }}
            onMouseEnter={(e) => {
              if (!isLoading) {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 6px 20px rgba(99, 102, 241, 0.3)';
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.15)';
            }}
            aria-label="Connect Gmail with Google"
          >
            {isLoading ? (
              <>
                <div
                  className="animate-spin"
                  style={{
                    width: '18px',
                    height: '18px',
                    border: '2px solid #cbd5e1',
                    borderTopColor: '#4f46e5',
                    borderRadius: '50%',
                  }}
                />
                <span>Connecting to Google...</span>
              </>
            ) : (
              <>
                <svg width="20" height="20" viewBox="0 0 18 18" fill="none">
                  <path
                    d="M17.64 9.20455C17.64 8.56636 17.5827 7.95273 17.4764 7.36364H9V10.845H13.8436C13.635 11.97 13.0009 12.9232 12.0477 13.5614V15.8195H14.9564C16.6582 14.2527 17.64 11.9455 17.64 9.20455Z"
                    fill="#4285F4"
                  />
                  <path
                    d="M9 18C11.43 18 13.4673 17.1941 14.9564 15.8195L12.0477 13.5614C11.2418 14.1014 10.2109 14.4205 9 14.4205C6.65591 14.4205 4.67182 12.8373 3.96409 10.71H0.957275V13.0418C2.43818 15.9832 5.48182 18 9 18Z"
                    fill="#34A853"
                  />
                  <path
                    d="M3.96409 10.71C3.78409 10.17 3.68182 9.59318 3.68182 9C3.68182 8.40682 3.78409 7.83 3.96409 7.29V4.95818H0.957275C0.347727 6.17318 0 7.54773 0 9C0 10.4523 0.347727 11.8268 0.957275 13.0418L3.96409 10.71Z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M9 3.57955C10.3214 3.57955 11.5077 4.03364 12.4405 4.92545L15.0218 2.34409C13.4632 0.891818 11.4259 0 9 0C5.48182 0 2.43818 2.01682 0.957275 4.95818L3.96409 7.29C4.67182 5.16273 6.65591 3.57955 9 3.57955Z"
                    fill="#EA4335"
                  />
                </svg>
                <span>Connect with Gmail</span>
                <ArrowRight size={17} style={{ marginLeft: 'auto', opacity: 0.7 }} />
              </>
            )}
          </button>

          {/* Privacy Trust Note */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.65rem',
              fontSize: '0.78rem',
              color: 'var(--text-muted)',
            }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              <Shield size={13} style={{ color: '#10b981' }} />
              Read-Only Access
            </span>
            <span>·</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              <Lock size={13} style={{ color: '#6366f1' }} />
              Zero Data Stored
            </span>
          </div>
        </div>

        {/* Interactive Live Triage Sandbox Preview */}
        <div
          style={{
            width: '100%',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-xl)',
            padding: '1.5rem',
            boxShadow: 'var(--shadow-md)',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                <Zap size={16} style={{ color: 'var(--accent)' }} />
                Interactive Priority Classification Simulator
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Click below to test how MailMind's machine learning engine analyzes real-world incoming mail.
              </div>
            </div>

            {/* Priority Selector Tabs */}
            <div
              style={{
                display: 'inline-flex',
                background: 'var(--bg-card)',
                padding: '3px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                gap: '3px',
              }}
            >
              {['P1', 'P2', 'P3', 'P4'].map((tierKey) => (
                <button
                  key={tierKey}
                  type="button"
                  onClick={() => setActiveDemoTier(tierKey)}
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    border: 'none',
                    transition: 'all var(--transition-fast)',
                    backgroundColor: activeDemoTier === tierKey ? 'var(--accent)' : 'transparent',
                    color: activeDemoTier === tierKey ? '#ffffff' : 'var(--text-muted)',
                    boxShadow: activeDemoTier === tierKey ? '0 2px 8px rgba(99, 102, 241, 0.4)' : 'none',
                  }}
                >
                  {tierKey}
                </button>
              ))}
            </div>
          </div>

          {/* Simulated Email Card with Micro-Interactions */}
          <div
            className="animate-fade-in"
            key={activeDemoTier}
            style={{
              backgroundColor: 'var(--bg-card)',
              border: `1px solid ${demoEmail.border}`,
              borderLeft: `4px solid ${demoEmail.color}`,
              borderRadius: 'var(--radius-lg)',
              padding: '1.25rem',
              boxShadow: `0 4px 18px ${demoEmail.badgeGlow}`,
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}
          >
            {/* Header: Tier pill + Sender + Time */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    padding: '0.2rem 0.55rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    backgroundColor: demoEmail.bg,
                    color: demoEmail.color,
                    border: `1px solid ${demoEmail.border}`,
                  }}
                >
                  <span
                    className={activeDemoTier === 'P1' ? 'animate-pulse-p1' : ''}
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: demoEmail.color,
                    }}
                  />
                  {demoEmail.tier}
                </span>

                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>
                  {demoEmail.sender}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                <Clock size={13} />
                <span>{demoEmail.time}</span>
              </div>
            </div>

            {/* Subject */}
            <div style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.3 }}>
              {demoEmail.subject}
            </div>

            {/* Snippet */}
            <div style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {demoEmail.snippet}
            </div>

            {/* ML Explainability & Extracted Tokens Footer */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '0.65rem',
                paddingTop: '0.75rem',
                borderTop: '1px solid var(--border-divider)',
                marginTop: '0.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 600 }}>Salient Tokens:</span>
                {demoEmail.signals.map((sig, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: '0.72rem',
                      padding: '0.15rem 0.45rem',
                      borderRadius: 'var(--radius-xs)',
                      backgroundColor: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--text-secondary)',
                      fontFamily: 'monospace',
                    }}
                  >
                    {sig}
                  </span>
                ))}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>
                  Model Confidence: <strong style={{ color: demoEmail.color }}>{demoEmail.confidence}</strong>
                </span>
                <span
                  style={{
                    padding: '0.15rem 0.5rem',
                    borderRadius: 'var(--radius-xs)',
                    backgroundColor: demoEmail.bg,
                    color: demoEmail.color,
                    fontWeight: 600,
                  }}
                >
                  {demoEmail.deadline}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Feature Grid: Why MailMind */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '1rem',
            width: '100%',
          }}
        >
          <div
            style={{
              padding: '1.25rem',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.45rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent)', fontWeight: 700, fontSize: '0.92rem' }}>
              <Zap size={18} />
              <span>Sub-Millisecond Inference</span>
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
              Evaluates emails in 1.35ms without CPU starvation. Entire mailboxes sync incrementally without memory bloat.
            </p>
          </div>

          <div
            style={{
              padding: '1.25rem',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.45rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981', fontWeight: 700, fontSize: '0.92rem' }}>
              <Clock size={18} />
              <span>Dynamic Priority Aging</span>
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
              Expired OTPs and passed deadlines automatically de-escalate so your critical view stays current and actionable.
            </p>
          </div>

          <div
            style={{
              padding: '1.25rem',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.45rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#818cf8', fontWeight: 700, fontSize: '0.92rem' }}>
              <Shield size={18} />
              <span>Strict Privacy By Design</span>
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
              Read-only Gmail scope (`gmail.readonly`). We never modify messages, train external LLMs, or resell user data.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ConnectAccountHero;
