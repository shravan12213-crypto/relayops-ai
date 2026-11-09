import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiGet, apiPatch, apiPost, type ApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";

// ============================================================================
// Types & Interfaces
// ============================================================================

export interface HandoverViewClaim {
  id: string;
  section: string;
  kind: string;
  text: string;
  status: string;
  confidence: number;
  sensitivity: number;
  origin: string;
  evidence?: Array<{
    artifact_id: string;
    source_uri?: string;
    snippet?: string;
    char_start?: number;
    char_end?: number;
  }>;
  is_masked?: boolean;
  mask_reason?: string;
  superseded_by?: string;
  supersedes?: string;
  audit_mode?: boolean;
}

export interface HandoverViewAmbiguity {
  id: string;
  type: string;
  severity: "low" | "med" | "high" | string;
  title: string;
  description: string;
  artifact_ids?: string[];
  status: "open" | "resolved" | "waived" | string;
  resolution_note?: string;
}

export interface HandoverViewPlanItem {
  id: string;
  day_bucket: string;
  title: string;
  description: string;
  priority: string;
  status: string;
  assignee?: string;
  claim_ids?: string[];
}

export interface HandoverSignature {
  user_id: string;
  role: string;
  signed_at: string;
  signature: string;
  comment: string;
}

export interface AuditVerification {
  chain_valid: boolean;
  entries_count: number;
  tampered_index?: number | null;
  latest_hash?: string;
}

export interface GlossaryItem {
  term: string;
  why_it_matters: string;
}

export interface RedactionSummary {
  total_redactions: number;
  rules: Array<{
    rule: string;
    count: number;
    sample_masked: string;
  }>;
}

export interface HandoverView {
  handover_id: string;
  project_id: string;
  version: number;
  hash: string;
  viewing_role: string;
  effective_clearance: number;
  status: string;
  claims: HandoverViewClaim[];
  ambiguities: HandoverViewAmbiguity[];
  plan_items: HandoverViewPlanItem[];
  scorecard: Record<string, unknown>;
  glossary?: GlossaryItem[] | null;
  signatures: HandoverSignature[];
  audit_verification?: AuditVerification | null;
  redaction_summary?: RedactionSummary | null;
}

export interface LinkedClaimSummary {
  id: string;
  text: string;
  section: string;
  status: string;
  kind: string;
}

export interface PlanItemWithClaims {
  id: string;
  created_at: string;
  updated_at: string;
  handover_id: string;
  day_bucket: "d1_7" | "d8_14" | "d15_30" | string;
  title: string;
  description: string;
  priority: "high" | "med" | "low" | string;
  claim_ids: string[];
  status: "todo" | "doing" | "done" | string;
  assignee?: string | null;
  linked_claims: LinkedClaimSummary[];
}

export interface PlanItemCreateInput {
  day_bucket?: string;
  title: string;
  description?: string;
  priority?: string;
  claim_ids?: string[];
  assignee?: string;
}

export interface PlanItemUpdateInput {
  item_id?: string;
  day_bucket?: string;
  status?: string;
  assignee?: string;
  title?: string;
  description?: string;
  priority?: string;
}

export interface ReceiptsProgress {
  handover_id: string;
  total_sections: string[];
  acknowledged_sections: string[];
  total_sections_count: number;
  acknowledged_count: number;
  progress_pct: number;
  receipts: Array<{
    id: string;
    section: string;
    acknowledged_at: string;
    comprehension_note?: string | null;
    user_id: string;
  }>;
}

export interface ReceiptInput {
  section: string;
  comprehension_note?: string;
}

export interface CopilotCitation {
  id: string;
  snippet: string;
}

export interface CopilotChatResponse {
  session_id: string;
  message_id: string;
  answer: string;
  citations: CopilotCitation[];
  can_answer: boolean;
  refused: boolean;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Array<{ id: string; snippet?: string }>;
  refused: boolean;
  feedback?: "up" | "down" | null;
  created_at: string;
}

export interface OpenQuestionInput {
  title: string;
  question: string;
  ambiguity_id?: string;
  artifact_ids?: string[];
}

// ============================================================================
// TanStack Query Hooks
// ============================================================================

export function useHandoverView(handoverId: string | undefined, role?: string) {
  return useQuery({
    queryKey: handoverId ? queryKeys.handovers.view(handoverId, role) : ["view", "none"],
    queryFn: ({ signal }) => {
      const url = role
        ? `/api/v1/handovers/${handoverId}/view?as=${encodeURIComponent(role)}`
        : `/api/v1/handovers/${handoverId}/view`;
      return apiGet<HandoverView>(url, signal);
    },
    enabled: Boolean(handoverId),
    retry: 1,
  });
}

export function useDeliverHandover() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (handoverId: string) =>
      apiPost<{ handover_id: string; status: string; delivered_at: string; notification: string }>(
        `/api/v1/handovers/${handoverId}/deliver`,
      ),
    onSuccess: (_, handoverId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.handovers.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.handovers.view(handoverId) });
      toast.success("Handover successfully delivered to successor!");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to deliver handover");
    },
  });
}

export function usePlanItems(handoverId: string | undefined) {
  return useQuery({
    queryKey: handoverId ? queryKeys.handovers.plan(handoverId) : ["plan", "none"],
    queryFn: ({ signal }) =>
      apiGet<PlanItemWithClaims[]>(`/api/v1/handovers/${handoverId}/plan`, signal),
    enabled: Boolean(handoverId),
  });
}

export function useCreatePlanItem(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: PlanItemCreateInput) =>
      apiPost<PlanItemWithClaims>(`/api/v1/handovers/${handoverId}/plan`, input),
    onSuccess: () => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.plan(handoverId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.view(handoverId) });
      }
      toast.success("Task added to Day 1-30 onboarding plan");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to create plan item");
    },
  });
}

export function useUpdatePlanItem(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: PlanItemUpdateInput }) =>
      apiPatch<PlanItemWithClaims>(`/api/v1/handovers/${handoverId}/plan/${itemId}`, data),
    onMutate: async ({ itemId, data }) => {
      if (!handoverId) return;
      await queryClient.cancelQueries({ queryKey: queryKeys.handovers.plan(handoverId) });
      const previousPlan = queryClient.getQueryData<PlanItemWithClaims[]>(
        queryKeys.handovers.plan(handoverId),
      );

      if (previousPlan) {
        queryClient.setQueryData<PlanItemWithClaims[]>(
          queryKeys.handovers.plan(handoverId),
          previousPlan.map((item) => (item.id === itemId ? { ...item, ...data } : item)),
        );
      }

      return { previousPlan };
    },
    onError: (_err, _vars, context) => {
      if (handoverId && context?.previousPlan) {
        queryClient.setQueryData(queryKeys.handovers.plan(handoverId), context.previousPlan);
      }
      toast.error("Failed to update task");
    },
    onSettled: () => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.plan(handoverId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.view(handoverId) });
      }
    },
  });
}

export function useReceiptsProgress(handoverId: string | undefined) {
  return useQuery({
    queryKey: handoverId ? queryKeys.handovers.receipts(handoverId) : ["receipts", "none"],
    queryFn: ({ signal }) =>
      apiGet<ReceiptsProgress>(`/api/v1/handovers/${handoverId}/receipts`, signal),
    enabled: Boolean(handoverId),
  });
}

export function useAcknowledgeReceipt(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ReceiptInput) =>
      apiPost(`/api/v1/handovers/${handoverId}/receipts`, input),
    onSuccess: () => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.receipts(handoverId) });
      }
      toast.success("Section reading and comprehension acknowledged");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to record comprehension receipt");
    },
  });
}

export function useCopilotMessages(handoverId: string | undefined, sessionId?: string) {
  return useQuery({
    queryKey: handoverId
      ? queryKeys.handovers.copilotMessages(handoverId, sessionId)
      : ["copilot", "messages", "none"],
    queryFn: ({ signal }) => {
      const url = sessionId
        ? `/api/v1/handovers/${handoverId}/chat/messages?session_id=${encodeURIComponent(sessionId)}`
        : `/api/v1/handovers/${handoverId}/chat/messages`;
      return apiGet<ChatMessage[]>(url, signal);
    },
    enabled: Boolean(handoverId),
  });
}

export function useCopilotChat(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ message, sessionId }: { message: string; sessionId?: string }) =>
      apiPost<CopilotChatResponse>(`/api/v1/handovers/${handoverId}/chat`, {
        message,
        session_id: sessionId,
      }),
    onSuccess: (data) => {
      if (handoverId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.handovers.copilotMessages(handoverId, data.session_id),
        });
      }
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Copilot response failed");
    },
  });
}

export function useCopilotFeedback(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ messageId, feedback }: { messageId: string; feedback: "up" | "down" }) =>
      apiPost(`/api/v1/handovers/${handoverId}/chat/messages/${messageId}/feedback`, { feedback }),
    onSuccess: () => {
      if (handoverId) {
        queryClient.invalidateQueries({
          queryKey: [...queryKeys.handovers.all, handoverId, "chat"],
        });
      }
      toast.success("Feedback recorded");
    },
  });
}

export function useCreateQuestion(handoverId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: OpenQuestionInput) =>
      apiPost<HandoverViewAmbiguity>(`/api/v1/handovers/${handoverId}/questions`, input),
    onSuccess: () => {
      if (handoverId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.ambiguities(handoverId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.handovers.view(handoverId) });
      }
      toast.success("Question submitted to the outgoing contributor");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to submit question");
    },
  });
}

export function getExportUrl(handoverId: string, format: "json" | "md" | "html"): string {
  return `/api/v1/handovers/${handoverId}/export?format=${format}`;
}
