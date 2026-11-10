import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api/client";

export interface AuditLogItem {
  seq: number;
  created_at: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  payload: Record<string, unknown>;
  hash: string;
}

export interface AuditLogsPaginated {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AuditChainVerifyResponse {
  valid: boolean;
  entries_count: number;
  tampered_seq: number | null;
  error: string | null;
}

export interface AuditLogFilterParams {
  actor_id?: string;
  action?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}

const DEFAULT_AUDIT_PAGE_SIZE = 25;

/**
 * The audit endpoint returns a bare list unless `paged=true` is requested, and it
 * does not send a `pages` count. Normalise both shapes so the table always gets a
 * complete envelope and renders its empty state instead of throwing on undefined.
 */
function toPaginatedAuditLogs(raw: unknown, fallbackPageSize: number): AuditLogsPaginated {
  if (Array.isArray(raw)) {
    const items = raw as AuditLogItem[];
    const size = items.length || fallbackPageSize;
    return {
      items,
      total: items.length,
      page: 1,
      page_size: size,
      pages: Math.max(1, Math.ceil(items.length / size)),
    };
  }

  const data = (raw ?? {}) as Partial<AuditLogsPaginated>;
  const items = Array.isArray(data.items) ? data.items : [];
  const total = typeof data.total === "number" ? data.total : items.length;
  const pageSize =
    typeof data.page_size === "number" && data.page_size > 0 ? data.page_size : fallbackPageSize;
  const page = typeof data.page === "number" && data.page > 0 ? data.page : 1;
  const pages =
    typeof data.pages === "number" && data.pages > 0
      ? data.pages
      : Math.max(1, Math.ceil(total / pageSize));

  return { items, total, page, page_size: pageSize, pages };
}

export function useGovernanceAuditLogs(params: AuditLogFilterParams = {}) {
  const queryParams = new URLSearchParams();
  if (params.actor_id) queryParams.set("actor_id", params.actor_id);
  if (params.action) queryParams.set("action", params.action);
  if (params.from_date) queryParams.set("from_date", params.from_date);
  if (params.to_date) queryParams.set("to_date", params.to_date);
  if (params.page) queryParams.set("page", params.page.toString());
  if (params.page_size) queryParams.set("page_size", params.page_size.toString());
  queryParams.set("paged", "true");

  const queryString = queryParams.toString();
  const url = `/api/v1/audit/logs${queryString ? `?${queryString}` : ""}`;
  const pageSize = params.page_size ?? DEFAULT_AUDIT_PAGE_SIZE;

  return useQuery({
    queryKey: ["governance", "audit-logs", params],
    queryFn: ({ signal }) => apiGet<AuditLogsPaginated | AuditLogItem[]>(url, signal),
    select: (raw) => toPaginatedAuditLogs(raw, pageSize),
  });
}

export function useVerifyAuditChain() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<AuditChainVerifyResponse>("/api/v1/audit/verify-chain"),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["governance", "audit-logs"] });
      if (data.valid) {
        toast.success(`Audit chain verified: all ${data.entries_count} entries cryptographic integrity valid.`);
      } else {
        toast.error(`Audit chain compromised! Tampered sequence: #${data.tampered_seq}`);
      }
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to verify audit chain");
    },
  });
}

export interface PolicyMatrixRule {
  role: string;
  clearance: number;
  can_view_unverified: boolean;
  can_view_conflicts: boolean;
  can_view_ambiguities: boolean;
  can_view_credentials: boolean;
  can_export: boolean;
  can_signoff: boolean;
  max_claim_sensitivity: number;
  description: string;
}

export interface PolicyMatrixResponse {
  roles: string[];
  clearance_levels: number[];
  rules: PolicyMatrixRule[];
}

export function usePolicyMatrix() {
  return useQuery({
    queryKey: ["governance", "policy-matrix"],
    queryFn: ({ signal }) => apiGet<PolicyMatrixResponse>("/api/v1/policy", signal),
    staleTime: 60_000,
  });
}

export interface SensitivityBucket {
  level: number;
  name: string;
  artifacts_count: number;
  claims_count: number;
  percentage: number;
}

export interface SensitivityDistributionResponse {
  project_id: string;
  total_artifacts: number;
  total_claims: number;
  levels: SensitivityBucket[];
}

export function useSensitivityDistribution(projectId: string | undefined) {
  return useQuery({
    queryKey: ["governance", "sensitivity", projectId],
    queryFn: ({ signal }) =>
      apiGet<SensitivityDistributionResponse>(
        `/api/v1/projects/${projectId}/sensitivity-distribution`,
        signal
      ),
    enabled: !!projectId,
  });
}

export interface ProjectMember {
  user_id: string;
  name: string;
  email: string;
  role: string;
  clearance: number;
  joined_at: string;
}

export function useProjectMembers(projectId: string | undefined) {
  return useQuery({
    queryKey: ["governance", "members", projectId],
    queryFn: ({ signal }) =>
      apiGet<ProjectMember[]>(`/api/v1/projects/${projectId}/members`, signal),
    enabled: !!projectId,
  });
}

export function useAddProjectMember(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { user_id: string; role: string; clearance: number }) =>
      apiPost<ProjectMember>(`/api/v1/projects/${projectId}/members`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["governance", "members", projectId] });
      toast.success("Member added to project");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to add member");
    },
  });
}

export function useUpdateProjectMember(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      userId,
      role,
      clearance,
    }: {
      userId: string;
      role?: string;
      clearance?: number;
    }) =>
      apiPatch<ProjectMember>(`/api/v1/projects/${projectId}/members/${userId}`, {
        role,
        clearance,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["governance", "members", projectId] });
      toast.success("Member updated");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to update member");
    },
  });
}

export function useRemoveProjectMember(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      apiDelete<{ status: string; user_id: string }>(
        `/api/v1/projects/${projectId}/members/${userId}`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["governance", "members", projectId] });
      toast.success("Member removed from project");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to remove member");
    },
  });
}

export interface SystemStatusResponse {
  llm_mode: string;
  llm_provider: string;
  llm_model: string;
  environment: string;
  database: string;
  counts: Record<string, number>;
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["governance", "system-status"],
    queryFn: ({ signal }) => apiGet<SystemStatusResponse>("/api/v1/system/status", signal),
    staleTime: 30_000,
  });
}

export interface ResetDemoResponse {
  status: string;
  message: string;
  reseeded_at: string;
}

export function useResetDemoData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<ResetDemoResponse>("/api/v1/system/reset-demo"),
    onSuccess: (data) => {
      queryClient.invalidateQueries();
      toast.success(data.message || "Demo dataset reset successfully");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to reset demo dataset");
    },
  });
}
