import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  GitBranch,
  HelpCircle,
  MessageSquare,
  Search,
} from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { type HandoverViewAmbiguity } from "@/lib/api/portal";
import { AskQuestionDialog } from "./AskQuestionDialog";

interface KnownUnknownsTabProps {
  ambiguities: HandoverViewAmbiguity[];
  handoverId: string;
  outgoingName: string;
}

const TYPE_CONFIG: Record<string, { label: string; icon: typeof AlertTriangle; color: string }> = {
  conflict: {
    label: "Contradiction",
    icon: AlertTriangle,
    color: "border-red-500/30 text-red-500 bg-red-500/10",
  },
  missing_doc: {
    label: "Missing Documentation",
    icon: HelpCircle,
    color: "border-amber-500/30 text-amber-500 bg-amber-500/10",
  },
  unclosed_thread: {
    label: "Unclosed Discussion",
    icon: MessageSquare,
    color: "border-blue-500/30 text-blue-500 bg-blue-500/10",
  },
  orphan_branch: {
    label: "Orphan Branch",
    icon: GitBranch,
    color: "border-purple-500/30 text-purple-500 bg-purple-500/10",
  },
  open_question: {
    label: "Open Inquiry",
    icon: HelpCircle,
    color: "border-emerald-500/30 text-emerald-500 bg-emerald-500/10",
  },
  low_evidence: {
    label: "Low Evidence",
    icon: AlertTriangle,
    color: "border-orange-500/30 text-orange-500 bg-orange-500/10",
  },
};

export function KnownUnknownsTab({
  ambiguities,
  handoverId,
  outgoingName,
}: KnownUnknownsTabProps) {
  const [search, setSearch] = React.useState("");
  const [selectedAmbiguity, setSelectedAmbiguity] = React.useState<HandoverViewAmbiguity | null>(null);
  const [askDialogOpen, setAskDialogOpen] = React.useState(false);

  const filteredAmbiguities = React.useMemo(() => {
    if (!search.trim()) return ambiguities;
    const q = search.toLowerCase();
    return ambiguities.filter(
      (a) =>
        a.title.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.type.toLowerCase().includes(q),
    );
  }, [ambiguities, search]);

  const handleAsk = (amb: HandoverViewAmbiguity) => {
    setSelectedAmbiguity(amb);
    setAskDialogOpen(true);
  };

  return (
    <div className="space-y-4">
      {/* Search and header info */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-needs-review" />
            Known Unknowns & Ambiguity Ledger
          </h2>
          <p className="text-xs text-muted-foreground">
            Unresolved discrepancies, unclosed threads, and unverified assumptions. We never smooth over gaps.
          </p>
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Filter ambiguities..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 text-xs h-8"
          />
        </div>
      </div>

      {/* Ambiguity Cards */}
      {filteredAmbiguities.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="No Open Ambiguities Found"
          description={
            search ? "No ambiguities match your search query." : "All tracked ambiguities in this handover have been resolved."
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredAmbiguities.map((amb) => {
            const conf = TYPE_CONFIG[amb.type] ?? {
              label: amb.type.replace("_", " "),
              icon: AlertTriangle,
              color: "border-border text-muted-foreground bg-muted",
            };
            const Icon = conf.icon;
            const isOpen = amb.status === "open";

            return (
              <Card key={amb.id} className="border-border shadow-xs hover:border-primary/30 transition-all">
                <CardHeader className="p-4 pb-2">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold ${conf.color}`}>
                        <Icon className="h-3 w-3" />
                        {conf.label}
                      </span>
                      <Badge
                        variant="outline"
                        className={`text-[9px] uppercase font-semibold ${
                          amb.severity === "high"
                            ? "border-red-500/30 text-red-500 bg-red-500/10"
                            : amb.severity === "med"
                              ? "border-amber-500/30 text-amber-500 bg-amber-500/10"
                              : "border-blue-500/30 text-blue-500 bg-blue-500/10"
                        }`}
                      >
                        {amb.severity} severity
                      </Badge>
                      <Badge variant="secondary" className="text-[9px] capitalize">
                        {amb.status}
                      </Badge>
                    </div>

                    {isOpen && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleAsk(amb)}
                        className="gap-1.5 text-xs h-7 border-primary/40 text-primary hover:bg-primary/10 self-start sm:self-auto"
                      >
                        <HelpCircle className="h-3.5 w-3.5" />
                        Ask {outgoingName.split(" ")[0]}
                      </Button>
                    )}
                  </div>
                  <CardTitle className="text-sm font-semibold text-foreground pt-1.5">
                    {amb.title}
                  </CardTitle>
                </CardHeader>

                <CardContent className="p-4 pt-0 space-y-2.5">
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {amb.description}
                  </p>

                  {/* Resolution Note if resolved */}
                  {amb.resolution_note && (
                    <div className="rounded-lg border border-verified/30 bg-verified/10 p-2.5 text-xs text-foreground">
                      <p className="font-semibold text-verified flex items-center gap-1.5">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Resolution Note:
                      </p>
                      <p className="text-muted-foreground pt-0.5">{amb.resolution_note}</p>
                    </div>
                  )}

                  {/* Artifact references */}
                  {amb.artifact_ids && amb.artifact_ids.length > 0 && (
                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground pt-1">
                      <span>Referenced artifacts:</span>
                      <span className="font-mono text-[10px] text-foreground">
                        {amb.artifact_ids.join(", ")}
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Ask Question Dialog */}
      {selectedAmbiguity && (
        <AskQuestionDialog
          open={askDialogOpen}
          onOpenChange={setAskDialogOpen}
          handoverId={handoverId}
          outgoingName={outgoingName}
          initialTitle={`Clarification: ${selectedAmbiguity.title}`}
          initialQuestion={`Regarding ambiguity "${selectedAmbiguity.title}":\n\n${selectedAmbiguity.description}\n\nCould you please clarify the expected resolution?`}
          ambiguityId={selectedAmbiguity.id}
          artifactIds={selectedAmbiguity.artifact_ids}
        />
      )}
    </div>
  );
}
