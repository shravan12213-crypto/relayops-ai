import * as React from "react";
import { ExternalLink, FileText, GitCommit, GitPullRequest, MessageSquare, ShieldCheck, Eye } from "lucide-react";

import { EvidenceDrawerContext } from "@/components/shared/evidence-drawer-context";
import { CopyButton } from "@/components/shared/CopyButton";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useArtifact, type EvidenceRef } from "@/lib/api/review";

export function EvidenceDrawerProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [activeEvidence, setActiveEvidence] = React.useState<EvidenceRef | null>(null);
  const [fullArtifactOpen, setFullArtifactOpen] = React.useState(false);

  const { data: artifact, isLoading } = useArtifact(activeEvidence?.artifact_id);

  const openEvidenceDrawer = React.useCallback((evidence: EvidenceRef) => {
    setActiveEvidence(evidence);
    setIsOpen(true);
  }, []);

  const closeEvidenceDrawer = React.useCallback(() => {
    setIsOpen(false);
  }, []);

  const getSourceIcon = (type?: string) => {
    switch (type?.toLowerCase()) {
      case "commit":
      case "git_commit":
        return GitCommit;
      case "pr":
      case "pull_request":
        return GitPullRequest;
      case "slack":
      case "slack_json":
        return MessageSquare;
      default:
        return FileText;
    }
  };

  const Icon = getSourceIcon(activeEvidence?.source_type || artifact?.kind);

  const renderRedactedBody = (body: string) => {
    const parts = body.split(/(\[REDACTED_[A-Z0-9_]+\])/g);
    return parts.map((part, i) => {
      if (part.startsWith("[REDACTED_")) {
        return (
          <span
            key={i}
            className="inline-flex items-center gap-1 rounded-md bg-warn-soft px-1 py-0.5 font-mono text-[11px] font-semibold text-needs-review"
          >
            <ShieldCheck className="h-3 w-3" />
            {part}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <EvidenceDrawerContext.Provider
      value={{ openEvidenceDrawer, closeEvidenceDrawer, isOpen, activeEvidence }}
    >
      {children}

      {/* Global Slide-Out Evidence Sheet */}
      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetContent side="right" className="w-full sm:max-w-md p-0 flex flex-col bg-background">
          <SheetHeader className="p-4 border-b border-border/80">
            <div className="flex items-center justify-between">
              <SheetTitle className="text-sm font-semibold flex items-center gap-2">
                <Icon className="h-4 w-4 text-primary" />
                <span>Source Artifact Evidence</span>
              </SheetTitle>
            </div>
          </SheetHeader>

          {activeEvidence && (
            <div className="flex-1 flex flex-col min-h-0 p-4 space-y-4">
              {/* Header Metadata */}
              <div className="rounded-lg border border-border/80 bg-card p-3 space-y-2 shadow-2xs">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold capitalize text-foreground">
                      {activeEvidence.source_type || artifact?.kind || "Artifact Source"}
                    </span>
                    <p className="font-mono text-[10px] text-muted-foreground truncate max-w-[220px]">
                      {activeEvidence.artifact_id}
                    </p>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <CopyButton value={activeEvidence.snippet || ""} />
                    {activeEvidence.source_uri && (
                      <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
                        <a
                          href={activeEvidence.source_uri}
                          target="_blank"
                          rel="noreferrer"
                          title="Open permalink"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      </Button>
                    )}
                  </div>
                </div>

                {artifact?.title && (
                  <div className="text-xs font-medium text-foreground line-clamp-1 border-t border-border/40 pt-1.5">
                    {artifact.title}
                  </div>
                )}
              </div>

              {/* Exact Snippet */}
              <div className="flex-1 flex flex-col min-h-0 rounded-lg border border-border/80 bg-card overflow-hidden shadow-2xs">
                <div className="flex items-center justify-between border-b border-border/60 bg-muted/40 px-3 py-2 text-xs font-medium text-muted-foreground">
                  <span>Exact Verified Snippet</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-[11px] gap-1 hover:text-foreground"
                    onClick={() => setFullArtifactOpen(true)}
                  >
                    <Eye className="h-3 w-3" />
                    Show Full Document
                  </Button>
                </div>

                <ScrollArea className="flex-1 p-3">
                  <div className="rounded-md border border-verified/30 bg-verified/5 p-3 font-mono text-xs leading-relaxed text-foreground whitespace-pre-wrap select-text">
                    {activeEvidence.snippet || (isLoading ? "Loading snippet..." : "No snippet recorded.")}
                  </div>

                  {activeEvidence.char_start !== undefined && activeEvidence.char_end !== undefined && (
                    <div className="mt-2 text-[11px] font-mono text-muted-foreground">
                      Offsets: [{activeEvidence.char_start} - {activeEvidence.char_end}]
                    </div>
                  )}
                </ScrollArea>
              </div>

              {/* Provenance Reassurance */}
              <div className="rounded-lg border border-border/40 bg-muted/20 p-2.5 text-[11px] text-muted-foreground flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-verified shrink-0" />
                <span>Every claim shown to a successor has ≥ 1 verified evidence link to a real artifact.</span>
              </div>
            </div>
          )}

          {/* Full Artifact Modal */}
          <Dialog open={fullArtifactOpen} onOpenChange={setFullArtifactOpen}>
            <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-base">
                  <Icon className="h-4 w-4 text-primary" />
                  <span>{artifact?.title || activeEvidence?.artifact_id}</span>
                </DialogTitle>
                <DialogDescription className="font-mono text-xs">
                  {activeEvidence?.source_uri || `Artifact ID: ${activeEvidence?.artifact_id}`}
                </DialogDescription>
              </DialogHeader>

              <div className="flex-1 min-h-0 my-2">
                {isLoading ? (
                  <div className="space-y-2 p-4">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" />
                  </div>
                ) : (
                  <ScrollArea className="h-[55vh] rounded-md border p-4 bg-muted/30">
                    <div className="font-mono text-xs leading-relaxed whitespace-pre-wrap select-text">
                      {artifact?.body_redacted
                        ? renderRedactedBody(artifact.body_redacted)
                        : "No full artifact body available."}
                    </div>
                  </ScrollArea>
                )}
              </div>

              <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-verified" />
                  Pre-scrubbed at ingestion: PII and credentials redacted before storage.
                </span>
                <Button size="sm" variant="outline" onClick={() => setFullArtifactOpen(false)}>
                  Close
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </SheetContent>
      </Sheet>
    </EvidenceDrawerContext.Provider>
  );
}
