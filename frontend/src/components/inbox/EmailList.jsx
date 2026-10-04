import React, { useCallback } from 'react';
import { EmailRow } from './EmailRow';
import { SkeletonList } from '../common/Skeleton';
import { EmptyState } from '../common/EmptyState';

function EmailListComponent({
  emails = [],
  selectedEmailId,
  onSelectEmail,
  isLoading,
  isRefreshing = false,
  isInitialLoading = false,
  emptyType = 'inbox',
  onRefresh,
}) {
  const handleSelectEmail = useCallback(
    (email) => {
      onSelectEmail?.(email);
    },
    [onSelectEmail]
  );

  if (isInitialLoading || (isLoading && emails.length === 0)) {
    return <SkeletonList count={8} />;
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
        opacity: isRefreshing ? 0.7 : 1,
        transition: 'opacity 0.15s cubic-bezier(0.16, 1, 0.3, 1)',
        pointerEvents: isRefreshing ? 'none' : 'auto',
      }}
    >
      {emails.map((email) => {
        const rowId = email.message_id || email.email_id;
        return (
          <EmailRow
            key={rowId}
            email={email}
            isSelected={rowId === selectedEmailId || email.email_id === selectedEmailId}
            onClick={handleSelectEmail}
          />
        );
      })}
    </div>
  );
}

export const EmailList = React.memo(EmailListComponent);

