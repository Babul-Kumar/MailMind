import React from 'react';
import { EmailRow } from './EmailRow';
import { SkeletonList } from '../common/Skeleton';
import { EmptyState } from '../common/EmptyState';

export function EmailList({
  emails = [],
  selectedEmailId,
  onSelectEmail,
  isLoading,
  isRefreshing = false,
  isInitialLoading = false,
  emptyType = 'inbox',
  onRefresh,
}) {
  if (isInitialLoading || (isLoading && emails.length === 0)) {
    return <SkeletonList count={6} />;
  }

  if (emails.length === 0) {
    return (
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
          overflow: 'hidden',
        }}
      >
        <EmptyState
          type={emptyType}
          onAction={onRefresh}
          actionText={emptyType === 'inbox' ? 'Refresh Inbox' : null}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-subtle)',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-sm)',
        opacity: isRefreshing ? 0.72 : 1,
        transition: 'opacity 0.2s ease',
        pointerEvents: isRefreshing ? 'none' : 'auto',
      }}
    >
      {emails.map((email) => (
        <EmailRow
          key={email.email_id}
          email={email}
          isSelected={email.email_id === selectedEmailId}
          onClick={() => onSelectEmail(email)}
        />
      ))}
    </div>
  );
}
