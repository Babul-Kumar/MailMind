import React from 'react';

export function SkeletonRow() {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '56px 160px 1fr 75px',
        alignItems: 'center',
        gap: '0.85rem',
        padding: '0.75rem 1.15rem',
        borderBottom: '1px solid var(--border-divider)',
      }}
    >
      <div
        className="animate-shimmer"
        style={{ height: '22px', width: '48px', borderRadius: 'var(--radius-sm)' }}
      />
      <div
        className="animate-shimmer"
        style={{ height: '16px', width: '120px', borderRadius: 'var(--radius-xs)' }}
      />
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <div
          className="animate-shimmer"
          style={{ height: '16px', width: '40%', borderRadius: 'var(--radius-xs)' }}
        />
        <div
          className="animate-shimmer"
          style={{ height: '14px', width: '50%', borderRadius: 'var(--radius-xs)' }}
        />
      </div>
      <div
        className="animate-shimmer"
        style={{ height: '14px', width: '60px', borderRadius: 'var(--radius-xs)', justifySelf: 'end' }}
      />
    </div>
  );
}

export function SkeletonList({ count = 6 }) {
  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
      }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
}
