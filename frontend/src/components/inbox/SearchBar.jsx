import React from 'react';
import { Search, X } from 'lucide-react';

export function SearchBar({ value, onChange, matchCount = null }) {
  const [isFocused, setIsFocused] = React.useState(false);

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        width: '100%',
        maxWidth: '520px',
      }}
    >
      <Search
        size={16}
        style={{
          position: 'absolute',
          left: '0.85rem',
          color: isFocused ? 'var(--accent)' : 'var(--text-muted)',
          pointerEvents: 'none',
          transition: 'color var(--transition-fast)',
        }}
      />
      <input
        type="text"
        placeholder="Search emails (sender, subject, body)..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        aria-label="Search emails"
        style={{
          width: '100%',
          padding: '0.52rem 5.5rem 0.52rem 2.4rem',
          backgroundColor: 'var(--bg-input)',
          border: `1px solid ${isFocused ? 'var(--accent)' : 'var(--border-subtle)'}`,
          boxShadow: isFocused ? '0 0 0 3px var(--accent-light)' : 'none',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-main)',
          fontSize: '0.85rem',
          outline: 'none',
          transition: 'all var(--transition-fast)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          right: '0.6rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.35rem',
        }}
      >
        {value.trim() && matchCount !== null && (
          <span
            style={{
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
              backgroundColor: 'var(--badge-bg)',
              padding: '0.1rem 0.4rem',
              borderRadius: 'var(--radius-full)',
            }}
          >
            {matchCount} result{matchCount === 1 ? '' : 's'}
          </span>
        )}

        {value && (
          <button
            onClick={() => onChange('')}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              padding: '0.2rem',
              borderRadius: 'var(--radius-full)',
              cursor: 'pointer',
              border: 'none',
              background: 'transparent',
            }}
            title="Clear search"
            aria-label="Clear search"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
