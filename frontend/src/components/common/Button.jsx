import React from 'react';

export function Button({
  children,
  variant = 'secondary',
  size = 'md',
  className = '',
  disabled = false,
  icon = null,
  onClick,
  title,
  ...props
}) {
  const styles = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.45rem',
    fontWeight: 500,
    borderRadius: 'var(--radius-md)',
    transition: 'all var(--transition-fast)',
    fontSize: size === 'sm' ? '0.78rem' : size === 'lg' ? '0.95rem' : '0.85rem',
    padding:
      size === 'sm'
        ? '0.35rem 0.65rem'
        : size === 'lg'
        ? '0.65rem 1.25rem'
        : '0.48rem 0.95rem',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    border: '1px solid transparent',
  };

  const variantStyles = {
    primary: {
      backgroundColor: 'var(--accent)',
      color: '#ffffff',
      borderColor: 'var(--accent)',
    },
    secondary: {
      backgroundColor: 'var(--bg-surface-hover)',
      color: 'var(--text-main)',
      borderColor: 'var(--border-subtle)',
    },
    ghost: {
      backgroundColor: 'transparent',
      color: 'var(--text-secondary)',
    },
    iconOnly: {
      padding: '0.45rem',
      backgroundColor: 'transparent',
      color: 'var(--text-secondary)',
      borderRadius: 'var(--radius-sm)',
    },
  };

  return (
    <button
      style={{ ...styles, ...(variantStyles[variant] || variantStyles.secondary) }}
      className={`btn ${className}`}
      disabled={disabled}
      onClick={onClick}
      title={title}
      {...props}
    >
      {icon && <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>}
      {children}
    </button>
  );
}
