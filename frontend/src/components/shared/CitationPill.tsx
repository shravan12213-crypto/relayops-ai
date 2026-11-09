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
          "inline-flex select-none items-center gap-1 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[11px] text-amber-700 dark:text-amber-400 font-medium cursor-not-allowed",
          className,
        )}
        {...props}
      >
        <Lock className="h-3 w-3 shrink-0" />
        <span>Restricted</span>
        <span className="rounded bg-amber-500/20 px-1 text-[9px] font-bold">L{sensitivity}</span>
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
              "inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border/70 bg-muted/40 px-2 py-0.5 font-mono text-[11px] text-foreground transition-all duration-150 hover:border-primary/50 hover:bg-accent hover:shadow-2xs active:scale-98 select-none",
              kind === "pr" && "hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-400",
              kind === "commit" && "hover:border-blue-500/40 hover:text-blue-600 dark:hover:text-blue-400",
              kind === "slack" && "hover:border-amber-500/40 hover:text-amber-600 dark:hover:text-amber-400",
              className,
            )}
            {...props}
          >
            <Icon className="h-3 w-3 shrink-0 text-muted-foreground group-hover:text-foreground" />
            <span className="font-semibold">{label}</span>
            {sensitivity > 0 && (
              <span className="text-[9px] text-amber-500 font-bold">L{sensitivity}</span>
            )}
          </span>
        </TooltipTrigger>

        {/* Hover Popover with preview, date, authority */}
        <TooltipContent
          side="top"
          align="start"
          className="max-w-xs sm:max-w-sm p-3 font-sans text-xs bg-popover text-popover-foreground border shadow-md space-y-2"
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-2 border-b border-border/60 pb-1.5 font-mono text-[10px]">
            <span className="font-semibold text-foreground flex items-center gap-1">
              <Icon className="h-3 w-3 text-primary" />
              {label}
            </span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground flex items-center gap-1">
              <Scale className="h-2.5 w-2.5 text-primary" />
              Auth: {effectiveAuth.toFixed(1)}
            </span>
          </div>

          {/* Snippet Preview */}
          {snippet ? (
            <p className="line-clamp-3 rounded border border-border/40 bg-muted/40 p-2 font-mono text-[11px] leading-relaxed text-foreground select-text">
              "{snippet}"
            </p>
          ) : (
            <p className="italic text-muted-foreground text-[11px]">
              Click to view supporting snippet in the Evidence drawer.
            </p>
          )}

          {/* Footer with date and permalink */}
          <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1">
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
              <span className="flex items-center gap-0.5 text-primary font-medium">
                Deep link <ExternalLink className="h-2.5 w-2.5" />
              </span>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
