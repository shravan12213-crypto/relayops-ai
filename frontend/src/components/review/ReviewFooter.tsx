import * as React from "react";
import {
  Camera,
  FileSignature,
  GitCompare,
  HelpCircle,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

import { SignoffModal } from "@/components/review/SignoffModal";
import { VersionDiffModal } from "@/components/review/VersionDiffModal";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  useCreateSnapshot,
  useVersions,
  type Ambiguity,
  type Claim,
} from "@/lib/api/review";
import { cn } from "@/lib/utils";

export interface ReviewFooterProps {
  handoverId: string;
  claims: Claim[];
  ambiguities: Ambiguity[];
  hasUnsavedEdits: boolean;
  onOpenShortcutsHelp: () => void;
}

export function ReviewFooter({
  handoverId,
  claims,
  ambiguities,
  hasUnsavedEdits,
  onOpenShortcutsHelp,
}: ReviewFooterProps) {
  const { data: versions = [] } = useVersions(handoverId);
  const createSnapshotMutation = useCreateSnapshot(handoverId);

  const [snapshotDialogOpen, setSnapshotDialogOpen] = React.useState(false);
  const [snapshotReason, setSnapshotReason] = React.useState("");
  const [diffModalOpen, setDiffModalOpen] = React.useState(false);
  const [signoffModalOpen, setSignoffModalOpen] = React.useState(false);
  const [selectedVersion, setSelectedVersion] = React.useState<string>("latest");

  const latestVersion = versions.length > 0 ? versions[versions.length - 1] : null;

  // Blockers computation
  const draftCount = claims.filter((c) => c.status === "draft").length;
  const highAmbiguitiesCount = ambiguities.filter(
    (a) => a.status === "open" && a.severity === "high",
  ).length;

  const blockers: string[] = [];
  if (draftCount > 0) {
    blockers.push(`${draftCount} draft claim${draftCount === 1 ? "" : "s"} require review`);
  }
  if (highAmbiguitiesCount > 0) {
    blockers.push(
      `${highAmbiguitiesCount} high-severity ambiguit${highAmbiguitiesCount === 1 ? "y" : "ies"} unresolved`,
    );
  }
  if (!latestVersion) {
    blockers.push("Must freeze at least one snapshot version");
  }

  const isSignoffBlocked = blockers.length > 0;

  const handleCreateSnapshot = async () => {
    await createSnapshotMutation.mutateAsync(snapshotReason.trim() || undefined);
    setSnapshotReason("");
    setSnapshotDialogOpen(false);
  };

  return (
    <>
      <footer className="flex h-12 w-full shrink-0 items-center justify-between border-t border-card-border bg-card px-3 sm:px-4 backdrop-blur-xs select-none gap-2 overflow-x-auto min-w-0">
        {/* Left Side: Unsaved Changes & Version Info */}
        <div className="flex items-center gap-2 sm:gap-3 text-xs shrink-0 min-w-0">
          {hasUnsavedEdits ? (
            <div className="flex items-center gap-1.5 text-needs-review dark:text-needs-review font-medium shrink-0">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-needs-review opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-needs-review"></span>
              </span>
              <span>Unsaved draft</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-ink-muted shrink-0">
              <CheckCircle2 className="h-3.5 w-3.5 text-verified" />
              <span className="hidden sm:inline">All changes synced</span>
            </div>
          )}

          <div className="h-4 w-px bg-border/60 shrink-0" />

          {/* Version Selector */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-ink-muted hidden sm:inline">Snapshot:</span>
            <Select
              value={selectedVersion}
              onValueChange={setSelectedVersion}
            >
              <SelectTrigger className="h-7 w-24 sm:w-28 text-xs bg-canvas-2">
                <SelectValue placeholder="Version" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="latest">
                  Latest {latestVersion ? `(v${latestVersion.version})` : "(None)"}
                </SelectItem>
                {versions.map((v) => (
                  <SelectItem key={v.version} value={String(v.version)}>
                    v{v.version} ({v.hash.slice(0, 6)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Diff Button */}
          {versions.length >= 2 && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs gap-1 px-2 text-ink-muted hover:text-ink shrink-0"
              onClick={() => setDiffModalOpen(true)}
            >
              <GitCompare className="h-3.5 w-3.5" />
              <span className="hidden md:inline">Compare Versions</span>
            </Button>
          )}
        </div>

        {/* Right Side: Actions */}
        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          {/* Shortcuts Help */}
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7 text-ink-muted hover:text-ink"
                  onClick={onOpenShortcutsHelp}
                >
                  <HelpCircle className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top">Keyboard shortcuts (?) </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* Create Snapshot Button */}
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs gap-1 px-2.5"
            onClick={() => setSnapshotDialogOpen(true)}
          >
            <Camera className="h-3.5 w-3.5 text-brand-text" />
            <span><span className="hidden sm:inline">Create </span>Snapshot</span>
          </Button>

          {/* Request Sign-off Button with Blockers Explanation */}
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div>
                  <Button
                    size="sm"
                    disabled={isSignoffBlocked}
                    className={cn(
                      "h-7 text-xs gap-1.5 px-2.5 font-medium shadow-xs",
                      !isSignoffBlocked && "bg-verified hover:bg-verified/90 text-white",
                    )}
                    onClick={() => setSignoffModalOpen(true)}
                  >
                    <FileSignature className="h-3.5 w-3.5" />
                    <span><span className="hidden sm:inline">Request </span>Sign-Off</span>
                  </Button>
                </div>
              </TooltipTrigger>

              {isSignoffBlocked ? (
                <TooltipContent side="top" className="max-w-xs p-2.5 text-xs bg-popover text-popover-foreground">
                  <div className="space-y-1">
                    <div className="flex items-center gap-1 font-semibold text-conflict">
                      <AlertCircle className="h-3.5 w-3.5" />
                      Sign-off Blocked
                    </div>
                    <ul className="list-disc pl-4 space-y-0.5 text-ink-muted">
                      {blockers.map((b, idx) => (
                        <li key={idx}>{b}</li>
                      ))}
                    </ul>
                  </div>
                </TooltipContent>
              ) : (
                <TooltipContent side="top">
                  All requirements met! Open dual sign-off workflow.
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        </div>
      </footer>

      {/* Snapshot Dialog */}
      <Dialog open={snapshotDialogOpen} onOpenChange={setSnapshotDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Camera className="h-4 w-4 text-brand-text" />
              <span>Freeze Cryptographic Snapshot</span>
            </DialogTitle>
            <DialogDescription className="text-xs">
              Freezes current claims, ambiguities, plan, and scorecard into an immutable version
              chained by SHA-256 state tree.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-2">
            <label className="text-xs font-medium text-ink">
              Snapshot Reason / Tag (Optional)
            </label>
            <Input
              value={snapshotReason}
              onChange={(e) => setSnapshotReason(e.target.value)}
              placeholder="e.g., Completed Architecture & Blockers review"
              className="text-xs"
            />
          </div>

          <DialogFooter className="gap-2">
            <Button size="sm" variant="outline" onClick={() => setSnapshotDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={createSnapshotMutation.isPending}
              onClick={handleCreateSnapshot}
            >
              Freeze Snapshot v{(latestVersion?.version ?? 0) + 1}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Version Diff Modal */}
      <VersionDiffModal
        handoverId={handoverId}
        open={diffModalOpen}
        onOpenChange={setDiffModalOpen}
      />

      {/* Sign-off Modal */}
      <SignoffModal
        handoverId={handoverId}
        open={signoffModalOpen}
        onOpenChange={setSignoffModalOpen}
        claims={claims}
        unresolvedHighAmbiguitiesCount={highAmbiguitiesCount}
      />
    </>
  );
}
