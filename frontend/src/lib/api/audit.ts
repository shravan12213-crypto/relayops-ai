import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api/client";

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

export function useAuditLogs(limit: number = 20, enabled: boolean = true) {
  return useQuery({
    queryKey: ["audit-logs", { limit }],
    queryFn: ({ signal }) => apiGet<AuditLogItem[]>(`/api/v1/audit/logs?limit=${limit}`, signal),
    refetchInterval: 15_000,
    enabled,
    retry: false,
  });
}
