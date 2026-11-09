import * as React from "react";
import { type EvidenceRef } from "@/lib/api/review";

export interface EvidenceDrawerContextType {
  openEvidenceDrawer: (evidence: EvidenceRef) => void;
  closeEvidenceDrawer: () => void;
  isOpen: boolean;
  activeEvidence: EvidenceRef | null;
}

export const EvidenceDrawerContext = React.createContext<EvidenceDrawerContextType | undefined>(
  undefined,
);

export function useEvidenceDrawer() {
  const ctx = React.useContext(EvidenceDrawerContext);
  if (!ctx) {
    throw new Error("useEvidenceDrawer must be used within an EvidenceDrawerProvider");
  }
  return ctx;
}
