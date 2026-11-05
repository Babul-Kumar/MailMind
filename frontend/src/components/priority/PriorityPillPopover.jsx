import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, Sparkles } from 'lucide-react';
import { submitFeedback } from '../../services/api';

const PRIORITY_LABELS = {
  P1: 'P1 · Urgent',
  P2: 'P2 · Important',
  P3: 'P3 · Routine',
  P4: 'P4 · Low',
};

const PRIORITY_COLORS = {
  P1: {
    color: 'var(--p1-color)',
    bg: 'var(--p1-bg)',
    border: 'var(--p1-border)',
  },
  P2: {
    color: 'var(--p2-color)',
    bg: 'var(--p2-bg)',
    border: 'var(--p2-border)',
  },
  P3: {
    color: 'var(--p3-color)',
    bg: 'var(--p3-bg)',
    border: 'var(--p3-border)',
  },
  P4: {
    color: 'var(--p4-color)',
    bg: 'var(--p4-bg)',
    border: 'var(--p4-border)',
  },
};

export function PriorityPillPopover({
  priority = 'P1',
  confidence = 0.94,
  actionReason = '',
  signals = [],
  messageId,
  threadId,
  onOverride,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentPriority, setCurrentPriority] = useState(priority);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [justOverridden, setJustOverridden] = useState(false);
  const popoverRef = useRef(null);

  useEffect(() => {
    setCurrentPriority(priority);
  }, [priority]);

  // Click outside listener to dismiss micro-popover
  useEffect(() => {
    function handleClickOutside(e) {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // Calculate clean display values
  const normalizedConfidence = typeof confidence === 'number'
    ? (confidence > 1 ? confidence : Math.round(confidence * 100))
    : 94;

  const currentTheme = PRIORITY_COLORS[currentPriority] || PRIORITY_COLORS.P1;
  const label = PRIORITY_LABELS[currentPriority] || `${currentPriority} · Urgent`;

  // Matched keyword tags from actionReason and signals
  const displayTags = React.useMemo(() => {
    const set = new Set();
    if (actionReason) {
      set.add(actionReason.toLowerCase().replace(/_/g, ' '));
    }
    if (Array.isArray(signals)) {
      signals.forEach((s) => s && set.add(String(s).toLowerCase().trim()));
    }
    if (set.size === 0) {
      if (currentPriority === 'P1') {
        set.add('action required');
        set.add('critical deadline');
      } else if (currentPriority === 'P2') {
        set.add('important');
        set.add('follow up');
      } else if (currentPriority === 'P3') {
        set.add('routine update');
      } else {
        set.add('newsletter');
      }
    }
    return Array.from(set).slice(0, 4);
  }, [actionReason, signals, currentPriority]);

  const handleSelectOverride = async (newTier) => {
    if (newTier === currentPriority || isSubmitting) return;
    setIsSubmitting(true);
    try {
      if (messageId) {
        await submitFeedback({
          message_id: messageId,
          suggested_priority: newTier,
          feedback_type: 'OVERRIDE',
          thread_id: threadId,
        });
      }
      setCurrentPriority(newTier);
      setJustOverridden(true);
      onOverride?.(newTier);
      setTimeout(() => setJustOverridden(false), 2000);
    } catch (err) {
      console.warn('Priority override notice:', err);
      setCurrentPriority(newTier);
      onOverride?.(newTier);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ position: 'relative', display: 'inline-block' }} ref={popoverRef}>
      {/* Interactive Pill Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        title="Click to view AI classification confidence and model weight"
        className="priority-pill-interactive-btn"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          padding: '4px 10px',
          borderRadius: 'var(--radius-full)',
          backgroundColor: currentTheme.bg,
          color: currentTheme.color,
          border: `1px solid ${currentTheme.border}`,
          fontSize: '0.8rem',
          fontWeight: 600,
          cursor: 'pointer',
          transition: 'all var(--transition-fast)',
          userSelect: 'none',
        }}
      >
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: currentTheme.color,
            display: 'inline-block',
            flexShrink: 0,
          }}
        />
        <span>{label}</span>
        <ChevronDown
          size={12}
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'none',
            transition: 'transform var(--transition-fast)',
            opacity: 0.75,
          }}
        />
      </button>

      {/* Floating Micro-Popover Card (Macro UI) */}
      {isOpen && (
        <div
          className="priority-micro-popover animate-slide-down"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            left: 0,
            width: '280px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-popover)',
            padding: '12px 14px',
            zIndex: 1500,
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          {/* Header line: Model info & confidence */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Sparkles size={13} style={{ color: 'var(--accent)' }} />
              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-main)' }}>
                ML Model: priority-v5.1
              </span>
            </div>
            <span
              style={{
                fontSize: '0.74rem',
                fontWeight: 700,
                color: currentTheme.color,
              }}
            >
              {normalizedConfidence}% confidence
            </span>
          </div>

          {/* Horizontal Weight / Confidence Bar */}
          <div
            style={{
              width: '100%',
              height: '4px',
              backgroundColor: 'var(--border-subtle)',
              borderRadius: '999px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${normalizedConfidence}%`,
                height: '100%',
                backgroundColor: currentTheme.color,
                borderRadius: '999px',
                transition: 'width 0.4s ease',
              }}
            />
          </div>

          {/* Matched keyword tags */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
              Salient Keyword Signals
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {displayTags.map((tag, idx) => (
                <span
                  key={idx}
                  style={{
                    fontSize: '0.72rem',
                    padding: '2px 7px',
                    borderRadius: 'var(--radius-xs)',
                    backgroundColor: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'Inter, -apple-system, sans-serif',
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Four Small Override Buttons [P1] [P2] [P3] [P4] */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', paddingTop: '4px', borderTop: '1px solid var(--border-divider)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.68rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                Override Classification
              </span>
              {justOverridden && (
                <span style={{ fontSize: '0.68rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '2px' }}>
                  <Check size={11} /> Feedback saved
                </span>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px' }}>
              {['P1', 'P2', 'P3', 'P4'].map((tier) => {
                const isSelected = currentPriority === tier;
                const tierTheme = PRIORITY_COLORS[tier];
                return (
                  <button
                    key={tier}
                    type="button"
                    onClick={() => handleSelectOverride(tier)}
                    disabled={isSubmitting}
                    style={{
                      padding: '4px 0',
                      borderRadius: 'var(--radius-xs)',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      border: `1px solid ${isSelected ? tierTheme.color : 'var(--border-subtle)'}`,
                      backgroundColor: isSelected ? tierTheme.bg : 'var(--bg-input)',
                      color: isSelected ? tierTheme.color : 'var(--text-secondary)',
                      transition: 'all var(--transition-fast)',
                      textAlign: 'center',
                    }}
                  >
                    {tier}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PriorityPillPopover;
