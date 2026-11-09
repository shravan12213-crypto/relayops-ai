export interface FormattedCitation {
  label: string;
  kind: "pr" | "commit" | "issue" | "slack" | "doc";
  authorityWeight: number;
  authorityLabel: string;
}

export function formatCitationLabel(
  artifactId: string,
  sourceType?: string,
): FormattedCitation {
  const cleanId = artifactId.trim();
  const lower = cleanId.toLowerCase();
  const typeLower = (sourceType || "").toLowerCase();

  // 1. Pull Request
  if (
    typeLower === "pr" ||
    typeLower === "pull_request" ||
    lower.startsWith("pr-") ||
    lower.startsWith("pr_")
  ) {
    const num = cleanId.replace(/[^0-9]/g, "") || cleanId;
    return {
      label: `PR #${num}`,
      kind: "pr",
      authorityWeight: 1.0,
      authorityLabel: "1.0 Merged Code/PR",
    };
  }

  // 2. Commit
  if (
    typeLower === "commit" ||
    typeLower === "git_commit" ||
    lower.startsWith("commit_") ||
    /^[0-9a-f]{7,40}$/i.test(cleanId)
  ) {
    const sha = cleanId.replace("commit_", "").slice(0, 6);
    return {
      label: `Commit ${sha}`,
      kind: "commit",
      authorityWeight: 1.0,
      authorityLabel: "1.0 Merged Code/PR",
    };
  }

  // 3. ADR / RFC / Doc
  if (
    typeLower === "adr_doc" ||
    typeLower === "doc" ||
    typeLower === "meeting_note" ||
    typeLower === "runbook" ||
    lower.startsWith("adr-") ||
    lower.startsWith("rfc-") ||
    lower.includes("runbook")
  ) {
    if (lower.startsWith("adr-") || lower.includes("adr")) {
      const num = cleanId.match(/\d+/)?.[0] || "003";
      return {
        label: `ADR-${num.padStart(3, "0")}`,
        kind: "doc",
        authorityWeight: 0.6,
        authorityLabel: "0.6 ADR / Design Doc",
      };
    }
    if (lower.startsWith("rfc-") || lower.includes("rfc")) {
      const num = cleanId.match(/\d+/)?.[0] || "007";
      return {
        label: `RFC-${num.padStart(3, "0")}`,
        kind: "doc",
        authorityWeight: 0.6,
        authorityLabel: "0.6 RFC / Design Doc",
      };
    }
    return {
      label: cleanId,
      kind: "doc",
      authorityWeight: 0.6,
      authorityLabel: "0.6 ADR / Design Doc",
    };
  }

  // 4. Issue Ticket
  if (typeLower === "issue" || typeLower === "jira" || /^[A-Z]+-\d+$/i.test(cleanId)) {
    return {
      label: cleanId.toUpperCase(),
      kind: "issue",
      authorityWeight: 0.8,
      authorityLabel: "0.8 Issue Ticket",
    };
  }

  // 5. Slack
  if (
    typeLower === "slack" ||
    typeLower === "chat" ||
    lower.includes("slack") ||
    lower.startsWith("msg_")
  ) {
    const channelMatch = cleanId.match(/#([a-zA-Z0-9_-]+)/);
    const channel = channelMatch
      ? channelMatch[1]
      : lower.includes("partner")
        ? "partners"
        : "backend-dev";
    return {
      label: `Slack #${channel}`,
      kind: "slack",
      authorityWeight: 0.4,
      authorityLabel: "0.4 Chat Discussion",
    };
  }

  return {
    label: cleanId.length > 16 ? `${cleanId.slice(0, 14)}...` : cleanId,
    kind: "doc",
    authorityWeight: 0.6,
    authorityLabel: "0.6 Architecture Doc",
  };
}
