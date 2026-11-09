import * as React from "react";
import {
  FileCode,
  Lock,
  Shield,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { AuditLogTable } from "@/components/governance/AuditLogTable";
import { PolicyMatrixView } from "@/components/governance/PolicyMatrixView";
import { ProjectMembersView } from "@/components/governance/ProjectMembersView";
import { RedactionAndSensitivityView } from "@/components/governance/RedactionAndSensitivityView";
import { PageHeader } from "@/components/shared/PageHeader";
import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/lib/api/auth";

export function GovernancePage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  React.useEffect(() => {
    document.title = "Governance & Audit Trail — RelayOps";
  }, []);

  const isAuthorized = user?.role === "lead" || user?.role === "auditor";

  // Polite 403 Screen for unauthorized roles (outgoing, successor, contractor)
  if (!isAuthorized) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted border border-border text-muted-foreground mb-4">
          <Lock className="h-8 w-8 text-muted-foreground" />
        </div>
        <Badge variant="outline" className="font-mono text-xs mb-2">
          HTTP 403 Forbidden
        </Badge>
        <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
          Governance & Audit Access Restricted
        </h1>
        <p className="mt-2 max-w-md text-xs text-muted-foreground leading-relaxed">
          The cryptographic audit ledger, policy matrices, redaction reports, and team membership controls
          are restricted to users with the <strong className="text-foreground">Project Lead</strong> or{" "}
          <strong className="text-foreground">Auditor</strong> role.
        </p>
        <div className="mt-4 flex items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-xs">
          <span className="text-muted-foreground">Your Active Identity:</span>
          <span className="font-semibold text-foreground">{user?.name}</span>
          <Badge variant="secondary" className="capitalize text-[11px]">
            {user?.role}
          </Badge>
          <SensitivityBadge level={user?.clearance ?? 0} size="sm" />
        </div>
        <div className="mt-6 flex items-center gap-3">
          <Button
            variant="default"
            size="sm"
            onClick={() => navigate("/")}
            className="text-xs"
          >
            Return to Dashboard
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/handovers")}
            className="text-xs"
          >
            View Handovers
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Governance, Audit & Compliance"
        description="Cryptographically linked SHA-256 audit ledger, role-clearance authorization matrix, project secret redaction transparency, and team governance."
      />

      <Tabs defaultValue="audit" className="space-y-4">
        <TabsList className="bg-muted/60 p-1">
          <TabsTrigger value="audit" className="gap-1.5 text-xs">
            <ShieldCheck className="h-3.5 w-3.5 text-verified" />
            Audit Ledger & Integrity
          </TabsTrigger>
          <TabsTrigger value="policy" className="gap-1.5 text-xs">
            <Shield className="h-3.5 w-3.5 text-primary" />
            Policy Matrix
          </TabsTrigger>
          <TabsTrigger value="redaction" className="gap-1.5 text-xs">
            <FileCode className="h-3.5 w-3.5 text-amber-500" />
            Redaction & Sensitivity
          </TabsTrigger>
          <TabsTrigger value="members" className="gap-1.5 text-xs">
            <Users className="h-3.5 w-3.5 text-blue-500" />
            Team Members
          </TabsTrigger>
        </TabsList>

        <TabsContent value="audit" className="space-y-4">
          <AuditLogTable />
        </TabsContent>

        <TabsContent value="policy" className="space-y-4">
          <PolicyMatrixView />
        </TabsContent>

        <TabsContent value="redaction" className="space-y-4">
          <RedactionAndSensitivityView />
        </TabsContent>

        <TabsContent value="members" className="space-y-4">
          <ProjectMembersView />
        </TabsContent>
      </Tabs>
    </div>
  );
}
