import { describe, expect, it } from "vitest";
import { formatCitationLabel } from "../lib/citation-utils";

describe("formatCitationLabel", () => {
  it("formats pull request artifacts with 1.0 authority", () => {
    const pr1 = formatCitationLabel("PR-89", "pull_request");
    expect(pr1.label).toBe("PR #89");
    expect(pr1.kind).toBe("pr");
    expect(pr1.authorityWeight).toBe(1.0);

    const pr2 = formatCitationLabel("PR_42");
    expect(pr2.label).toBe("PR #42");
    expect(pr2.kind).toBe("pr");
  });

  it("formats commit SHAs with 1.0 authority", () => {
    const commit = formatCitationLabel("c1a0110000000000000000000000000000000072", "commit");
    expect(commit.label).toBe("Commit c1a011");
    expect(commit.kind).toBe("commit");
    expect(commit.authorityWeight).toBe(1.0);
  });

  it("formats Jira issue keys with 0.8 authority", () => {
    const issue = formatCitationLabel("PAY-142", "issue");
    expect(issue.label).toBe("PAY-142");
    expect(issue.kind).toBe("issue");
    expect(issue.authorityWeight).toBe(0.8);
  });

  it("formats Slack discussion threads with 0.4 authority", () => {
    const slack = formatCitationLabel("msg_rate_100", "slack");
    expect(slack.label).toBe("Slack #backend-dev");
    expect(slack.kind).toBe("slack");
    expect(slack.authorityWeight).toBe(0.4);

    const partnerSlack = formatCitationLabel("#partners-acquirer", "chat");
    expect(partnerSlack.label).toBe("Slack #partners-acquirer");
  });

  it("formats ADR and RFC documents with 0.6 authority", () => {
    const adr = formatCitationLabel("ADR-003", "adr_doc");
    expect(adr.label).toBe("ADR-003");
    expect(adr.kind).toBe("doc");
    expect(adr.authorityWeight).toBe(0.6);

    const rfc = formatCitationLabel("RFC-007", "rfc");
    expect(rfc.label).toBe("RFC-007");
    expect(rfc.kind).toBe("doc");
    expect(rfc.authorityWeight).toBe(0.6);
  });
});
