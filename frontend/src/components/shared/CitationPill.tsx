import * as React from "react";
import {
  FileText,
  GitCommit,
  GitPullRequest,
  Lock,
  MessageSquare,
  Scale,
  Ticket,
  Calendar,
  ExternalLink,
} from "lucide-react";

import { useEvidenceDrawer } from "@/components/shared/evidence-drawer-context";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/api/auth";
import { formatCitationLabel } from "@/lib/citation-utils";
import { cn } from "@/lib/utils";

export interface CitationPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  artifactId: string;
  sourceUri?: string;
  snippet?: string;
  sourceType?: "commit" | "pr" | "issue" | "slack" | "doc" | "adr" | string;
  sensitivity?: number;
  occurredAt?: string;
  authority?: number;
  onClickSnippet?: () => void;
}

export function CitationPill({
  artifactId,
  sourceUri,
  snippet,
  sourceType = "doc",
  sensitivity = 0,
  occurredAt,
  authority,
  onClickSnippet,
  className,
  ...props
}: CitationPillProps) {
  const { user } = useAuth();
  const { openEvidenceDrawer } = useEvidenceDrawer();

  const viewerClearance = user?.clearance ?? 1;
  const isRestricted = sensitivity > viewerClearance;

  // If user lacks clearance, render locked restricted chip without snippet
  if (isRestricted) {
    return (
      <span
        title={`Restricted Artifact (Level ${sensitivity}) - Requires clearance`}
        className={cn(
          "inline-flex select-none items-center gap-1 rounded border border-needs-review bg-warn-soft px-2 py-0.5 font-mono text-[11px] text-needs-review dark:text-needs-review font-medium cursor-not-allowed",
          className,
        )}
        {...props}
      >
        <Lock className="h-3 w-3 shrink-0" />
        <span>Restricted</span>
        <span className="rounded bg-warn-soft px-1 text-[9px] font-bold">L{sensitivity}</span>
      </span>
    );
  }

  const { label, kind, authorityWeight, authorityLabel } = formatCitationLabel(
    artifactId,
    sourceType,
  );
  const effectiveAuth = authority !== undefined ? authority : authorityWeight;

  const getKindIcon = () => {
    switch (kind) {
      case "pr":
        return GitPullRequest;
      case "commit":
        return GitCommit;
      case "issue":
        return Ticket;
      case "slack":
        return MessageSquare;
      case "doc":
      default:
        return FileText;
    }
  };

  const Icon = getKindIcon();

  const handleClick = (e: React.MouseEvent<HTMLSpanElement>) => {
    e.stopPropagation();
    if (onClickSnippet) {
      onClickSnippet();
    } else {
      openEvidenceDrawer({
        artifact_id: artifactId,
        source_uri: sourceUri,
        snippet,
        source_type: sourceType,
      });
    }
  };

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            onClick={handleClick}
            className={cn(
              "inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-card-border bg-canvas-2 px-2 py-0.5 font-mono text-[11px] text-ink transition-all duration-150 hover:border-brand hover:bg-canvas-2 hover:shadow-2xs active:scale-98 select-none",
              kind === "pr" && "hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-400",
              kind === "commit" && "hover:border-brand hover:text-brand-text",
              kind === "slack" && "hover:border-needs-review hover:text-needs-review dark:hover:text-needs-review",
              className,
            )}
            {...props}
          >
            <Icon className="h-3 w-3 shrink-0 text-ink-muted group-hover:text-ink" />
            <span className="font-semibold">{label}</span>
            {sensitivity > 0 && (
              <span className="text-[9px] text-needs-review font-bold">L{sensitivity}</span>
            )}
          </span>
        </TooltipTrigger>

        {/* Hover Popover with preview, date, authority */}
        <TooltipContent
          side="top"
          align="start"
          className="max-w-xs sm:max-w-sm p-3 font-sans text-xs bg-popover text-ink border shadow-md space-y-2"
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-2 border-b border-card-border pb-1.5 font-mono text-[10px]">
            <span className="font-semibold text-ink flex items-center gap-1">
              <Icon className="h-3 w-3 text-brand-text" />
              {label}
            </span>
            <span className="rounded bg-canvas-2 px-1.5 py-0.5 text-ink-muted flex items-center gap-1">
              <Scale className="h-2.5 w-2.5 text-brand-text" />
              Auth: {effectiveAuth.toFixed(1)}
            </span>
          </div>

          {/* Snippet Preview */}
          {snippet ? (
            <p className="line-clamp-3 rounded border border-card-border bg-canvas-2 p-2 font-mono text-[11px] leading-relaxed text-ink select-text">
              "{snippet}"
            </p>
          ) : (
            <p className="italic text-ink-muted text-[11px]">
              Click to view supporting snippet in the Evidence drawer.
            </p>
          )}

          {/* Footer with date and permalink */}
          <div className="flex items-center justify-between text-[10px] text-ink-muted pt-1">
            <span className="flex items-center gap-1">
              {occurredAt ? (
                <>
                  <Calendar className="h-3 w-3" />
                  <span>{new Date(occurredAt).toLocaleDateString()}</span>
                </>
              ) : (
                <span>{authorityLabel}</span>
              )}
            </span>

            {sourceUri && (
              <span className="flex items-center gap-0.5 text-brand-text font-medium">
                Deep link <ExternalLink className="h-2.5 w-2.5" />
              </span>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
