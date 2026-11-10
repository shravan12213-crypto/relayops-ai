import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiGet, apiPost, type ApiError } from "@/lib/api/client";
import { type Job } from "@/lib/api/jobs";
import { queryKeys } from "@/lib/api/query-keys";

export type HandoverStatus = "draft" | "review" | "in_review" | "signed" | "delivered" | "archived";

export interface Handover {
  id: string;
  project_id: string;
  outgoing_user_id: string;
  successor_user_id: string;
  lead_user_id: string;
  status: HandoverStatus;
  due_date: string | null;
  notes: string;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface HandoverCreateInput {
  outgoing_user_id: string;
  successor_user_id: string;
  lead_user_id: string;
  due_date?: string | null;
  notes?: string;
}

export interface ScorecardMetrics {
  project_id?: string;
  overall_score?: number;
  readiness_score?: number; // 0 - 100
  total_claims?: number;
  verified_claims?: number;
  unverified_claims?: number;
  claims_with_evidence_pct?: number;
  modules_documented_pct?: number;
  open_ambiguities_by_severity?: Record<string, number>;
  contradictions_count?: Record<string, number>;
  conflicts_count?: number;
  ambiguities_count?: number;
  coverage?: Record<string, number>;
  epistemic_confidence_avg?: number;
  authority_distribution?: Record<string, number>;
  summary?: string;
}

export function useHandovers(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.handovers.list(projectId),
    queryFn: async ({ signal }) => {
      const url = projectId ? `/api/v1/projects/${projectId}/handovers` : "/api/v1/handovers";
      const res = await apiGet<Handover[] | { items: Handover[] }>(url, signal);
      return Array.isArray(res) ? res : res.items || [];
    },
  });
}

export function useHandover(handoverId: string | undefined) {
  return useQuery({
    queryKey: handoverId ? queryKeys.handovers.detail(handoverId) : ["handovers", "none"],
    queryFn: ({ signal }) => apiGet<Handover>(`/api/v1/handovers/${handoverId}`, signal),
    enabled: Boolean(handoverId),
  });
}

export function useHandoverScorecard(handoverId: string | undefined) {
  return useQuery({
    queryKey: handoverId ? queryKeys.handovers.scorecard(handoverId) : ["scorecard", "none"],
    queryFn: ({ signal }) =>
      apiGet<ScorecardMetrics>(`/api/v1/handovers/${handoverId}/scorecard`, signal),
    enabled: Boolean(handoverId),
  });
}

export interface GraphNode {
  id: string;
  key: string;
  label: string;
  type: string;
  owner: string;
  commit_share: number;
  bus_factor: number;
  bus_factor_risk?: "high" | "medium" | null;
  undocumented: boolean;
  doc_count: number;
  sensitivity: number;
  claims_count: number;
  open_work_count: number;
  risks_count: number;
  claims: Array<{ id: string; text: string; kind: string; status: string; confidence?: number }>;
  open_work: Array<{ id: string; text: string; kind: string; status: string }>;
  risks: Array<{ id: string; text: string; kind: string; status: string }>;
}

export interface GraphEdge {
  id: string;
  src: string;
  dst: string;
  type: "DEPENDS_ON" | "BLOCKS" | "OWNS" | string;
  confidence: number;
  evidence?: Array<Record<string, unknown>>;
}

export interface HandoverGraph {
  project_id: string;
  handover_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TimelineEvent {
  id: string;
  topic: string;
  label: string;
  text: string;
  type: "decision" | "pr" | "commit" | "adr" | "blocker" | "claim" | "runbook" | string;
  timestamp: string;
  author?: string | null;
  authority: number;
  sensitivity: number;
  status: "active" | "superseded" | "conflict" | string;
  superseded_by?: string | null;
  supersedes?: string | null;
  evidence?: Array<{ artifact_id: string; title?: string; snippet?: string }>;
  source_uri?: string | null;
  source_type?: string | null;
}

export interface TimelineLink {
  id: string;
  src_id: string;
  dst_id: string;
  type: "SUPERSEDES" | "CONFLICT" | string;
}

export interface HandoverTimeline {
  project_id: string;
  handover_id: string;
  topics: string[];
  events: TimelineEvent[];
  links: TimelineLink[];
}

export function useHandoverGraph(handoverId: string | undefined) {
  return useQuery({
    queryKey: handoverId ? queryKeys.handovers.graph(handoverId) : ["graph", "none"],
    queryFn: ({ signal }) =>
      apiGet<HandoverGraph>(`/api/v1/handovers/${handoverId}/graph`, signal),
    enabled: Boolean(handoverId),
  });
}

export function useHandoverTimeline(
  handoverId: string | undefined,
  filters?: { module?: string; from_time?: string; to_time?: string },
) {
  return useQuery({
    queryKey: handoverId
      ? queryKeys.handovers.timeline(handoverId, filters)
      : ["timeline", "none"],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams();
      if (filters?.module && filters.module !== "all") params.set("module", filters.module);
      if (filters?.from_time) params.set("from_time", filters.from_time);
      if (filters?.to_time) params.set("to_time", filters.to_time);

      const qs = params.toString();
      const url = `/api/v1/handovers/${handoverId}/timeline${qs ? `?${qs}` : ""}`;
      return apiGet<HandoverTimeline>(url, signal);
    },
    enabled: Boolean(handoverId),
  });
}

export function useCreateHandover(projectId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: HandoverCreateInput) =>
      apiPost<Handover>(`/api/v1/projects/${projectId}/handovers`, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.handovers.all });
      toast.success("Handover workflow created");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to create handover");
    },
  });
}

export function useRunPipeline() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ handoverId, fromStage }: { handoverId: string; fromStage?: string }) =>
      apiPost<Job>(
        `/api/v1/handovers/${handoverId}/run`,
        fromStage ? { from_stage: fromStage } : {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.handovers.all });
      toast.info("Pipeline execution started");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to start pipeline");
    },
  });
}

export function useRetryPipeline() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ jobId, fromStage }: { jobId: string; fromStage?: string }) =>
      apiPost<Job>(`/api/v1/jobs/${jobId}/retry${fromStage ? `?from_stage=${fromStage}` : ""}`),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      toast.info(`Retrying pipeline from stage: ${data.stage}`);
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to retry pipeline");
    },
  });
}
