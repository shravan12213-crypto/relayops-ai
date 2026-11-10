import * as React from "react";
import {
  AlertTriangle,
  BookOpen,
  Calendar,
  FileCheck2,
  FileSignature,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { AuditorView } from "@/components/portal/AuditorView";
import { CopilotDrawer } from "@/components/portal/CopilotDrawer";
import { DayBoard } from "@/components/portal/DayBoard";
import { EditorialSectionsView } from "@/components/portal/EditorialSectionsView";
import { KnownUnknownsTab } from "@/components/portal/KnownUnknownsTab";
import { PortalHeader } from "@/components/portal/PortalHeader";
import {
  RolePreviewSwitcher,
  type PortalRole,
} from "@/components/portal/RolePreviewSwitcher";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/lib/api/auth";
import { useHandover } from "@/lib/api/handovers";
import {
  useHandoverView,
  useReceiptsProgress,
} from "@/lib/api/portal";
import { useUsers } from "@/lib/api/users";

export function HandoverPortalPage() {
  const { handoverId } = useParams<{ handoverId: string }>();
  const { user: currentUser } = useAuth();

  const isLead = currentUser?.role === "lead";

  // Role preview state for lead
  const [previewRole, setPreviewRole] = React.useState<PortalRole>(() => {
    if (currentUser?.role === "contractor") return "contractor";
    if (currentUser?.role === "auditor") return "auditor";
    if (currentUser?.role === "successor") return "junior";
    return "maintainer";
  });

  const [copilotOpen, setCopilotOpen] = React.useState(false);

  const {
    data: handover,
    isLoading: isHandoverLoading,
    error: handoverError,
  } = useHandover(handoverId);

  const { data: users } = useUsers();

  const {
    data: handoverView,
    isLoading: isViewLoading,
    error: viewError,
    refetch: refetchView,
  } = useHandoverView(handoverId, isLead ? previewRole : undefined);

  const { data: receiptsProgress } = useReceiptsProgress(handoverId);

  // Derive human-readable names
  const outgoingName = React.useMemo(() => {
    if (users && handover) {
      const u = users.find((x) => x.id === handover.outgoing_user_id);
      if (u) return u.name;
    }
    return "Aarav Kulkarni";
  }, [users, handover]);

  const leadName = React.useMemo(() => {
    if (users && handover) {
      const u = users.find((x) => x.id === handover.lead_user_id);
      if (u) return u.name;
    }
    return "Meera Patel";
  }, [users, handover]);

  React.useEffect(() => {
    document.title = `${outgoingName} Handover Portal — RelayOps`;
  }, [outgoingName]);

  // Loading Skeleton
  if (isHandoverLoading || isViewLoading) {
    return (
      <div className="space-y-6">
        <div className="rounded-xl border p-6 space-y-4">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-4 w-96" />
          <div className="flex gap-3 pt-2">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-8 w-28" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  // Precondition failed (Awaiting dual sign-off before viewing)
  if (viewError && "status" in viewError && (viewError as { status: number }).status === 400) {
    return (
      <div className="space-y-6">
        <div className="flex items-start gap-3 rounded-xl border border-needs-review bg-warn-soft p-5 text-needs-review dark:text-needs-review">
          <FileSignature className="h-6 w-6 shrink-0 text-needs-review mt-0.5" />
          <div className="space-y-1.5 flex-1">
            <h2 className="text-base font-semibold">Dual Sign-Off Pending</h2>
            <p className="text-xs leading-relaxed text-ink-muted">
              In accordance with Non-negotiable Product Rule #5, a handover document cannot be
              published to the successor portal until <strong>both</strong> the outgoing contributor
              ({outgoingName}) and project lead ({leadName}) sign off on the verified claims.
            </p>
            <div className="pt-2 flex items-center gap-2">
              <Button asChild size="sm" className="text-xs h-8">
                <Link to={`/handovers/${handoverId}/review`}>
                  Open Review Studio to Sign Off
                </Link>
              </Button>
              <Button asChild variant="outline" size="sm" className="text-xs h-8">
                <Link to="/handovers">Back to Handovers</Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // General error
  if (handoverError || viewError || !handoverView) {
    return (
      <ErrorState
        title="Unable to Load Handover Portal"
        message={
          viewError?.message ||
          handoverError?.message ||
          "Could not retrieve the signed handover view. Please verify permissions."
        }
        onRetry={() => refetchView()}
      />
    );
  }

  const effectiveClearance = handoverView.effective_clearance;
  const acknowledgedCount = receiptsProgress?.acknowledged_count ?? 0;
  const totalSectionsCount = receiptsProgress?.total_sections_count ?? 5;
  const progressPct = receiptsProgress?.progress_pct ?? 0;

  return (
    <div className="space-y-6 print:space-y-4">
      {/* 1. Welcome & Trust Strip Header */}
      <PortalHeader
        handoverView={handoverView}
        outgoingName={outgoingName}
        leadName={leadName}
        handoverDate={handover?.due_date}
        acknowledgedCount={acknowledgedCount}
        totalSectionsCount={totalSectionsCount}
        progressPct={progressPct}
        onOpenCopilot={() => setCopilotOpen(true)}
        isLead={isLead}
      />

      {/* 2. Role Preview Switcher (Lead only, preview banner) */}
      <div className="print:hidden">
        <RolePreviewSwitcher
          currentRole={previewRole}
          onRoleChange={setPreviewRole}
          isLead={isLead}
          actualUserRole={currentUser?.role ?? "successor"}
          effectiveClearance={effectiveClearance}
        />
      </div>

      {/* 3. Main Views / Tabs */}
      {previewRole === "auditor" ? (
        // Auditor view directly displays compliance without raw bodies
        <AuditorView
          handoverView={handoverView}
          outgoingName={outgoingName}
          leadName={leadName}
        />
      ) : (
        <Tabs defaultValue="sections" className="space-y-5">
          <TabsList className="bg-canvas-2 p-1 border text-xs print:hidden">
            <TabsTrigger value="sections" className="gap-1.5 text-xs">
              <BookOpen className="h-3.5 w-3.5" />
              Verified Knowledge
            </TabsTrigger>
            <TabsTrigger value="board" className="gap-1.5 text-xs">
              <Calendar className="h-3.5 w-3.5" />
              Day 1-30 Board
            </TabsTrigger>
            <TabsTrigger value="unknowns" className="gap-1.5 text-xs">
              <AlertTriangle className="h-3.5 w-3.5" />
              Known Unknowns ({handoverView.ambiguities.length})
            </TabsTrigger>
            {isLead && (
              <TabsTrigger value="compliance" className="gap-1.5 text-xs">
                <FileCheck2 className="h-3.5 w-3.5" />
                Compliance & Signatures
              </TabsTrigger>
            )}
          </TabsList>

          {/* Tab 1: Editorial Sections View */}
          <TabsContent value="sections">
            <EditorialSectionsView
              handoverView={handoverView}
              receiptsProgress={receiptsProgress}
              viewingRole={previewRole}
            />
          </TabsContent>

          {/* Tab 2: Day 1-30 Execution Board */}
          <TabsContent value="board">
            <DayBoard handoverId={handoverView.handover_id} />
          </TabsContent>

          {/* Tab 3: Known Unknowns */}
          <TabsContent value="unknowns">
            <KnownUnknownsTab
              ambiguities={handoverView.ambiguities}
              handoverId={handoverView.handover_id}
              outgoingName={outgoingName}
            />
          </TabsContent>

          {/* Tab 4: Compliance (Available for Lead in maintainer mode) */}
          {isLead && (
            <TabsContent value="compliance">
              <AuditorView
                handoverView={handoverView}
                outgoingName={outgoingName}
                leadName={leadName}
              />
            </TabsContent>
          )}
        </Tabs>
      )}

      {/* 4. Slide-out Grounded Copilot Drawer */}
      <CopilotDrawer
        open={copilotOpen}
        onOpenChange={setCopilotOpen}
        handoverId={handoverView.handover_id}
        outgoingName={outgoingName}
      />
    </div>
  );
}
