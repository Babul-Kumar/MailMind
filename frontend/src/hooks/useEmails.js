import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchEmails,
  fetchScanStatus,
  startScan,
  cancelScan,
  rescanMailbox,
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

  // Scan state from background scan engine
  const [scanStatus, setScanStatus] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const pollTimerRef = useRef(null);

  // Load emails and stats from backend
  const loadData = useCallback(async (customPage, customPageSize, customQuery) => {
    if (!isAuthenticated) return;

    const pageToUse = customPage !== undefined ? customPage : page;
    const sizeToUse = customPageSize !== undefined ? customPageSize : pageSize;
    const queryToUse = customQuery !== undefined ? customQuery : gmailQuery;

    setIsLoading(true);
    setError(null);
    setLoadingStep('Accessing mailbox cache...');

    try {
      const data = await fetchEmails({
        page: pageToUse,
        pageSize: sizeToUse,
        query: queryToUse,
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
  }, [isAuthenticated, page, pageSize, gmailQuery]);

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
            loadData();
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
  }, [isAuthenticated, isScanning, checkScanStatus, loadData]);

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

  // Initial load on authentication
  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    } else {
      setEmails([]);
      setStats(null);
      setProfile(null);
      setError(null);
      setIsLoading(false);
      setScanStatus(null);
      setIsScanning(false);
    }
  }, [isAuthenticated, loadData]);

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
    scanStatus,
    isScanning,
    startScan: triggerScan,
    rescan: triggerRescan,
    cancelScan: triggerCancelScan,
  };
}
