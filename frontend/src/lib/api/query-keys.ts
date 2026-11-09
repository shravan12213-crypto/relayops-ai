/**
 * Canonical TanStack Query key factory for RelayOps
 */

export const queryKeys = {
  auth: {
    all: ["auth"] as const,
    me: () => [...queryKeys.auth.all, "me"] as const,
  },
  system: {
    health: () => ["system", "health"] as const,
  },
  projects: {
    all: ["projects"] as const,
    list: () => [...queryKeys.projects.all, "list"] as const,
    detail: (id: string) => [...queryKeys.projects.all, "detail", id] as const,
    sources: (projectId: string) => [...queryKeys.projects.all, projectId, "sources"] as const,
  },
  handovers: {
    all: ["handovers"] as const,
    list: (projectId?: string) => [...queryKeys.handovers.all, "list", { projectId }] as const,
    detail: (id: string) => [...queryKeys.handovers.all, "detail", id] as const,
    claims: (id: string, params?: Record<string, unknown>) =>
      [...queryKeys.handovers.all, id, "claims", params] as const,
    ambiguities: (id: string, params?: Record<string, unknown>) =>
      [...queryKeys.handovers.all, id, "ambiguities", params] as const,
    scorecard: (id: string) => [...queryKeys.handovers.all, id, "scorecard"] as const,
    versions: (id: string) => [...queryKeys.handovers.all, id, "versions"] as const,
    diff: (id: string, vA: number, vB: number) =>
      [...queryKeys.handovers.all, id, "diff", { vA, vB }] as const,
    view: (id: string, role?: string) =>
      [...queryKeys.handovers.all, id, "view", { role }] as const,
    plan: (id: string) => [...queryKeys.handovers.all, id, "plan"] as const,
    receipts: (id: string) => [...queryKeys.handovers.all, id, "receipts"] as const,
    graph: (id: string) => [...queryKeys.handovers.all, id, "graph"] as const,
    timeline: (id: string, params?: Record<string, unknown>) =>
      [...queryKeys.handovers.all, id, "timeline", params] as const,
    copilotMessages: (id: string, sessionId?: string) =>
      [...queryKeys.handovers.all, id, "chat", "messages", { sessionId }] as const,
  },
  jobs: {
    all: ["jobs"] as const,
    detail: (id: string) => [...queryKeys.jobs.all, "detail", id] as const,
  },
};
