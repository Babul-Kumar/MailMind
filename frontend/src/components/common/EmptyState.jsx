import React from 'react';
import { Mail, Search, Zap, CheckCircle2, Inbox as InboxIcon } from 'lucide-react';
import { Button } from './Button';

export function EmptyState({ type = 'inbox', onAction, actionText }) {
  const configs = {
    inbox: {
      icon: <InboxIcon size={34} style={{ color: 'var(--accent)' }} />,
      title: 'Your inbox is clear',
      description: 'No emails currently match this filter. Everything is triaged and under control.',
      accent: 'var(--accent)',
      bg: 'var(--accent-light)',
    },
    search: {
      icon: <Search size={34} style={{ color: 'var(--sparkle-color)' }} />,
      title: 'No matching emails found',
      description: 'We couldn’t find anything matching your search term. Try another keyword or clear the search query.',
      accent: 'var(--sparkle-color)',
      bg: 'rgba(99, 102, 241, 0.12)',
    },
    focus: {
      icon: <CheckCircle2 size={34} style={{ color: '#10b981' }} />,
      title: "All caught up",
      description: 'Zero urgent crises or pending deadlines detected in this scope. Enjoy the peace!',
      accent: '#10b981',
      bg: 'rgba(16, 185, 129, 0.12)',
    },
  };

  const config = configs[type] || configs.inbox;

  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '5rem 1.5rem',
        textAlign: 'center',
        gap: '0.85rem',
        margin: '2rem auto',
        maxWidth: '480px',
      }}
    >
      <div
        style={{
          width: '68px',
          height: '68px',
          borderRadius: 'var(--radius-xl)',
          backgroundColor: config.bg,
          border: '1px solid var(--border-glow)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
          marginBottom: '0.5rem',
        }}
      >
        {config.icon}
      </div>
      <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-main)', margin: 0, letterSpacing: '-0.02em' }}>
        {config.title}
      </h3>
      <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', maxWidth: '380px', margin: 0, lineHeight: 1.5 }}>
        {config.description}
      </p>
      {onAction && actionText && (
        <Button onClick={onAction} style={{ marginTop: '0.75rem', borderRadius: 'var(--radius-md)' }}>
          {actionText}
        </Button>
      )}
    </div>
  );
}

export default EmptyState;
