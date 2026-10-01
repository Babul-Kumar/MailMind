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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <TopBar
        searchQuery={searchHook.searchQuery}
        onSearchChange={searchHook.setSearchQuery}
        matchCount={searchHook.filteredEmails?.length}
        isLoading={emailsHook.isLoading}
        isRefreshing={emailsHook.isRefreshing}
        isJustUpdated={emailsHook.isJustUpdated}
        loadingStep={emailsHook.loadingStep}
        profile={emailsHook.profile}
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

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar
          activeFilter={searchHook.activeFilter}
          onSelectFilter={searchHook.setActiveFilter}
          focusMode={searchHook.focusMode}
          onToggleFocusMode={searchHook.setFocusMode}
          stats={emailsHook.stats}
          totalCount={emailsHook.stats?.total_analyzed || emailsHook.pagination?.total_emails || emailsHook.emails.length}
          attentionCount={searchHook.attentionCount}
          onOpenSettings={() => setIsSettingsOpen(true)}
          isOpenMobile={isSidebarOpenMobile}
          onCloseMobile={() => setIsSidebarOpenMobile(false)}
        />

        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1.25rem 1.5rem',
            backgroundColor: 'var(--bg-app)',
          }}
        >
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
        theme={theme}
        onToggleTheme={onToggleTheme}
        density={density}
        onToggleDensity={onToggleDensity}
        onChangeDensity={onChangeDensity}
      />

    </div>
  );
}
