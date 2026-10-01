import { useState, useEffect, useCallback } from 'react';
import { fetchAuthStatus, fetchAuthLogin, logout as apiLogout } from '../services/api';

export function useAuth() {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const checkStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchAuthStatus();
      if (data.authenticated && data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (err) {
      console.error('Failed to check auth status:', err);
      setError(err.message || 'Authentication check failed');
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Check if error parameter in URL (e.g. from OAuth redirect failure)
    const urlParams = new URLSearchParams(window.location.search);
    const authError = urlParams.get('auth_error');
    if (authError) {
      setError(`OAuth authentication error: ${authError}`);
      // Clean up URL without reload
      window.history.replaceState({}, document.title, window.location.pathname);
    }
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
  };
}
