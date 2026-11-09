import * as React from "react";
import { BookOpen, Search } from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  type HandoverView,
  type ReceiptsProgress,
} from "@/lib/api/portal";
import { SectionCard } from "./SectionCard";

interface EditorialSectionsViewProps {
  handoverView: HandoverView;
  receiptsProgress?: ReceiptsProgress;
  viewingRole: string;
}

const SECTION_LABELS: Record<string, string> = {
  architecture: "Architecture Decisions",
  ownership: "Ownership & Code Distribution",
  blocker: "Blockers & Partner Dependencies",
  acquirercorp_blocker: "Partner Access & Sandboxes",
  runbook: "Runbooks & Operational Procedures",
  risk: "Risks & Epistemic Warnings",
  dependency: "Infrastructure & Package Dependencies",
  contact: "Vendor & Internal Escalation Contacts",
  open_work: "Open Work & Feature PRs",
  credential_ref: "Credentials & Vault Keys",
  webhook: "Payment Webhooks & Retries",
  database: "Ledger Storage & ACID Guarantees",
  session_caching: "Session Caching & Gateway Auth",
};

export function EditorialSectionsView({
  handoverView,
  receiptsProgress,
  viewingRole,
}: EditorialSectionsViewProps) {
  const [searchQuery, setSearchQuery] = React.useState("");
  const { claims, glossary } = handoverView;

  // Group claims by section
  const sectionsMap = React.useMemo(() => {
    const map = new Map<string, typeof claims>();
    for (const c of claims) {
      const s = c.section || "general";
      if (!map.has(s)) {
        map.set(s, []);
      }
      map.get(s)!.push(c);
    }
    return map;
  }, [claims]);

  // Build glossary lookup if present
  const glossaryMap = React.useMemo(() => {
    const map = new Map<string, { term: string; why_it_matters: string }>();
    if (glossary) {
      for (const g of glossary) {
        // match by lowercase prefix or term
        map.set(g.term.toLowerCase(), g);
      }
    }
    return map;
  }, [glossary]);

  // Receipts status lookup
  const acknowledgedSet = React.useMemo(() => {
    return new Set(receiptsProgress?.acknowledged_sections ?? []);
  }, [receiptsProgress]);

  const receiptsBySection = React.useMemo(() => {
    const map = new Map<string, { acknowledged_at: string; comprehension_note?: string | null }>();
    if (receiptsProgress?.receipts) {
      for (const r of receiptsProgress.receipts) {
        map.set(r.section, r);
      }
    }
    return map;
  }, [receiptsProgress]);

  const sectionsList = Array.from(sectionsMap.entries());

  // Search filter
  const filteredSections = React.useMemo(() => {
    if (!searchQuery.trim()) return sectionsList;
    const q = searchQuery.toLowerCase();
    return sectionsList
      .map(([sKey, claims]) => {
        const matchesSection = (SECTION_LABELS[sKey] ?? sKey).toLowerCase().includes(q);
        const filteredClaims = claims.filter(
          (c) =>
            c.text.toLowerCase().includes(q) ||
            c.kind.toLowerCase().includes(q) ||
            (c.evidence ?? []).some((e) => (e.artifact_id || "").toLowerCase().includes(q)),
        );
        if (matchesSection) return [sKey, claims] as const;
        return [sKey, filteredClaims] as const;
      })
      .filter(([, claims]) => claims.length > 0);
  }, [sectionsList, searchQuery]);

  const totalSections = sectionsList.length;
  const acknowledgedCount = sectionsList.filter(([sKey]) => acknowledgedSet.has(sKey)).length;
  const progressPct = totalSections > 0 ? (acknowledgedCount / totalSections) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Top Filter & Progress Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-xl border bg-card/60 p-4">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search claims and sections..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 text-xs"
          />
        </div>

        <div className="flex items-center gap-3 w-full sm:w-72">
          <div className="flex-1 space-y-1">
            <div className="flex justify-between text-[11px] text-muted-foreground">
              <span>Section Reading Progress</span>
              <span className="font-semibold text-foreground">
                {acknowledgedCount} / {totalSections}
              </span>
            </div>
            <Progress value={progressPct} className="h-1.5" />
          </div>
        </div>
      </div>

      {/* Sections Cards */}
      {filteredSections.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No Matching Claims"
          description={`No verified claims found matching "${searchQuery}".`}
          action={
            <Button size="sm" variant="outline" onClick={() => setSearchQuery("")} className="text-xs">
              Clear Search
            </Button>
          }
        />
      ) : (
        <div className="space-y-5">
          {filteredSections.map(([sKey, claims]) => {
            const label = SECTION_LABELS[sKey] ?? sKey.replace("_", " ");
            const isAck = acknowledgedSet.has(sKey);
            const receipt = receiptsBySection.get(sKey);
            // Check for glossary item match
            const glossary =
              viewingRole === "junior" || viewingRole === "successor"
                ? Array.from(glossaryMap.values()).find(
                    (g) =>
                      g.term.toLowerCase().includes(sKey.toLowerCase()) ||
                      sKey.toLowerCase().includes(g.term.toLowerCase().slice(0, 5)),
                  ) ?? null
                : null;

            return (
              <SectionCard
                key={sKey}
                sectionKey={sKey}
                sectionTitle={label}
                claims={claims}
                handoverId={handoverView.handover_id}
                isAcknowledged={isAck}
                acknowledgedAt={receipt?.acknowledged_at}
                comprehensionNote={receipt?.comprehension_note}
                glossaryItem={glossary}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
