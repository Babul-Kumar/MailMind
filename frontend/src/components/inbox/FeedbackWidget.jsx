import React, { useState } from 'react';
import { ChevronDown, Loader, Check, AlertCircle, HelpCircle, ThumbsUp } from 'lucide-react';

/* -------------------------------------------------------------------------
 * FeedbackWidget — Phase 53 Production Feedback UX
 *
 * Lightweight, non-intrusive inline feedback widget.
 * Usable from email rows, email detail drawers, desktop and mobile.
 *
 * Design constraints:
 *   - No ML jargon ("model training", "weights", "fine-tuning").
 *   - 2-step compact interaction:
 *       1. "What was wrong?" (priority too high/low, action, deadline, other)
 *       2. "Correct priority": [P1] [P2] [P3] [P4] + [Not sure]
 *   - Quick confirm option ("Looks right" / ACCEPT)
 *   - Easy cancel without submission
 *   - Double-click / retry protection (disables during and immediately after submission)
 *   - Never sends raw email body, OAuth tokens, or credentials
 *   - Server resolves user identity and production model version
 * -------------------------------------------------------------------------*/

const PRIORITY_OPTIONS = [
  { value: 'P1', label: 'P1 — Urgent / Critical', short: 'P1' },
  { value: 'P2', label: 'P2 — Action Required', short: 'P2' },
  { value: 'P3', label: 'P3 — Informational', short: 'P3' },
  { value: 'P4', label: 'P4 — Low Priority', short: 'P4' },
];

const REASON_OPTIONS = [
  { value: 'priority_too_high', label: 'Priority too high' },
  { value: 'priority_too_low', label: 'Priority too low' },
  { value: 'action_misunderstood', label: 'Action requirement misread' },
  { value: 'deadline_misunderstood', label: 'Deadline misunderstood' },
  { value: 'context_missing', label: 'Missing context' },
  { value: 'other', label: 'Other' },
];

const PRIORITY_COLOUR = {
  P1: '#ef4444',
  P2: '#f97316',
  P3: '#3b82f6',
  P4: '#6b7280',
};

/**
 * FeedbackWidget
 *
 * Props:
 *   messageId        {string}  required — the email's unique message ID
 *   currentPriority  {string}  optional — displayed priority (P1-P4)
 *   confidence       {number}  optional — model confidence (0-1)
 *   topic            {string}  optional — topic label
 *   threadId         {string}  optional — thread identifier
 *   deadlineDetected {bool}    optional — deadline detected flag
 *   actionRequired   {bool}    optional — action required flag
 *   compact          {bool}    optional — compact icon/pill mode
 *   showAccept       {bool}    optional — offer quick "Looks right" action
 */
export function FeedbackWidget({
  messageId,
  currentPriority = 'P3',
  confidence = null,
  topic = null,
  threadId = null,
  deadlineDetected = false,
  actionRequired = false,
  compact = false,
  showAccept = false,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [selectedPriority, setSelectedPriority] = useState('');
  const [isNotSure, setIsNotSure] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null); // 'success' | 'error' | null

  if (!messageId) return null;

  const handleReset = () => {
    setIsOpen(false);
    setReason('');
    setSelectedPriority('');
    setIsNotSure(false);
  };

  const handleQuickAccept = async (e) => {
    if (e) e.stopPropagation();
    if (submitting) return;

    setSubmitting(true);
    try {
      const body = {
        message_id: messageId,
        feedback_type: 'ACCEPT',
        predicted_priority: currentPriority,
        predicted_action_required: actionRequired,
        original_confidence: typeof confidence === 'number' ? confidence : null,
        original_topic: topic || null,
        original_deadline_detected: deadlineDetected,
        thread_id: threadId || null,
      };

      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        setResult('success');
        setTimeout(() => {
          handleReset();
          setResult(null);
        }, 1200);
      } else {
        setResult('error');
      }
    } catch {
      setResult('error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitCorrection = async () => {
    if (submitting) return;
    if (!selectedPriority && !isNotSure && !reason) return;

    setSubmitting(true);
    try {
      const ftype = isNotSure ? 'NOT_SURE' : 'CORRECT';
      const body = {
        message_id: messageId,
        feedback_type: ftype,
        predicted_priority: currentPriority,
        predicted_action_required: actionRequired,
        original_confidence: typeof confidence === 'number' ? confidence : null,
        original_topic: topic || null,
        original_deadline_detected: deadlineDetected,
        corrected_priority: isNotSure ? null : (selectedPriority || null),
        reason: reason || (isNotSure ? 'context_missing' : 'other'),
        notes: reason || null,
        thread_id: threadId || null,
      };

      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        setResult('success');
        setTimeout(() => {
          handleReset();
          setResult(null);
        }, 1400);
      } else {
        setResult('error');
      }
    } catch {
      setResult('error');
    } finally {
      setSubmitting(false);
    }
  };

  const priorityColor = PRIORITY_COLOUR[currentPriority] || '#6b7280';
  const confDisplay = typeof confidence === 'number' ? Math.round(confidence * 100) : null;

  return (
    <div
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Quick Accept button if showAccept enabled */}
      {showAccept && !isOpen && (
        <button
          onClick={handleQuickAccept}
          disabled={submitting}
          title="Classification looks correct"
          aria-label="Confirm classification is correct"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.2rem',
            padding: '0.2rem 0.45rem',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            backgroundColor: 'transparent',
            color: 'var(--text-muted)',
            cursor: submitting ? 'not-allowed' : 'pointer',
            fontSize: '0.7rem',
            fontWeight: 500,
            opacity: 0.75,
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = '#10b981'; }}
          onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.75'; e.currentTarget.style.color = 'var(--text-muted)'; }}
        >
          <ThumbsUp size={11} />
          <span>Correct</span>
        </button>
      )}

      {/* Main "Wrong?" Trigger Button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
          if (!isOpen) {
            setResult(null);
          }
        }}
        disabled={submitting}
        title="Report priority or classification issue"
        aria-label="Report classification issue"
        aria-expanded={isOpen}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.25rem',
          padding: compact ? '0.15rem 0.4rem' : '0.25rem 0.55rem',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-subtle)',
          backgroundColor: isOpen ? 'var(--bg-card)' : 'transparent',
          color: isOpen ? 'var(--text-primary)' : 'var(--text-muted)',
          cursor: submitting ? 'not-allowed' : 'pointer',
          fontSize: '0.72rem',
          fontWeight: 500,
          opacity: isOpen ? 1 : 0.75,
          transition: 'all 0.15s ease',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.borderColor = priorityColor; }}
        onMouseLeave={(e) => { if (!isOpen) { e.currentTarget.style.opacity = '0.75'; e.currentTarget.style.borderColor = 'var(--border-subtle)'; } }}
      >
        {result === 'success' ? (
          <Check size={11} color="#10b981" />
        ) : result === 'error' ? (
          <AlertCircle size={11} color="#ef4444" />
        ) : (
          <HelpCircle size={11} />
        )}
        <span>Wrong?</span>
        {!compact && <ChevronDown size={10} style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />}
      </button>

      {/* Popover Card */}
      {isOpen && result !== 'success' && (
        <div
          role="dialog"
          aria-label="Priority correction panel"
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute',
            right: 0,
            top: '100%',
            marginTop: '0.35rem',
            zIndex: 1600,
            width: '270px',
            maxWidth: '90vw',
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            boxShadow: '0 6px 20px rgba(0, 0, 0, 0.3)',
            padding: '0.85rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.65rem',
            animation: 'fadeIn 0.15s ease-out',
          }}
        >
          {/* Header context */}
          <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.45rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                Classification Feedback
              </span>
              <span style={{ fontSize: '0.68rem', color: priorityColor, fontWeight: 700 }}>
                {currentPriority}{confDisplay !== null ? ` · ${confDisplay}%` : ''}
              </span>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
              What was wrong with this email?
            </div>
          </div>

          {/* Step 1: Issue type / reason */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <label style={{ fontSize: '0.68rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              1. What was wrong?
            </label>
            <select
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (e.target.value === 'priority_too_high' && currentPriority === 'P2') {
                  setSelectedPriority('P3');
                  setIsNotSure(false);
                } else if (e.target.value === 'priority_too_low' && currentPriority === 'P3') {
                  setSelectedPriority('P2');
                  setIsNotSure(false);
                }
              }}
              style={{
                width: '100%',
                padding: '0.35rem 0.5rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-input)',
                color: 'var(--text-primary)',
                fontSize: '0.74rem',
              }}
            >
              <option value="">Select issue (optional)...</option>
              {REASON_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Step 2: Correct priority */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <label style={{ fontSize: '0.68rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              2. Correct priority:
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.3rem' }}>
              {PRIORITY_OPTIONS.map((opt) => {
                const isSelected = selectedPriority === opt.value && !isNotSure;
                const isCurrent = opt.value === currentPriority;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      setIsNotSure(false);
                      setSelectedPriority(isSelected ? '' : opt.value);
                    }}
                    disabled={isCurrent}
                    title={isCurrent ? 'Current prediction' : opt.label}
                    style={{
                      padding: '0.35rem 0.2rem',
                      borderRadius: 'var(--radius-sm)',
                      border: `1px solid ${isSelected ? PRIORITY_COLOUR[opt.value] : 'var(--border-subtle)'}`,
                      backgroundColor: isSelected ? `${PRIORITY_COLOUR[opt.value]}22` : 'var(--bg-surface)',
                      color: isCurrent ? 'var(--text-muted)' : (isSelected ? PRIORITY_COLOUR[opt.value] : 'var(--text-primary)'),
                      fontWeight: isSelected ? 800 : 600,
                      fontSize: '0.72rem',
                      cursor: isCurrent ? 'not-allowed' : 'pointer',
                      opacity: isCurrent ? 0.4 : 1,
                      textAlign: 'center',
                    }}
                  >
                    {opt.short}
                  </button>
                );
              })}
            </div>

            {/* "Not sure" button */}
            <button
              type="button"
              onClick={() => {
                setIsNotSure(!isNotSure);
                if (!isNotSure) {
                  setSelectedPriority('');
                }
              }}
              style={{
                marginTop: '0.15rem',
                padding: '0.25rem 0.5rem',
                borderRadius: 'var(--radius-sm)',
                border: `1px solid ${isNotSure ? 'var(--accent)' : 'var(--border-subtle)'}`,
                backgroundColor: isNotSure ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                color: isNotSure ? 'var(--accent)' : 'var(--text-muted)',
                fontSize: '0.7rem',
                fontWeight: isNotSure ? 700 : 500,
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              Not sure
            </button>
          </div>

          {/* Footer Actions */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.2rem', paddingTop: '0.45rem', borderTop: '1px solid var(--border-subtle)' }}>
            <button
              type="button"
              onClick={handleReset}
              style={{
                padding: '0.3rem 0.55rem',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                backgroundColor: 'transparent',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.72rem',
              }}
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleSubmitCorrection}
              disabled={(!selectedPriority && !isNotSure && !reason) || submitting}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                padding: '0.32rem 0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                backgroundColor: (selectedPriority || isNotSure || reason) && !submitting ? 'var(--accent)' : 'var(--bg-surface-hover)',
                color: (selectedPriority || isNotSure || reason) && !submitting ? '#ffffff' : 'var(--text-muted)',
                fontWeight: 600,
                fontSize: '0.73rem',
                cursor: (selectedPriority || isNotSure || reason) && !submitting ? 'pointer' : 'not-allowed',
                transition: 'all 0.15s ease',
              }}
            >
              {submitting && <Loader size={12} className="spin" />}
              <span>Submit</span>
            </button>
          </div>

          {result === 'error' && (
            <div style={{ fontSize: '0.68rem', color: '#ef4444', textAlign: 'center' }}>
              Submission failed. Please try again.
            </div>
          )}

          <div style={{ fontSize: '0.63rem', color: 'var(--text-muted)', textAlign: 'center', fontStyle: 'italic' }}>
            Reviewed by human adjudicators. Does not alter models in runtime.
          </div>
        </div>
      )}
    </div>
  );
}
