import * as React from "react";
import { Outlet, useLocation } from "react-router-dom";

import { CommandPalette } from "@/components/CommandPalette";
import { OfflineBanner } from "@/components/layout/OfflineBanner";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { type Role } from "@/lib/api/auth";

const SIDEBAR_COLLAPSED_KEY = "relayops-sidebar-collapsed";

export function AppLayout() {
  const [collapsed, setCollapsed] = React.useState<boolean>(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });

  const [commandPaletteOpen, setCommandPaletteOpen] = React.useState(false);
  const location = useLocation();

  // Full-bleed routes (studios and visualizations) need full width/height without max-w-6xl or outer padding
  const isFullBleed =
    location.pathname.includes("/review") ||
    /^\/handovers\/[^/]+$/.test(location.pathname) ||
    location.pathname.includes("/timeline") ||
    location.pathname.includes("/topology") ||
    location.pathname.includes("/visualizations");

  const toggleCollapse = React.useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      } catch {
        // localStorage not available
      }
      return next;
    });
  }, []);

  const handleSwitchPreviewRole = React.useCallback((role: Role) => {
    // Lead preview role switcher logic
    window.sessionStorage.setItem("relayops-preview-role", role);
    window.dispatchEvent(new CustomEvent("relayops-role-change", { detail: { role } }));
  }, []);

  return (
    <div className="flex h-screen max-h-screen w-full overflow-hidden bg-background text-foreground antialiased selection:bg-primary/20">
      {/* Accessible Skip to Content Link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3.5 focus:py-2 focus:text-xs focus:font-semibold focus:text-primary-foreground focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </a>

      {/* Collapsible Left Sidebar */}
      <Sidebar collapsed={collapsed} onToggleCollapse={toggleCollapse} />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden h-full min-h-0">
        {/* Offline / Disconnection Banner */}
        <OfflineBanner />

        <TopBar
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
          onSwitchPreviewRole={handleSwitchPreviewRole}
        />

        {isFullBleed ? (
          <main id="main-content" tabIndex={-1} className="flex-1 overflow-hidden outline-none flex flex-col w-full min-h-0">
            <Outlet />
          </main>
        ) : (
          <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8 outline-none">
            <div className="mx-auto max-w-6xl space-y-6">
              <Outlet />
            </div>
          </main>
        )}
      </div>

      {/* Global Command Palette */}
      <CommandPalette
        open={commandPaletteOpen}
        onOpenChange={setCommandPaletteOpen}
        onSwitchPreviewRole={handleSwitchPreviewRole}
      />
    </div>
  );
}
