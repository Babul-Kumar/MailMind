import React, { useEffect } from 'react';
import { CheckCircle2, AlertTriangle, X } from 'lucide-react';

export function Toast({ message, type = 'success', onClose, duration = 3500 }) {
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => {
      onClose();
    }, duration);
    return () => clearTimeout(timer);
  }, [message, duration, onClose]);

  if (!message) return null;

  const isError = type === 'error';

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '1.5rem',
        right: '1.5rem',
        zIndex: 2000,
        display: 'flex',
        alignItems: 'center',
        gap: '0.65rem',
        padding: '0.75rem 1.1rem',
        backgroundColor: 'var(--bg-card)',
        border: `1px solid ${isError ? 'var(--p1-border)' : 'var(--accent-light)'}`,
        borderRadius: 'var(--radius-md)',
        boxShadow: 'var(--shadow-lg)',
        color: 'var(--text-main)',
        fontSize: '0.86rem',
        animation: 'fadeIn 0.2s ease-out',
      }}
    >
      {isError ? (
        <AlertTriangle size={17} color="var(--p1-color)" />
      ) : (
        <CheckCircle2 size={17} color="var(--accent)" />
      )}
      <span>{message}</span>
      <button
        onClick={onClose}
        style={{ color: 'var(--text-muted)', marginLeft: '0.5rem', display: 'flex' }}
      >
        <X size={15} />
      </button>
    </div>
  );
}
