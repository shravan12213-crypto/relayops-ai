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
      <CardHeader className="pb-3 border-b border-border/60">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-primary" />
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
        <div className="flex items-start gap-3 rounded-lg border border-verified/30 bg-verified/5 p-3.5 text-xs">
          <ShieldCheck className="h-4 w-4 shrink-0 text-verified mt-0.5" />
          <div className="space-y-1 text-muted-foreground">
            <p className="font-medium text-foreground">Zero-leakage security guarantee</p>
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
            <div className="h-4 w-full bg-muted animate-pulse rounded" />
            <div className="h-4 w-3/4 bg-muted animate-pulse rounded" />
            <div className="h-4 w-1/2 bg-muted animate-pulse rounded" />
          </div>
        ) : audit && audit.rules.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-xs">
              <thead className="border-b bg-muted/50 font-medium text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5">Rule Name</th>
                  <th className="px-4 py-2.5 text-right">Occurrences</th>
                  <th className="px-4 py-2.5">Masked Replacement Pattern</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {audit.rules.map((rule) => (
                  <tr key={rule.rule} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-2.5 font-mono text-[11px] font-semibold text-foreground">
                      {rule.rule}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[11px] text-foreground">
                      <span className="rounded bg-muted px-2 py-0.5 font-bold">{rule.count}</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-muted-foreground">
                      <span className="rounded bg-muted/80 px-2 py-0.5 border border-border/60">
                        {rule.sample_masked}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-6 text-center text-xs text-muted-foreground">
            No secrets or sensitive tokens have been detected yet in this project.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
