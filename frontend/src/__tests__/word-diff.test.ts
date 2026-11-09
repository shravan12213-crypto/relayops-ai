import { describe, expect, it } from "vitest";
import { computeWordDiff } from "../lib/diff-utils";

describe("computeWordDiff", () => {
  it("identifies unchanged text", () => {
    const text = "Redis session caching proposed in ADR-003";
    const tokens = computeWordDiff(text, text);

    expect(tokens.every((t) => t.type === "same")).toBe(true);
    expect(tokens.map((t) => t.word).join(" ")).toBe(text);
  });

  it("identifies additions", () => {
    const original = "Stateless JWT tokens";
    const edited = "Stateless HMAC-SHA256 JWT tokens";
    const tokens = computeWordDiff(original, edited);

    const added = tokens.filter((t) => t.type === "added");
    expect(added.length).toBe(1);
    expect(added[0].word).toBe("HMAC-SHA256");
  });

  it("identifies removals", () => {
    const original = "Maximum 3 retry attempts with backoff";
    const edited = "Maximum 3 retry attempts";
    const tokens = computeWordDiff(original, edited);

    const removed = tokens.filter((t) => t.type === "removed");
    expect(removed.map((t) => t.word)).toEqual(["with", "backoff"]);
  });

  it("handles word replacement (removal + addition)", () => {
    const original = "Database migrated to MongoDB";
    const edited = "Database migrated to PostgreSQL";
    const tokens = computeWordDiff(original, edited);

    expect(tokens.some((t) => t.type === "removed" && t.word === "MongoDB")).toBe(true);
    expect(tokens.some((t) => t.type === "added" && t.word === "PostgreSQL")).toBe(true);
    expect(tokens.some((t) => t.type === "same" && t.word === "Database")).toBe(true);
  });
});
