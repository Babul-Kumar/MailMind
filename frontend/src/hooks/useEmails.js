import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchEmails,
  fetchScanStatus,
  startScan,
  cancelScan,
  rescanMailbox,
  resolveAction,
  unresolveAction,
  snoozeAction,
  unsnoozeAction,
  fetchActionQueue,
} from '../services/api';

export function useEmails(isAuthenticated = false) {
  const [emails, setEmails] = useState([]);
  const [stats, setStats] = useState(null);
  const [profile, setProfile] = useState(null);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: 50,
    total_emails: 0,
    total_pages: 1,
    has_next: false,
    has_prev: false,
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [error, setError] = useState(null);
  const [gmailQuery, setGmailQuery] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isJustUpdated, setIsJustUpdated] = useState(false);

  const [activeFilter, setActiveFilterState] = useState('ALL');
  const [actionFilter, setActionFilterState] = useState('ALL');
  const [searchQuery, setSearchQueryState] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');

  // Debounce search input to avoid hitting backend on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 280);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const setActiveFilter = useCallback((newFilter) => {
    setActiveFilterState(newFilter);
    setActionFilterState('ALL');
    setPage(1);
  }, []);

  const setActionFilter = useCallback((newAction) => {
    setActionFilterState(newAction);
    setPage(1);
  }, []);

  const setSearchQuery = useCallback((newQuery) => {
    setSearchQueryState(newQuery);
    setPage(1);
  }, []);

  // Scan state from background scan engine
  const [scanStatus, setScanStatus] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const pollTimerRef = useRef(null);

  // Load emails and stats from backend
  const loadData = useCallback(async (customPage, customPageSize, customQuery, customFilter, customAction) => {
    if (!isAuthenticated) return;

    const pageToUse = customPage !== undefined ? customPage : page;
    const sizeToUse = customPageSize !== undefined ? customPageSize : pageSize;
    const filterToUse = customFilter !== undefined ? customFilter : activeFilter;
    const actionToUse = customAction !== undefined ? customAction : actionFilter;
    const searchToUse = customQuery !== undefined ? customQuery : debouncedSearchQuery;

    const priorityParam = filterToUse !== 'ALL' ? filterToUse : '';
    const actionParam = actionToUse === 'ACTION_REQUIRED' ? true : actionToUse === 'NO_ACTION' ? false : null;
    const queryParam = searchToUse.trim() || gmailQuery;

    setIsLoading(true);
    setError(null);
    setLoadingStep('Accessing mailbox cache...');

    try {
      const data = await fetchEmails({
        page: pageToUse,
        pageSize: sizeToUse,
        priority: priorityParam,
        query: queryParam,
        actionRequired: actionParam,
      });

      setEmails(data.emails || []);
      setStats(data.stats || null);
      setProfile(data.profile || null);
      if (data.pagination) {
        setPagination(data.pagination);
      } else {
        setPagination({
          page: pageToUse,
          page_size: sizeToUse,
          total_emails: data.emails?.length || 0,
          total_pages: 1,
          has_next: false,
          has_prev: false,
        });
      }
      if (data.scan_status) {
        setScanStatus(data.scan_status);
        const active = ['QUEUED', 'SCANNING', 'ANALYZING', 'FINALIZING'].includes(data.scan_status.status);
        setIsScanning(active);
      }

      setLastUpdated(new Date());
      setLoadingStep('Mailbox synchronized');

      setIsJustUpdated(true);
      setTimeout(() => {
        setIsJustUpdated(false);
      }, 1500);
    } catch (err) {
      if (err.status === 401) {
        setEmails([]);
        setStats(null);
        setProfile(null);
        setError(null);
      } else {
        console.error('Error fetching mailbox:', err);
        setError(err.message || 'Failed to connect to Gmail.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, page, pageSize, activeFilter, actionFilter, debouncedSearchQuery, gmailQuery]);

  // Check and update scan status
  const checkScanStatus = useCallback(async () => {
    if (!isAuthenticated) return null;
    try {
      const statusData = await fetchScanStatus();
      setScanStatus(statusData);
      const active = ['QUEUED', 'SCANNING', 'ANALYZING', 'FINALIZING'].includes(statusData.status);
      setIsScanning(active);
      return statusData;
    } catch (err) {
      console.warn('Failed to poll scan status:', err);
      return null;
    }
  }, [isAuthenticated]);

  // Polling loop for active background scans
  const lastRefreshedCount = useRef(0);
  const loadDataRef = useRef(loadData);
  useEffect(() => {
    loadDataRef.current = loadData;
  });

  const initialLoadedRef = useRef(false);

  useEffect(() => {
    if (!isAuthenticated) {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      return;
    }

    // Initial check
    checkScanStatus();

    const startPolling = () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(async () => {
        const latest = await checkScanStatus();
        if (latest) {
          const isActive = ['QUEUED', 'SCANNING', 'ANALYZING', 'FINALIZING'].includes(latest.status);
          if (!isActive) {
            // Scan finished or stopped — refresh email view
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
            loadDataRef.current();
          } else if (latest.status === 'ANALYZING' && latest.analyzed) {
            // As batches complete and are committed to cache, refresh list periodically
            if (latest.analyzed - lastRefreshedCount.current >= 50) {
              lastRefreshedCount.current = latest.analyzed;
              loadDataRef.current();
            }
          }
        }
      }, 1500);
    };

    if (isScanning) {
      startPolling();
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [isAuthenticated, isScanning, checkScanStatus]);

  // Trigger Complete Scan (Incremental by default, or full discovery)
  const triggerScan = useCallback(async ({ scope = 'mailbox', mode = 'incremental', forceRescan = false } = {}) => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await startScan({
        scope,
        mode,
        query: gmailQuery,
        forceRescan,
      });
      setScanStatus(res.scan_status);
      setIsScanning(true);
    } catch (err) {
      console.error('Error initiating scan:', err);
      setError(err.message || 'Failed to start Gmail scan.');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, gmailQuery]);

  // Trigger Full Rescan
  const triggerRescan = useCallback(async ({ scope = 'mailbox' } = {}) => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await rescanMailbox({ scope });
      setScanStatus(res.scan_status);
      setIsScanning(true);
    } catch (err) {
      console.error('Error initiating rescan:', err);
      setError(err.message || 'Failed to start full rescan.');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Cancel running scan
  const triggerCancelScan = useCallback(async () => {
    try {
      const res = await cancelScan();
      setScanStatus(res.scan_status);
      setIsScanning(false);
    } catch (err) {
      console.error('Error cancelling scan:', err);
    }
  }, []);

  // Initial load once upon authentication
  useEffect(() => {
    if (isAuthenticated) {
      if (!initialLoadedRef.current) {
        initialLoadedRef.current = true;
        loadDataRef.current().then(() => {
          checkScanStatus().then((status) => {
            if (!status || status.status === 'NOT_STARTED' || (status.status === 'COMPLETE' && status.total === 0)) {
              triggerScan({ scope: 'mailbox', mode: 'incremental' });
            }
          });
        });
      }
    } else {
      initialLoadedRef.current = false;
      setEmails([]);
      setStats(null);
      setProfile(null);
      setError(null);
      setIsLoading(false);
      setScanStatus(null);
      setIsScanning(false);
    }
  }, [isAuthenticated, checkScanStatus, triggerScan]);

  // Subsequent data fetch when query, page, or filters change
  useEffect(() => {
    if (isAuthenticated && initialLoadedRef.current) {
      loadDataRef.current();
    }
  }, [isAuthenticated, page, pageSize, activeFilter, actionFilter, debouncedSearchQuery, gmailQuery]);

  // Smart Action Queue State
  const [actionQueue, setActionQueue] = useState({
    active_queue: [],
    older_actions: [],
    snoozed_items: [],
    resolved_items: [],
    counts: {
      urgent: 0,
      due_soon: 0,
      other_active: 0,
      total_active: 0,
      older: 0,
      snoozed: 0,
      resolved: 0,
    },
  });
  const [actionQueueLoading, setActionQueueLoading] = useState(false);
  const [actionSortBy, setActionSortBy] = useState('urgent');
  const [olderSortBy, setOlderSortBy] = useState('oldest');
  const [recentlyResolved, setRecentlyResolved] = useState(null);

  // Load Action Queue from backend
  const loadActionQueue = useCallback(async (customSort, customOlderSort) => {
    if (!isAuthenticated) return;
    const sToUse = customSort || actionSortBy;
    const osToUse = customOlderSort || olderSortBy;
    setActionQueueLoading(true);
    try {
      const res = await fetchActionQueue({ sortBy: sToUse, olderSortBy: osToUse });
      if (res.data) {
        setActionQueue(res.data);
      }
    } catch (err) {
      console.warn('Could not load action queue:', err);
    } finally {
      setActionQueueLoading(false);
    }
  }, [isAuthenticated, actionSortBy, olderSortBy]);

  // Refresh action queue whenever activeFilter becomes 'NEEDS_ATTENTION'
  useEffect(() => {
    if (isAuthenticated && activeFilter === 'NEEDS_ATTENTION') {
      loadActionQueue();
    }
  }, [isAuthenticated, activeFilter, loadActionQueue]);

  // Mark Resolved with Optimistic Update and Undo
  const handleResolve = useCallback(async (messageId, threadId = null, note = null) => {
    if (!messageId) return;

    // Optimistic UI update
    setActionQueue((prev) => {
      const itemToResolve = prev.active_queue.find((e) => (e.email_id || e.id || e.message_id) === messageId)
        || prev.older_actions.find((e) => (e.email_id || e.id || e.message_id) === messageId);

      const newActive = prev.active_queue.filter((e) => (e.email_id || e.id || e.message_id) !== messageId);
      const newOlder = prev.older_actions.filter((e) => (e.email_id || e.id || e.message_id) !== messageId);
      const resolvedList = itemToResolve
        ? [{ ...itemToResolve, is_resolved: true, queue_placement: 'RESOLVED' }, ...prev.resolved_items]
        : prev.resolved_items;

      return {
        ...prev,
        active_queue: newActive,
        older_actions: newOlder,
        resolved_items: resolvedList,
        counts: {
          ...prev.counts,
          total_active: Math.max(0, newActive.length),
          older: Math.max(0, newOlder.length),
          resolved: (prev.counts.resolved || 0) + 1,
        },
      };
    });

    setEmails((prev) =>
      prev.map((e) => ((e.email_id || e.id || e.message_id) === messageId ? { ...e, is_resolved: true } : e))
    );

    // Provide undo toast
    setRecentlyResolved({ messageId, timestamp: Date.now() });

    try {
      await resolveAction(messageId, threadId, note);
    } catch (err) {
      console.error('Failed to resolve action:', err);
      setError('Could not save resolution on server. Please try again.');
      // Revert optimistic update
      loadActionQueue();
    }
  }, [loadActionQueue]);

  // Undo / Unresolve
  const handleUnresolve = useCallback(async (messageId) => {
    if (!messageId) return;
    setRecentlyResolved(null);
    try {
      await unresolveAction(messageId);
      await loadActionQueue();
      loadDataRef.current();
    } catch (err) {
      console.error('Failed to undo resolution:', err);
      setError('Failed to undo resolution.');
    }
  }, [loadActionQueue]);

  // Snooze Action
  const handleSnooze = useCallback(async (messageId, snoozeUntil, threadId = null, reason = null) => {
    if (!messageId || !snoozeUntil) return;

    // Optimistic UI update
    setActionQueue((prev) => {
      const itemToSnooze = prev.active_queue.find((e) => (e.email_id || e.id || e.message_id) === messageId)
        || prev.older_actions.find((e) => (e.email_id || e.id || e.message_id) === messageId);

      const newActive = prev.active_queue.filter((e) => (e.email_id || e.id || e.message_id) !== messageId);
      const newOlder = prev.older_actions.filter((e) => (e.email_id || e.id || e.message_id) !== messageId);
      const snoozedList = itemToSnooze
        ? [{ ...itemToSnooze, is_snoozed: true, snoozed_until: snoozeUntil, queue_placement: 'SNOOZED' }, ...prev.snoozed_items]
        : prev.snoozed_items;

      return {
        ...prev,
        active_queue: newActive,
        older_actions: newOlder,
        snoozed_items: snoozedList,
        counts: {
          ...prev.counts,
          total_active: Math.max(0, newActive.length),
          older: Math.max(0, newOlder.length),
          snoozed: (prev.counts.snoozed || 0) + 1,
        },
      };
    });

    try {
      await snoozeAction(messageId, snoozeUntil, threadId, reason);
    } catch (err) {
      console.error('Failed to snooze action:', err);
      setError('Could not snooze item on server.');
      loadActionQueue();
    }
  }, [loadActionQueue]);

  // Unsnooze Action
  const handleUnsnooze = useCallback(async (messageId) => {
    if (!messageId) return;
    try {
      await unsnoozeAction(messageId);
      await loadActionQueue();
      loadDataRef.current();
    } catch (err) {
      console.error('Failed to unsnooze:', err);
      setError('Failed to unsnooze item.');
    }
  }, [loadActionQueue]);

  const isInitialLoading = isLoading && emails.length === 0;
  const isRefreshing = isLoading && emails.length > 0;


  return {
    emails,
    stats,
    profile,
    pagination,
    page,
    setPage,
    pageSize,
    setPageSize,
    isLoading,
    isInitialLoading,
    isRefreshing,
    isJustUpdated,
    loadingStep,
    error,
    gmailQuery,
    setGmailQuery,
    lastUpdated,
    refresh: loadData,
    activeFilter,
    setActiveFilter,
    actionFilter,
    setActionFilter,
    searchQuery,
    setSearchQuery,
    scanStatus,
    isScanning,
    startScan: triggerScan,
    rescan: triggerRescan,
    cancelScan: triggerCancelScan,
    actionQueue,
    actionQueueLoading,
    actionSortBy,
    setActionSortBy,
    olderSortBy,
    setOlderSortBy,
    loadActionQueue,
    resolveEmail: handleResolve,
    unresolveEmail: handleUnresolve,
    snoozeEmail: handleSnooze,
    unsnoozeEmail: handleUnsnooze,
    recentlyResolved,
    clearRecentlyResolved: () => setRecentlyResolved(null),
  };
}
