/**
 * Security clearance and access control policy helpers for the frontend.
 *
 * Clearance levels:
 * 0: Public
 * 1: Internal
 * 2: Confidential
 * 3: Restricted
 */

export function canViewerAccessSensitivity(sensitivity: number, clearance: number): boolean {
  return clearance >= sensitivity;
}

export function isRestrictedArtifact(artifactSensitivity: number, viewerClearance: number): boolean {
  return artifactSensitivity > viewerClearance;
}

export function maskClaimText(text: string, sensitivity: number, clearance: number): string {
  if (clearance >= sensitivity) {
    return text;
  }
  return `[Confidential Item - Requires Clearance Level ${sensitivity}]`;
}

export interface MaskableClaim {
  id?: string;
  text: string;
  sensitivity: number;
  is_masked?: boolean;
}

export function applyClientClaimMasking<T extends MaskableClaim>(
  claim: T,
  clearance: number,
): T & { is_masked: boolean } {
  if (canViewerAccessSensitivity(claim.sensitivity, clearance)) {
    return { ...claim, is_masked: false };
  }
  return {
    ...claim,
    text: maskClaimText(claim.text, claim.sensitivity, clearance),
    is_masked: true,
  };
}

export function getClearanceLabel(clearance: number): string {
  switch (clearance) {
    case 0:
      return "Level 0 (Public)";
    case 1:
      return "Level 1 (Internal)";
    case 2:
      return "Level 2 (Confidential)";
    case 3:
      return "Level 3 (Restricted)";
    default:
      return `Level ${clearance}`;
  }
}
