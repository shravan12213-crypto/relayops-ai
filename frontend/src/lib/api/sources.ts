import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiGet, apiPost, type ApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import { type Job } from "@/lib/api/jobs";
import { type Source } from "@/lib/api/projects";

export interface DemoLoadResult {
  status: string;
  project_id: string;
  counts: Record<string, number>;
  total_artifacts: number;
}

export interface RedactionRuleSummary {
  rule: string;
  count: number;
  sample_masked: string;
}

export interface RedactionAuditResponse {
  rules: RedactionRuleSummary[];
  total_redactions: number;
}

export interface SourceCreateInput {
  name: string;
  type: string;
  config?: Record<string, unknown>;
}

export function useLoadDemo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (projectId?: string) => {
      const url = projectId ? `/api/v1/projects/${projectId}/demo-load` : "/api/v1/demo/load";
      return apiPost<DemoLoadResult>(url);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.handovers.all });
      toast.success(
        `PayFlow demo loaded successfully (${data.total_artifacts} artifacts ingested)`,
      );
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to load demo dataset");
    },
  });
}

export function useCreateSource(projectId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: SourceCreateInput) =>
      apiPost<Source>(`/api/v1/projects/${projectId}/sources`, input),
    onSuccess: () => {
      if (projectId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.projects.sources(projectId) });
      }
      toast.success("Source configured successfully");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to create source");
    },
  });
}

export function useUploadSourceFile(projectId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiPost<Source>(`/api/v1/projects/${projectId}/sources/upload`, formData);
    },
    onSuccess: (data) => {
      if (projectId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.projects.sources(projectId) });
      }
      toast.success(`Uploaded ${data.name} as data source`);
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to upload file");
    },
  });
}

export function useSyncSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sourceId: string) => apiPost<Job>(`/api/v1/sources/${sourceId}/sync`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      toast.info("Source synchronization started");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to start sync");
    },
  });
}

export function useRedactionAudit(projectId: string | undefined) {
  return useQuery({
    queryKey: projectId ? ["redaction-audit", projectId] : ["redaction-audit", "none"],
    queryFn: ({ signal }) =>
      apiGet<RedactionAuditResponse>(`/api/v1/projects/${projectId}/redaction-audit`, signal),
    enabled: Boolean(projectId),
  });
}

export function useRescanRedactions(projectId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiPost<RedactionAuditResponse>(`/api/v1/projects/${projectId}/redact-rescan`),
    onSuccess: () => {
      if (projectId) {
        queryClient.invalidateQueries({ queryKey: ["redaction-audit", projectId] });
      }
      toast.success("Redaction re-scan complete");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to re-scan redactions");
    },
  });
}
