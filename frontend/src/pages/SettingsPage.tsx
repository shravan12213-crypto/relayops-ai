import * as React from "react";
import {
  AlertTriangle,
  Clock,
  Cpu,
  Globe,
  HelpCircle,
  Loader2,
  Moon,
  RotateCcw,
  Shield,
  Sun,
  User as UserIcon,
} from "lucide-react";

import { useTheme } from "@/app/theme-context";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { PageHeader } from "@/components/shared/PageHeader";
import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/lib/api/auth";
import { useResetDemoData, useSystemStatus } from "@/lib/api/governance";

export function SettingsPage() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { data: systemStatus, isLoading: statusLoading, refetch: refetchStatus } = useSystemStatus();
  const resetDemoMutation = useResetDemoData();

  const [resetDialogOpen, setResetDialogOpen] = React.useState(false);
  const [currentTime, setCurrentTime] = React.useState<string>(new Date().toLocaleTimeString());

  React.useEffect(() => {
    document.title = "Settings & Environment — RelayOps";
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Browser timezone details
  const timeZone = React.useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
      return "UTC";
    }
  }, []);

  const utcOffset = React.useMemo(() => {
    const offsetMin = -new Date().getTimezoneOffset();
    const sign = offsetMin >= 0 ? "+" : "-";
    const hours = Math.floor(Math.abs(offsetMin) / 60)
      .toString()
      .padStart(2, "0");
    const mins = (Math.abs(offsetMin) % 60).toString().padStart(2, "0");
    return `UTC${sign}${hours}:${mins}`;
  }, []);

  const isLiveMode = systemStatus?.llm_mode === "live";
  const isDevOrDemo =
    systemStatus?.environment === "dev" ||
    systemStatus?.environment === "demo" ||
    !systemStatus?.environment;

  const handleConfirmReset = async () => {
    await resetDemoMutation.mutateAsync();
    refetchStatus();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings & Environment"
        description="User identity, interface preferences, timezone configuration, LLM execution mode, and demo data administration."
      />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* User Profile Card */}
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <UserIcon className="h-4 w-4 text-primary" />
              User Profile & Authorization
            </CardTitle>
            <CardDescription className="text-xs">
              Your active identity, role, and security clearance level in RelayOps
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-xs">
              <dt className="text-muted-foreground">Full Name</dt>
              <dd className="font-semibold text-foreground">{user?.name}</dd>
              <dt className="text-muted-foreground">Email</dt>
              <dd className="font-mono text-foreground">{user?.email}</dd>
              <dt className="text-muted-foreground">Assigned Role</dt>
              <dd>
                <Badge variant="secondary" className="capitalize text-[11px]">
                  {user?.role}
                </Badge>
              </dd>
              <dt className="text-muted-foreground">Clearance Level</dt>
              <dd>
                <SensitivityBadge level={user?.clearance ?? 0} size="sm" />
              </dd>
            </dl>
          </CardContent>
        </Card>

        {/* Interface Preferences */}
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Shield className="h-4 w-4 text-primary" />
              Interface Theme
            </CardTitle>
            <CardDescription className="text-xs">
              Calm, dense developer-tool aesthetic with persistent light/dark mode
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-foreground">Color Mode</p>
                <p className="text-[11px] text-muted-foreground">
                  Currently active: <span className="font-semibold capitalize text-foreground">{theme}</span>
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={toggleTheme} className="gap-2 text-xs">
                {theme === "dark" ? (
                  <>
                    <Sun className="h-3.5 w-3.5 text-amber-500" />
                    Switch to Light
                  </>
                ) : (
                  <>
                    <Moon className="h-3.5 w-3.5 text-blue-500" />
                    Switch to Dark
                  </>
                )}
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed pt-2 border-t border-border">
              Theme preferences are stored locally in your browser and automatically respect your operating system settings.
            </p>
          </CardContent>
        </Card>

        {/* Timezone Configuration Card */}
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary" />
              Timezone & Timestamps
            </CardTitle>
            <CardDescription className="text-xs">
              Local presentation of UTC-stored handover timelines and audit records
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-xs">
              <dt className="text-muted-foreground">Detected Zone</dt>
              <dd className="font-mono text-foreground font-semibold flex items-center gap-1.5">
                <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                {timeZone} ({utcOffset})
              </dd>
              <dt className="text-muted-foreground">Local Time</dt>
              <dd className="font-mono text-foreground">{currentTime}</dd>
              <dt className="text-muted-foreground">DB Storage</dt>
              <dd className="font-mono text-muted-foreground">UTC ISO-8601 (Strict)</dd>
            </div>
            <div className="rounded border border-border bg-muted/20 p-2.5 text-[11px] text-muted-foreground leading-relaxed">
              All dates and times in RelayOps are stored immutably in UTC. They are rendered here in your browser's local timezone.
            </div>
          </CardContent>
        </Card>

        {/* LLM Runtime & Environment Card */}
        <Card className="border-border">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Cpu className="h-4 w-4 text-primary" />
                LLM Execution Mode
              </CardTitle>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground transition-colors"
                      aria-label="LLM mode info"
                    >
                      <HelpCircle className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs text-xs p-3">
                    <p className="font-semibold mb-1">Dual LLM Architecture</p>
                    <p className="text-[11px] leading-relaxed">
                      <strong>Replay Mode:</strong> Deterministic pre-recorded golden outputs for zero-key local testing.
                      <br />
                      <strong>Live Mode:</strong> Direct API calls to Anthropic Claude or OpenAI models.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <CardDescription className="text-xs">
              Configured AI provider, model selection, and database status
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {statusLoading ? (
              <div className="p-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                Loading system status...
              </div>
            ) : systemStatus ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Runtime Mode</span>
                  {isLiveMode ? (
                    <Badge variant="outline" className="font-mono text-xs bg-verified/10 text-verified border-verified/30">
                      ● Live ({systemStatus.llm_model})
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="font-mono text-xs bg-primary/10 text-primary border-primary/30">
                      Replay (recorded)
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-xs pt-1 border-t border-border">
                  <dt className="text-muted-foreground">Provider</dt>
                  <dd className="font-mono text-foreground capitalize">
                    {systemStatus.llm_provider || "Replay Engine"}
                  </dd>
                  <dt className="text-muted-foreground">Model</dt>
                  <dd className="font-mono text-foreground">{systemStatus.llm_model}</dd>
                  <dt className="text-muted-foreground">Environment</dt>
                  <dd className="font-mono text-foreground capitalize">
                    {systemStatus.environment}
                  </dd>
                  <dt className="text-muted-foreground">Database</dt>
                  <dd className="font-mono text-foreground">{systemStatus.database}</dd>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">System status unavailable.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Danger Zone: Reset Demo Data */}
      {isDevOrDemo && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-4 w-4" />
              Danger Zone — Demo & Development Data Reset
            </CardTitle>
            <CardDescription className="text-xs text-destructive/80">
              Administrative actions available only in dev and demo environments.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <p className="text-xs font-semibold text-foreground">Reset Demo Dataset</p>
                <p className="text-xs text-muted-foreground max-w-lg leading-relaxed">
                  Resets the database, reseeds the PayFlow golden dataset (commits, PRs, Jira tickets, Slack logs, ADRs),
                  and clears transient handovers and review comments.
                </p>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setResetDialogOpen(true)}
                disabled={resetDemoMutation.isPending || user?.role !== "lead"}
                className="gap-1.5 text-xs shrink-0"
              >
                {resetDemoMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Resetting...
                  </>
                ) : (
                  <>
                    <RotateCcw className="h-3.5 w-3.5" />
                    Reset Demo Data
                  </>
                )}
              </Button>
            </div>
            {user?.role !== "lead" && (
              <p className="text-[11px] text-muted-foreground italic">
                * Only users with the Project Lead role can trigger demo database resets.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Reset Confirmation Dialog */}
      <ConfirmDialog
        open={resetDialogOpen}
        onOpenChange={setResetDialogOpen}
        title="Reset Demo Dataset?"
        description="Are you sure you want to reset the demo dataset? All newly created handovers, claim edits, ambiguities, and transient state will be restored to the initial PayFlow baseline."
        confirmLabel="Reset Everything"
        variant="destructive"
        onConfirm={handleConfirmReset}
        isLoading={resetDemoMutation.isPending}
      />
    </div>
  );
}
