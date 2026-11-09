import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";

export interface Project {
  id: string;
  name: string;
  description: string;
  default_branch: string;
  created_at: string;
  updated_at: string;
}

export interface Source {
  id: string;
  project_id: string;
  name: string;
  type: string;
  status: string;
  last_synced_at: string | null;
  stats: Record<string, unknown>;
  created_at: string;
}

export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: ({ signal }) => apiGet<Project[]>("/api/v1/projects", signal),
  });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: projectId ? queryKeys.projects.detail(projectId) : ["projects", "none"],
    queryFn: ({ signal }) => apiGet<Project>(`/api/v1/projects/${projectId}`, signal),
    enabled: Boolean(projectId),
  });
}

export function useProjectSources(projectId: string | undefined) {
  return useQuery({
    queryKey: projectId ? queryKeys.projects.sources(projectId) : ["sources", "none"],
    queryFn: ({ signal }) => apiGet<Source[]>(`/api/v1/projects/${projectId}/sources`, signal),
    enabled: Boolean(projectId),
  });
}
