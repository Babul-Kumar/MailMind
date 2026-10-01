import React, { useState, useEffect } from 'react';
import { useAuth } from './hooks/useAuth';
import { useEmails } from './hooks/useEmails';
import { useSearch } from './hooks/useSearch';
import { AppShell } from './components/layout/AppShell';
import { Inbox } from './components/inbox/Inbox';
import { ConnectAccountHero } from './components/auth/ConnectAccountHero';

export function App() {
  const auth = useAuth();
  const emailsHook = useEmails(auth.isAuthenticated);
  const searchHook = useSearch(emailsHook.emails);

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

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleToggleDensity = () => {
    setDensity((prev) => (prev === 'comfortable' ? 'compact' : 'comfortable'));
  };

  // Safe Account Switching: Clears all mailbox state, selected emails, search and temporary filters
  const handleSwitchAccount = async () => {
    searchHook.setSearchQuery('');
    searchHook.setActiveFilter('ALL');
    searchHook.setFocusMode(false);
    await auth.switchAccount();
  };

  const handleLogout = async () => {
    searchHook.setSearchQuery('');
    searchHook.setActiveFilter('ALL');
    searchHook.setFocusMode(false);
    await auth.logout();
  };

  const authWrapper = {
    ...auth,
    switchAccount: handleSwitchAccount,
    logout: handleLogout,
  };

  const showConnectHero = !auth.isLoading && !auth.isAuthenticated && emailsHook.emails.length === 0;

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
      {showConnectHero ? (
        <ConnectAccountHero
          onLogin={auth.login}
          isLoading={auth.isLoading}
          error={auth.error || emailsHook.error}
        />
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
