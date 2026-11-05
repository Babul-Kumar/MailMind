import React, { useState, useEffect } from 'react';
import { ArrowLeft, X, Calendar, User, Users, ExternalLink, Clock, Check, RotateCcw, AlertTriangle, FileText } from 'lucide-react';
import { PriorityPillPopover } from '../priority/PriorityPillPopover';
import { AIInsight } from '../ai/AIInsight';
import { getDeadlineState, cleanSenderName } from '../../utils/formatting';
import { SnoozeModal } from './SnoozeModal';

export function EmailDetail({
  email,
  onClose,
  onResolve,
  onUnresolve,
  onSnooze,
  isInline = false,
}) {
  const [snoozeOpen, setSnoozeOpen] = useState(false);
  const [localResolved, setLocalResolved] = useState(Boolean(email?.is_resolved));

  useEffect(() => {
    setLocalResolved(Boolean(email?.is_resolved));
  }, [email]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isInline) onClose?.();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, isInline]);

  if (!email) return null;

  const priority = email.effective_priority || email.final_priority || email.predicted_priority || 'P3';
  const topic = email.topic && email.topic !== 'other' && email.topic !== 'general' ? email.topic : null;
  const actionRequired = Boolean(email.action_required);
  const deadlineState = getDeadlineState(email);
  const gmailUrl = `https://mail.google.com/mail/u/0/#all/${email.email_id || ''}`;
  const senderDisplay = cleanSenderName(email.sender);

  const detailContent = (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        backgroundColor: 'var(--bg-main)',
        color: 'var(--text-main)',
        overflow: 'hidden',
      }}
    >
      {/* Top Header Actions Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.65rem 1.25rem',
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-surface)',
          minHeight: '48px',
          flexShrink: 0,
        }}
      >
        {/* Left: Interactive Priority Pill & Popover (Macro UI) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {!isInline && (
            <button
              onClick={onClose}
              className="drawer-back-btn"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                color: 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '0.84rem',
                padding: '0.4rem 0.6rem',
                borderRadius: 'var(--radius-sm)',
                minHeight: '36px',
                cursor: 'pointer',
                border: 'none',
                background: 'transparent',
              }}
            >
              <ArrowLeft size={16} />
              <span>Back</span>
            </button>
          )}

          <PriorityPillPopover
            priority={priority}
            confidence={email.confidence}
            actionReason={email.action_reason}
            messageId={email.email_id || email.id}
            threadId={email.thread_id}
          />

          {topic && (
            <span
              style={{
                fontSize: '0.68rem',
                fontWeight: 500,
                padding: '2px 7px',
                borderRadius: 'var(--radius-xs)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border-subtle)',
                textTransform: 'capitalize',
                backgroundColor: 'var(--bg-input)',
              }}
            >
              {topic}
            </span>
          )}
        </div>

        {/* Right: Quick Action Buttons & Gmail Link */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {localResolved && (
            <button
              onClick={() => {
                setLocalResolved(false);
                onUnresolve?.(email.email_id || email.id);
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.35rem 0.65rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid rgba(34, 197, 94, 0.4)',
                backgroundColor: 'rgba(34, 197, 94, 0.1)',
                color: '#22c55e',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <RotateCcw size={12} />
              <span>Resolved</span>
            </button>
          )}

          <a
            href={gmailUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="detail-open-gmail-btn"
            title="Open thread in Gmail"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--accent)',
              color: '#ffffff',
              fontSize: '0.78rem',
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            <span>Gmail</span>
            <ExternalLink size={12} />
          </a>

          {!isInline && (
            <button
              onClick={onClose}
              className="drawer-close-x"
              aria-label="Close reader"
              title="Close (Esc)"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-muted)',
                padding: '0.4rem',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                background: 'transparent',
                border: 'none',
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Scrollable Reading Pane Body with Generous Typographic Margins */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '1.5rem clamp(1.25rem, 3vw, 2.25rem) 2.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.25rem',
          WebkitOverflowScrolling: 'touch',
        }}
      >
        {/* Subject Heading */}
        <h1
          style={{
            fontSize: '1.28rem',
            fontWeight: 700,
            lineHeight: 1.35,
            color: 'var(--text-main)',
            wordBreak: 'break-word',
            margin: 0,
            letterSpacing: '-0.02em',
          }}
        >
          {email.subject || '(No Subject)'}
        </h1>

        {/* Sender & Metadata Line */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '8px',
            paddingBottom: '0.85rem',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.78rem',
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              {senderDisplay.slice(0, 2).toUpperCase()}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <strong style={{ fontSize: '0.88rem', color: 'var(--text-main)', fontWeight: 600 }}>
                {senderDisplay}
              </strong>
              {email.sender && email.sender !== senderDisplay && (
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                  {email.sender.replace(/<|>/g, '')}
                </span>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {email.date && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <Calendar size={13} />
                <span>{email.date}</span>
              </span>
            )}
          </div>
        </div>

        {/* Deadline or Action Banner if present */}
        {deadlineState && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: deadlineState.state === 'overdue' ? 'rgba(239, 68, 68, 0.08)' : 'rgba(245, 158, 11, 0.08)',
              border: `1px solid ${deadlineState.state === 'overdue' ? 'rgba(239, 68, 68, 0.22)' : 'rgba(245, 158, 11, 0.22)'}`,
              fontSize: '0.8rem',
              fontWeight: 600,
              color: deadlineState.state === 'overdue' ? 'var(--p1-color)' : 'var(--p2-color)',
            }}
          >
            <span>⏰</span>
            <span>{deadlineState.label}</span>
          </div>
        )}

        {/* AI Insight (Why This Matters) */}
        <AIInsight email={email} />

        {/* Inter Font Body Text */}
        <div
          style={{
            fontSize: '0.92rem',
            lineHeight: 1.7,
            color: 'var(--text-main)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            padding: '4px 0',
          }}
        >
          {email.body || '(No textual content found in message payload)'}
        </div>

        {/* Discreet Attachment Card (Apple Mail / Linear design) */}
        {(email.attachments?.length > 0 || email.has_attachment || (email.subject && /invoice|document|contract|statement|report|pdf|spec|proposal/i.test(email.subject))) && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.65rem 0.95rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              width: 'fit-content',
              marginTop: '0.5rem',
              cursor: 'pointer',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div
              style={{
                width: '30px',
                height: '30px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--bg-input)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent)',
              }}
            >
              <FileText size={16} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-main)' }}>
                {email.attachment_name || `${(email.subject || 'document').slice(0, 22).trim().replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf`}
              </span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                PDF Document · 240 KB
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Snooze Modal */}
      {snoozeOpen && (
        <SnoozeModal
          email={email}
          isOpen={snoozeOpen}
          onClose={() => setSnoozeOpen(false)}
          onSnooze={onSnooze}
        />
      )}
    </div>
  );

  if (isInline) {
    return (
      <div style={{ height: '100%', width: '100%', overflow: 'hidden' }}>
        {detailContent}
      </div>
    );
  }

  return (
    <>
      {/* Mobile Drawer Overlay */}
      <div
        className="animate-backdrop-in"
        style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          backdropFilter: 'blur(1px)',
          WebkitBackdropFilter: 'blur(1px)',
          zIndex: 2099,
        }}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className="email-detail email-detail-drawer"
        role="dialog"
        aria-modal="true"
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          height: '100%',
          maxHeight: '100dvh',
          backgroundColor: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border-subtle)',
          boxShadow: 'var(--shadow-drawer)',
          zIndex: 2100,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'slideInRight 0.20s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        aria-label="Email detail drawer"
      >
        {detailContent}
      </aside>
    </>
  );
}

export default EmailDetail;
