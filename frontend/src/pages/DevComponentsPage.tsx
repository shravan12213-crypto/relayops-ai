import * as React from "react";
import { AlertTriangle, CheckCircle2, FileText, Sparkles, Zap } from "lucide-react";
import { toast } from "sonner";

import { useTheme } from "@/app/theme-context";
import {
  CitationPill,
  ConfirmDialog,
  CopyButton,
  EmptyState,
  ErrorState,
  JobProgress,
  Kbd,
  PageHeader,
  RelativeTime,
  SensitivityBadge,
  StatCard,
  StatusBadge,
  TableSkeleton,
} from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export function DevComponentsPage() {
  const { theme, toggleTheme } = useTheme();
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [isRetrying, setIsRetrying] = React.useState(false);
  const [jobProgressVal, setJobProgressVal] = React.useState(42);

  React.useEffect(() => {
    document.title = "Design System & Components — RelayOps";
  }, []);

  const handleSimulateRetry = () => {
    setIsRetrying(true);
    setTimeout(() => {
      setIsRetrying(false);
      toast.success("Retry simulation succeeded!");
    }, 1500);
  };

  return (
    <div className="space-y-8 pb-12">
      <PageHeader
        title="RelayOps Design System & Shared Components"
        description="Storybook-lite reference gallery demonstrating tokens, accessibility, and visual patterns across themes."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={toggleTheme} className="gap-2 text-xs">
              Current: <span className="font-semibold capitalize">{theme}</span> (Toggle)
            </Button>
          </div>
        }
      />

      {/* 1. Status Colors & Semantic Badges */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink flex items-center gap-1.5">
          <Zap className="h-4 w-4 text-brand-text" />
          1. Semantic Status Badges & Tokens
        </h2>
        <Card>
          <CardContent className="space-y-4 p-5">
            <p className="text-xs text-ink-muted">
              Status colors are reserved strictly for verification & claim lifecycle, never for
              arbitrary decoration.
            </p>
            <div className="flex flex-wrap gap-2.5">
              <StatusBadge status="verified" />
              <StatusBadge status="needs_review" />
              <StatusBadge status="conflict" />
              <StatusBadge status="unverified" />
              <StatusBadge status="accepted" />
              <StatusBadge status="draft" />
              <StatusBadge status="rejected" />
              <StatusBadge status="edited" />
              <StatusBadge status="signed" />
              <StatusBadge status="delivered" />
            </div>
            <div className="flex flex-wrap gap-2.5 pt-2 border-t">
              <span className="text-xs text-ink-muted mr-2 self-center">
                Compact (dot only):
              </span>
              <StatusBadge status="verified" showIcon={false} size="sm" />
              <StatusBadge status="needs_review" showIcon={false} size="sm" />
              <StatusBadge status="conflict" showIcon={false} size="sm" />
              <StatusBadge status="unverified" showIcon={false} size="sm" />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* 2. Sensitivity Levels (0 - 3) */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink flex items-center gap-1.5">
          <Sparkles className="h-4 w-4 text-brand-text" />
          2. Sensitivity Badges (0-3 with Lock Icons & Tooltips)
        </h2>
        <Card>
          <CardContent className="space-y-3 p-5">
            <p className="text-xs text-ink-muted">
              Hover over each badge to read its clearance policy and visibility rules:
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <SensitivityBadge level={0} />
              <SensitivityBadge level={1} />
              <SensitivityBadge level={2} />
              <SensitivityBadge level={3} />
            </div>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <span className="text-xs text-ink-muted mr-2">Small variant:</span>
              <SensitivityBadge level={0} size="sm" />
              <SensitivityBadge level={1} size="sm" />
              <SensitivityBadge level={2} size="sm" />
              <SensitivityBadge level={3} size="sm" />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* 3. Stat Cards */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">
          3. Stat Cards with Semantic Accents
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Verified Ground Truth"
            value="142"
            description="Linked to valid artifacts"
            icon={CheckCircle2}
            accent="verified"
          />
          <StatCard
            title="Active Contradictions"
            value="3"
            description="Cross-source discrepancy"
            icon={AlertTriangle}
            accent="conflict"
          />
          <StatCard
            title="Ambiguities Pending"
            value="5"
            description="Awaiting lead resolution"
            icon={AlertTriangle}
            accent="needs-review"
          />
          <StatCard
            title="Audited Events"
            value="1,208"
            description="SHA-256 linked entries"
            icon={FileText}
            accent="primary"
          />
        </div>
      </section>

      {/* 4. Citation Pills & Evidence Micro-UI */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">
          4. Citation Pills & Evidence Links
        </h2>
        <Card>
          <CardContent className="space-y-3 p-5">
            <p className="text-xs text-ink-muted">
              Every claim displayed to a successor links directly to source artifacts (PRs, commits,
              issues, Slack threads, ADRs):
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <CitationPill
                artifactId="art_commit_8f3a"
                sourceType="commit"
                sourceUri="https://github.com/payflow/core/commit/8f3a201"
                snippet="Bump webhook retry count from 3 to 5 and add exponential jitter."
                sensitivity={1}
              />
              <CitationPill
                artifactId="art_pr_142"
                sourceType="pr"
                sourceUri="https://github.com/payflow/core/pull/142"
                snippet="PAY-142: Fix idempotency key cache race under high concurrent loads."
                sensitivity={1}
              />
              <CitationPill
                artifactId="art_slack_backend_42"
                sourceType="slack"
                snippet="Aarav: We opted for SQLite WAL mode because of its single-writer lock simplicity."
                sensitivity={2}
              />
              <CitationPill
                artifactId="art_adr_004"
                sourceType="doc"
                snippet="ADR 004: Payment Webhook Idempotency Architecture."
                sensitivity={0}
              />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* 5. Utility Micro-Components: Kbd, CopyButton, RelativeTime */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">
          5. Micro-Components (Kbd, CopyButton, RelativeTime)
        </h2>
        <Card>
          <CardContent className="flex flex-wrap items-center gap-6 p-5 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-ink-muted">Keyboard shortcut:</span>
              <Kbd>⌘K</Kbd>
              <Kbd>Esc</Kbd>
              <Kbd>J</Kbd>
              <Kbd>K</Kbd>
            </div>

            <Separator orientation="vertical" className="h-6" />

            <div className="flex items-center gap-2">
              <span className="text-ink-muted">Copy button:</span>
              <span className="font-mono text-ink">01JBCDEFGHJKMNPQRSTVWXYZ</span>
              <CopyButton value="01JBCDEFGHJKMNPQRSTVWXYZ" label="Copy ULID" />
            </div>

            <Separator orientation="vertical" className="h-6" />

            <div className="flex items-center gap-2">
              <span className="text-ink-muted">Relative time:</span>
              <RelativeTime date={new Date(Date.now() - 3600000 * 4)} />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* 6. Pipeline Job Progress */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight text-ink">
            6. Pipeline Orchestration & Job Progress
          </h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setJobProgressVal((prev) => (prev >= 100 ? 10 : prev + 20))}
            className="text-xs"
          >
            Step Progress ({jobProgressVal}%)
          </Button>
        </div>
        <JobProgress stage="verify_citations" progress={jobProgressVal} status="running" />
      </section>

      {/* 7. Dialogs, Alerts, Skeletons, and Feedback */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">
          7. Modals, Alerts, Error/Empty States & Skeletons
        </h2>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Interactive Confirm Dialog */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-semibold">Interactive Confirm Dialog</CardTitle>
              <CardDescription className="text-xs">
                Accessible modal for high-impact handover actions (e.g. sign-off, claim rejection)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setConfirmOpen(true)}
                className="text-xs"
              >
                Trigger Destructive Confirm Dialog
              </Button>

              <ConfirmDialog
                open={confirmOpen}
                onOpenChange={setConfirmOpen}
                title="Reject Candidate Claim?"
                description="This claim will be permanently marked as rejected and removed from verified successor views."
                confirmLabel="Reject Claim"
                variant="destructive"
                onConfirm={() => {
                  toast.error("Claim was rejected with reason: insufficient citations");
                }}
              />
            </CardContent>
          </Card>

          {/* Toast Triggers */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-semibold">Sonner Toasts</CardTitle>
              <CardDescription className="text-xs">
                Non-blocking feedback for mutations, pipeline runs, and sign-offs
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => toast.success("Handover v1 created and signed.")}
                className="text-xs"
              >
                Success Toast
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => toast.error("Verification failed: claim lacks evidence.")}
                className="text-xs"
              >
                Error Toast
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => toast.info("Ingesting 240 PayFlow artifacts...")}
                className="text-xs"
              >
                Info Toast
              </Button>
            </CardContent>
          </Card>

          {/* Error State with Retry */}
          <div className="md:col-span-1">
            <ErrorState
              title="Failed to fetch source citations"
              message="The backend timed out while parsing references for artifact art_commit_8f3a."
              code="E_CITATION_FETCH_TIMEOUT"
              onRetry={handleSimulateRetry}
              isRetrying={isRetrying}
            />
          </div>

          {/* Empty State */}
          <div className="md:col-span-1">
            <EmptyState
              title="No unresolved ambiguities"
              description="All detected contradictions have been addressed by the team lead."
              action={
                <Button size="sm" variant="outline" className="text-xs">
                  Inspect Resolved Ledger
                </Button>
              }
            />
          </div>
        </div>
      </section>

      {/* 8. Loading Skeleton Preview */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">
          8. Table Loading Skeletons
        </h2>
        <TableSkeleton rows={3} cols={4} />
      </section>
    </div>
  );
}
