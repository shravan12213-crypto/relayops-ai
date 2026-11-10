import * as React from "react";
import {
  Layers,
  Users,
  AlertOctagon,
  Briefcase,
  BookOpen,
  AlertTriangle,
  Contact2,
  GitFork,
  Search,
  CheckCheck,
  Filter,
} from "lucide-react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type Claim } from "@/lib/api/review";
import { cn } from "@/lib/utils";

export interface OutlineFilters {
  section: string;
  status: string;
  kind: string;
  sensitivity: string;
  confidence: string;
  search: string;
  onlyNeedsAttention: boolean;
}

export interface ReviewLeftOutlineProps {
  claims: Claim[];
  filters: OutlineFilters;
  onChangeFilters: (filters: OutlineFilters) => void;
  onBulkAcceptHighConfidence: () => void;
  searchRef?: React.RefObject<HTMLInputElement>;
}

const SECTIONS_CONFIG = [
  { id: "all", label: "All Sections", icon: Layers },
  { id: "architecture", label: "Architecture", icon: Layers },
  { id: "ownership", label: "Ownership", icon: Users },
  { id: "blocker", label: "Blockers", icon: AlertOctagon },
  { id: "open_work", label: "Open Work", icon: Briefcase },
  { id: "runbook", label: "Runbooks", icon: BookOpen },
  { id: "risk", label: "Risks", icon: AlertTriangle },
  { id: "contact", label: "Contacts", icon: Contact2 },
  { id: "dependency", label: "Dependencies", icon: GitFork },
];

export function ReviewLeftOutline({
  claims,
  filters,
  onChangeFilters,
  onBulkAcceptHighConfidence,
  searchRef,
}: ReviewLeftOutlineProps) {
  const [confirmBulkOpen, setConfirmBulkOpen] = React.useState(false);

  // Calculate reviewed metrics
  const total = claims.length;
  const reviewed = claims.filter(
    (c) => c.status === "accepted" || c.status === "edited" || c.status === "rejected",
  ).length;
  const pctReviewed = total > 0 ? Math.round((reviewed / total) * 100) : 0;

  // High confidence verified eligible for bulk accept
  const bulkEligibleClaims = claims.filter(
    (c) => c.status === "draft" && c.confidence >= 0.8 && c.evidence && c.evidence.length > 0,
  );

  // Count by section
  const sectionCounts = React.useMemo(() => {
    const counts: Record<string, number> = { all: claims.length };
    claims.forEach((c) => {
      const s = c.section?.toLowerCase();
      // match both plural and singular keys
      for (const cfg of SECTIONS_CONFIG) {
        if (cfg.id !== "all" && (s.includes(cfg.id) || cfg.id.includes(s))) {
          counts[cfg.id] = (counts[cfg.id] || 0) + 1;
        }
      }
    });
    return counts;
  }, [claims]);

  return (
    <div className="flex h-full flex-col bg-canvas/60 select-none">
      {/* Header & Progress Ring */}
      <div className="p-4 border-b border-card-border">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Review Progress
            </h3>
            <p className="text-sm font-medium text-ink">
              {reviewed} of {total} claims reviewed
            </p>
          </div>

          {/* Progress Ring */}
          <div className="relative flex h-11 w-11 items-center justify-center">
            <svg className="h-full w-full -rotate-90 transform" viewBox="0 0 36 36">
              <path
                className="text-muted/40"
                strokeWidth="3.5"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className={cn(
                  "transition-all duration-300",
                  pctReviewed === 100
                    ? "text-verified"
                    : pctReviewed > 50
                      ? "text-brand-text"
                      : "text-needs-review",
                )}
                strokeDasharray={`${pctReviewed}, 100`}
                strokeWidth="3.5"
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <span className="absolute text-[11px] font-bold text-ink">
              {pctReviewed}%
            </span>
          </div>
        </div>

        {/* Search input with shortcut hint */}
        <div className="relative mt-3">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-ink-muted" />
          <Input
            ref={searchRef}
            type="search"
            placeholder="Search claims... (/)"
            value={filters.search}
            onChange={(e) => onChangeFilters({ ...filters, search: e.target.value })}
            className="h-8 pl-8 pr-7 text-xs bg-canvas-2"
          />
          <kbd className="pointer-events-none absolute right-2.5 top-2 rounded border bg-canvas px-1 text-[10px] font-mono text-ink-muted">
            /
          </kbd>
        </div>

        {/* Attention filter toggle */}
        <div className="mt-3 flex items-center justify-between rounded-lg border border-card-border bg-canvas-2 px-2.5 py-1.5">
          <label
            htmlFor="attention-toggle"
            className="flex cursor-pointer items-center gap-2 text-xs font-medium text-ink"
          >
            <Checkbox
              id="attention-toggle"
              checked={filters.onlyNeedsAttention}
              onCheckedChange={(checked) =>
                onChangeFilters({ ...filters, onlyNeedsAttention: Boolean(checked) })
              }
            />
            <span>Only needs attention</span>
          </label>
          <span className="rounded bg-warn-soft px-1.5 py-0.5 text-[10px] font-semibold text-needs-review dark:text-needs-review">
            {claims.filter((c) => c.status === "draft" || c.status === "needs_review").length}
          </span>
        </div>
      </div>

      {/* Sections List */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
        <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
          Sections
        </div>
        {SECTIONS_CONFIG.map((sec) => {
          const Icon = sec.icon;
          const count = sectionCounts[sec.id] || 0;
          const isSelected = filters.section === sec.id;

          return (
            <button
              key={sec.id}
              type="button"
              onClick={() => onChangeFilters({ ...filters, section: sec.id })}
              className={cn(
                "flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors text-left",
                isSelected
                  ? "bg-primary text-primary-foreground shadow-xs"
                  : "text-ink-muted hover:bg-canvas-2 hover:text-ink",
              )}
            >
              <div className="flex items-center gap-2 min-w-0 truncate">
                <Icon className={cn("h-3.5 w-3.5 shrink-0", isSelected ? "text-primary-foreground" : "text-ink-muted")} />
                <span className="truncate">{sec.label}</span>
              </div>
              <span
                className={cn(
                  "rounded-full px-1.5 py-0.5 text-[10px] font-mono font-semibold shrink-0 ml-1",
                  isSelected ? "bg-white/20 text-white" : "bg-canvas-2 text-ink-muted",
                )}
              >
                {count}
              </span>
            </button>
          );
        })}

        {/* Filter controls */}
        <div className="pt-4 pb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-ink-muted flex items-center gap-1">
          <Filter className="h-3 w-3" />
          <span>Detailed Filters</span>
        </div>

        <div className="space-y-2 px-1">
          {/* Status filter */}
          <div>
            <span className="text-[11px] text-ink-muted mb-1 block">Status</span>
            <Select
              value={filters.status}
              onValueChange={(val) => onChangeFilters({ ...filters, status: val })}
            >
              <SelectTrigger className="h-7 text-xs bg-canvas-2">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="accepted">Accepted</SelectItem>
                <SelectItem value="edited">Edited</SelectItem>
                <SelectItem value="needs_review">Needs Review</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Sensitivity filter */}
          <div>
            <span className="text-[11px] text-ink-muted mb-1 block">Min Sensitivity</span>
            <Select
              value={filters.sensitivity}
              onValueChange={(val) => onChangeFilters({ ...filters, sensitivity: val })}
            >
              <SelectTrigger className="h-7 text-xs bg-canvas-2">
                <SelectValue placeholder="Any Sensitivity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Levels (0-3)</SelectItem>
                <SelectItem value="0">L0 (Public)</SelectItem>
                <SelectItem value="1">L1 (Internal)</SelectItem>
                <SelectItem value="2">L2 (Confidential)</SelectItem>
                <SelectItem value="3">L3 (Restricted)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Confidence filter */}
          <div>
            <span className="text-[11px] text-ink-muted mb-1 block">Confidence Tier</span>
            <Select
              value={filters.confidence}
              onValueChange={(val) => onChangeFilters({ ...filters, confidence: val })}
            >
              <SelectTrigger className="h-7 text-xs bg-canvas-2">
                <SelectValue placeholder="All Confidence" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Scores</SelectItem>
                <SelectItem value="high">High (≥ 80%)</SelectItem>
                <SelectItem value="medium">Medium (50 - 79%)</SelectItem>
                <SelectItem value="low">Low (&lt; 50%)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Bulk Action Footer */}
      <div className="p-3 border-t border-card-border bg-canvas-2">
        <Button
          variant="outline"
          size="sm"
          disabled={bulkEligibleClaims.length === 0}
          onClick={() => setConfirmBulkOpen(true)}
          className="w-full text-xs h-8 gap-1.5 font-medium border-brand hover:bg-brand-soft hover:text-brand-text"
        >
          <CheckCheck className="h-3.5 w-3.5 text-verified" />
          <span>Accept High-Confidence</span>
          <span className="ml-auto rounded-full bg-verified/20 text-verified px-1.5 py-0.5 text-[10px] font-mono">
            {bulkEligibleClaims.length}
          </span>
        </Button>

        <ConfirmDialog
          open={confirmBulkOpen}
          onOpenChange={setConfirmBulkOpen}
          title="Accept High-Confidence Claims"
          description={`Are you sure you want to accept all ${bulkEligibleClaims.length} draft claims with >= 80% confidence and verified evidence in view? This action can be reversed individually if needed.`}
          confirmLabel={`Accept ${bulkEligibleClaims.length} Claims`}
          onConfirm={() => {
            onBulkAcceptHighConfidence();
            setConfirmBulkOpen(false);
          }}
        />
      </div>
    </div>
  );
}
