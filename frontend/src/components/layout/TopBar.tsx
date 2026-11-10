import * as React from "react";
import { ChevronRight, LogOut, Moon, Search, Sun, UserCheck } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useTheme } from "@/app/theme-context";
import { Kbd } from "@/components/shared/Kbd";
import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth, type Role } from "@/lib/api/auth";

export interface TopBarProps {
  onOpenCommandPalette: () => void;
  onSwitchPreviewRole?: (role: Role) => void;
}

export function TopBar({ onOpenCommandPalette, onSwitchPreviewRole }: TopBarProps) {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Generate simple breadcrumbs from path
  const pathParts = location.pathname.split("/").filter(Boolean);
  const breadcrumbs = [
    { label: "RelayOps", href: "/" },
    ...pathParts.map((part, index) => {
      const href = "/" + pathParts.slice(0, index + 1).join("/");
      const label = part.charAt(0).toUpperCase() + part.slice(1).replace(/-/g, " ");
      return { label, href };
    }),
  ];

  const handleSignOut = async () => {
    await logout();
    navigate("/login");
  };

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((p) => p[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "U";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-card-border bg-background/80 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:px-6">
      {/* Left: Breadcrumbs */}
      <nav
        aria-label="Breadcrumbs"
        className="flex items-center space-x-1 text-xs text-ink-muted"
      >
        {breadcrumbs.map((crumb, idx) => {
          const isLast = idx === breadcrumbs.length - 1;
          return (
            <React.Fragment key={crumb.href}>
              {idx > 0 && <ChevronRight className="h-3 w-3 shrink-0 opacity-40" />}
              {isLast ? (
                <span className="font-semibold text-ink">{crumb.label}</span>
              ) : (
                <Link to={crumb.href} className="transition-colors hover:text-ink">
                  {crumb.label}
                </Link>
              )}
            </React.Fragment>
          );
        })}
      </nav>

      {/* Right controls */}
      <div className="flex items-center gap-2">
        {/* Command palette search trigger */}
        <Button
          variant="outline"
          size="sm"
          onClick={onOpenCommandPalette}
          className="relative h-9 w-9 rounded-full border-card-border bg-card p-0 text-ink-muted shadow-card transition-shadow hover:bg-card hover:text-ink hover:shadow-card-hover sm:w-52 sm:justify-start sm:px-3 sm:text-xs"
          aria-label="Search and command palette"
        >
          <Search className="h-3.5 w-3.5 sm:mr-2" />
          <span className="hidden sm:inline">Search or jump to...</span>
          <span className="ml-auto hidden sm:inline">
            <Kbd>⌘K</Kbd>
          </span>
        </Button>

        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          className="h-9 w-9 rounded-full border border-card-border bg-card text-ink-muted shadow-card hover:bg-card hover:text-ink"
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4 text-ink-muted" />
          ) : (
            <Moon className="h-4 w-4 text-ink-muted" />
          )}
        </Button>

        {/* User Menu */}
        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="relative h-9 gap-2 rounded-full border border-card-border bg-card px-3 text-xs font-normal text-ink shadow-card hover:bg-card"
                aria-label="User account menu"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-soft font-mono text-[11px] font-semibold text-brand-text">
                  {initials}
                </span>
                <span className="hidden font-medium text-ink sm:inline">
                  {user.name.split(" ")[0]}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-xs font-semibold leading-none">{user.name}</p>
                  <p className="font-mono text-[11px] leading-none text-muted-foreground">
                    {user.email}
                  </p>
                  <div className="mt-2 flex items-center gap-1.5 pt-1">
                    <Badge variant="secondary" className="capitalize text-[10px]">
                      {user.role}
                    </Badge>
                    <SensitivityBadge level={user.clearance} size="sm" />
                  </div>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />

              {user.role === "lead" && onSwitchPreviewRole && (
                <>
                  <DropdownMenuLabel className="text-[10px] uppercase text-muted-foreground">
                    Preview role as
                  </DropdownMenuLabel>
                  {(["lead", "outgoing", "successor", "contractor", "auditor"] as Role[]).map(
                    (roleOpt) => (
                      <DropdownMenuItem
                        key={roleOpt}
                        onClick={() => onSwitchPreviewRole(roleOpt)}
                        className="gap-2 text-xs capitalize"
                      >
                        <UserCheck className="h-3.5 w-3.5 text-primary" />
                        <span>{roleOpt}</span>
                      </DropdownMenuItem>
                    ),
                  )}
                  <DropdownMenuSeparator />
                </>
              )}

              <DropdownMenuItem
                onClick={handleSignOut}
                className="gap-2 text-xs text-destructive focus:text-destructive"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span>Sign Out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Button size="sm" asChild className="h-8 text-xs">
            <Link to="/login">Sign In</Link>
          </Button>
        )}
      </div>
    </header>
  );
}
