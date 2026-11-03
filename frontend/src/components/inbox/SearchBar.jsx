import React from 'react';
import { Search, X } from 'lucide-react';

export function SearchBar({ value, onChange, matchCount = null, placeholder = 'Search all analyzed mail...' }) {
  const [isFocused, setIsFocused] = React.useState(false);

  return (
    <div className={`searchbar-container ${isFocused ? 'is-focused' : ''}`}>
      <Search
        size={17}
        className="searchbar-icon"
      />
      <input
        type="text"
        className="searchbar-input"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        aria-label="Search emails"
      />

      <div className="searchbar-actions">
        {value.trim() && matchCount !== null && (
          <span className="searchbar-match-badge">
            {matchCount}
          </span>
        )}

        {value ? (
          <button
            type="button"
            onClick={() => onChange('')}
            className="searchbar-clear-btn"
            title="Clear search"
            aria-label="Clear search"
          >
            <X size={15} />
          </button>
        ) : (
          !isFocused && (
            <kbd
              style={{
                fontSize: '11px',
                padding: '2px 6px',
                borderRadius: '4px',
                backgroundColor: 'var(--bg-surface-hover)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-dim)',
                fontFamily: 'monospace',
                pointerEvents: 'none',
                userSelect: 'none',
              }}
              title="Press / to focus search"
            >
              /
            </kbd>
          )
        )}
      </div>
    </div>
  );
}

export default SearchBar;
