import React from 'react';

export function AISignals({ signals = [] }) {
  if (!signals || signals.length === 0) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      <span
        style={{
          fontSize: '0.72rem',
          fontWeight: 600,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Key Model Text Signals:
      </span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
        {signals.map((sig, idx) => (
          <span
            key={idx}
            title={`Learned feature weight: +${sig.weight}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0.18rem 0.55rem',
              backgroundColor: 'var(--bg-surface-hover)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.75rem',
              fontWeight: 500,
              color: 'var(--text-main)',
            }}
          >
            <span style={{ color: 'var(--accent)', marginRight: '0.25rem', fontWeight: 700 }}>+</span>
            {sig.term}
          </span>
        ))}
      </div>
    </div>
  );
}
