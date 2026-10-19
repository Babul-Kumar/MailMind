import React, { useState } from 'react';
import { Clock, AlertTriangle, X, Calendar, Sun, Sunrise, ArrowRight } from 'lucide-react';

export function SnoozeModal({ email, isOpen, onClose, onSnooze }) {
  if (!isOpen || !email) return null;

  const [customDateTime, setCustomDateTime] = useState('');
  const [selectedPreset, setSelectedPreset] = useState('tomorrow');
  const isCritical = email.is_critical_incident || email.action_policy?.is_critical_incident || email.final_priority === 'P1';

  // Compute preset timestamps in seconds (Unix epoch)
  const getPresetTimestamp = (preset) => {
    const now = new Date();
    if (preset === 'later_today') {
      const later = new Date();
      // If before 16:00, set to 18:00 today; else 4 hours from now
      if (now.getHours() < 16) {
        later.setHours(18, 0, 0, 0);
      } else {
        later.setTime(now.getTime() + 4 * 3600 * 1000);
      }
      return Math.floor(later.getTime() / 1000);
    } else if (preset === 'tomorrow') {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(9, 0, 0, 0);
      return Math.floor(tomorrow.getTime() / 1000);
    } else if (preset === 'in_3_days') {
      const in3 = new Date();
      in3.setDate(in3.getDate() + 3);
      in3.setHours(9, 0, 0, 0);
      return Math.floor(in3.getTime() / 1000);
    } else if (preset === 'custom' && customDateTime) {
      const custom = new Date(customDateTime);
      return Math.floor(custom.getTime() / 1000);
    }
    return Math.floor((Date.now() + 86400000) / 1000);
  };

  const handleConfirm = () => {
    const ts = getPresetTimestamp(selectedPreset);
    if (!ts || isNaN(ts) || ts <= Math.floor(Date.now() / 1000)) {
      alert('Please choose a valid future date and time.');
      return;
    }
    const mid = email.email_id || email.id || email.message_id;
    const tid = email.thread_id || null;
    onSnooze(mid, ts, tid, selectedPreset);
    onClose();
  };

  // Min datetime for HTML5 input
  const minDateTimeStr = new Date(Date.now() + 60000).toISOString().slice(0, 16);

  return (
    <>
      {/* Backdrop */}
      <div
        className="animate-backdrop-in"
        style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.55)',
          backdropFilter: 'blur(3px)',
          zIndex: 3000,
        }}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="snooze-modal-title"
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '92%',
          maxWidth: '460px',
          backgroundColor: 'var(--bg-surface)',
          borderRadius: 'var(--radius-lg, 12px)',
          border: '1px solid var(--border-subtle)',
          boxShadow: 'var(--shadow-drawer, 0 20px 40px rgba(0,0,0,0.4))',
          zIndex: 3001,
          padding: '1.4rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.1rem',
          animation: 'fadeIn 0.18s ease-out',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '8px',
                backgroundColor: 'rgba(59, 130, 246, 0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#3b82f6',
              }}
            >
              <Clock size={18} />
            </div>
            <div>
              <h3 id="snooze-modal-title" style={{ fontSize: '1.05rem', fontWeight: 600, margin: 0, color: 'var(--text-main)' }}>
                Snooze Action
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>
                Temporarily hide until return time
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '0.3rem',
              borderRadius: '6px',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Critical Incident Warning */}
        {isCritical && (
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.65rem',
              backgroundColor: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.28)',
              borderRadius: '8px',
              padding: '0.75rem 0.85rem',
              fontSize: '0.8rem',
              color: '#f87171',
              lineHeight: 1.35,
            }}
          >
            <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '1px' }} />
            <div>
              <strong style={{ display: 'block', marginBottom: '2px' }}>Critical Action / Incident</strong>
              Snoozing postpones visibility in Needs Attention. It does <em>not</em> resolve or complete this critical action.
            </div>
          </div>
        )}

        {/* Preset Options Grid */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
          {[
            {
              id: 'later_today',
              label: 'Later today',
              detail: '6:00 PM (or +4 hours)',
              icon: <Sun size={15} />,
            },
            {
              id: 'tomorrow',
              label: 'Tomorrow morning',
              detail: '9:00 AM',
              icon: <Sunrise size={15} />,
            },
            {
              id: 'in_3_days',
              label: 'In 3 days',
              detail: '9:00 AM in 3 days',
              icon: <Calendar size={15} />,
            },
            {
              id: 'custom',
              label: 'Choose date and time',
              detail: 'Select custom return schedule',
              icon: <Clock size={15} />,
            },
          ].map((opt) => {
            const isSel = selectedPreset === opt.id;
            return (
              <label
                key={opt.id}
                onClick={() => setSelectedPreset(opt.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.65rem 0.85rem',
                  borderRadius: '8px',
                  border: `1px solid ${isSel ? '#3b82f6' : 'var(--border-subtle)'}`,
                  backgroundColor: isSel ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  <span style={{ color: isSel ? '#3b82f6' : 'var(--text-muted)' }}>{opt.icon}</span>
                  <div>
                    <span style={{ fontSize: '0.86rem', fontWeight: 500, color: 'var(--text-main)' }}>
                      {opt.label}
                    </span>
                    <span style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {opt.detail}
                    </span>
                  </div>
                </div>
                <input
                  type="radio"
                  name="snooze-preset"
                  checked={isSel}
                  onChange={() => setSelectedPreset(opt.id)}
                  style={{ cursor: 'pointer' }}
                />
              </label>
            );
          })}
        </div>

        {/* Custom Datetime Picker */}
        {selectedPreset === 'custom' && (
          <div style={{ marginTop: '0.2rem' }}>
            <label style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Custom return date and time (Local timezone)
            </label>
            <input
              type="datetime-local"
              min={minDateTimeStr}
              value={customDateTime}
              onChange={(e) => setCustomDateTime(e.target.value)}
              style={{
                width: '100%',
                padding: '0.55rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-main, #0f172a)',
                color: 'var(--text-main)',
                fontSize: '0.85rem',
              }}
            />
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.65rem', marginTop: '0.4rem' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '0.5rem 0.95rem',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'transparent',
              color: 'var(--text-secondary)',
              fontSize: '0.84rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.5rem 1.1rem',
              borderRadius: '6px',
              border: 'none',
              backgroundColor: '#3b82f6',
              color: '#ffffff',
              fontSize: '0.84rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 2px 8px rgba(59, 130, 246, 0.35)',
            }}
          >
            <span>Snooze Action</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </>
  );
}
