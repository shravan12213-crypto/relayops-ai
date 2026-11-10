import { Loader2, RefreshCw, Shield, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useRedactionAudit, useRescanRedactions } from "@/lib/api/sources";

export interface RedactionTransparencyPanelProps {
  projectId: string;
}

export function RedactionTransparencyPanel({ projectId }: RedactionTransparencyPanelProps) {
  const { data: audit, isLoading, refetch } = useRedactionAudit(projectId);
  const rescan = useRescanRedactions(projectId);

  const handleRescan = async () => {
    await rescan.mutateAsync();
    refetch();
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-card-border pb-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-brand-text" />
              <CardTitle className="text-sm font-semibold">Redaction Transparency Report</CardTitle>
              {audit && (
                <Badge variant="outline" className="font-mono text-[10px]">
                  {audit.total_redactions} scrubbing events
                </Badge>
              )}
            </div>
            <CardDescription className="text-xs">
              Pre-storage, pre-inference redaction audit log across all project artifacts.
            </CardDescription>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRescan}
            disabled={rescan.isPending}
            className="gap-1.5 text-xs self-start sm:self-auto"
          >
            {rescan.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Re-scanning...
              </>
            ) : (
              <>
                <RefreshCw className="h-3.5 w-3.5" />
                Re-scan Redactions
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 p-5">
        {/* Reassurance Copy */}
        <div className="flex items-start gap-3 rounded-2xl border border-brand/30 bg-brand-soft p-3.5 text-xs">
          <ShieldCheck className="h-4 w-4 shrink-0 text-verified mt-0.5" />
          <div className="space-y-1 text-ink-muted">
            <p className="font-semibold text-ink">Zero-leakage security guarantee</p>
            <p className="leading-relaxed">
              Secrets, API keys, credentials, and personal identifiers are scrubbed at ingestion
              BEFORE storage in the database and BEFORE any LLM retrieval. Only safe masked
              placeholders are displayed below; raw secret strings are never retained.
            </p>
          </div>
        </div>

        {/* Table of redaction rules */}
        {isLoading ? (
          <div className="space-y-2 py-4">
            <div className="h-4 w-full animate-pulse rounded bg-canvas-2" />
            <div className="h-4 w-3/4 animate-pulse rounded bg-canvas-2" />
            <div className="h-4 w-1/2 animate-pulse rounded bg-canvas-2" />
          </div>
        ) : audit && audit.rules.length > 0 ? (
          <div className="overflow-x-auto rounded-2xl border border-card-border">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-card-border text-ink-muted">
                <tr>
                  <th className="px-4 py-2.5">Rule Name</th>
                  <th className="px-4 py-2.5 text-right">Occurrences</th>
                  <th className="px-4 py-2.5">Masked Replacement Pattern</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-card-border">
                {audit.rules.map((rule) => (
                  <tr key={rule.rule} className="transition-colors hover:bg-canvas-2">
                    <td className="px-4 py-2.5 font-mono text-[11px] font-semibold text-ink">
                      {rule.rule}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[11px] text-ink">
                      <span className="rounded-md bg-canvas-2 px-2 py-0.5 font-bold">{rule.count}</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-ink-muted">
                      <span className="rounded-md border border-card-border bg-canvas-2 px-2 py-0.5">
                        {rule.sample_masked}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-6 text-center text-xs text-ink-muted">
            No secrets or sensitive tokens have been detected yet in this project.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
