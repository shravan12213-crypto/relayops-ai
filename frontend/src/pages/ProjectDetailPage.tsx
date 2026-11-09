import * as React from "react";
import {
  FileCode,
  FileText,
  FolderGit2,
  Github,
  MessageSquare,
  Plus,
  RefreshCw,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { CreateHandoverDialog } from "@/components/handover/CreateHandoverDialog";
import { AddSourceWizardDialog } from "@/components/project/AddSourceWizardDialog";
import { RedactionTransparencyPanel } from "@/components/project/RedactionTransparencyPanel";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { RelativeTime } from "@/components/shared/RelativeTime";
import { CardGridSkeleton } from "@/components/shared/Skeletons";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHandovers } from "@/lib/api/handovers";
import { useProject, useProjectSources } from "@/lib/api/projects";
import { useSyncSource } from "@/lib/api/sources";

function getSourceIcon(type: string) {
  switch (type.toLowerCase()) {
    case "github":
      return Github;
    case "jira":
    case "jira_json":
      return FileCode;
    case "slack":
    case "slack_json":
      return MessageSquare;
    case "markdown":
    case "docs":
    default:
      return FileText;
  }
}

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading: projectLoading } = useProject(projectId);
  const {
    data: sources,
    isLoading: sourcesLoading,
    refetch: refetchSources,
  } = useProjectSources(projectId);
  const { data: handovers } = useHandovers(projectId);
  const syncSource = useSyncSource();

  const [addSourceOpen, setAddSourceOpen] = React.useState(false);
  const [createHandoverOpen, setCreateHandoverOpen] = React.useState(false);

  React.useEffect(() => {
    if (project) {
      document.title = `${project.name} — RelayOps`;
    }
  }, [project]);

  if (projectLoading || !project) {
    return (
      <div className="space-y-6">
        <PageHeader title="Loading Project..." />
        <CardGridSkeleton count={3} />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title={project.name}
        description={
          project.description || "Ingested repositories, documents, and active handovers."
        }
        breadcrumbs={[{ label: "Projects", href: "/projects" }, { label: project.name }]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAddSourceOpen(true)}
              className="gap-1.5 text-xs"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Source
            </Button>
            <Button
              size="sm"
              onClick={() => setCreateHandoverOpen(true)}
              className="gap-1.5 text-xs"
            >
              <Sparkles className="h-3.5 w-3.5" />
              New Handover
            </Button>
          </div>
        }
      />

      {/* Sources Grid Panel */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-1.5">
              <FolderGit2 className="h-4 w-4 text-primary" />
              Connected Data Sources
            </h2>
            <p className="text-xs text-muted-foreground">
              Repository feeds, ticket exports, channels, and architecture markdown files.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void refetchSources()}
            className="text-xs text-muted-foreground"
          >
            <RefreshCw className="mr-1.5 h-3 w-3" />
            Refresh
          </Button>
        </div>

        {sourcesLoading ? (
          <CardGridSkeleton count={4} />
        ) : sources && sources.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {sources.map((src) => {
              const Icon = getSourceIcon(src.type);
              const artifactCount = (src.stats?.artifacts_count as number) || 0;
              return (
                <Card key={src.id} className="transition-all hover:border-primary/40">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="rounded-md bg-muted p-1.5 text-foreground">
                          <Icon className="h-4 w-4" />
                        </div>
                        <CardTitle className="text-xs font-semibold truncate max-w-[140px]">
                          {src.name}
                        </CardTitle>
                      </div>
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {src.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3 pt-2">
                    <div className="flex items-baseline justify-between text-xs">
                      <span className="text-muted-foreground">Artifacts:</span>
                      <span className="font-mono font-semibold text-foreground">
                        {artifactCount}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t">
                      <span>Last sync:</span>
                      <RelativeTime date={src.last_synced_at} />
                    </div>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => syncSource.mutate(src.id)}
                      disabled={syncSource.isPending}
                      className="w-full text-xs h-7 gap-1.5"
                    >
                      <RefreshCw className="h-3 w-3" />
                      Sync Now
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={UploadCloud}
            title="No sources configured yet"
            description="Add GitHub repositories, Slack channels, Jira exports, or load the PayFlow demo."
            action={
              <Button size="sm" onClick={() => setAddSourceOpen(true)} className="gap-1.5 text-xs">
                <Plus className="h-3.5 w-3.5" />
                Add Source
              </Button>
            }
          />
        )}
      </section>

      {/* Redaction Transparency Panel */}
      <RedactionTransparencyPanel projectId={project.id} />

      {/* Active Handovers for this project */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-1.5">
          <FileText className="h-4 w-4 text-primary" />
          Active Handovers
        </h2>
        {handovers && handovers.length > 0 ? (
          <div className="space-y-2.5">
            {handovers.map((h) => (
              <Card key={h.id}>
                <CardContent className="flex items-center justify-between p-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-foreground">
                        {h.notes || "Engineering Handover"}
                      </span>
                      <StatusBadge status={h.status} size="sm" />
                    </div>
                    <p className="font-mono text-[11px] text-muted-foreground">
                      ID: {h.id} · Version: v{h.current_version}
                    </p>
                  </div>
                  <Button asChild size="sm" variant="outline" className="text-xs">
                    <Link to={`/handovers/${h.id}/pipeline`}>Pipeline Progress →</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic">
            No handovers initiated for this project yet. Click "New Handover" above to create one.
          </p>
        )}
      </section>

      {/* Modals */}
      <AddSourceWizardDialog
        open={addSourceOpen}
        onOpenChange={setAddSourceOpen}
        projectId={project.id}
      />
      <CreateHandoverDialog
        open={createHandoverOpen}
        onOpenChange={setCreateHandoverOpen}
        projectId={project.id}
      />
    </div>
  );
}
