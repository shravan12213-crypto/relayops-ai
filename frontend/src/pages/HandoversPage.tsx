import * as React from "react";
import { ArrowRight, FileText, Play, Plus, RefreshCw, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { CreateHandoverDialog } from "@/components/handover/CreateHandoverDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { TableSkeleton } from "@/components/shared/Skeletons";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useHandovers } from "@/lib/api/handovers";
import { useProjects } from "@/lib/api/projects";

export function HandoversPage() {
  const { data: handovers, isLoading, refetch, isRefetching } = useHandovers();
  const { data: projects } = useProjects();
  const [createOpen, setCreateOpen] = React.useState(false);

  const defaultProject = projects?.[0];

  React.useEffect(() => {
    document.title = "Handovers — RelayOps";
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Handovers"
        description="Traceable handover packages, candidate claims, dual sign-offs, and successor onboarding views."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void refetch()}
              disabled={isRefetching}
              className="gap-1.5 text-xs"
            >
              <RefreshCw className={isRefetching ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
              Refresh
            </Button>
            {defaultProject && (
              <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5 text-xs">
                <Plus className="h-3.5 w-3.5" />
                New Handover
              </Button>
            )}
          </div>
        }
      />

      {isLoading ? (
        <TableSkeleton rows={4} cols={5} />
      ) : handovers && handovers.length > 0 ? (
        <div className="space-y-3">
          {handovers.map((h) => (
            <Card key={h.id} className="transition-all hover:border-brand">
              <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-brand-text" />
                    <span className="font-semibold text-xs sm:text-sm text-ink">
                      {h.notes || "Engineering Handover"}
                    </span>
                    <StatusBadge status={h.status} size="sm" />
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-muted font-mono">
                    <span>ID: {h.id}</span>
                    <span>Version: v{h.current_version}</span>
                    {h.due_date && <span>Due: {h.due_date}</span>}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button asChild size="sm" variant="outline" className="text-xs">
                    <Link to={`/handovers/${h.id}/pipeline`}>
                      <Play className="mr-1 h-3 w-3" />
                      Pipeline
                    </Link>
                  </Button>
                  <Button asChild size="sm" variant="outline" className="text-xs">
                    <Link to={`/handovers/${h.id}/portal`}>
                      Portal
                    </Link>
                  </Button>
                  <Button asChild size="sm" className="text-xs">
                    <Link to={`/handovers/${h.id}`}>
                      <span>Inspect Review</span>
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FileText}
          title="No handovers initiated"
          description="Create a handover workflow for an outgoing team member or run the seed pipeline."
          action={
            defaultProject ? (
              <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5 text-xs">
                <Plus className="h-3.5 w-3.5" />
                Create Handover
              </Button>
            ) : (
              <Button asChild size="sm" className="gap-1.5 text-xs">
                <Link to="/projects">
                  <Sparkles className="h-3.5 w-3.5" />
                  Load Demo Project
                </Link>
              </Button>
            )
          }
        />
      )}

      {defaultProject && (
        <CreateHandoverDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          projectId={defaultProject.id}
        />
      )}
    </div>
  );
}
