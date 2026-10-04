import { useState, useEffect, useCallback } from 'react';
import { fetchAuthStatus, fetchAuthLogin, fetchAuthExchange, logout as apiLogout } from '../services/api';

export function useAuth() {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

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
        setError(null);
      } else {
        setUser(null);
        setIsAuthenticated(false);
        if (initialError) {
          setError(initialError);
        }
      }
    } catch (err) {
      console.error('Failed to check auth status:', err);
      setError(initialError || err.message || 'Authentication check failed');
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const exchangeHandoff = useCallback(async (handoffCode) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchAuthExchange(handoffCode);
      if (data && data.authenticated && data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
        setError(null);
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
        // Handled by AuthCallback component
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
    } catch (e) {
      // Continue even if logout failed
    }
    setUser(null);
    setIsAuthenticated(false);
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
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch (e) {
      console.warn('Logout request error:', e);
    }
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    switchAccount,
    logout,
    refreshStatus: checkStatus,
    exchangeHandoff,
  };
}
