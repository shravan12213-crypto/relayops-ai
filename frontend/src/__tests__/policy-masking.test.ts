import { describe, expect, it } from "vitest";
import {
  applyClientClaimMasking,
  canViewerAccessSensitivity,
  getClearanceLabel,
  isRestrictedArtifact,
  maskClaimText,
} from "../lib/policy-utils";

describe("policy masking helpers", () => {
  it("evaluates clearance vs sensitivity access", () => {
    // Level 1 contractor
    expect(canViewerAccessSensitivity(0, 1)).toBe(true);
    expect(canViewerAccessSensitivity(1, 1)).toBe(true);
    expect(canViewerAccessSensitivity(2, 1)).toBe(false);
    expect(canViewerAccessSensitivity(3, 1)).toBe(false);

    // Level 3 project lead
    expect(canViewerAccessSensitivity(2, 3)).toBe(true);
    expect(canViewerAccessSensitivity(3, 3)).toBe(true);
  });

  it("identifies restricted artifacts correctly", () => {
    expect(isRestrictedArtifact(2, 1)).toBe(true);
    expect(isRestrictedArtifact(1, 1)).toBe(false);
    expect(isRestrictedArtifact(0, 1)).toBe(false);
  });

  it("masks claim text when clearance is insufficient", () => {
    const text = "Escalation contact is David Vance (+1-555-019-2834)";
    const masked = maskClaimText(text, 2, 1);
    expect(masked).toBe("[Confidential Item - Requires Clearance Level 2]");
    expect(masked).not.toContain("David Vance");

    // Sufficient clearance -> unmasked
    const unmasked = maskClaimText(text, 2, 2);
    expect(unmasked).toBe(text);
  });

  it("applies client-side claim masking to claim objects", () => {
    const confidentialClaim = {
      id: "claim_01",
      text: "Vendor escalation contact: David Vance (david.vance@acquirercorp.com)",
      sensitivity: 2,
    };

    const maskedForContractor = applyClientClaimMasking(confidentialClaim, 1);
    expect(maskedForContractor.is_masked).toBe(true);
    expect(maskedForContractor.text).toContain("[Confidential Item");
    expect(maskedForContractor.text).not.toContain("david.vance@acquirercorp.com");

    const visibleForLead = applyClientClaimMasking(confidentialClaim, 3);
    expect(visibleForLead.is_masked).toBe(false);
    expect(visibleForLead.text).toContain("david.vance@acquirercorp.com");
  });

  it("provides human-readable clearance labels", () => {
    expect(getClearanceLabel(0)).toBe("Level 0 (Public)");
    expect(getClearanceLabel(1)).toBe("Level 1 (Internal)");
    expect(getClearanceLabel(2)).toBe("Level 2 (Confidential)");
    expect(getClearanceLabel(3)).toBe("Level 3 (Restricted)");
  });
});
