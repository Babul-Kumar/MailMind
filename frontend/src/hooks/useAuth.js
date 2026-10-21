import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchAuthStatus, fetchAuthLogin, fetchAuthExchange, logout as apiLogout } from '../services/api';

const AUTH_BROADCAST_CHANNEL = 'mailmind_auth_sync';

export function useAuth() {
  const [user, setUser] = useState(() => {
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem('mailmind_last_user');
        return raw ? JSON.parse(raw) : null;
      } catch (_) {
        return null;
      }
    }
    return null;
  });

  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    if (typeof window !== 'undefined') {
      return Boolean(localStorage.getItem('mailmind_last_user'));
    }
    return false;
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [error, setError] = useState(null);

  // Broadcast channel for multi-tab synchronization
  const channelRef = useRef(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'BroadcastChannel' in window) {
      try {
        channelRef.current = new BroadcastChannel(AUTH_BROADCAST_CHANNEL);
        channelRef.current.onmessage = (event) => {
          if (event.data?.type === 'LOGOUT') {
            setUser(null);
            setIsAuthenticated(false);
            try {
              localStorage.removeItem('mailmind_last_user');
            } catch (_) {}
          } else if (event.data?.type === 'LOGIN' && event.data?.user) {
            setUser(event.data.user);
            setIsAuthenticated(true);
          }
        };
      } catch (_) {}
    }

    return () => {
      if (channelRef.current) {
        channelRef.current.close();
      }
    };
  }, []);

  const clearClientCaches = useCallback(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.removeItem('mailmind_last_user');
      // Purge all account-scoped caches
      const keysToRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('mailmind_cache_')) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach((k) => localStorage.removeItem(k));
    } catch (_) {}
  }, []);

  const checkStatus = useCallback(async (initialError = null) => {
    setIsLoading(true);
    if (!initialError) {
      setError(null);
    }
    try {
      const data = await fetchAuthStatus();
      if (data.authenticated && data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
        setIsOffline(false);
        setError(null);
        try {
          localStorage.setItem('mailmind_last_user', JSON.stringify(data.user));
        } catch (_) {}
      } else {
        setUser(null);
        setIsAuthenticated(false);
        setIsOffline(false);
        clearClientCaches();
        if (initialError) {
          setError(initialError);
        }
      }
    } catch (err) {
      console.warn('Backend session check error (offline or cold start):', err);
      // Check if we have a cached user from earlier session
      let cachedUser = null;
      try {
        const raw = localStorage.getItem('mailmind_last_user');
        cachedUser = raw ? JSON.parse(raw) : null;
      } catch (_) {}

      if (cachedUser) {
        // Backend temporarily unavailable / cold start -> preserve session in offline mode
        setUser(cachedUser);
        setIsAuthenticated(true);
        setIsOffline(true);
        setError('Backend is connecting. Showing saved emails.');
      } else {
        setError(initialError || err.message || 'Authentication check failed');
        setUser(null);
        setIsAuthenticated(false);
        setIsOffline(false);
      }
    } finally {
      setIsLoading(false);
    }
  }, [clearClientCaches]);

  const exchangeHandoff = useCallback(async (handoffCode) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchAuthExchange(handoffCode);
      if (data && data.authenticated && data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
        setIsOffline(false);
        setError(null);
        try {
          localStorage.setItem('mailmind_last_user', JSON.stringify(data.user));
          if (channelRef.current) {
            channelRef.current.postMessage({ type: 'LOGIN', user: data.user });
          }
        } catch (_) {}
        return data;
      } else {
        throw new Error('Authentication response unauthenticated.');
      }
    } catch (err) {
      console.error('Failed to exchange handoff code:', err);
      setUser(null);
      setIsAuthenticated(false);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // If on callback route or handoff query exists, let AuthCallback component handle exchange
    if (typeof window !== 'undefined') {
      const pathname = window.location.pathname;
      const search = window.location.search;
      if (pathname.includes('/auth/callback') || search.includes('handoff=') || search.includes('auth_error=')) {
        return;
      }
    }

    // Normal mount check
    checkStatus();
  }, [checkStatus]);

  const login = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchAuthLogin();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error('No authorization URL returned by server.');
      }
    } catch (err) {
      console.error('OAuth login initiation failed:', err);
      setError(err.message || 'Failed to start Google sign-in.');
    }
  }, []);

  const switchAccount = useCallback(async () => {
    try {
      await apiLogout();
    } catch (_) {}
    clearClientCaches();
    setUser(null);
    setIsAuthenticated(false);
    if (channelRef.current) {
      try {
        channelRef.current.postMessage({ type: 'LOGOUT' });
      } catch (_) {}
    }
    // Google OAuth with prompt=select_account forces account selection screen
    try {
      const data = await fetchAuthLogin('select_account');
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      console.error('Account switch initiation failed:', err);
      setError(err.message || 'Failed to initiate account switch.');
    }
  }, [clearClientCaches]);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch (e) {
      console.warn('Logout request warning:', e);
    }
    clearClientCaches();
    setUser(null);
    setIsAuthenticated(false);
    if (channelRef.current) {
      try {
        channelRef.current.postMessage({ type: 'LOGOUT' });
      } catch (_) {}
    }
  }, [clearClientCaches]);

  return {
    user,
    isAuthenticated,
    isLoading,
    isOffline,
    error,
    login,
    switchAccount,
    logout,
    refreshStatus: checkStatus,
    exchangeHandoff,
  };
}

