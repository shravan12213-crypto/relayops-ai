import * as React from "react";
import {
  ChevronDown,
  ChevronRight,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";

import { CopyButton } from "@/components/shared/CopyButton";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { RelativeTime } from "@/components/shared/RelativeTime";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useGovernanceAuditLogs,
  useVerifyAuditChain,
  type AuditChainVerifyResponse,
  type AuditLogItem,
} from "@/lib/api/governance";
import { useDebounce } from "@/hooks/use-debounce";

const COMMON_ACTIONS = [
  "ALL",
  "CREATE_PROJECT",
  "CREATE_SOURCE",
  "TRIGGER_INGEST",
  "CREATE_HANDOVER",
  "RUN_STAGE",
  "EDIT_CLAIM",
  "ACCEPT_CLAIM",
  "REJECT_CLAIM",
  "RESOLVE_AMBIGUITY",
  "SIGNOFF",
  "DELIVER_HANDOVER",
  "VERIFY_CHAIN",
  "RESCAN_REDACTIONS",
  "ADD_MEMBER",
  "UPDATE_MEMBER",
  "REMOVE_MEMBER",
];

export function AuditLogTable() {
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(25);
  const [actionFilter, setActionFilter] = React.useState<string>("ALL");
  const [actorFilter, setActorFilter] = React.useState<string>("");
  const [fromDate, setFromDate] = React.useState<string>("");
  const [toDate, setToDate] = React.useState<string>("");
  const [expandedSeq, setExpandedSeq] = React.useState<number | null>(null);
  const [verifyResult, setVerifyResult] = React.useState<AuditChainVerifyResponse | null>(null);

  const debouncedActor = useDebounce(actorFilter, 300);

  const queryParams = {
    action: actionFilter !== "ALL" ? actionFilter : undefined,
    actor_id: debouncedActor.trim() ? debouncedActor.trim() : undefined,
    from_date: fromDate ? new Date(fromDate).toISOString() : undefined,
    to_date: toDate ? new Date(toDate).toISOString() : undefined,
    page,
    page_size: pageSize,
  };

  const { data, isLoading, isError, error, refetch, isFetching } = useGovernanceAuditLogs(queryParams);
  const verifyMutation = useVerifyAuditChain();

  const handleVerify = () => {
    verifyMutation.mutate(undefined, {
      onSuccess: (res) => {
        setVerifyResult(res);
      },
      onError: (err) => {
        setVerifyResult({
          valid: false,
          entries_count: 0,
          tampered_seq: null,
          error: err.message,
        });
      },
    });
  };

  const handleClearFilters = () => {
    setActionFilter("ALL");
    setActorFilter("");
    setFromDate("");
    setToDate("");
    setPage(1);
  };

  const toggleExpand = (seq: number) => {
    setExpandedSeq((prev) => (prev === seq ? null : seq));
  };

  const hasActiveFilters = actionFilter !== "ALL" || actorFilter !== "" || fromDate !== "" || toDate !== "";

  return (
    <div className="space-y-4">
      {/* Verify Chain Header Card */}
      <Card className="border-card-border">
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-verified" />
                Audit Trail & Hash Chain Verification
              </CardTitle>
              <CardDescription className="text-xs">
                Immutable, append-only ledger chained via SHA-256 rolling cryptographic hashes.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
                className="gap-1.5 text-xs"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Button
                size="sm"
                onClick={handleVerify}
                disabled={verifyMutation.isPending}
                className="gap-1.5 text-xs bg-primary hover:bg-brand-soft text-primary-foreground font-medium"
              >
                {verifyMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Verifying Chain...
                  </>
                ) : (
                  <>
                    <ShieldCheck className="h-3.5 w-3.5" />
                    Verify Hash Chain
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardHeader>

        {/* Verification Result Banner */}
        {verifyResult && (
          <div className="px-6 pb-4">
            {verifyResult.valid ? (
              <div className="flex items-center gap-3 rounded-lg border border-verified/40 bg-verified/10 p-3 text-xs text-ink">
                <ShieldCheck className="h-5 w-5 text-verified shrink-0" />
                <div className="flex-1">
                  <span className="font-semibold text-verified">
                    Cryptographic Integrity Confirmed:
                  </span>{" "}
                  All {verifyResult.entries_count} audit log entries verified against the SHA-256 rolling hash chain. No tampering detected.
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setVerifyResult(null)}
                  className="h-6 w-6 p-0 text-ink-muted hover:text-ink"
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            ) : (
              <div className="flex items-start gap-3 rounded-lg border border-destructive bg-destructive/10 p-3 text-xs text-ink">
                <ShieldAlert className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="font-bold text-destructive flex items-center gap-2">
                    CRITICAL: AUDIT CHAIN COMPROMISED
                    {verifyResult.tampered_seq != null && (
                      <Badge variant="destructive" className="font-mono text-[10px]">
                        First Broken Sequence: #{verifyResult.tampered_seq}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 text-ink-muted">
                    {verifyResult.error ||
                      `Sequence #${verifyResult.tampered_seq} failed cryptographic verification. Database records have been modified out-of-band.`}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setVerifyResult(null)}
                  className="h-6 w-6 p-0 text-ink-muted hover:text-ink"
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Filter Toolbar */}
      <Card className="border-card-border">
        <CardContent className="pt-4 pb-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5 items-end">
            <div>
              <label className="text-[11px] font-medium text-ink-muted block mb-1">
                Filter by Action
              </label>
              <Select
                value={actionFilter}
                onValueChange={(val) => {
                  setActionFilter(val);
                  setPage(1);
                }}
              >
                <SelectTrigger className="h-8 text-xs font-mono">
                  <SelectValue placeholder="All actions" />
                </SelectTrigger>
                <SelectContent>
                  {COMMON_ACTIONS.map((act) => (
                    <SelectItem key={act} value={act} className="text-xs font-mono">
                      {act}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-[11px] font-medium text-ink-muted block mb-1">
                Actor User ID
              </label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-ink-muted" />
                <Input
                  placeholder="e.g. 01J..."
                  value={actorFilter}
                  onChange={(e) => {
                    setActorFilter(e.target.value);
                    setPage(1);
                  }}
                  className="h-8 pl-8 text-xs font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-medium text-ink-muted block mb-1">
                From Date
              </label>
              <Input
                type="date"
                value={fromDate}
                onChange={(e) => {
                  setFromDate(e.target.value);
                  setPage(1);
                }}
                className="h-8 text-xs"
              />
            </div>

            <div>
              <label className="text-[11px] font-medium text-ink-muted block mb-1">
                To Date
              </label>
              <Input
                type="date"
                value={toDate}
                onChange={(e) => {
                  setToDate(e.target.value);
                  setPage(1);
                }}
                className="h-8 text-xs"
              />
            </div>

            <div className="flex items-center gap-2">
              {hasActiveFilters && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearFilters}
                  className="h-8 gap-1 text-xs text-ink-muted hover:text-ink"
                >
                  <Filter className="h-3 w-3" />
                  Clear
                </Button>
              )}
              <div className="text-[11px] text-ink-muted ml-auto">
                {data ? `${data.total} recorded events` : ""}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Audit Log Table */}
      <Card className="border-card-border">
        {isLoading ? (
          <div className="p-8 flex flex-col items-center justify-center gap-2 text-ink-muted">
            <Loader2 className="h-6 w-6 animate-spin text-brand-text" />
            <span className="text-xs">Loading cryptographically verified audit records...</span>
          </div>
        ) : isError ? (
          <div className="p-6">
            <ErrorState
              title="Failed to load audit logs"
              message={error instanceof Error ? error.message : "Error fetching audit ledger"}
              onRetry={() => refetch()}
            />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="No audit log records found"
              description={
                hasActiveFilters
                  ? "No audit events match your filter criteria. Try clearing filters."
                  : "No events recorded in the ledger yet."
              }
              action={
                hasActiveFilters ? (
                  <Button variant="outline" size="sm" onClick={handleClearFilters} className="text-xs">
                    Clear Filters
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-card-border bg-canvas-2 font-medium text-ink-muted">
                <tr>
                  <th className="py-2.5 px-3 w-12 text-center">Seq</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Actor</th>
                  <th className="py-2.5 px-3">Target</th>
                  <th className="py-2.5 px-3">SHA-256 Hash</th>
                  <th className="py-2.5 px-3 w-16 text-center">Payload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((item: AuditLogItem) => {
                  const isExpanded = expandedSeq === item.seq;
                  return (
                    <React.Fragment key={item.seq}>
                      <tr className="hover:bg-canvas-2 transition-colors">
                        <td className="py-2.5 px-3 text-center font-mono text-ink-muted text-[11px]">
                          #{item.seq}
                        </td>
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <RelativeTime date={item.created_at} />
                        </td>
                        <td className="py-2.5 px-3">
                          <Badge variant="outline" className="font-mono text-[10px] bg-canvas-2">
                            {item.action}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-ink-muted">
                          {item.actor_id ? (
                            <span title={item.actor_id}>
                              {item.actor_id.length > 12
                                ? `${item.actor_id.slice(0, 10)}...`
                                : item.actor_id}
                            </span>
                          ) : (
                            <span className="italic text-ink-faint">system</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px]">
                          <span className="text-ink-muted">{item.target_type}</span>
                          {item.target_id && (
                            <span className="text-ink ml-1 font-semibold">
                              #{item.target_id.slice(-6)}
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[10px] text-ink-muted">
                          <div className="flex items-center gap-1.5">
                            <span title={item.hash}>{item.hash.slice(0, 12)}...</span>
                            <CopyButton value={item.hash} label="Copy full SHA-256 hash" />
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleExpand(item.seq)}
                            className="h-6 w-6 p-0"
                            title={isExpanded ? "Collapse payload" : "Expand JSON payload"}
                          >
                            {isExpanded ? (
                              <ChevronDown className="h-3.5 w-3.5" />
                            ) : (
                              <ChevronRight className="h-3.5 w-3.5" />
                            )}
                          </Button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-canvas-2 border-b border-card-border">
                          <td colSpan={7} className="py-3 px-4">
                            <div className="rounded-md border border-card-border bg-card p-3 space-y-2">
                              <div className="flex items-center justify-between text-[11px] text-ink-muted">
                                <span className="font-semibold text-ink">
                                  Payload Data for Event #{item.seq} ({item.action})
                                </span>
                                <CopyButton
                                  value={JSON.stringify(item.payload, null, 2)}
                                  label="Copy JSON"
                                />
                              </div>
                              <pre className="font-mono text-[11px] leading-relaxed overflow-x-auto p-2 bg-canvas-2 rounded text-ink max-h-60">
                                {JSON.stringify(item.payload, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {data && data.pages > 1 && (
          <div className="flex items-center justify-between border-t border-card-border px-4 py-3 text-xs text-ink-muted">
            <div>
              Page <span className="font-medium text-ink">{data.page}</span> of{" "}
              <span className="font-medium text-ink">{data.pages}</span> ({data.total} total
              events)
            </div>
            <div className="flex items-center gap-2">
              <Select
                value={pageSize.toString()}
                onValueChange={(val) => {
                  setPageSize(Number(val));
                  setPage(1);
                }}
              >
                <SelectTrigger className="h-7 w-20 text-xs font-mono">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10" className="text-xs">
                    10 / page
                  </SelectItem>
                  <SelectItem value="25" className="text-xs">
                    25 / page
                  </SelectItem>
                  <SelectItem value="50" className="text-xs">
                    50 / page
                  </SelectItem>
                  <SelectItem value="100" className="text-xs">
                    100 / page
                  </SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="h-7 text-xs"
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page >= data.pages}
                className="h-7 text-xs"
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
