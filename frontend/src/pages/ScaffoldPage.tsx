import { AlertTriangle, ArrowRight, Moon, Sun } from "lucide-react";

import { useTheme } from "@/app/theme-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useHealth } from "@/lib/api/system";
import { cn } from "@/lib/utils";

const STAGES = ["Connect", "Reconstruct", "Verify", "Review", "Handover"];

const SWATCHES = [
  { name: "background", className: "bg-background border" },
  { name: "primary", className: "bg-primary" },
  { name: "verified", className: "bg-verified" },
  { name: "needs-review", className: "bg-needs-review" },
  { name: "conflict", className: "bg-conflict" },
  { name: "unverified", className: "bg-unverified" },
];

function HealthCard() {
  const health = useHealth();

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3">
          API status
          {health.data && (
            <Badge
              variant="outline"
              className={cn(
                "gap-1.5 font-mono text-[11px] uppercase tracking-wide",
                health.data.status === "ok" ? "text-verified" : "text-conflict",
              )}
            >
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  health.data.status === "ok" ? "bg-verified" : "bg-conflict",
                )}
              />
              {health.data.status}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Live from <span className="font-mono text-xs">GET /api/v1/health</span>, proxied by Vite.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        {health.isPending ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-3/5" />
          </div>
        ) : health.isError ? (
          <div className="flex flex-col items-start gap-3">
            <p className="flex items-center gap-2 text-sm text-conflict">
              <AlertTriangle className="size-4" />
              API unreachable — is the backend running on :8000?
            </p>
            <Button size="sm" variant="outline" onClick={() => void health.refetch()}>
              Retry
            </Button>
          </div>
        ) : (
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-ink-muted">Version</dt>
            <dd className="font-mono text-xs leading-6">{health.data.version}</dd>
            <dt className="text-ink-muted">LLM mode</dt>
            <dd>
              <Badge variant="secondary" className="font-mono text-[11px]">
                {health.data.llm_mode}
              </Badge>
            </dd>
            <dt className="text-ink-muted">Database</dt>
            <dd className="font-mono text-xs leading-6">{health.data.db}</dd>
          </dl>
        )}
      </CardContent>
    </Card>
  );
}

export function ScaffoldPage() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <span className="grid size-7 place-items-center rounded-md bg-primary font-mono text-sm font-semibold text-primary-foreground">
              R
            </span>
            <span className="text-sm font-semibold tracking-tight">RelayOps</span>
            <Badge
              variant="outline"
              className="ml-1 font-mono text-[10px] uppercase tracking-wider"
            >
              P01 · scaffold
            </Badge>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-14">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-muted">
          Foundation ready
        </p>
        <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-tight">
          A handover you can check.
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-muted">
          RelayOps turns scattered commits, tickets, chat and docs into a traceable handover — every
          claim tied to real evidence, every gap named instead of smoothed over. This page is the
          P01 scaffold: theme, API proxy and tooling are live; the pipeline lands in the next
          prompts.
        </p>

        <div className="mt-10 grid gap-4 md:grid-cols-2">
          <HealthCard />

          <Card>
            <CardHeader>
              <CardTitle>Design tokens</CardTitle>
              <CardDescription>One accent, semantic colour only for status.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-6 gap-2">
                {SWATCHES.map((swatch) => (
                  <div key={swatch.name} className="space-y-1.5">
                    <div className={cn("h-10 rounded-md", swatch.className)} />
                    <p className="font-mono text-[10px] leading-tight text-ink-muted">
                      {swatch.name}
                    </p>
                  </div>
                ))}
              </div>
              <Separator />
              <div className="space-y-1.5">
                <p className="text-sm">Inter — dense, quiet interface text.</p>
                <p className="font-mono text-xs text-ink-muted">
                  JetBrains Mono — commit 9f2c1ab · PAY-142 · application/json
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        <section className="mt-4 rounded-lg border bg-card p-6">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="text-sm font-semibold">Pipeline</h2>
            <span className="font-mono text-[11px] text-ink-muted">
              5 stages · not yet wired
            </span>
          </div>
          <ol className="mt-4 flex flex-wrap items-center gap-2">
            {STAGES.map((stage, index) => (
              <li key={stage} className="flex items-center gap-2">
                <span
                  className={cn(
                    "flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm",
                    index === 0
                      ? "border-brand bg-accent text-accent-foreground"
                      : "text-ink-muted",
                  )}
                >
                  <span className="font-mono text-[10px] tabular-nums">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {stage}
                </span>
                {index < STAGES.length - 1 && (
                  <ArrowRight className="size-3.5 text-ink-faint" aria-hidden="true" />
                )}
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-6 py-6 text-xs text-ink-muted">
          <span className="font-mono">make dev · npm run dev · make test</span>
          <span>RelayOps — verifiable handovers, not a chatbot.</span>
        </div>
      </footer>
    </div>
  );
}
