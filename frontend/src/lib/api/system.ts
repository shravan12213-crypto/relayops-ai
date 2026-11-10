import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api/client";

export type LlmMode = "anthropic" | "openai" | "openai_compatible" | "replay";

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  llm_mode: LlmMode;
  db: "ok" | "error";
}

export function useHealth() {
  return useQuery({
    queryKey: ["system", "health"],
    queryFn: ({ signal }) => apiGet<HealthResponse>("/api/v1/health", signal),
    refetchInterval: 30_000,
    retry: 1,
  });
}
