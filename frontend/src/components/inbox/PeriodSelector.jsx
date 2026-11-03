import React, { useState, useRef, useEffect } from 'react';
import { Calendar, ChevronDown, Check, Clock, Sparkles } from 'lucide-react';

const PERIOD_LABELS = {
  this_month: 'This month',
  last_3_months: 'Last 3 months',
  last_1_year: 'Last 1 year',
  all_time: 'All time',
  custom: 'Custom range',
};

export function PeriodSelector({
  activePeriod = 'last_3_months',
  customStartDate = '',
  customEndDate = '',
  onChangePeriod,
  summary = null,
  isAnalyzing = false,
  disabled = false,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [showCustomInputs, setShowCustomInputs] = useState(activePeriod === 'custom');
  const [startDate, setStartDate] = useState(customStartDate || '');
  const [endDate, setEndDate] = useState(customEndDate || '');
  const [customError, setCustomError] = useState(null);
  const menuRef = useRef(null);

  useEffect(() => {
    setStartDate(customStartDate || '');
    setEndDate(customEndDate || '');
    setShowCustomInputs(activePeriod === 'custom');
  }, [activePeriod, customStartDate, customEndDate]);

  // Click outside listener
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleSelectPeriod = (period) => {
    if (period === 'custom') {
      setShowCustomInputs(true);
      return;
    }
    setShowCustomInputs(false);
    setCustomError(null);
    setIsOpen(false);
    onChangePeriod?.(period);
  };

  const handleApplyCustom = (e) => {
    e.preventDefault();
    if (!startDate || !endDate) {
      setCustomError('Please enter both start and end dates.');
      return;
    }
    if (startDate > endDate) {
      setCustomError('Start date cannot be after end date.');
      return;
    }
    const todayStr = new Date().toISOString().split('T')[0];
    if (endDate > todayStr) {
      setCustomError('End date cannot be in the future.');
      return;
    }
    setCustomError(null);
    setIsOpen(false);
    onChangePeriod?.('custom', startDate, endDate);
  };

  const currentLabel =
    activePeriod === 'custom' && customStartDate && customEndDate
      ? `${customStartDate} → ${customEndDate}`
      : PERIOD_LABELS[activePeriod] || 'Last 3 months';

  return (
    <div style={{ position: 'relative', display: 'inline-block' }} ref={menuRef}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen((prev) => !prev)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        title="Select date range for email analysis"
        className="period-selector-btn"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.45rem',
          padding: '0.35rem 0.65rem',
          backgroundColor: isOpen ? 'var(--bg-surface-hover)' : 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          fontSize: '0.8rem',
          fontWeight: 600,
          color: 'var(--text-main)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: 'all var(--transition-fast)',
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <Calendar size={14} color="var(--accent)" />
        <span style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {currentLabel}
        </span>
        {isAnalyzing ? (
          <span className="period-pulse-dot animate-pulse" style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
        ) : (
          <ChevronDown size={13} style={{ color: 'var(--text-muted)', transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease' }} />
        )}
      </button>

      {isOpen && (
        <div
          className="period-dropdown-menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            minWidth: '220px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-md)',
            padding: '0.45rem',
            zIndex: 1400,
            display: 'flex',
            flexDirection: 'column',
            gap: '0.2rem',
            animation: 'fadeIn 0.15s ease',
          }}
        >
          <div style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', padding: '0.35rem 0.5rem 0.2rem' }}>
            Analysis Scope
          </div>

          {['this_month', 'last_3_months', 'last_1_year', 'all_time'].map((pKey) => {
            const isSelected = activePeriod === pKey && !showCustomInputs;
            const isDefault = pKey === 'last_3_months';
            return (
              <button
                key={pKey}
                type="button"
                onClick={() => handleSelectPeriod(pKey)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.45rem 0.6rem',
                  fontSize: '0.8rem',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: isSelected ? 'var(--bg-surface-hover)' : 'transparent',
                  color: isSelected ? 'var(--accent)' : 'var(--text-main)',
                  fontWeight: isSelected ? 600 : 500,
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                  transition: 'background-color var(--transition-fast)',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <span>{PERIOD_LABELS[pKey]}</span>
                  {isDefault && (
                    <span
                      style={{
                        fontSize: '0.65rem',
                        padding: '0.1rem 0.35rem',
                        borderRadius: '999px',
                        backgroundColor: 'rgba(99, 102, 241, 0.12)',
                        color: 'var(--accent)',
                        fontWeight: 600,
                      }}
                    >
                      Default
                    </span>
                  )}
                </div>
                {isSelected && <Check size={14} color="var(--accent)" />}
              </button>
            );
          })}

          <div style={{ height: '1px', backgroundColor: 'var(--border-subtle)', margin: '0.3rem 0' }} />

          {/* Custom Date Range Toggle */}
          <button
            type="button"
            onClick={() => setShowCustomInputs((prev) => !prev)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.45rem 0.6rem',
              fontSize: '0.8rem',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: activePeriod === 'custom' ? 'var(--bg-surface-hover)' : 'transparent',
              color: activePeriod === 'custom' ? 'var(--accent)' : 'var(--text-main)',
              fontWeight: activePeriod === 'custom' ? 600 : 500,
              border: 'none',
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
            }}
          >
            <span>Custom range...</span>
            {activePeriod === 'custom' && <Check size={14} color="var(--accent)" />}
          </button>

          {showCustomInputs && (
            <form onSubmit={handleApplyCustom} style={{ padding: '0.5rem 0.4rem 0.2rem', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>From</label>
                <input
                  type="date"
                  value={startDate}
                  max={endDate || new Date().toISOString().split('T')[0]}
                  onChange={(e) => setStartDate(e.target.value)}
                  style={{
                    padding: '0.35rem 0.45rem',
                    fontSize: '0.78rem',
                    borderRadius: 'var(--radius-xs)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-card)',
                    color: 'var(--text-main)',
                  }}
                  required
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>To</label>
                <input
                  type="date"
                  value={endDate}
                  min={startDate}
                  max={new Date().toISOString().split('T')[0]}
                  onChange={(e) => setEndDate(e.target.value)}
                  style={{
                    padding: '0.35rem 0.45rem',
                    fontSize: '0.78rem',
                    borderRadius: 'var(--radius-xs)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-card)',
                    color: 'var(--text-main)',
                  }}
                  required
                />
              </div>

              {customError && (
                <div style={{ fontSize: '0.7rem', color: 'var(--p1-color)', marginTop: '0.1rem' }}>
                  {customError}
                </div>
              )}

              <button
                type="submit"
                style={{
                  marginTop: '0.3rem',
                  padding: '0.4rem',
                  backgroundColor: 'var(--accent)',
                  color: '#ffffff',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  border: 'none',
                  borderRadius: 'var(--radius-xs)',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                Apply Range
              </button>
            </form>
          )}

          {summary && (
            <div
              style={{
                marginTop: '0.4rem',
                padding: '0.45rem 0.6rem',
                backgroundColor: 'var(--bg-card)',
                borderRadius: 'var(--radius-xs)',
                fontSize: '0.72rem',
                color: 'var(--text-secondary)',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.2rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Analyzed:</span>
                <strong style={{ color: 'var(--text-main)' }}>{summary.analyzed?.toLocaleString() || 0} / {summary.total_eligible?.toLocaleString() || 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Cached:</span>
                <strong style={{ color: '#22c55e' }}>{summary.reused_from_cache?.toLocaleString() || 0} reused</strong>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

