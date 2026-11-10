import * as React from "react";
import { EyeOff, Loader2, RefreshCw, Shield } from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSensitivityDistribution, type SensitivityBucket } from "@/lib/api/governance";
import { useProjects } from "@/lib/api/projects";
import { useRedactionAudit, useRescanRedactions } from "@/lib/api/sources";

const LEVEL_COLORS = [
  { bg: "bg-unverified", text: "text-ink-muted", border: "border-card-border", fill: "#64748b" }, // Level 0 Public
  { bg: "bg-brand", text: "text-ink-muted", border: "border-brand", fill: "#3b82f6" },   // Level 1 Internal
  { bg: "bg-needs-review", text: "text-needs-review", border: "border-needs-review", fill: "#f59e0b" }, // Level 2 Confidential
  { bg: "bg-red-500", text: "text-red-500", border: "border-red-500/20", fill: "#ef4444" },     // Level 3 Restricted
];

export function RedactionAndSensitivityView() {
  const { data: projects, isLoading: projectsLoading } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = React.useState<string>("");

  React.useEffect(() => {
    if (projects && projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const {
    data: sensitivityData,
    isLoading: sensitivityLoading,
    isError: sensitivityError,
    error: sensError,
    refetch: refetchSensitivity,
  } = useSensitivityDistribution(selectedProjectId);

  const {
    data: redactionData,
    isLoading: redactionLoading,
    isError: redactionError,
    error: redError,
    refetch: refetchRedaction,
  } = useRedactionAudit(selectedProjectId);

  const rescanMutation = useRescanRedactions(selectedProjectId);

  const handleRescan = () => {
    rescanMutation.mutate(undefined, {
      onSuccess: () => {
        refetchSensitivity();
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Project Selector Bar */}
      <Card className="border-card-border">
        <CardContent className="py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-ink-muted whitespace-nowrap">
                Select Project:
              </span>
              <Select
                value={selectedProjectId}
                onValueChange={setSelectedProjectId}
                disabled={projectsLoading || !projects || projects.length === 0}
              >
                <SelectTrigger className="h-8 w-60 text-xs">
                  <SelectValue placeholder="Choose a project..." />
                </SelectTrigger>
                <SelectContent>
                  {projects?.map((p) => (
                    <SelectItem key={p.id} value={p.id} className="text-xs">
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  refetchSensitivity();
                  refetchRedaction();
                }}
                className="h-8 gap-1.5 text-xs"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Refresh Reports
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sensitivity Distribution Section */}
      <Card className="border-card-border">
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Shield className="h-5 w-5 text-brand-text" />
                Sensitivity Level Distribution
              </CardTitle>
              <CardDescription className="text-xs">
                Classification breakdown across all ingested artifacts and verified claims.
              </CardDescription>
            </div>
            {sensitivityData && (
              <div className="flex items-center gap-3 text-xs font-mono">
                <Badge variant="outline" className="bg-canvas-2">
                  {sensitivityData.total_artifacts} artifacts
                </Badge>
                <Badge variant="outline" className="bg-canvas-2">
                  {sensitivityData.total_claims} claims
                </Badge>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {sensitivityLoading ? (
            <div className="p-8 text-center text-xs text-ink-muted flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-brand-text" />
              Calculating sensitivity distribution...
            </div>
          ) : sensitivityError ? (
            <ErrorState
              title="Failed to load sensitivity distribution"
              message={sensError instanceof Error ? sensError.message : "Error reading distribution"}
              onRetry={() => refetchSensitivity()}
            />
          ) : !sensitivityData ? (
            <EmptyState
              title="No project selected"
              description="Please select an active project above to inspect sensitivity metrics."
            />
          ) : (
            <div className="space-y-4">
              {/* Composite SVG Stacked Progress Bar */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs text-ink-muted">
                  <span className="font-medium">Composite Project Sensitivity Breakdown</span>
                  <span className="font-mono text-[11px]">
                    {sensitivityData.total_claims + sensitivityData.total_artifacts > 0
                      ? "100% categorized"
                      : "0 items"}
                  </span>
                </div>
                {/* SVG/CSS Horizontal Stacked Bar */}
                <div className="w-full h-5 rounded-md overflow-hidden bg-canvas-2 flex border border-card-border">
                  {sensitivityData.levels.map((lvl: SensitivityBucket) => {
                    const widthPct = Math.max(0, lvl.percentage);
                    if (widthPct === 0) return null;
                    const color = LEVEL_COLORS[lvl.level] ?? LEVEL_COLORS[0];
                    return (
                      <div
                        key={lvl.level}
                        className={`${color.bg} h-full transition-all duration-300 relative group`}
                        style={{ width: `${widthPct}%` }}
                        title={`Level ${lvl.level} (${lvl.name}): ${lvl.percentage}% (${lvl.claims_count} claims, ${lvl.artifacts_count} artifacts)`}
                      />
                    );
                  })}
                </div>
              </div>

              {/* Individual Breakdown Cards */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {sensitivityData.levels.map((lvl: SensitivityBucket) => {
                  const style = LEVEL_COLORS[lvl.level] ?? LEVEL_COLORS[0];
                  return (
                    <div
                      key={lvl.level}
                      className="rounded-lg border border-card-border bg-card p-3.5 space-y-2.5 shadow-sm"
                    >
                      <div className="flex items-center justify-between">
                        <SensitivityBadge level={lvl.level} size="sm" />
                        <span className="font-mono text-xs font-semibold text-ink">
                          {lvl.percentage.toFixed(1)}%
                        </span>
                      </div>

                      {/* Simple CSS meter bar */}
                      <div className="w-full h-1.5 bg-canvas-2 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${style.bg} rounded-full transition-all duration-500`}
                          style={{ width: `${Math.min(100, Math.max(lvl.percentage, 2))}%` }}
                        />
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-ink-muted pt-1 border-t border-card-border">
                        <span>{lvl.artifacts_count} artifacts</span>
                        <span className="font-medium text-ink">{lvl.claims_count} claims</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Redaction Audit Report Section */}
      <Card className="border-card-border">
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <EyeOff className="h-5 w-5 text-needs-review" />
                Project Secret Redaction Transparency
              </CardTitle>
              <CardDescription className="text-xs">
                Guaranteed zero secret leakage. Redaction occurs at ingestion before storage and before LLM context construction.
              </CardDescription>
            </div>
            <div className="flex items-center gap-3">
              {redactionData && (
                <Badge variant="outline" className="font-mono text-xs bg-warn-soft text-needs-review border-needs-review">
                  {redactionData.total_redactions} total redactions fired
                </Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleRescan}
                disabled={rescanMutation.isPending || !selectedProjectId}
                className="h-8 gap-1.5 text-xs"
              >
                {rescanMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Re-scanning...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-3.5 w-3.5" />
                    Re-scan Project
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {redactionLoading ? (
            <div className="p-8 text-center text-xs text-ink-muted flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-brand-text" />
              Loading redaction audit events...
            </div>
          ) : redactionError ? (
            <ErrorState
              title="Failed to load redaction audit report"
              message={redError instanceof Error ? redError.message : "Error reading redactions"}
              onRetry={() => refetchRedaction()}
            />
          ) : !redactionData || redactionData.rules.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="No secrets detected"
                description="Zero secrets or credentials triggered redaction in this project's ingested sources."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-card-border bg-canvas-2 font-medium text-ink-muted">
                  <tr>
                    <th className="py-2.5 px-3">Rule Name</th>
                    <th className="py-2.5 px-3 text-center">Fired Hits</th>
                    <th className="py-2.5 px-3">Sample Masked Output</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-card-border">
                  {redactionData.rules.map((rule) => (
                    <tr key={rule.rule} className="hover:bg-canvas-2 transition-colors">
                      <td className="py-2.5 px-3 font-semibold font-mono text-ink">
                        <Badge variant="outline" className="font-mono text-[11px]">
                          {rule.rule}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono font-semibold text-ink">
                        {rule.count}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-needs-review dark:text-needs-review">
                        <code className="bg-canvas-2 px-1.5 py-0.5 rounded border border-card-border">
                          {rule.sample_masked}
                        </code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
