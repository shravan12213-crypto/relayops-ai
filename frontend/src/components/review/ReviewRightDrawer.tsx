import { FileText, AlertCircle, GitCompare, Gauge } from "lucide-react";

import { AmbiguitiesTab } from "@/components/review/AmbiguitiesTab";
import { ConflictsTab } from "@/components/review/ConflictsTab";
import { EvidenceTab } from "@/components/review/EvidenceTab";
import { ScorecardTab } from "@/components/review/ScorecardTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type Ambiguity, type Claim, type EvidenceRef } from "@/lib/api/review";

export type RightTabType = "evidence" | "ambiguities" | "conflicts" | "scorecard";

export interface ReviewRightDrawerProps {
  handoverId: string;
  selectedEvidence: EvidenceRef | null;
  activeTab: RightTabType;
  onTabChange: (tab: RightTabType) => void;
  claims: Claim[];
  ambiguities: Ambiguity[];
  conflictsCount?: number;
  onJumpToClaim?: (claimId: string) => void;
}

export function ReviewRightDrawer({
  handoverId,
  selectedEvidence,
  activeTab,
  onTabChange,
  claims,
  ambiguities,
  conflictsCount = 0,
  onJumpToClaim,
}: ReviewRightDrawerProps) {
  const openAmbiguitiesCount = ambiguities.filter((a) => a.status === "open").length;

  return (
    <div className="flex h-full flex-col bg-canvas/80 overflow-hidden">
      <Tabs
        value={activeTab}
        onValueChange={(val) => onTabChange(val as RightTabType)}
        className="flex h-full flex-col"
      >
        {/* Tab Headers */}
        <div className="border-b border-card-border px-3 pt-2">
          <TabsList className="grid w-full grid-cols-4 bg-canvas-2 p-1">
            {/* Evidence Tab Trigger */}
            <TabsTrigger
              value="evidence"
              className="text-xs gap-1 data-[state=active]:bg-canvas"
            >
              <FileText className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">Evidence</span>
            </TabsTrigger>

            {/* Ambiguities Tab Trigger */}
            <TabsTrigger
              value="ambiguities"
              className="text-xs gap-1 data-[state=active]:bg-canvas"
            >
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">Ledger</span>
              {openAmbiguitiesCount > 0 && (
                <span className="ml-0.5 rounded-full bg-danger-soft text-conflict dark:text-conflict px-1 text-[9px] font-mono font-bold">
                  {openAmbiguitiesCount}
                </span>
              )}
            </TabsTrigger>

            {/* Conflicts Tab Trigger */}
            <TabsTrigger
              value="conflicts"
              className="text-xs gap-1 data-[state=active]:bg-canvas"
            >
              <GitCompare className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">Conflicts</span>
              {conflictsCount > 0 && (
                <span className="ml-0.5 rounded-full bg-warn-soft text-needs-review dark:text-needs-review px-1 text-[9px] font-mono font-bold">
                  {conflictsCount}
                </span>
              )}
            </TabsTrigger>

            {/* Scorecard Tab Trigger */}
            <TabsTrigger
              value="scorecard"
              className="text-xs gap-1 data-[state=active]:bg-canvas"
            >
              <Gauge className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">Scorecard</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Tab Contents */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <TabsContent value="evidence" className="h-full m-0 p-0">
            <EvidenceTab evidence={selectedEvidence} />
          </TabsContent>

          <TabsContent value="ambiguities" className="h-full m-0 p-0">
            <AmbiguitiesTab handoverId={handoverId} />
          </TabsContent>

          <TabsContent value="conflicts" className="h-full m-0 p-0">
            <ConflictsTab handoverId={handoverId} onJumpToClaim={onJumpToClaim} />
          </TabsContent>

          <TabsContent value="scorecard" className="h-full m-0 p-0">
            <ScorecardTab handoverId={handoverId} claims={claims} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
