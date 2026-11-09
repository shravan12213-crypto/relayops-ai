import * as React from "react";
import { FolderGit2, Loader2, Plus, RefreshCw, Sparkles, UploadCloud } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { AddSourceWizardDialog } from "@/components/project/AddSourceWizardDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { TableSkeleton } from "@/components/shared/Skeletons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProjects } from "@/lib/api/projects";
import { useLoadDemo } from "@/lib/api/sources";

export function ProjectsPage() {
  const { data: projects, isLoading, refetch, isRefetching } = useProjects();
  const loadDemo = useLoadDemo();
  const navigate = useNavigate();

  const [addSourceOpen, setAddSourceOpen] = React.useState(false);
  const selectedProject = projects?.[0];

  React.useEffect(() => {
    document.title = "Projects & Ingest — RelayOps";
  }, []);

  const handleLoadDemo = async () => {
    try {
      const res = await loadDemo.mutateAsync();
      navigate(`/projects/${res.project_id}`);
    } catch {
      // Handled by toast
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Projects & Ingestion Gateway"
        description="Connected data sources, artifact ingestion pipelines, and automated redaction audits."
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
            <Button
              variant="outline"
              size="sm"
              onClick={handleLoadDemo}
              disabled={loadDemo.isPending}
              className="gap-1.5 text-xs text-primary"
            >
              {loadDemo.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              Load PayFlow Demo
            </Button>
            {selectedProject && (
              <Button size="sm" onClick={() => setAddSourceOpen(true)} className="gap-1.5 text-xs">
                <Plus className="h-3.5 w-3.5" />
                Add Source
              </Button>
            )}
          </div>
        }
      />

      {isLoading ? (
        <TableSkeleton rows={4} cols={4} />
      ) : projects && projects.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Card key={project.id} className="transition-all hover:border-primary/40">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FolderGit2 className="h-4 w-4 text-primary" />
                    <CardTitle className="text-sm font-semibold">{project.name}</CardTitle>
                  </div>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {project.default_branch}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {project.description || "Active engineering project with integrated sources."}
                </p>
                <div className="flex items-center justify-between pt-2 text-[11px] text-muted-foreground border-t">
                  <span className="font-mono">{project.id}</span>
                  <Button asChild variant="ghost" size="sm" className="h-7 text-xs text-primary">
                    <Link to={`/projects/${project.id}`}>Configure Sources →</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FolderGit2}
          title="No projects configured"
          description="Load the PayFlow synthetic demo dataset or connect GitHub/Jira/Slack sources to begin."
          action={
            <Button
              size="sm"
              onClick={handleLoadDemo}
              disabled={loadDemo.isPending}
              className="gap-1.5 text-xs"
            >
              {loadDemo.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <UploadCloud className="h-3.5 w-3.5" />
              )}
              Load PayFlow Demo
            </Button>
          }
        />
      )}

      {selectedProject && (
        <AddSourceWizardDialog
          open={addSourceOpen}
          onOpenChange={setAddSourceOpen}
          projectId={selectedProject.id}
        />
      )}
    </div>
  );
}
