import * as React from "react";
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  FolderGit2,
  Home,
  Shield,
  Sliders,
  Wrench,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useHealth } from "@/lib/api/system";
import { cn } from "@/lib/utils";

export interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({ collapsed, onToggleCollapse }: SidebarProps) {
  const location = useLocation();
  const health = useHealth();

  const navItems = [
    { label: "Dashboard", href: "/", icon: Home },
    { label: "Projects & Ingest", href: "/projects", icon: FolderGit2 },
    { label: "Handovers", href: "/handovers", icon: FileText },
    { label: "Governance", href: "/governance", icon: Shield },
    { label: "Settings", href: "/settings", icon: Sliders },
  ];

  // In development, show Dev Components route
  navItems.push({
    label: "Design System (Dev)",
    href: "/dev/components",
    icon: Wrench,
  });

  return (
    <aside
      className={cn(
        "relative flex flex-col border-r border-transparent bg-gradient-to-b from-sidebar-from to-sidebar-to text-sidebar-fg transition-all duration-300 ease-in-out",
        collapsed ? "w-16" : "w-60",
      )}
    >
      {/* Brand Header */}
      <div className="flex h-14 items-center justify-between border-b border-white/10 px-3.5">
        <Link
          to="/"
          className={cn(
            "flex items-center gap-2.5 overflow-hidden transition-opacity hover:opacity-90",
            collapsed && "justify-center w-full",
          )}
        >
          <img
            src="/logo.png"
            alt="RelayOps"
            className="size-8 shrink-0 rounded-xl object-contain shadow-sm ring-1 ring-white/10"
          />
          {!collapsed && (
            <div className="flex flex-col">
              <span className="text-sm font-semibold tracking-tight text-white">RelayOps</span>
              <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-sidebar-fg-muted">
                Verifiable Handovers
              </span>
            </div>
          )}
        </Link>
      </div>

      {/* Nav Links */}
      <nav aria-label="Main Navigation" className="flex-1 space-y-1 p-2">
        <TooltipProvider delayDuration={150}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.href);

            const linkContent = (
              <Link
                to={item.href}
                className={cn(
                  "flex h-11 items-center gap-3 rounded-xl px-2.5 text-[13px] font-medium transition-colors duration-150",
                  isActive
                    ? "bg-sidebar-active text-white font-semibold"
                    : "text-sidebar-fg-muted hover:bg-white/5 hover:text-white",
                  collapsed && "justify-center px-2",
                )}
              >
                <span
                  className={cn(
                    "grid size-8 shrink-0 place-items-center rounded-full transition-colors",
                    isActive ? "bg-brand text-sidebar-from" : "bg-white/5 text-sidebar-fg-muted",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                </span>
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );

            if (collapsed) {
              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                  <TooltipContent side="right" className="text-xs">
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return <React.Fragment key={item.href}>{linkContent}</React.Fragment>;
          })}
        </TooltipProvider>
      </nav>

      {/* System Status and Collapse Button */}
      <div className="border-t border-white/10 p-2">
        {!collapsed && (
          <div className="mb-2 flex items-center justify-between rounded-xl bg-white/5 px-2.5 py-2 text-[11px] text-sidebar-fg-muted">
            <span className="flex items-center gap-1.5 font-mono">
              <span
                className={cn(
                  "size-2 rounded-full",
                  health.data?.status === "ok"
                    ? "bg-brand shadow-[0_0_0_3px_rgba(47,203,122,0.25)]"
                    : "bg-danger shadow-[0_0_0_3px_rgba(217,69,61,0.25)]",
                )}
              />
              API {health.data?.status ?? "connecting..."}
            </span>
            {health.data?.llm_mode && (
              <span className="font-mono text-[10px] uppercase text-sidebar-fg-muted/70">
                {health.data.llm_mode}
              </span>
            )}
          </div>
        )}

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onToggleCollapse}
          className={cn(
            "w-full text-sidebar-fg-muted hover:text-white hover:bg-white/5 h-9 rounded-xl text-xs",
            collapsed && "justify-center px-0",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <div className="flex w-full items-center justify-between">
              <span>Collapse</span>
              <ChevronLeft className="h-4 w-4" />
            </div>
          )}
        </Button>
      </div>
    </aside>
  );
}
