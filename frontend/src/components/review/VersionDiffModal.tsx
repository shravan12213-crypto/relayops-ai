import * as React from "react";
import { GitCompare, Plus, Minus, Edit3, ArrowRight } from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useVersionDiff, useVersions } from "@/lib/api/review";

export interface VersionDiffModalProps {
  handoverId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialBaseVersion?: number;
  initialTargetVersion?: number;
}

interface DiffWordToken {
  type: string;
  text: string;
}

interface DiffClaimItem {
  id?: string;
  text?: string;
  section?: string;
  status?: string;
  kind?: string;
}

interface ChangedClaimItem {
  id?: string;
  changes?: {
    text?: {
      from?: string;
      to?: string;
      word_diff?: DiffWordToken[];
    };
    status?: { from?: string; to?: string };
    section?: { from?: string; to?: string };
    kind?: { from?: string; to?: string };
  };
}

export function VersionDiffModal({
  handoverId,
  open,
  onOpenChange,
  initialBaseVersion,
  initialTargetVersion,
}: VersionDiffModalProps) {
  const { data: versions = [] } = useVersions(handoverId);

  const [v1, setV1] = React.useState<number | null>(null);
  const [v2, setV2] = React.useState<number | null>(null);

  // Set default versions when available
  React.useEffect(() => {
    if (versions.length >= 2) {
      setV1(initialBaseVersion ?? versions[versions.length - 2].version);
      setV2(initialTargetVersion ?? versions[versions.length - 1].version);
    } else if (versions.length === 1) {
      setV1(1);
      setV2(1);
    }
  }, [versions, initialBaseVersion, initialTargetVersion]);

  const { data: diff, isLoading } = useVersionDiff(handoverId, v1, v2);

  const claimsData = diff?.claims as unknown as {
    added?: DiffClaimItem[];
    removed?: DiffClaimItem[];
    changed?: ChangedClaimItem[];
  } | undefined;

  const addedClaims: DiffClaimItem[] = claimsData?.added || [];
  const removedClaims: DiffClaimItem[] = claimsData?.removed || [];
  const changedClaims: ChangedClaimItem[] = claimsData?.changed || [];
  const totalChanges = addedClaims.length + removedClaims.length + changedClaims.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <GitCompare className="h-4 w-4 text-brand-text" />
            <span>Cryptographic Snapshot Version Diff</span>
          </DialogTitle>
          <DialogDescription className="text-xs">
            Inspect changes across immutable frozen snapshot versions.
          </DialogDescription>
        </DialogHeader>

        {/* Version Selectors */}
        <div className="flex items-center justify-between gap-3 rounded-lg border bg-canvas-2 p-3 my-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-muted font-medium">Base:</span>
            <Select
              value={v1 !== null ? String(v1) : ""}
              onValueChange={(val) => setV1(Number(val))}
            >
              <SelectTrigger className="h-7 w-28 text-xs bg-background">
                <SelectValue placeholder="Base v" />
              </SelectTrigger>
              <SelectContent>
                {versions.map((v) => (
                  <SelectItem key={v.version} value={String(v.version)}>
                    v{v.version} ({v.hash.slice(0, 6)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <ArrowRight className="h-4 w-4 text-ink-muted" />

          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-muted font-medium">Target:</span>
            <Select
              value={v2 !== null ? String(v2) : ""}
              onValueChange={(val) => setV2(Number(val))}
            >
              <SelectTrigger className="h-7 w-28 text-xs bg-background">
                <SelectValue placeholder="Target v" />
              </SelectTrigger>
              <SelectContent>
                {versions.map((v) => (
                  <SelectItem key={v.version} value={String(v.version)}>
                    v{v.version} ({v.hash.slice(0, 6)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="ml-auto text-xs font-mono text-ink-muted">
            {totalChanges} claim delta{totalChanges === 1 ? "" : "s"}
          </div>
        </div>

        {/* Diff Content Area */}
        <div className="flex-1 min-h-0">
          {v1 === v2 ? (
            <div className="py-12">
              <EmptyState
                icon={GitCompare}
                title="Identical Versions Selected"
                description="Select two different snapshot versions above to compare added, removed, and modified claims."
              />
            </div>
          ) : isLoading ? (
            <div className="p-8 text-center text-xs text-ink-muted">
              Computing cryptographic version diff...
            </div>
          ) : totalChanges === 0 ? (
            <div className="py-12">
              <EmptyState
                icon={GitCompare}
                title="Zero Claim Differences"
                description="The claims and text in these two snapshot versions are identical."
              />
            </div>
          ) : (
            <ScrollArea className="h-[55vh] -mr-2 pr-2">
              <div className="space-y-4 py-2">
                {/* Changed Claims */}
                {changedClaims.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-muted">
                      <Edit3 className="h-3 w-3 text-needs-review" />
                      Modified Claims ({changedClaims.length})
                    </h4>
                    {changedClaims.map((item: ChangedClaimItem, idx: number) => {
                      const textChange = item.changes?.text;
                      return (
                        <div
                          key={idx}
                          className="rounded-lg border border-needs-review bg-warn-soft p-3 space-y-2 text-xs"
                        >
                          <div className="font-mono text-[10px] text-ink-muted">
                            Claim #{item.id?.slice(0, 8)}
                          </div>
                          {textChange?.word_diff ? (
                            <div className="font-mono text-xs leading-relaxed whitespace-pre-wrap rounded bg-background/80 p-2 border">
                              {textChange.word_diff.map((token: DiffWordToken, tIdx: number) => {
                                if (token.type === "added") {
                                  return (
                                    <span
                                      key={tIdx}
                                      className="bg-verified/25 text-verified-foreground font-semibold underline px-0.5"
                                    >
                                      {token.text}{" "}
                                    </span>
                                  );
                                }
                                if (token.type === "removed") {
                                  return (
                                    <span
                                      key={tIdx}
                                      className="bg-danger-soft text-conflict dark:text-conflict line-through px-0.5"
                                    >
                                      {token.text}{" "}
                                    </span>
                                  );
                                }
                                return <span key={tIdx}>{token.text} </span>;
                              })}
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <p className="line-through text-conflict/80">{textChange?.from}</p>
                              <p className="text-verified">{textChange?.to}</p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Added Claims */}
                {addedClaims.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-muted">
                      <Plus className="h-3 w-3 text-verified" />
                      Added Claims ({addedClaims.length})
                    </h4>
                    {addedClaims.map((claim: DiffClaimItem, idx: number) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-verified/30 bg-verified/5 p-3 space-y-1 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-ink-muted">
                            #{claim.id?.slice(0, 8)}
                          </span>
                          <Badge variant="outline" className="text-[10px] text-verified border-verified/30">
                            + added in v{v2}
                          </Badge>
                        </div>
                        <p className="font-medium text-ink">{claim.text}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Removed Claims */}
                {removedClaims.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-muted">
                      <Minus className="h-3 w-3 text-conflict" />
                      Removed Claims ({removedClaims.length})
                    </h4>
                    {removedClaims.map((claim: DiffClaimItem, idx: number) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-conflict/30 bg-danger-soft p-3 space-y-1 text-xs opacity-80"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-ink-muted">
                            #{claim.id?.slice(0, 8)}
                          </span>
                          <Badge variant="outline" className="text-[10px] text-conflict border-conflict/30">
                            - removed in v{v2}
                          </Badge>
                        </div>
                        <p className="line-through text-ink-muted">{claim.text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </ScrollArea>
          )}
        </div>

        <div className="flex items-center justify-end pt-3 border-t">
          <Button size="sm" variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
