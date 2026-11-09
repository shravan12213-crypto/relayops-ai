import * as React from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  FilterX,
  GitFork,
  Keyboard,
  Play,
  Workflow,
} from "lucide-react";
import { toast } from "sonner";

import { ReviewClaimCard } from "@/components/review/ReviewClaimCard";
import { ReviewFooter } from "@/components/review/ReviewFooter";
import {
  ReviewLeftOutline,
  type OutlineFilters,
} from "@/components/review/ReviewLeftOutline";
import { ReviewRightDrawer, type RightTabType } from "@/components/review/ReviewRightDrawer";
import { ShortcutsHelpModal } from "@/components/review/ShortcutsHelpModal";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebounce } from "@/hooks/use-debounce";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useHandover } from "@/lib/api/handovers";
import { cn } from "@/lib/utils";
import {
  useAmbiguities,
  useClaims,
  useConflicts,
  usePatchClaim,
  type Claim,
  type EvidenceRef,
} from "@/lib/api/review";

const DEFAULT_LEFT_WIDTH = 260;
const DEFAULT_RIGHT_WIDTH = 380;

export function ReviewStudioPage() {
  const { handoverId = "" } = useParams<{ handoverId: string }>();

  // Data fetching
  const { data: handover } = useHandover(handoverId);
  const { data: claims = [], isLoading: claimsLoading } = useClaims(handoverId);
  const { data: ambiguities = [] } = useAmbiguities(handoverId);
  const { data: conflicts = [] } = useConflicts(handoverId);
  const patchClaimMutation = usePatchClaim(handoverId);

  // Pane width state with localStorage persistence
  const [leftWidth, setLeftWidth] = React.useState<number>(() => {
    const saved = localStorage.getItem("relayops_pane_left");
    return saved ? Number(saved) : DEFAULT_LEFT_WIDTH;
  });

  const [rightWidth, setRightWidth] = React.useState<number>(() => {
    const saved = localStorage.getItem("relayops_pane_right");
    return saved ? Number(saved) : DEFAULT_RIGHT_WIDTH;
  });

  // Filter state
  const [filters, setFilters] = React.useState<OutlineFilters>({
    section: "all",
    status: "all",
    kind: "all",
    sensitivity: "all",
    confidence: "all",
    search: "",
    onlyNeedsAttention: false,
  });

  // Selection & UI state
  const [selectedClaimId, setSelectedClaimId] = React.useState<string | null>(null);
  const [editingClaimId, setEditingClaimId] = React.useState<string | null>(null);
  const [selectedEvidence, setSelectedEvidence] = React.useState<EvidenceRef | null>(null);
  const [activeRightTab, setActiveRightTab] = React.useState<RightTabType>("evidence");
  const [shortcutsHelpOpen, setShortcutsHelpOpen] = React.useState(false);
  const [concurrencyConflictIds, setConcurrencyConflictIds] = React.useState<Set<string>>(new Set());

  // Responsive & Virtualization state
  const isCompact = useMediaQuery("(max-width: 1023px)");
  const [compactTab, setCompactTab] = React.useState<"outline" | "claims" | "drawer">("claims");
  const [displayLimit, setDisplayLimit] = React.useState(100);

  // Debounced search for smooth typing
  const debouncedSearch = useDebounce(filters.search, 200);

  // Refs
  const searchInputRef = React.useRef<HTMLInputElement>(null);
  const claimCardsContainerRef = React.useRef<HTMLDivElement>(null);

  // Resize handling
  const isDraggingLeft = React.useRef(false);
  const isDraggingRight = React.useRef(false);

  const startResizeLeft = (e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingLeft.current = true;
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  const startResizeRight = (e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRight.current = true;
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  const onMouseMove = (e: MouseEvent) => {
    if (isDraggingLeft.current) {
      const newWidth = Math.max(200, Math.min(420, e.clientX));
      setLeftWidth(newWidth);
      localStorage.setItem("relayops_pane_left", String(newWidth));
    } else if (isDraggingRight.current) {
      const newWidth = Math.max(280, Math.min(560, window.innerWidth - e.clientX));
      setRightWidth(newWidth);
      localStorage.setItem("relayops_pane_right", String(newWidth));
    }
  };

  const onMouseUp = () => {
    isDraggingLeft.current = false;
    isDraggingRight.current = false;
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
  };

  // Filtered Claims
  const filteredClaims = React.useMemo(() => {
    return claims.filter((claim) => {
      // Section filter
      if (filters.section !== "all") {
        const sec = claim.section?.toLowerCase() || "";
        if (!sec.includes(filters.section) && !filters.section.includes(sec)) {
          return false;
        }
      }

      // Attention filter (draft or needs_review)
      if (filters.onlyNeedsAttention) {
        if (claim.status !== "draft" && claim.status !== "needs_review") {
          return false;
        }
      }

      // Status filter
      if (filters.status !== "all" && claim.status !== filters.status) {
        return false;
      }

      // Kind filter
      if (filters.kind !== "all" && claim.kind !== filters.kind) {
        return false;
      }

      // Sensitivity filter
      if (filters.sensitivity !== "all") {
        const minLvl = Number(filters.sensitivity);
        if (claim.sensitivity < minLvl) return false;
      }

      // Confidence tier filter
      if (filters.confidence !== "all") {
        if (filters.confidence === "high" && claim.confidence < 0.8) return false;
        if (filters.confidence === "medium" && (claim.confidence < 0.5 || claim.confidence >= 0.8))
          return false;
        if (filters.confidence === "low" && claim.confidence >= 0.5) return false;
      }

      // Search query (debounced)
      if (debouncedSearch.trim()) {
        const q = debouncedSearch.toLowerCase();
        const matchesText = claim.text?.toLowerCase().includes(q);
        const matchesId = claim.id?.toLowerCase().includes(q);
        const matchesKind = claim.kind?.toLowerCase().includes(q);
        if (!matchesText && !matchesId && !matchesKind) return false;
      }

      return true;
    });
  }, [claims, filters, debouncedSearch]);

  // Virtualized slice for lists > 200 items to preserve 60fps rendering
  React.useEffect(() => {
    if (selectedClaimId && filteredClaims.length > 200) {
      const idx = filteredClaims.findIndex((c) => c.id === selectedClaimId);
      if (idx >= displayLimit) {
        setDisplayLimit(idx + 50);
      }
    }
  }, [selectedClaimId, filteredClaims, displayLimit]);

  const displayedClaims = React.useMemo(() => {
    if (filteredClaims.length <= 200) return filteredClaims;
    return filteredClaims.slice(0, displayLimit);
  }, [filteredClaims, displayLimit]);

  // Keep active selected claim valid
  React.useEffect(() => {
    if (filteredClaims.length > 0) {
      if (!selectedClaimId || !filteredClaims.some((c) => c.id === selectedClaimId)) {
        setSelectedClaimId(filteredClaims[0].id);
        // Default evidence to first citation if present
        if (filteredClaims[0].evidence && filteredClaims[0].evidence.length > 0) {
          setSelectedEvidence(filteredClaims[0].evidence[0]);
        }
      }
    } else {
      setSelectedClaimId(null);
    }
  }, [filteredClaims, selectedClaimId]);

  // Scroll active claim into view
  const scrollToActiveClaim = (claimId: string) => {
    const el = document.getElementById(`claim-card-${claimId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  // Select a claim
  const handleSelectClaim = (claim: Claim) => {
    setSelectedClaimId(claim.id);
    if (claim.evidence && claim.evidence.length > 0) {
      setSelectedEvidence(claim.evidence[0]);
    }
  };

  // Jump to claim (from conflict or ribbon)
  const handleJumpToClaim = (targetClaimId: string) => {
    // Reset filters if target is not in filtered list
    const isInFiltered = filteredClaims.some((c) => c.id === targetClaimId);
    if (!isInFiltered) {
      setFilters((prev) => ({
        ...prev,
        section: "all",
        status: "all",
        onlyNeedsAttention: false,
        search: "",
      }));
    }
    setSelectedClaimId(targetClaimId);
    setTimeout(() => {
      scrollToActiveClaim(targetClaimId);
    }, 50);
  };

  // Keyboard navigation helpers
  const moveToNextClaim = React.useCallback(() => {
    if (filteredClaims.length === 0) return;
    const currentIndex = filteredClaims.findIndex((c) => c.id === selectedClaimId);
    if (currentIndex < filteredClaims.length - 1) {
      const nextClaim = filteredClaims[currentIndex + 1];
      setSelectedClaimId(nextClaim.id);
      if (nextClaim.evidence && nextClaim.evidence.length > 0) {
        setSelectedEvidence(nextClaim.evidence[0]);
      }
      scrollToActiveClaim(nextClaim.id);
    }
  }, [filteredClaims, selectedClaimId]);

  const moveToPrevClaim = React.useCallback(() => {
    if (filteredClaims.length === 0) return;
    const currentIndex = filteredClaims.findIndex((c) => c.id === selectedClaimId);
    if (currentIndex > 0) {
      const prevClaim = filteredClaims[currentIndex - 1];
      setSelectedClaimId(prevClaim.id);
      if (prevClaim.evidence && prevClaim.evidence.length > 0) {
        setSelectedEvidence(prevClaim.evidence[0]);
      }
      scrollToActiveClaim(prevClaim.id);
    }
  }, [filteredClaims, selectedClaimId]);

  // Claim actions
  const handleAcceptClaim = React.useCallback(async (claim: Claim) => {
    try {
      await patchClaimMutation.mutateAsync({
        claimId: claim.id,
        patch: {
          status: "accepted",
          expected_updated_at: claim.updated_at,
        },
      });
      // Move to next claim if currently selected
      moveToNextClaim();
    } catch (err: unknown) {
      if (typeof err === "object" && err !== null && "status" in err && (err as { status: number }).status === 409) {
        setConcurrencyConflictIds((prev) => new Set(prev).add(claim.id));
      }
    }
  }, [patchClaimMutation, moveToNextClaim]);

  const handleRejectClaim = async (claim: Claim, reason: string) => {
    try {
      await patchClaimMutation.mutateAsync({
        claimId: claim.id,
        patch: {
          status: "rejected",
          rejected_reason: reason,
          expected_updated_at: claim.updated_at,
        },
      });
      moveToNextClaim();
    } catch (err: unknown) {
      if (typeof err === "object" && err !== null && "status" in err && (err as { status: number }).status === 409) {
        setConcurrencyConflictIds((prev) => new Set(prev).add(claim.id));
      }
    }
  };

  const handleSaveEdit = async (claim: Claim, newText: string) => {
    try {
      await patchClaimMutation.mutateAsync({
        claimId: claim.id,
        patch: {
          text: newText,
          status: "edited",
          expected_updated_at: claim.updated_at,
        },
      });
      setEditingClaimId(null);
      toast.success("Claim updated");
    } catch (err: unknown) {
      if (typeof err === "object" && err !== null && "status" in err && (err as { status: number }).status === 409) {
        setConcurrencyConflictIds((prev) => new Set(prev).add(claim.id));
      }
    }
  };

  // Bulk action: Accept all high-confidence verified claims in view
  const handleBulkAcceptHighConfidence = async () => {
    const eligible = filteredClaims.filter(
      (c) => c.status === "draft" && c.confidence >= 0.8 && c.evidence && c.evidence.length > 0,
    );
    if (eligible.length === 0) return;

    let successCount = 0;
    for (const c of eligible) {
      try {
        await patchClaimMutation.mutateAsync({
          claimId: c.id,
          patch: { status: "accepted" },
        });
        successCount++;
      } catch {
        // continue
      }
    }
    toast.success(`Accepted ${successCount} verified claims`);
  };

  // Global Keyboard listener
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // If typing in any input / textarea, do not trigger single-key actions
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;

      if (isInput) {
        if (e.key === "Escape" && editingClaimId) {
          setEditingClaimId(null);
        }
        return;
      }

      switch (e.key) {
        case "j":
        case "ArrowDown":
          e.preventDefault();
          moveToNextClaim();
          break;
        case "k":
        case "ArrowUp":
          e.preventDefault();
          moveToPrevClaim();
          break;
        case "a": {
          e.preventDefault();
          const currentClaim = filteredClaims.find((c) => c.id === selectedClaimId);
          if (currentClaim) handleAcceptClaim(currentClaim);
          break;
        }
        case "e": {
          e.preventDefault();
          if (selectedClaimId) {
            setEditingClaimId(selectedClaimId);
          }
          break;
        }
        case "x": {
          e.preventDefault();
          // Trigger click on the reject button for current claim
          const btn = document.querySelector(
            `#claim-card-${selectedClaimId} button[title*="Reject"], #claim-card-${selectedClaimId} button:has(svg.lucide-x)`,
          ) as HTMLButtonElement | null;
          if (btn) btn.click();
          break;
        }
        case "/":
          e.preventDefault();
          searchInputRef.current?.focus();
          break;
        case "?":
          e.preventDefault();
          setShortcutsHelpOpen(true);
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filteredClaims, selectedClaimId, editingClaimId, handleAcceptClaim, moveToNextClaim, moveToPrevClaim]);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col bg-background overflow-hidden">
      {/* Studio Header Bar */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border/80 px-4 bg-card/60 backdrop-blur-xs select-none">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
            <Link to="/handovers" title="Back to Handovers">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>

          <div className="flex items-center gap-2">
            <h1 className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Review Studio
            </h1>
            <span className="text-muted-foreground/60">•</span>
            <span className="text-xs font-medium text-muted-foreground truncate max-w-[240px]">
              {handover?.notes || `Handover ${handoverId.slice(0, 8)}`}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs gap-1.5"
            asChild
          >
            <Link to={`/handovers/${handoverId}/portal`}>
              <BookOpen className="h-3.5 w-3.5 text-primary" />
              <span>Portal</span>
            </Link>
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs gap-1.5"
            asChild
          >
            <Link to={`/handovers/${handoverId}/timeline`}>
              <Workflow className="h-3.5 w-3.5 text-primary" />
              <span>Timeline</span>
            </Link>
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs gap-1.5"
            asChild
          >
            <Link to={`/handovers/${handoverId}/topology`}>
              <GitFork className="h-3.5 w-3.5 text-primary" />
              <span>Topology</span>
            </Link>
          </Button>

          <div className="h-4 w-px bg-border/60 mx-0.5" />

          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs gap-1.5 text-muted-foreground hover:text-foreground"
            onClick={() => setShortcutsHelpOpen(true)}
          >
            <Keyboard className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Shortcuts</span>
            <kbd className="rounded border bg-muted px-1 text-[10px] font-mono">?</kbd>
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs gap-1"
            asChild
          >
            <Link to={`/handovers/${handoverId}/pipeline`}>
              <Play className="h-3 w-3 text-primary" />
              <span>Pipeline</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* Compact / Mobile / Tablet Tab Switcher (< 1024px) */}
      {isCompact && (
        <div className="flex items-center justify-around border-b border-border bg-card px-2 py-1 text-xs shrink-0 select-none">
          <Button
            variant={compactTab === "outline" ? "default" : "ghost"}
            size="sm"
            onClick={() => setCompactTab("outline")}
            className="h-7 text-xs px-3"
          >
            Outline & Filters
          </Button>
          <Button
            variant={compactTab === "claims" ? "default" : "ghost"}
            size="sm"
            onClick={() => setCompactTab("claims")}
            className="h-7 text-xs px-3"
          >
            Claims ({filteredClaims.length})
          </Button>
          <Button
            variant={compactTab === "drawer" ? "default" : "ghost"}
            size="sm"
            onClick={() => setCompactTab("drawer")}
            className="h-7 text-xs px-3"
          >
            Evidence & Issues
          </Button>
        </div>
      )}

      {/* Main Body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* LEFT PANE: Outline & Filters */}
        {(!isCompact || compactTab === "outline") && (
          <div
            style={isCompact ? { width: "100%" } : { width: `${leftWidth}px` }}
            className={cn(
              "shrink-0 overflow-hidden",
              !isCompact && "border-r border-border/70"
            )}
          >
            <ReviewLeftOutline
              claims={claims}
              filters={filters}
              onChangeFilters={(newFilters) => {
                setFilters(newFilters);
                if (isCompact) setCompactTab("claims");
              }}
              onBulkAcceptHighConfidence={handleBulkAcceptHighConfidence}
              searchRef={searchInputRef}
            />
          </div>
        )}

        {/* Left Resizer Handle (Desktop only) */}
        {!isCompact && (
          <div
            onMouseDown={startResizeLeft}
            className="w-1 cursor-col-resize hover:bg-primary/50 transition-colors bg-transparent select-none z-10 -ml-0.5"
            title="Drag to resize left outline"
          />
        )}

        {/* CENTER PANE: Claim Cards Stream */}
        {(!isCompact || compactTab === "claims") && (
          <div
            ref={claimCardsContainerRef}
            className="flex-1 min-w-0 overflow-y-auto bg-muted/15 p-4 space-y-3"
          >
            {claimsLoading ? (
              <div className="space-y-3 max-w-3xl mx-auto">
                <Skeleton className="h-28 w-full rounded-xl" />
                <Skeleton className="h-28 w-full rounded-xl" />
                <Skeleton className="h-28 w-full rounded-xl" />
              </div>
            ) : filteredClaims.length === 0 ? (
              <div className="py-20 max-w-md mx-auto">
                <EmptyState
                  icon={FilterX}
                  title="No Matching Claims"
                  description={
                    filters.onlyNeedsAttention
                      ? "Great job! All claims matching your criteria have already been reviewed and accepted."
                      : "No claims match the active filters or search text."
                  }
                  action={
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        setFilters({
                          section: "all",
                          status: "all",
                          kind: "all",
                          sensitivity: "all",
                          confidence: "all",
                          search: "",
                          onlyNeedsAttention: false,
                        })
                      }
                    >
                      Reset All Filters
                    </Button>
                  }
                />
              </div>
            ) : (
              <div className="max-w-3xl mx-auto space-y-3 pb-8">
                {displayedClaims.map((claim) => (
                  <div key={claim.id} id={`claim-card-${claim.id}`}>
                    <ReviewClaimCard
                      claim={claim}
                      isSelected={claim.id === selectedClaimId}
                      isEditing={editingClaimId === claim.id}
                      onSelect={() => handleSelectClaim(claim)}
                      onAccept={handleAcceptClaim}
                      onReject={handleRejectClaim}
                      onSaveEdit={handleSaveEdit}
                      onCancelEdit={() => setEditingClaimId(null)}
                      onStartEdit={() => setEditingClaimId(claim.id)}
                      onSelectEvidence={(ev) => {
                        setSelectedEvidence(ev);
                        setActiveRightTab("evidence");
                        if (isCompact) setCompactTab("drawer");
                      }}
                      onJumpToClaim={(id) => {
                        handleJumpToClaim(id);
                        if (isCompact) setCompactTab("claims");
                      }}
                      concurrencyConflict={concurrencyConflictIds.has(claim.id)}
                    />
                  </div>
                ))}

                {/* Virtualization Load More Trigger when list > 200 items */}
                {filteredClaims.length > 200 && displayLimit < filteredClaims.length && (
                  <div className="py-4 text-center">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setDisplayLimit((prev) => Math.min(filteredClaims.length, prev + 100))
                      }
                      className="text-xs"
                    >
                      Load more claims ({filteredClaims.length - displayLimit} remaining)
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Right Resizer Handle (Desktop only) */}
        {!isCompact && (
          <div
            onMouseDown={startResizeRight}
            className="w-1 cursor-col-resize hover:bg-primary/50 transition-colors bg-transparent select-none z-10 -mr-0.5"
            title="Drag to resize right drawer"
          />
        )}

        {/* RIGHT PANE: Evidence & Issues Drawer */}
        {(!isCompact || compactTab === "drawer") && (
          <div
            style={isCompact ? { width: "100%" } : { width: `${rightWidth}px` }}
            className={cn(
              "shrink-0 overflow-hidden",
              !isCompact && "border-l border-border/70"
            )}
          >
            <ReviewRightDrawer
              handoverId={handoverId}
              selectedEvidence={selectedEvidence}
              activeTab={activeRightTab}
              onTabChange={setActiveRightTab}
              claims={claims}
              ambiguities={ambiguities}
              conflictsCount={conflicts.length}
              onJumpToClaim={(id) => {
                handleJumpToClaim(id);
                if (isCompact) setCompactTab("claims");
              }}
            />
          </div>
        )}
      </div>

      {/* FOOTER BAR: Snapshots & Dual Sign-Off */}
      <ReviewFooter
        handoverId={handoverId}
        claims={claims}
        ambiguities={ambiguities}
        hasUnsavedEdits={Boolean(editingClaimId)}
        onOpenShortcutsHelp={() => setShortcutsHelpOpen(true)}
      />

      {/* Shortcuts Cheat-Sheet Modal */}
      <ShortcutsHelpModal
        open={shortcutsHelpOpen}
        onOpenChange={setShortcutsHelpOpen}
      />
    </div>
  );
}
export default ReviewStudioPage;
