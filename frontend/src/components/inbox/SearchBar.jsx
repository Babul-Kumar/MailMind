import React from 'react';
import { Search, X } from 'lucide-react';

export function SearchBar({ value, onChange, matchCount = null }) {
  const [isFocused, setIsFocused] = React.useState(false);

  return (
    <div
      className="searchbar-container"
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        width: '100%',
        flex: '1 1 auto',
      }}
    >
      <Search
        size={16}
        style={{
          position: 'absolute',
          left: '0.8rem',
          color: isFocused ? 'var(--accent)' : 'var(--text-muted)',
          pointerEvents: 'none',
          transition: 'color var(--transition-fast)',
        }}
      />
      <input
        type="text"
        className="searchbar-input"
        placeholder="Search all analyzed mail..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        aria-label="Search emails"
        style={{
          width: '100%',
          backgroundColor: 'var(--bg-input)',
          border: `1px solid ${isFocused ? 'var(--border-focus)' : 'var(--border-subtle)'}`,
          boxShadow: isFocused ? '0 0 0 2px var(--accent-light)' : 'none',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-main)',
          outline: 'none',
          transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
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
              padding: '0.12rem 0.45rem',
              borderRadius: 'var(--radius-full)',
              fontWeight: 500,
            }}
          >
            {matchCount}
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
              padding: '0.35rem',
              borderRadius: 'var(--radius-full)',
              cursor: 'pointer',
              border: 'none',
              background: 'transparent',
              minWidth: '32px',
              minHeight: '32px',
            }}
            title="Clear search"
            aria-label="Clear search"
          >
            <X size={15} />
          </button>
        )}
      </div>
    </div>
  );
}
