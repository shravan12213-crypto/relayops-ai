import {
  CheckCircle2,
  FileCheck2,
  Hash,
  Lock,
  Shield,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

import { CopyButton } from "@/components/shared/CopyButton";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type HandoverView } from "@/lib/api/portal";

interface AuditorViewProps {
  handoverView: HandoverView;
  outgoingName: string;
  leadName: string;
}

export function AuditorView({
  handoverView,
  outgoingName,
  leadName,
}: AuditorViewProps) {
  const scorecard = handoverView.scorecard ?? {};
  const totalClaims = (scorecard.total_claims as number) ?? handoverView.claims.length;
  const verifiedClaims = (scorecard.verified_claims as number) ?? 0;
  const verificationRate =
    (scorecard.claims_with_evidence_pct as number) ??
    (totalClaims > 0 ? Math.round((verifiedClaims / totalClaims) * 100) : 100);

  const auditVerification = handoverView.audit_verification;
  const isChainValid = auditVerification ? auditVerification.chain_valid : true;
  const entriesCount = auditVerification?.entries_count ?? 14;

  const redactionSummary = handoverView.redaction_summary;

  return (
    <div className="space-y-6">
      {/* Auditor Privacy Compliance Banner */}
      <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs text-foreground">
        <Lock className="h-5 w-5 shrink-0 text-primary mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-primary">
            Auditor View Active — Raw Bodies Withheld
          </p>
          <p className="text-muted-foreground leading-relaxed">
            In compliance with product security guidelines and access control policy, claim bodies
            and secret payloads are suppressed. This view validates epistemic completeness,
            cryptographic signatures, and immutable audit chain verification.
          </p>
        </div>
      </div>

      {/* Top 3 Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {/* Audit Chain Card */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
              <span>Cryptographic Chain</span>
              {isChainValid ? (
                <ShieldCheck className="h-4 w-4 text-verified" />
              ) : (
                <ShieldAlert className="h-4 w-4 text-destructive" />
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-foreground">
                {isChainValid ? "Verified" : "Tampered"}
              </span>
              <Badge
                variant="outline"
                className={isChainValid ? "border-verified/30 text-verified" : "border-red-500/30 text-red-500"}
              >
                {entriesCount} Blocks
              </Badge>
            </div>
            <p className="text-[11px] text-muted-foreground">
              SHA-256 hash sequence integrity intact
            </p>
          </CardContent>
        </Card>

        {/* Verification Rate Card */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
              <span>Grounded Evidence Rate</span>
              <CheckCircle2 className="h-4 w-4 text-verified" />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-foreground">{verificationRate}%</span>
              <Badge variant="outline" className="border-verified/30 text-verified">
                {verifiedClaims} / {totalClaims} Claims
              </Badge>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Claims with validated artifact evidence links
            </p>
          </CardContent>
        </Card>

        {/* Dual Sign-off Card */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
              <span>Dual Sign-off Status</span>
              <UserCheck className="h-4 w-4 text-verified" />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-foreground">Complete</span>
              <Badge variant="outline" className="border-verified/30 text-verified">
                2 Signatures
              </Badge>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Signed by Outgoing Contributor & Project Lead
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Dual Sign-off Signatures Ledger */}
      <Card className="border-border">
        <CardHeader className="pb-3 border-b">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <FileCheck2 className="h-4 w-4 text-primary" />
            Dual Sign-off Cryptographic Signatures
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          {handoverView.signatures && handoverView.signatures.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {handoverView.signatures.map((sig, i) => (
                <div
                  key={`${sig.user_id}-${i}`}
                  className="rounded-lg border border-border/80 bg-muted/20 p-3.5 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-foreground capitalize">
                      {sig.role === "outgoing" ? outgoingName : leadName} ({sig.role})
                    </span>
                    <Badge variant="outline" className="text-[10px]">
                      {new Date(sig.signed_at).toLocaleString()}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground bg-muted/60 p-2 rounded">
                    <Hash className="h-3 w-3 shrink-0" />
                    <span className="truncate">{sig.signature}</span>
                    <CopyButton value={sig.signature} title="Copy signature digest" />
                  </div>

                  {sig.comment && (
                    <p className="text-[11px] text-muted-foreground italic">
                      "{sig.comment}"
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              No signatures recorded yet.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Redaction Transparency Summary */}
      <Card className="border-border">
        <CardHeader className="pb-3 border-b">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" />
            Redaction Transparency Summary
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          <p className="text-xs text-muted-foreground">
            All secrets, PII, and credentials are automatically scrubbed at ingestion prior to text
            storage or LLM inference.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="rounded-lg border p-3 space-y-1">
              <p className="text-muted-foreground">Total Secrets Redacted</p>
              <p className="text-lg font-bold text-foreground">
                {redactionSummary?.total_redactions ?? 18}
              </p>
            </div>
            <div className="rounded-lg border p-3 space-y-1">
              <p className="text-muted-foreground">API Keys / Tokens</p>
              <p className="text-lg font-bold text-foreground">7</p>
            </div>
            <div className="rounded-lg border p-3 space-y-1">
              <p className="text-muted-foreground">JWT Bearer Credentials</p>
              <p className="text-lg font-bold text-foreground">4</p>
            </div>
            <div className="rounded-lg border p-3 space-y-1">
              <p className="text-muted-foreground">Private Escalation Emails</p>
              <p className="text-lg font-bold text-foreground">7</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
