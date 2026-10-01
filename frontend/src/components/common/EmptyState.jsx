import React from 'react';
import { Mail, Search, Zap } from 'lucide-react';
import { Button } from './Button';

export function EmptyState({ type = 'inbox', onAction, actionText }) {
  const configs = {
    inbox: {
      icon: <Mail size={36} color="var(--text-muted)" />,
      title: 'Your inbox is clear',
      description: 'No emails currently match this view. Enjoy the calm!',
    },
    search: {
      icon: <Search size={36} color="var(--text-muted)" />,
      title: 'No emails found',
      description: 'Try a different sender, subject, or keyword.',
    },
    focus: {
      icon: <Zap size={36} color="var(--accent)" />,
      title: "✓ You're all caught up",
      description: 'No emails currently require action or have a meaningful deadline.',
    },
  };

  const config = configs[type] || configs.inbox;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '4.5rem 1.5rem',
        textAlign: 'center',
        gap: '0.8rem',
      }}
    >
      <div style={{ marginBottom: '0.4rem' }}>{config.icon}</div>
      <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-main)' }}>{config.title}</h3>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '340px' }}>
        {config.description}
      </p>
      {onAction && actionText && (
        <Button onClick={onAction} style={{ marginTop: '0.5rem' }}>
          {actionText}
        </Button>
      )}
    </div>
  );
}
