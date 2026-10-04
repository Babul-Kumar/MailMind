import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from './hooks/useAuth';
import { useEmails } from './hooks/useEmails';
import { useSearch } from './hooks/useSearch';
import { AppShell } from './components/layout/AppShell';
import { Inbox } from './components/inbox/Inbox';
import { ConnectAccountHero } from './components/auth/ConnectAccountHero';
import { AuthCallback } from './components/auth/AuthCallback';
import { MailboxLoadingState } from './components/common/MailboxLoadingState';

export function App() {
  const auth = useAuth();
  const emailsHook = useEmails(auth.isAuthenticated);

  const [currentPath, setCurrentPath] = useState(() => {
    if (typeof window !== 'undefined') {
      const pathname = window.location.pathname;
      const search = window.location.search;
      if (pathname.includes('/auth/callback') || search.includes('handoff=') || search.includes('auth_error=')) {
        return '/auth/callback';
      }
      return pathname;
    }
    return '/';
  });

  useEffect(() => {
    const handlePopState = () => {
      const pathname = window.location.pathname;
      const search = window.location.search;
      if (pathname.includes('/auth/callback') || search.includes('handoff=') || search.includes('auth_error=')) {
        setCurrentPath('/auth/callback');
      } else {
        setCurrentPath(pathname);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const searchOptions = useMemo(
    () => ({
      activeFilter: emailsHook.activeFilter,
      setActiveFilter: emailsHook.setActiveFilter,
      actionFilter: emailsHook.actionFilter,
      setActionFilter: emailsHook.setActionFilter,
      searchQuery: emailsHook.searchQuery,
      setSearchQuery: emailsHook.setSearchQuery,
      serverFiltered: true,
    }),
    [
      emailsHook.activeFilter,
      emailsHook.setActiveFilter,
      emailsHook.actionFilter,
      emailsHook.setActionFilter,
      emailsHook.searchQuery,
      emailsHook.setSearchQuery,
    ]
  );

  const searchHook = useSearch(emailsHook.emails, searchOptions);

  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('mailmind_theme') || 'dark';
  });

  const [density, setDensity] = useState(() => {
    return localStorage.getItem('mailmind_density') || 'comfortable';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('mailmind_theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute('data-density', density);
    localStorage.setItem('mailmind_density', density);
  }, [density]);

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  const handleToggleDensity = useCallback(() => {
    setDensity((prev) => (prev === 'comfortable' ? 'compact' : 'comfortable'));
  }, []);

  // Safe Account Switching: Clears all mailbox state, selected emails, search and temporary filters
  const handleSwitchAccount = useCallback(async () => {
    emailsHook.setSearchQuery('');
    emailsHook.setActiveFilter('ALL');
    emailsHook.setActionFilter('ALL');
    searchHook.setFocusMode(false);
    await auth.switchAccount();
  }, [emailsHook, searchHook, auth]);

  const handleLogout = useCallback(async () => {
    emailsHook.setSearchQuery('');
    emailsHook.setActiveFilter('ALL');
    emailsHook.setActionFilter('ALL');
    searchHook.setFocusMode(false);
    await auth.logout();
  }, [emailsHook, searchHook, auth]);

  const authWrapper = useMemo(
    () => ({
      ...auth,
      switchAccount: handleSwitchAccount,
      logout: handleLogout,
    }),
    [auth, handleSwitchAccount, handleLogout]
  );

  const showConnectHero = !auth.isLoading && !auth.isAuthenticated && emailsHook.emails.length === 0;
  const showInitialLoading = auth.isAuthenticated && emailsHook.emails.length === 0 && emailsHook.isScanning;

  return (
    <AppShell
      emailsHook={emailsHook}
      searchHook={searchHook}
      auth={authWrapper}
      theme={theme}
      onToggleTheme={handleToggleTheme}
      density={density}
      onToggleDensity={handleToggleDensity}
      onChangeDensity={setDensity}
    >
      {currentPath === '/auth/callback' ? (
        <AuthCallback
          exchangeHandoff={auth.exchangeHandoff}
          onAuthenticationComplete={(userData) => {
            if (auth.refreshStatus) {
              auth.refreshStatus();
            }
          }}
          onSuccess={(userData) => {
            window.history.replaceState({}, document.title, '/');
            setCurrentPath('/');
            if (auth.refreshStatus) {
              auth.refreshStatus();
            }
          }}
          onCancel={() => {
            window.history.replaceState({}, document.title, '/');
            setCurrentPath('/');
          }}
        />
      ) : showConnectHero ? (
        <ConnectAccountHero
          onLogin={auth.login}
          isLoading={auth.isLoading}
          error={auth.error || emailsHook.error}
        />
      ) : showInitialLoading ? (
        <MailboxLoadingState scanStatus={emailsHook.scanStatus} stepText={emailsHook.loadingStep} />
      ) : (
        <Inbox
          emails={searchHook.filteredEmails}
          allEmails={emailsHook.emails}
          stats={emailsHook.stats}
          isLoading={emailsHook.isLoading}
          isRefreshing={emailsHook.isRefreshing}
          isInitialLoading={emailsHook.isInitialLoading}
          searchQuery={searchHook.searchQuery}
          activeFilter={searchHook.activeFilter}
          onSelectFilter={searchHook.setActiveFilter}
          actionFilter={searchHook.actionFilter}
          onSelectActionFilter={searchHook.setActionFilter}
          focusMode={searchHook.focusMode}
          onToggleFocusMode={searchHook.setFocusMode}
          sortBy={searchHook.sortBy}
          onSortChange={searchHook.setSortBy}
          onRefresh={emailsHook.refresh}
          pagination={emailsHook.pagination}
          onPageChange={emailsHook.setPage}
          scanStatus={emailsHook.scanStatus}
          isScanning={emailsHook.isScanning}
        />
      )}
    </AppShell>
  );
}


export default App;
