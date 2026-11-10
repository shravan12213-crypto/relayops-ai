import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileCheck2,
  FileText,
  History,
  Loader2,
  Plus,
  Shield,
  Sparkles,
  UploadCloud,
  UserCheck,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { CreateHandoverDialog } from "@/components/handover/CreateHandoverDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { RelativeTime } from "@/components/shared/RelativeTime";
import { StatCard } from "@/components/shared/StatCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuditLogs } from "@/lib/api/audit";
import { useAuth } from "@/lib/api/auth";
import { useHandovers } from "@/lib/api/handovers";
import { useProjects } from "@/lib/api/projects";
import { useLoadDemo } from "@/lib/api/sources";

export function DashboardPage() {
  const { user } = useAuth();
  const { data: projects } = useProjects();
  const { data: handovers } = useHandovers();
  const isLeadOrAuditor = user?.role === "lead" || user?.role === "auditor";
  const { data: auditLogs } = useAuditLogs(15, isLeadOrAuditor);
  const loadDemo = useLoadDemo();
  const navigate = useNavigate();

  const [createHandoverOpen, setCreateHandoverOpen] = React.useState(false);

  React.useEffect(() => {
    document.title = "Dashboard — RelayOps";
  }, []);

  const totalHandovers = handovers?.length ?? 0;
  const draftCount = handovers?.filter((h) => h.status === "draft").length ?? 0;
  const reviewCount =
    handovers?.filter((h) => h.status === "review" || h.status === "in_review").length ?? 0;
  const signedCount = handovers?.filter((h) => h.status === "signed").length ?? 0;
  const deliveredCount = handovers?.filter((h) => h.status === "delivered").length ?? 0;

  const defaultProject = projects?.[0];

  const handleQuickLoadDemo = async () => {
    try {
      const res = await loadDemo.mutateAsync();
      navigate(`/projects/${res.project_id}`);
    } catch {
      // Handled by toast
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Engineering Handover Dashboard"
        description="Unified status of knowledge transfer pipelines, verified claims, and pending dual sign-offs."
        actions={
          <div className="flex items-center gap-2">
            {(!projects || projects.length === 0) && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleQuickLoadDemo}
                disabled={loadDemo.isPending}
                className="gap-1.5 text-xs text-brand-text"
              >
                {loadDemo.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <UploadCloud className="h-3.5 w-3.5" />
                )}
                Load PayFlow Demo
              </Button>
            )}
            <Button
              size="sm"
              onClick={() => {
                if (defaultProject) {
                  setCreateHandoverOpen(true);
                } else {
                  handleQuickLoadDemo();
                }
              }}
              className="gap-1.5 text-xs"
            >
              <Plus className="h-3.5 w-3.5" />
              New Handover
            </Button>
          </div>
        }
      />

      {/* 1. Handovers by Status KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="In Review (Dual Sign-off)"
          value={reviewCount}
          description="Claims & contradictions under review"
          icon={AlertTriangle}
          accent="needs-review"
        />
        <StatCard
          title="Signed (Tamper-Sealed)"
          value={signedCount}
          description="Ready for successor delivery"
          icon={CheckCircle2}
          accent="verified"
        />
        <StatCard
          title="Delivered to Successor"
          value={deliveredCount}
          description="Comprehension tracking active"
          icon={UserCheck}
          accent="primary"
        />
        <StatCard
          title="Draft / Ingestion"
          value={draftCount}
          description="Awaiting pipeline run"
          icon={FileText}
          accent="default"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Column: Needs Your Action & Active Handovers */}
        <div className="space-y-6 lg:col-span-7">
          {/* "Needs Your Action" Card */}
          <Card>
            <CardHeader className="border-b border-card-border pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-needs-review" />
                  Needs Your Action
                </CardTitle>
                <Badge
                  variant="outline"
                  className="border-transparent bg-brand-soft text-[10px] text-brand-text"
                >
                  Role: <span className="capitalize font-semibold ml-1">{user?.role}</span>
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Pending tasks requiring your input or cryptographic signature
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 p-4">
              {/* Dual Sign-off action item */}
              <div className="flex items-start justify-between gap-3 rounded-2xl bg-canvas-2 p-3.5 transition-shadow hover:shadow-card">
                <div className="flex items-start gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-card text-brand-text">
                    <FileCheck2 className="h-4 w-4" />
                  </span>
                  <div className="space-y-0.5 text-xs">
                    <p className="font-semibold text-ink">
                      Dual Sign-off Pending: PayFlow Webhook Refactor
                    </p>
                    <p className="text-ink-muted">
                      Aarav Kulkarni (Outgoing) and Meera Patel (Lead) sign-off required before
                      delivery.
                    </p>
                  </div>
                </div>
                <Button asChild size="sm" variant="outline" className="h-8 shrink-0 text-[11px]">
                  <Link
                    to={handovers && handovers[0] ? `/handovers/${handovers[0].id}` : "/handovers"}
                  >
                    Review
                  </Link>
                </Button>
              </div>

              {/* Ambiguity Resolution Item */}
              <div className="flex items-start justify-between gap-3 rounded-2xl bg-canvas-2 p-3.5 transition-shadow hover:shadow-card">
                <div className="flex items-start gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-card text-needs-review">
                    <AlertTriangle className="h-4 w-4" />
                  </span>
                  <div className="space-y-0.5 text-xs">
                    <p className="font-semibold text-ink">
                      Resolve Contradiction: Webhook Retry Limit
                    </p>
                    <p className="text-ink-muted">
                      Commit 8f3a sets retry limit to 5 while ADR 004 mentions 3.
                    </p>
                  </div>
                </div>
                <Button asChild size="sm" variant="outline" className="h-8 shrink-0 text-[11px]">
                  <Link to="/handovers">Resolve</Link>
                </Button>
              </div>

              {/* Comprehension Receipt Item for Successor */}
              <div className="flex items-start justify-between gap-3 rounded-2xl bg-canvas-2 p-3.5 transition-shadow hover:shadow-card">
                <div className="flex items-start gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-card text-verified">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <div className="space-y-0.5 text-xs">
                    <p className="font-semibold text-ink">
                      Comprehension Receipts: Core Runbooks
                    </p>
                    <p className="text-ink-muted">
                      2 onboarding sections awaiting reading acknowledgement from Kabir Sharma.
                    </p>
                  </div>
                </div>
                <Button asChild size="sm" variant="outline" className="h-8 shrink-0 text-[11px]">
                  <Link
                    to={
                      handovers && handovers[0]
                        ? `/handovers/${handovers[0].id}/portal`
                        : "/handovers"
                    }
                  >
                    Acknowledge
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Active Handover Workflows */}
          <Card>
            <CardHeader className="border-b border-card-border pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-semibold">Active Handover Workflows</CardTitle>
                  <CardDescription className="text-xs">
                    Pipeline status and verification scorecard for active handovers
                  </CardDescription>
                </div>
                <Button asChild variant="ghost" size="sm" className="text-xs">
                  <Link to="/handovers">View All ({totalHandovers})</Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
              {handovers && handovers.length > 0 ? (
                handovers.map((h) => (
                  <div
                    key={h.id}
                    className="flex flex-col justify-between gap-3 rounded-2xl border border-card-border p-3.5 transition-all duration-200 hover:shadow-card-hover motion-safe:hover:-translate-y-0.5 sm:flex-row sm:items-center"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-ink">
                          {h.notes || "PayFlow Handover"}
                        </span>
                        <StatusBadge status={h.status} size="sm" />
                      </div>
                      <p className="font-mono text-[11px] text-ink-muted">
                        ID: {h.id} · Version: v{h.current_version}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button asChild size="sm" variant="outline" className="text-xs h-8">
                        <Link to={`/handovers/${h.id}/pipeline`}>Pipeline</Link>
                      </Button>
                      <Button asChild size="sm" variant="outline" className="text-xs h-8">
                        <Link to={`/handovers/${h.id}/portal`}>Portal</Link>
                      </Button>
                      <Button asChild size="sm" className="text-xs h-8">
                        <Link to={`/handovers/${h.id}`}>Open Review</Link>
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState
                  icon={FileText}
                  title="No active handovers"
                  description="Load the PayFlow demo dataset or create your first handover workflow."
                  action={
                    <Button size="sm" onClick={handleQuickLoadDemo} className="gap-1.5 text-xs">
                      <Sparkles className="h-3.5 w-3.5" />
                      Load PayFlow Demo
                    </Button>
                  }
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Immutable Audit Trail Feed */}
        <div className="space-y-6 lg:col-span-5">
          <Card className="flex flex-col h-full">
            <CardHeader className="border-b border-card-border pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <History className="h-4 w-4 text-brand-text" />
                  <CardTitle className="text-xs font-semibold">Cryptographic Audit Trail</CardTitle>
                </div>
                <Badge
                  variant="outline"
                  className="border-transparent bg-brand-soft font-mono text-[10px] text-brand-text"
                >
                  <Shield className="h-2.5 w-2.5 mr-1" />
                  SHA-256 Chained
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Real-time append-only tamper-evident event stream
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 p-3">
              {!isLeadOrAuditor ? (
                <div className="py-8 text-center text-xs text-ink-muted">
                  Audit trail restricted to Lead & Auditor clearance.
                </div>
              ) : auditLogs && auditLogs.length > 0 ? (
                <div className="space-y-2.5">
                  {auditLogs.slice(0, 8).map((log) => (
                    <div
                      key={log.seq}
                      className="space-y-1 rounded-xl bg-canvas-2 p-2.5 text-xs transition-shadow hover:shadow-card"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[11px] font-bold text-brand-text">
                          #{log.seq} {log.action}
                        </span>
                        <RelativeTime date={log.created_at} />
                      </div>
                      <div className="flex items-center justify-between font-mono text-[11px] text-ink-muted">
                        <span>Target: {log.target_type}</span>
                        <span className="truncate max-w-[120px]" title={log.hash}>
                          {log.hash.substring(0, 8)}...
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center text-xs italic text-ink-muted">
                  No audit events recorded yet.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Create Handover Modal */}
      {defaultProject && (
        <CreateHandoverDialog
          open={createHandoverOpen}
          onOpenChange={setCreateHandoverOpen}
          projectId={defaultProject.id}
        />
      )}
    </div>
  );
}
