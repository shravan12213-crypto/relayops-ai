import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiGet, apiPatch, apiPost, type ApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";

export interface Claim {
  id: string;
  created_at: string;
  updated_at: string;
  project_id: string | null;
  handover_id: string | null;
  section: string;
  kind: string;
  text: string;
  status: "draft" | "accepted" | "edited" | "rejected" | "needs_review";
  confidence: number;
  sensitivity: number;
  evidence: EvidenceRef[];
  origin: "llm" | "rule" | "human";
  edited_by: string | null;
  rejected_reason: string | null;
  order_index: number;
  parent_claim_id?: string | null;
}

export interface EvidenceRef {
  artifact_id: string;
  source_uri?: string;
  snippet?: string;
  char_start?: number;
  char_end?: number;
  source_type?: string;
  title?: string;
}

export interface Ambiguity {
  id: string;
  handover_id?: string;
  project_id?: string;
  type: string;
  title: string;
  description?: string;
  severity: "high" | "medium" | "low";
  artifact_ids: string[];
  status: "open" | "resolved" | "waived";
  resolution_note?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConflictItem {
  id: string;
  handover_id: string;
  subject: string;
  title: string;
  description: string;
  status: "unresolved" | "resolved" | "superseded" | string;
  claim_a_id: string;
  claim_a_text: string;
  claim_a_authority: number;
  claim_a_created_at?: string | null;
  claim_b_id: string;
  claim_b_text: string;
  claim_b_authority: number;
  claim_b_created_at?: string | null;
  winner_claim_id?: string | null;
  loser_claim_id?: string | null;
  ambiguity_id?: string | null;
  chosen_resolution?: string | null;
}

export interface HandoverVersion {
  id: string;
  handover_id: string;
  version: number;
  hash: string;
  prev_hash: string;
  snapshot: Record<string, unknown>;
  created_at: string;
  created_by: string | null;
  reason?: string;
}

export interface VersionDiff {
  base_version: number;
  target_version: number;
  claims: {
    added: Claim[];
    removed: Claim[];
    modified: Array<{
      claim_id: string;
      field: string;
      old_value: unknown;
      new_value: unknown;
      word_diff?: {
        added: string[];
        removed: string[];
      };
    }>;
  };
  ambiguities: {
    added: Ambiguity[];
    resolved: Ambiguity[];
  };
}

export interface SignoffRecord {
  id: string;
  handover_id: string;
  user_id: string;
  user_role: string;
  user_name?: string;
  version: number;
  version_hash: string;
  signed_at: string;
  signature: string;
  comment?: string | null;
}

export interface HandoverVerification {
  chain_valid: boolean;
  signatures_valid: boolean;
  status: string;
  details: {
    versions_count: number;
    head_version: number;
    head_hash: string;
    signoffs: SignoffRecord[];
  };
}

export interface ArtifactDetail {
  id: string;
  project_id: string;
  source_id: string;
  kind: string;
  external_id: string;
  source_uri: string;
  title: string;
  body_redacted: string;
  occurred_at: string;
  meta: Record<string, unknown>;
  redaction_count: number;
}

export interface ClaimPatchInput {
  text?: string;
  status?: "draft" | "accepted" | "edited" | "rejected" | "needs_review";
  rejected_reason?: string;
  expected_updated_at?: string;
}

export function useClaims(
  handoverId: string | undefined,
  filters?: {
    section?: string;
    status?: string;
    kind?: string;
    min_sensitivity?: number;
    paged?: boolean;
  },
) {
  return useQuery({
    queryKey: queryKeys.handovers.claims(handoverId || "none", filters),
    queryFn: ({ signal }) => {
      const params = new URLSearchParams();
      if (filters?.section && filters.section !== "all") params.set("section", filters.section);
      if (filters?.status && filters.status !== "all") params.set("status", filters.status);
      if (filters?.kind && filters.kind !== "all") params.set("kind", filters.kind);
      if (filters?.min_sensitivity !== undefined)
        params.set("min_sensitivity", String(filters.min_sensitivity));
      params.set("limit", "150");

      return apiGet<Claim[]>(
        `/api/v1/handovers/${handoverId}/claims?${params.toString()}`,
        signal,
      );
    },
    enabled: Boolean(handoverId),
  });
}

export function usePatchClaim(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      claimId,
      patch,
    }: {
      claimId: string;
      patch: ClaimPatchInput;
    }) => apiPatch<Claim>(`/api/v1/claims/${claimId}`, patch),
    onMutate: async ({ claimId, patch }) => {
      // Optimistic update
      const key = queryKeys.handovers.claims(handoverId || "none");
      await queryClient.cancelQueries({ queryKey: key });
      const previousClaims = queryClient.getQueryData<Claim[]>(key);

      if (previousClaims) {
        queryClient.setQueryData<Claim[]>(
          key,
          previousClaims.map((c) =>
            c.id === claimId
              ? {
                  ...c,
                  ...patch,
                  status: patch.status ?? (patch.text && patch.text !== c.text ? "edited" : c.status),
                  text: patch.text ?? c.text,
                  updated_at: new Date().toISOString(),
                }
              : c,
          ),
        );
      }
      return { previousClaims };
    },
    onError: (error: ApiError, _, context) => {
      if (context?.previousClaims && handoverId) {
        queryClient.setQueryData(
          queryKeys.handovers.claims(handoverId),
          context.previousClaims,
        );
      }
      if (error.status === 409) {
        toast.error("Concurrency conflict: This claim was modified by another reviewer. Please refresh.");
      } else {
        toast.error(error.message || "Failed to update claim");
      }
    },
    onSettled: () => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.claims(handoverId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.scorecard(handoverId) });
      }
    },
  });
}

export function useAmbiguities(handoverId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.handovers.ambiguities(handoverId || "none"),
    queryFn: async ({ signal }) => {
      const res = await apiGet<Ambiguity[] | { items: Ambiguity[] }>(
        `/api/v1/handovers/${handoverId}/ambiguities`,
        signal,
      );
      return Array.isArray(res) ? res : res.items || [];
    },
    enabled: Boolean(handoverId),
  });
}

export function useConflicts(handoverId: string | undefined) {
  return useQuery({
    queryKey: ["conflicts", handoverId || "none"],
    queryFn: ({ signal }) =>
      apiGet<ConflictItem[]>(`/api/v1/handovers/${handoverId}/conflicts`, signal),
    enabled: Boolean(handoverId),
  });
}

export function useResolveAmbiguity(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      ambiguityId,
      resolution_note,
    }: {
      ambiguityId: string;
      resolution_note: string;
    }) =>
      apiPost<Ambiguity>(`/api/v1/ambiguities/${ambiguityId}/resolve`, {
        resolution_note,
      }),
    onSuccess: () => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.ambiguities(handoverId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.scorecard(handoverId) });
      }
      toast.success("Ambiguity marked as resolved");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to resolve ambiguity");
    },
  });
}

export function useWaiveAmbiguity(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      ambiguityId,
      waiver_reason,
    }: {
      ambiguityId: string;
      waiver_reason: string;
    }) =>
      apiPost<Ambiguity>(`/api/v1/ambiguities/${ambiguityId}/waive`, {
        waiver_reason,
      }),
    onSuccess: () => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.ambiguities(handoverId) });
      }
      toast.success("Ambiguity waived by project lead");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to waive ambiguity");
    },
  });
}

export function useVersions(handoverId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.handovers.versions(handoverId || "none"),
    queryFn: ({ signal }) =>
      apiGet<HandoverVersion[]>(`/api/v1/handovers/${handoverId}/versions`, signal),
    enabled: Boolean(handoverId),
  });
}

export function useVersionDiff(
  handoverId: string | undefined,
  v1: number | null,
  v2: number | null,
) {
  return useQuery({
    queryKey: queryKeys.handovers.diff(handoverId || "none", v1 ?? 1, v2 ?? 1),
    queryFn: ({ signal }) =>
      apiGet<VersionDiff>(
        `/api/v1/handovers/${handoverId}/diff?v1=${v1}&v2=${v2}`,
        signal,
      ),
    enabled: Boolean(handoverId && v1 !== null && v2 !== null && v1 !== v2),
  });
}

export function useCreateSnapshot(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (reason?: string) =>
      apiPost<HandoverVersion>(`/api/v1/handovers/${handoverId}/snapshot`, { reason }),
    onSuccess: (data) => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.versions(handoverId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.detail(handoverId) });
      }
      toast.success(`Frozen cryptographic snapshot v${data.version}`);
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to create snapshot");
    },
  });
}

export function useSignoffs(handoverId: string | undefined) {
  return useQuery({
    queryKey: ["signoffs", handoverId || "none"],
    queryFn: ({ signal }) =>
      apiGet<SignoffRecord[]>(`/api/v1/handovers/${handoverId}/signoffs`, signal),
    enabled: Boolean(handoverId),
  });
}

export function useSignoff(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { version: number; comment?: string }) =>
      apiPost<{ both_signed: boolean; handover_status: string }>(
        `/api/v1/handovers/${handoverId}/signoff`,
        payload,
      ),
    onSuccess: (data) => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: ["signoffs", handoverId] });
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.detail(handoverId) });
      }
      if (data.both_signed) {
        toast.success("Dual sign-off complete! Handover is now signed and sealed.");
      } else {
        toast.success("Your sign-off signature was cryptographically verified and recorded.");
      }
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to execute sign-off");
    },
  });
}

export function useVerifyHandover(handoverId: string | undefined) {
  return useQuery({
    queryKey: ["verify-handover", handoverId || "none"],
    queryFn: ({ signal }) =>
      apiGet<HandoverVerification>(`/api/v1/handovers/${handoverId}/verify`, signal),
    enabled: Boolean(handoverId),
  });
}

export function useArtifact(artifactId: string | undefined) {
  return useQuery({
    queryKey: ["artifact", artifactId || "none"],
    queryFn: ({ signal }) =>
      apiGet<ArtifactDetail>(`/api/v1/artifacts/${artifactId}`, signal),
    enabled: Boolean(artifactId),
    staleTime: 5 * 60 * 1000, // cache for 5 minutes (< 100ms opens from cache)
  });
}
