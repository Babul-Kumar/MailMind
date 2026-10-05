import React from 'react';
import { Search, X } from 'lucide-react';

export function SearchBar({ value, onChange, matchCount = null, placeholder = 'Search all analyzed mail...' }) {
  const [isFocused, setIsFocused] = React.useState(false);

  return (
    <div className={`searchbar-container ${isFocused ? 'is-focused' : ''}`}>
      <Search
        size={18}
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

        {value && (
          <button
            type="button"
            onClick={() => onChange('')}
            className="searchbar-clear-btn"
            title="Clear search"
            aria-label="Clear search"
          >
            <X size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
