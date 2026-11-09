import * as React from "react";
import { ExternalLink, FileText, GitCommit, GitPullRequest, MessageSquare, ShieldCheck, Eye } from "lucide-react";

import { CopyButton } from "@/components/shared/CopyButton";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { useArtifact, type EvidenceRef } from "@/lib/api/review";

export interface EvidenceTabProps {
  evidence: EvidenceRef | null;
}

export function EvidenceTab({ evidence }: EvidenceTabProps) {
  const [fullArtifactOpen, setFullArtifactOpen] = React.useState(false);

  const { data: artifact, isLoading } = useArtifact(evidence?.artifact_id);

  if (!evidence) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon={FileText}
          title="No Citation Selected"
          description="Click any citation pill on a claim card to inspect its exact source text, permalink, and redactions."
        />
      </div>
    );
  }

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

  const Icon = getSourceIcon(evidence.source_type || artifact?.kind);

  // Helper to render redacted spans with styling
  const renderRedactedBody = (body: string) => {
    const parts = body.split(/(\[REDACTED_[A-Z0-9_]+\])/g);
    return parts.map((part, i) => {
      if (part.startsWith("[REDACTED_")) {
        return (
          <span
            key={i}
            className="inline-flex items-center gap-1 rounded bg-amber-500/20 text-amber-800 dark:text-amber-300 px-1 py-0.5 font-mono text-[11px] font-semibold"
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
    <div className="flex h-full flex-col p-4 space-y-4">
      {/* Header Info */}
      <div className="rounded-lg border border-border/70 bg-card p-3 shadow-2xs space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="rounded-md bg-primary/10 p-1.5 text-primary">
              <Icon className="h-4 w-4" />
            </div>
            <div>
              <span className="text-xs font-semibold capitalize">
                {evidence.source_type || artifact?.kind || "Artifact Source"}
              </span>
              <p className="font-mono text-[10px] text-muted-foreground truncate max-w-[200px]">
                {evidence.artifact_id}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <CopyButton value={evidence.snippet || ""} />
            {evidence.source_uri && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                asChild
              >
                <a
                  href={evidence.source_uri}
                  target="_blank"
                  rel="noreferrer"
                  title="Open source permalink"
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

      {/* Snippet Card */}
      <div className="flex-1 flex flex-col min-h-0 rounded-lg border border-border/70 bg-card overflow-hidden shadow-2xs">
        <div className="flex items-center justify-between border-b border-border/60 bg-muted/40 px-3 py-2 text-xs font-medium text-muted-foreground">
          <span>Supporting Snippet</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px] gap-1 hover:text-foreground"
            onClick={() => setFullArtifactOpen(true)}
          >
            <Eye className="h-3 w-3" />
            Show Full Artifact
          </Button>
        </div>

        <ScrollArea className="flex-1 p-3">
          <div className="rounded-md border border-verified/30 bg-verified/5 p-3 font-mono text-xs leading-relaxed text-foreground whitespace-pre-wrap select-text">
            {evidence.snippet || (isLoading ? "Loading snippet..." : "No snippet recorded.")}
          </div>

          {evidence.char_start !== undefined && evidence.char_end !== undefined && (
            <div className="mt-2 text-[11px] font-mono text-muted-foreground">
              Span: [{evidence.char_start} - {evidence.char_end}]
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Full Artifact Modal */}
      <Dialog open={fullArtifactOpen} onOpenChange={setFullArtifactOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Icon className="h-4 w-4 text-primary" />
              <span>{artifact?.title || evidence.artifact_id}</span>
            </DialogTitle>
            <DialogDescription className="font-mono text-xs">
              {evidence.source_uri || `Artifact ID: ${evidence.artifact_id}`}
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
              Pre-scrubbed at ingestion: PII and credentials redacted before LLM and storage.
            </span>
            <Button size="sm" variant="outline" onClick={() => setFullArtifactOpen(false)}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
