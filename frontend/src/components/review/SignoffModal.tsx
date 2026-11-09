import * as React from "react";
import { CheckCircle2, ShieldCheck, Key, FileSignature, AlertCircle, Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/api/auth";
import {
  useSignoff,
  useSignoffs,
  useVerifyHandover,
  useVersions,
  type Claim,
} from "@/lib/api/review";
import { cn } from "@/lib/utils";

export interface SignoffModalProps {
  handoverId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  claims: Claim[];
  unresolvedHighAmbiguitiesCount: number;
}

export function SignoffModal({
  handoverId,
  open,
  onOpenChange,
  claims,
  unresolvedHighAmbiguitiesCount,
}: SignoffModalProps) {
  const { user } = useAuth();
  const { data: versions = [] } = useVersions(handoverId);
  const { data: signoffs = [] } = useSignoffs(handoverId);
  const { data: verification } = useVerifyHandover(handoverId);
  const signoffMutation = useSignoff(handoverId);

  const [comment, setComment] = React.useState("");
  const [justSigned, setJustSigned] = React.useState(false);

  const latestVersion = versions.length > 0 ? versions[versions.length - 1] : null;
  const draftCount = claims.filter((c) => c.status === "draft").length;

  const isBlocked = draftCount > 0 || unresolvedHighAmbiguitiesCount > 0 || !latestVersion;

  // Check if current user already signed latest version
  const alreadySigned = signoffs.some(
    (s) => s.user_id === user?.id && s.version === latestVersion?.version,
  );

  const outgoingSigned = signoffs.some((s) => s.user_role === "outgoing");
  const leadSigned = signoffs.some((s) => s.user_role === "lead");

  const handleSign = async () => {
    if (!latestVersion) return;
    await signoffMutation.mutateAsync({
      version: latestVersion.version,
      comment: comment.trim() || undefined,
    });
    setComment("");
    setJustSigned(true);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileSignature className="h-4 w-4 text-primary" />
            <span>Dual Cryptographic Sign-Off</span>
          </DialogTitle>
          <DialogDescription className="text-xs">
            A handover cannot be delivered until BOTH the outgoing contributor and the lead sign off.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Version & Hash Banner */}
          {latestVersion ? (
            <div className="rounded-lg border bg-muted/40 p-3 space-y-1 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-foreground">
                  Snapshot Version {latestVersion.version}
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  Hash: {latestVersion.hash.slice(0, 16)}...
                </span>
              </div>
              <p className="text-muted-foreground text-[11px]">
                Cryptographic integrity anchored via SHA-256 state tree.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400">
              No snapshot version created yet. Create a snapshot first to freeze the review.
            </div>
          )}

          {/* Verification Checklist */}
          <div className="rounded-lg border p-3 space-y-2 text-xs">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Pre-flight Sign-off Checklist
            </span>

            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                {draftCount === 0 ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-verified" />
                ) : (
                  <AlertCircle className="h-3.5 w-3.5 text-rose-500" />
                )}
                <span className={cn(draftCount === 0 ? "text-foreground" : "text-rose-600 font-medium")}>
                  {draftCount === 0
                    ? "All claims reviewed (0 drafts remaining)"
                    : `${draftCount} draft claims still require review`}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {unresolvedHighAmbiguitiesCount === 0 ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-verified" />
                ) : (
                  <AlertCircle className="h-3.5 w-3.5 text-rose-500" />
                )}
                <span
                  className={cn(
                    unresolvedHighAmbiguitiesCount === 0
                      ? "text-foreground"
                      : "text-rose-600 font-medium",
                  )}
                >
                  {unresolvedHighAmbiguitiesCount === 0
                    ? "Zero open high-severity ambiguities"
                    : `${unresolvedHighAmbiguitiesCount} open high-severity ambiguities`}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                <span className="text-foreground">
                  Dual authorization required (Outgoing Contributor + Lead)
                </span>
              </div>
            </div>
          </div>

          {/* Current Signers Status Chips */}
          <div className="rounded-lg border bg-card p-3 space-y-2 text-xs">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Signatures Recorded
            </span>

            <div className="grid grid-cols-2 gap-2">
              <div
                className={cn(
                  "rounded-md border p-2 flex items-center justify-between",
                  outgoingSigned
                    ? "border-verified/40 bg-verified/5"
                    : "border-border/60 bg-muted/20",
                )}
              >
                <div>
                  <div className="text-xs font-semibold">Outgoing Contributor</div>
                  <div className="text-[11px] text-muted-foreground">
                    {outgoingSigned ? "Signed & Sealed" : "Pending Signature"}
                  </div>
                </div>
                {outgoingSigned ? (
                  <Check className="h-4 w-4 text-verified" />
                ) : (
                  <Badge variant="outline" className="text-[10px] text-muted-foreground">
                    Pending
                  </Badge>
                )}
              </div>

              <div
                className={cn(
                  "rounded-md border p-2 flex items-center justify-between",
                  leadSigned
                    ? "border-verified/40 bg-verified/5"
                    : "border-border/60 bg-muted/20",
                )}
              >
                <div>
                  <div className="text-xs font-semibold">Project Lead</div>
                  <div className="text-[11px] text-muted-foreground">
                    {leadSigned ? "Signed & Sealed" : "Pending Signature"}
                  </div>
                </div>
                {leadSigned ? (
                  <Check className="h-4 w-4 text-verified" />
                ) : (
                  <Badge variant="outline" className="text-[10px] text-muted-foreground">
                    Pending
                  </Badge>
                )}
              </div>
            </div>

            {/* Verify Chain Status Badge */}
            {verification && (
              <div className="mt-2 flex items-center justify-between pt-2 border-t text-[11px] font-mono text-muted-foreground">
                <span className="flex items-center gap-1 text-verified">
                  <Key className="h-3 w-3" />
                  Chain: {verification.chain_valid ? "VALID" : "TAMPERED"}
                </span>
                <span>
                  Signatures: {verification.signatures_valid ? "VERIFIED" : "INVALID"}
                </span>
              </div>
            )}
          </div>

          {/* Comment input if signing */}
          {!alreadySigned && !isBlocked && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-foreground">
                Signer Endorsement / Comment (Optional)
              </label>
              <Textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                placeholder="e.g., Reviewed all architecture decisions and verified ownership with successor."
                className="text-xs"
              />
            </div>
          )}
          {/* Just Signed Animated Feedback */}
          {justSigned && (
            <div className="flex items-center gap-2.5 rounded-lg border border-verified/40 bg-verified/10 p-3 text-xs text-foreground animate-in zoom-in-95 duration-200">
              <CheckCircle2 className="h-5 w-5 text-verified shrink-0 animate-in zoom-in-75 duration-300" />
              <div>
                <span className="font-semibold text-verified">Signature Cryptographically Anchored!</span>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Your role-authenticated sign-off has been verified and added to the immutable audit chain.
                </p>
              </div>
            </div>
          )}

          {/* Dual Sign-Off Completed Banner */}
          {outgoingSigned && leadSigned && !justSigned && (
            <div className="flex items-center gap-2.5 rounded-lg border border-verified/50 bg-verified/10 p-3 text-xs text-foreground animate-in fade-in-50 duration-200">
              <ShieldCheck className="h-5 w-5 text-verified shrink-0" />
              <div>
                <span className="font-semibold text-verified">Dual Sign-Off Complete!</span>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Both the Outgoing Contributor and Project Lead have signed. This handover snapshot is now sealed and ready for formal delivery.
                </p>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button size="sm" variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>

          {alreadySigned ? (
            <Button size="sm" disabled className="bg-verified text-white text-xs gap-1">
              <Check className="h-3.5 w-3.5" />
              You Have Signed v{latestVersion?.version}
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={isBlocked || signoffMutation.isPending}
              onClick={handleSign}
              className="gap-1.5 text-xs"
            >
              <Key className="h-3.5 w-3.5" />
              I Confirm & Sign
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
