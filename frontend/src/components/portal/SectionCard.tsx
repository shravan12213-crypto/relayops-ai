import * as React from "react";
import { CheckCircle2, Lock, Sparkles } from "lucide-react";

import { CitationPill } from "@/components/shared/CitationPill";
import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type GlossaryItem,
  type HandoverViewClaim,
} from "@/lib/api/portal";
import { SectionAcknowledgementDialog } from "./SectionAcknowledgementDialog";

interface SectionCardProps {
  sectionKey: string;
  sectionTitle: string;
  claims: HandoverViewClaim[];
  handoverId: string;
  isAcknowledged: boolean;
  acknowledgedAt?: string;
  comprehensionNote?: string | null;
  glossaryItem?: GlossaryItem | null;
}

export function SectionCard({
  sectionKey,
  sectionTitle,
  claims,
  handoverId,
  isAcknowledged,
  acknowledgedAt,
  comprehensionNote,
  glossaryItem,
}: SectionCardProps) {
  const [ackDialogOpen, setAckDialogOpen] = React.useState(false);

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b pb-3.5">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base font-semibold text-foreground">
              {sectionTitle}
            </CardTitle>
            <Badge variant="outline" className="text-[10px]">
              {claims.length} {claims.length === 1 ? "claim" : "claims"}
            </Badge>
          </div>
          {isAcknowledged && acknowledgedAt && (
            <p className="text-[11px] text-verified flex items-center gap-1 font-medium">
              <CheckCircle2 className="h-3 w-3" />
              Acknowledged on {new Date(acknowledgedAt).toLocaleDateString()}
              {comprehensionNote ? ` — "${comprehensionNote}"` : ""}
            </p>
          )}
        </div>

        <div>
          {isAcknowledged ? (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-verified/30 bg-verified/10 px-3 py-1 text-xs font-semibold text-verified">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Read & Understood
            </div>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setAckDialogOpen(true)}
              className="gap-1.5 text-xs border-primary/40 text-primary hover:bg-primary/10"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              I've read and understood
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4 p-4">
        {/* Junior Glossary "Why It Matters" Callout */}
        {glossaryItem && (
          <div className="flex items-start gap-2.5 rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs text-primary-950 dark:text-primary-100">
            <Sparkles className="h-4 w-4 shrink-0 text-primary mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-primary">{glossaryItem.term} — Why It Matters</p>
              <p className="text-muted-foreground leading-relaxed">{glossaryItem.why_it_matters}</p>
            </div>
          </div>
        )}

        {/* Claims List */}
        <div className="space-y-3">
          {claims.map((claim) => {
            // Masked claim placeholder
            if (claim.is_masked) {
              return (
                <div
                  key={claim.id}
                  className="flex items-start gap-3 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-3 text-xs"
                >
                  <Lock className="h-4 w-4 shrink-0 text-muted-foreground mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-medium text-muted-foreground italic">
                      [Restricted Item — Clearance level {claim.sensitivity} required]
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      This item is masked for your viewing clearance. Contact the project lead if
                      access is required.
                    </p>
                  </div>
                </div>
              );
            }

            return (
              <div
                key={claim.id}
                className="space-y-2 rounded-lg border border-border/80 bg-card p-3.5 transition-colors hover:border-primary/30"
              >
                {/* Meta header */}
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-[10px] capitalize">
                      {claim.kind.replace("_", " ")}
                    </Badge>
                    <StatusBadge status={claim.status} size="sm" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground">
                      {Math.round(claim.confidence * 100)}% verified
                    </span>
                    <SensitivityBadge level={claim.sensitivity} />
                  </div>
                </div>

                {/* Claim editorial text */}
                <p className="text-xs text-foreground leading-relaxed font-sans">{claim.text}</p>

                {/* Grounded Citation Pills */}
                {claim.evidence && claim.evidence.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap pt-1">
                    <span className="text-[10px] font-medium text-muted-foreground">Evidence:</span>
                    {claim.evidence.map((ev, i) => (
                      <CitationPill
                        key={`${ev.artifact_id}-${i}`}
                        artifactId={ev.artifact_id}
                        sourceUri={ev.source_uri}
                        snippet={ev.snippet}
                        sensitivity={claim.sensitivity}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>

      <SectionAcknowledgementDialog
        open={ackDialogOpen}
        onOpenChange={setAckDialogOpen}
        handoverId={handoverId}
        section={sectionKey}
        sectionTitle={sectionTitle}
      />
    </Card>
  );
}
