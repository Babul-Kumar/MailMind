import React, { useEffect } from 'react';
import { ArrowLeft, X, Calendar, User, Users, ExternalLink } from 'lucide-react';
import { PriorityBadge } from '../priority/PriorityBadge';
import { AIInsight } from '../ai/AIInsight';
import { getDeadlineState, cleanSenderName } from '../../utils/formatting';
import { FeedbackWidget } from './FeedbackWidget';

export function EmailDetail({ email, onClose }) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!email) return null;

  const priority = email.final_priority || email.predicted_priority;
  const topic = email.topic && email.topic !== 'other' && email.topic !== 'general' ? email.topic : null;
  const actionRequired = Boolean(email.action_required);
  const deadlineState = getDeadlineState(email);
  const gmailUrl = `https://mail.google.com/mail/u/0/#all/${email.email_id || ''}`;
  const senderDisplay = cleanSenderName(email.sender);

  return (
    <>
      {/* Overlay — subtle dark overlay, low blur so inbox remains crisp & recognizable */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.25)',
          backdropFilter: 'blur(0.5px)',
          zIndex: 1500,
        }}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Detail Drawer */}
      <aside
        className="email-detail-drawer"
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          height: '100%',
          backgroundColor: 'var(--bg-surface)',
          color: 'var(--text-main)',
          borderLeft: '1px solid var(--border-subtle)',
          boxShadow: 'var(--shadow-drawer)',
          zIndex: 1501,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'slideInRight 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        aria-label="Email detail drawer"
      >
        {/* Navigation Bar: Mobile Back button / Desktop Close X (Phase 23) */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.65rem 1.25rem',
            borderBottom: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-surface)',
            minHeight: '44px',
          }}
        >
          {/* Mobile Back Control */}
          <button
            onClick={onClose}
            className="drawer-back-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              color: 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '0.84rem',
              padding: '0.4rem 0.6rem',
              borderRadius: 'var(--radius-sm)',
              minHeight: '36px',
            }}
          >
            <ArrowLeft size={16} />
            <span>Back to inbox</span>
          </button>

          {/* Desktop Close X */}
          <button
            onClick={onClose}
            className="drawer-close-x"
            aria-label="Close drawer"
            title="Close (Esc)"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              padding: '0.4rem',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              marginLeft: 'auto',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Structured Header Card (Phase 10 & 24) */}
        <div
          style={{
            padding: '1.1rem 1.25rem 0.95rem',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.65rem',
          }}
        >
          {/* 1. Priority + subtle topic (Phase 10 & 11) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <PriorityBadge priority={priority} showLabel={true} size="md" />
            {topic && (
              <span
                style={{
                  fontSize: '0.68rem',
                  fontWeight: 500,
                  padding: '0.12rem 0.45rem',
                  borderRadius: 'var(--radius-xs)',
                  color: 'var(--text-muted)',
                  border: '1px solid var(--border-subtle)',
                  textTransform: 'capitalize',
                  opacity: 0.75,
                }}
              >
                {topic}
              </span>
            )}
            <div style={{ marginLeft: 'auto' }}>
              <FeedbackWidget
                messageId={email.email_id || email.id}
                currentPriority={priority}
                confidence={email.confidence}
                topic={email.topic}
                threadId={email.thread_id}
                deadlineDetected={Boolean(email.deadline_detected)}
                actionRequired={actionRequired}
                compact={false}
                showAccept={true}
              />
            </div>
          </div>

          {/* 2. Subject */}
          <h2
            style={{
              fontSize: '1.15rem',
              fontWeight: 700,
              lineHeight: 1.35,
              color: 'var(--text-main)',
              wordBreak: 'break-word',
              margin: 0,
            }}
          >
            {email.subject || '(No Subject)'}
          </h2>

          {/* 3. Sender */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.84rem' }}>
            <User size={14} color="var(--text-muted)" style={{ flexShrink: 0 }} />
            <strong style={{ color: 'var(--text-main)', wordBreak: 'break-word' }}>
              {senderDisplay}
            </strong>
            {email.sender && email.sender !== senderDisplay && (
              <span style={{ color: 'var(--text-muted)', fontSize: '0.76rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                &lt;{email.sender.replace(/<|>/g, '')}&gt;
              </span>
            )}
          </div>

          {/* 4. Deadline + Action Signals (Stacked cleanly per Phase 10) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.15rem' }}>
            {deadlineState && (() => {
              const isHistorical = email.deadline_status === 'HISTORICAL' || deadlineState.state === 'historical';
              const isExpiredOtp = (deadlineState.state === 'overdue' || email.deadline_status === 'EXPIRED') && (
                email.action_reason === 'Immediate verification required' ||
                email.action_reason === 'Account security action' ||
                email.deadline_status === 'EXPIRED' ||
                (email.subject && /otp|verification\s*code|one-time\s*password|login\s*code/i.test(email.subject))
              );

              const isMuted = isHistorical || isExpiredOtp;
              const icon = isHistorical ? '📅' : (isExpiredOtp ? '⌛' : deadlineState.icon);
              let label = isExpiredOtp ? 'Expired verification code' : deadlineState.label;
              if (isHistorical && label.startsWith('Overdue · ')) {
                label = label.replace('Overdue · ', 'Past · ');
              }

              return (
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    color: isMuted ? 'var(--text-muted)' : deadlineState.state === 'overdue' ? 'var(--p1-color)' : 'var(--p2-color)',
                    backgroundColor: isMuted ? 'var(--bg-surface-hover)' : deadlineState.state === 'overdue' ? 'rgba(239, 68, 68, 0.08)' : 'rgba(245, 158, 11, 0.1)',
                    border: `1px solid ${isMuted ? 'var(--border-subtle)' : deadlineState.state === 'overdue' ? 'rgba(239, 68, 68, 0.25)' : 'rgba(245, 158, 11, 0.3)'}`,
                    padding: '0.25rem 0.6rem',
                    borderRadius: 'var(--radius-xs)',
                    width: 'fit-content',
                  }}
                >
                  <span>{icon}</span>
                  <span>{label}</span>
                </div>
              );
            })()}

            {actionRequired && (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  fontSize: '0.76rem',
                  fontWeight: 600,
                  color: email.action_reason === 'Account security action' ? 'var(--p1-color)' : 'var(--accent)',
                  backgroundColor: email.action_reason === 'Account security action' ? 'rgba(239, 68, 68, 0.08)' : 'var(--accent-light)',
                  border: `1px solid ${email.action_reason === 'Account security action' ? 'rgba(239, 68, 68, 0.25)' : 'rgba(99, 102, 241, 0.3)'}`,
                  padding: '0.22rem 0.55rem',
                  borderRadius: 'var(--radius-xs)',
                  width: 'fit-content',
                }}
              >
                <span>●</span>
                <span>{email.action_reason || 'Action required'}</span>
              </div>
            )}
          </div>

          {/* 5. Open in Gmail Button (Touch friendly, stacked per Phase 10) */}
          <a
            href={gmailUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.45rem',
              padding: '0.55rem 1rem',
              minHeight: '40px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--accent)',
              color: '#ffffff',
              fontSize: '0.84rem',
              fontWeight: 600,
              textDecoration: 'none',
              marginTop: '0.35rem',
              transition: 'background-color var(--transition-fast)',
            }}
          >
            <span>Open in Gmail</span>
            <ExternalLink size={14} />
          </a>
        </div>

        {/* Scrollable content body: Recipient, AI Insight, Email Content (natural height) */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1.15rem 1.25rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.15rem',
          }}
        >
          {email.recipients && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              <Users size={13} color="var(--text-muted)" />
              <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>To:</span>
              <span style={{ wordBreak: 'break-word' }}>{email.recipients}</span>
            </div>
          )}

          {email.date && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <Calendar size={13} color="var(--text-muted)" />
              <span>Received: {email.date}</span>
            </div>
          )}

          {/* AI Insight (Why This Matters) */}
          <AIInsight email={email} />

          {/* Email Body — sizes naturally without large empty fixed minimum height (Phase 22) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <div
              style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Email Content
            </div>
            <div
              style={{
                padding: '1rem 1.1rem',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.88rem',
                lineHeight: 1.65,
                color: 'var(--text-main)',
                whiteSpace: 'pre-wrap',
                overflowWrap: 'break-word',
                wordBreak: 'break-word',
              }}
            >
              {email.body || '(No textual content found in message payload)'}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

