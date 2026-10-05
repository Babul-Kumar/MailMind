import React, { useState } from 'react';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { SettingsPanel } from '../settings/SettingsPanel';

export function AppShell({
  emailsHook,
  searchHook,
  auth,
  theme,
  onToggleTheme,
  density = 'comfortable',
  onToggleDensity,
  onChangeDensity,
  children,
}) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isSidebarOpenMobile, setIsSidebarOpenMobile] = useState(false);

  // Lock background body scroll when mobile drawer is open
  React.useEffect(() => {
    if (isSidebarOpenMobile) {
      document.body.classList.add('mobile-drawer-open');
    } else {
      document.body.classList.remove('mobile-drawer-open');
    }
    return () => {
      document.body.classList.remove('mobile-drawer-open');
    };
  }, [isSidebarOpenMobile]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '100dvh', maxHeight: '100dvh', overflow: 'hidden' }}>
      <TopBar
        searchQuery={searchHook.searchQuery}
        onSearchChange={searchHook.setSearchQuery}
        matchCount={searchHook.filteredEmails?.length}
        isLoading={emailsHook.isLoading}
        isRefreshing={emailsHook.isRefreshing}
        isJustUpdated={emailsHook.isJustUpdated}
        loadingStep={emailsHook.loadingStep}
        profile={emailsHook.profile}
        stats={emailsHook.stats}
        auth={auth}
        onRefresh={emailsHook.refresh}
        scanStatus={emailsHook.scanStatus}
        isScanning={emailsHook.isScanning}
        onStartScan={emailsHook.startScan}
        onCancelScan={emailsHook.cancelScan}
        onRescan={emailsHook.rescan}
        theme={theme}
        onToggleTheme={onToggleTheme}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onToggleMobileMenu={() => setIsSidebarOpenMobile(!isSidebarOpenMobile)}
      />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>
        <Sidebar
          activeFilter={searchHook.activeFilter}
          onSelectFilter={searchHook.setActiveFilter}
          focusMode={searchHook.focusMode}
          onToggleFocusMode={searchHook.setFocusMode}
          stats={emailsHook.stats}
          totalCount={emailsHook.stats?.total_analyzed || emailsHook.pagination?.total_emails || emailsHook.emails.length}
          attentionCount={emailsHook.stats?.needs_attention_count ?? searchHook.attentionCount}
          onOpenSettings={() => {
            setIsSidebarOpenMobile(false);
            setIsSettingsOpen(true);
          }}
          isOpenMobile={isSidebarOpenMobile}
          onCloseMobile={() => setIsSidebarOpenMobile(false)}
          auth={auth}
          profile={emailsHook.profile}
          onRescan={emailsHook.rescan}
          isScanning={emailsHook.isScanning}
          scanStatus={emailsHook.scanStatus}
          theme={theme}
          onToggleTheme={onToggleTheme}
        />

        {isSidebarOpenMobile && (
          <div
            className="sidebar-backdrop"
            onClick={() => setIsSidebarOpenMobile(false)}
            aria-label="Close navigation backdrop"
          />
        )}

        <main className="app-main-content">
          {children}
        </main>
      </div>

      <SettingsPanel
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        pageSize={emailsHook.pageSize}
        onChangePageSize={emailsHook.setPageSize}
        gmailQuery={emailsHook.gmailQuery}
        onUpdateQuery={emailsHook.setGmailQuery}
        scanStatus={emailsHook.scanStatus}
        onStartScan={emailsHook.startScan}
        onRescan={emailsHook.rescan}
        onCancelScan={emailsHook.cancelScan}
        profile={emailsHook.profile}
        auth={auth}
        theme={theme}
        onToggleTheme={onToggleTheme}
        density={density}
        onToggleDensity={onToggleDensity}
        onChangeDensity={onChangeDensity}
      />

    </div>
  );
}
