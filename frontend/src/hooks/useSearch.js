import { useState, useEffect, useMemo } from 'react';
import { PRIORITY_CONFIG, isNeedsAttention } from '../utils/priority';

export function useSearch(emails, options = {}) {
  const [internalSearchQuery, setInternalSearchQuery] = useState('');
  const [internalActiveFilter, setInternalActiveFilter] = useState('ALL');
  const [focusMode, setFocusMode] = useState(false);
  const [sortBy, setSortBy] = useState('date_desc');

  const activeFilter = options.activeFilter !== undefined ? options.activeFilter : internalActiveFilter;
  const setActiveFilter = options.setActiveFilter || setInternalActiveFilter;
  const searchQuery = options.searchQuery !== undefined ? options.searchQuery : internalSearchQuery;
  const setSearchQuery = options.setSearchQuery || setInternalSearchQuery;
  const actionFilter = options.actionFilter || 'ALL';
  const setActionFilter = options.setActionFilter || (() => {});

  const filteredEmails = useMemo(() => {
    if (!emails) return [];
    let list = [...emails];

    // If serverFiltered is false (or omitted without external options), perform local filtering for testing compatibility
    if (!options.serverFiltered) {
      if (focusMode) {
        list = list.filter(isNeedsAttention);
      } else if (activeFilter === 'NEEDS_ATTENTION') {
        list = list.filter(isNeedsAttention);
      } else if (activeFilter === 'IMPORTANT') {
        list = list.filter((e) => (e.final_priority || e.predicted_priority) === 'P2');
      } else if (activeFilter !== 'ALL') {
        list = list.filter((e) => (e.final_priority || e.predicted_priority) === activeFilter);
      }

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        list = list.filter((e) => {
          const subj = (e.subject || '').toLowerCase();
          const sndr = (e.sender || '').toLowerCase();
          const body = (e.body || '').toLowerCase();
          return subj.includes(q) || sndr.includes(q) || body.includes(q);
        });
      }
    } else {
      if (focusMode) {
        list = list.filter(isNeedsAttention);
      }
    }

    // Sorting: skip client-side sort if backend already returned date_desc order
    if (sortBy !== 'date_desc' || !options.serverFiltered) {
      list.sort((a, b) => {
        if (sortBy === 'priority_desc') {
          const rankA = PRIORITY_CONFIG[a.predicted_priority]?.rank || 0;
          const rankB = PRIORITY_CONFIG[b.predicted_priority]?.rank || 0;
          return rankB - rankA;
        }
        if (sortBy === 'deadline_asc') {
          const hasA = a.deadline_detected ? 1 : 0;
          const hasB = b.deadline_detected ? 1 : 0;
          if (hasA !== hasB) return hasB - hasA;
          if (a.deadline_datetime && b.deadline_datetime) {
            return new Date(a.deadline_datetime).getTime() - new Date(b.deadline_datetime).getTime();
          }
          return new Date(b.date || 0).getTime() - new Date(a.date || 0).getTime();
        }
        if (sortBy === 'sender_asc') {
          return (a.sender || '').localeCompare(b.sender || '');
        }
        if (sortBy === 'confidence_desc') {
          return (b.confidence || 0) - (a.confidence || 0);
        }
        if (sortBy === 'date_asc') {
          return new Date(a.date || 0).getTime() - new Date(b.date || 0).getTime();
        }
        return new Date(b.date || 0).getTime() - new Date(a.date || 0).getTime();
      });
    }

    return list;
  }, [emails, activeFilter, searchQuery, focusMode, sortBy, options.serverFiltered]);

  const attentionCount = useMemo(() => {
    if (!emails) return 0;
    return emails.filter(isNeedsAttention).length;
  }, [emails]);

  return {
    searchQuery,
    setSearchQuery,
    activeFilter,
    setActiveFilter,
    actionFilter,
    setActionFilter,
    focusMode,
    setFocusMode,
    sortBy,
    setSortBy,
    filteredEmails,
    attentionCount,
  };
}
