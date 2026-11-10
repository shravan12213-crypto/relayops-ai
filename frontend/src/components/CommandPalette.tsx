import * as React from "react";
import {
  BookOpen,
  Bot,
  FileText,
  FolderGit2,
  Home,
  LogOut,
  Moon,
  Shield,
  Sun,
  UserCheck,
  Wrench,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useTheme } from "@/app/theme-context";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { useAuth, type Role } from "@/lib/api/auth";
import { useHandovers } from "@/lib/api/handovers";

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSwitchPreviewRole?: (role: Role) => void;
}

export function CommandPalette({ open, onOpenChange, onSwitchPreviewRole }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const { data: handovers } = useHandovers();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, onOpenChange]);

  const runCommand = React.useCallback(
    (command: () => void) => {
      onOpenChange(false);
      command();
    },
    [onOpenChange],
  );

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigation">
          <CommandItem onSelect={() => runCommand(() => navigate("/"))} className="gap-2">
            <Home className="h-4 w-4 text-muted-foreground" />
            <span>Dashboard</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => navigate("/projects"))} className="gap-2">
            <FolderGit2 className="h-4 w-4 text-muted-foreground" />
            <span>Projects & Ingestion</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => navigate("/handovers"))} className="gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span>Handovers</span>
          </CommandItem>
          {handovers && handovers[0] && (
            <>
              <CommandItem
                onSelect={() => runCommand(() => navigate(`/handovers/${handovers[0].id}/portal`))}
                className="gap-2"
              >
                <BookOpen className="h-4 w-4 text-primary" />
                <span>Successor Handover Portal</span>
              </CommandItem>
              <CommandItem
                onSelect={() => runCommand(() => navigate(`/handovers/${handovers[0].id}/copilot`))}
                className="gap-2"
              >
                <Bot className="h-4 w-4 text-primary" />
                <span>Handover Copilot (Full View)</span>
              </CommandItem>
            </>
          )}
          <CommandItem onSelect={() => runCommand(() => navigate("/governance"))} className="gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <span>Governance & Audit</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => navigate("/dev/components"))}
            className="gap-2"
          >
            <Wrench className="h-4 w-4 text-muted-foreground" />
            <span>Design System & Components (Dev)</span>
          </CommandItem>
        </CommandGroup>

        {user?.role === "lead" && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Switch View Role (Lead Preview)">
              {(["lead", "outgoing", "successor", "contractor", "auditor"] as Role[]).map(
                (roleOption) => (
                  <CommandItem
                    key={roleOption}
                    onSelect={() =>
                      runCommand(() => {
                        if (onSwitchPreviewRole) {
                          onSwitchPreviewRole(roleOption);
                        } else {
                          toast.info(`Switched preview role to ${roleOption}`);
                        }
                      })
                    }
                    className="gap-2 capitalize"
                  >
                    <UserCheck className="h-4 w-4 text-primary" />
                    <span>View as {roleOption}</span>
                  </CommandItem>
                ),
              )}
            </CommandGroup>
          </>
        )}

        <CommandSeparator />
        <CommandGroup heading="Preferences & Account">
          <CommandItem onSelect={() => runCommand(toggleTheme)} className="gap-2">
            {theme === "dark" ? (
              <Sun className="h-4 w-4 text-ink-muted" />
            ) : (
              <Moon className="h-4 w-4 text-ink-muted" />
            )}
            <span>Toggle {theme === "dark" ? "Light" : "Dark"} Mode</span>
          </CommandItem>
          <CommandItem
            onSelect={() =>
              runCommand(async () => {
                await logout();
                navigate("/login");
              })
            }
            className="gap-2 text-destructive"
          >
            <LogOut className="h-4 w-4" />
            <span>Sign Out</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
