import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";

export type JobStatus = "queued" | "pending" | "running" | "done" | "completed" | "failed";

export interface Job {
  id: string;
  project_id: string;
  handover_id: string | null;
  kind?: string;
  stage: string;
  progress: number;
  status: JobStatus;
  error: string | null;
  log?: Record<string, unknown>[];
  details?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: jobId ? queryKeys.jobs.detail(jobId) : ["jobs", "none"],
    queryFn: ({ signal }) => apiGet<Job>(`/api/v1/jobs/${jobId}`, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (
        data &&
        (data.status === "completed" || data.status === "done" || data.status === "failed")
      ) {
        return false;
      }
      return 1500;
    },
  });
}
