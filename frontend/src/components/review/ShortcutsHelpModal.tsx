import { Keyboard } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface ShortcutsHelpModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SHORTCUTS = [
  { key: "j", description: "Navigate to next claim card" },
  { key: "k", description: "Navigate to previous claim card" },
  { key: "a", description: "Accept selected claim into handover" },
  { key: "e", description: "Edit selected claim text inline" },
  { key: "x", description: "Reject selected claim (with required reason popover)" },
  { key: "/", description: "Focus filter search input" },
  { key: "Ctrl + Enter", description: "Save inline claim edit" },
  { key: "Esc", description: "Cancel claim edit or dismiss modal" },
  { key: "?", description: "Toggle this keyboard shortcuts cheat-sheet" },
];

export function ShortcutsHelpModal({ open, onOpenChange }: ShortcutsHelpModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Keyboard className="h-4 w-4 text-brand-text" />
            <span>Keyboard Shortcuts</span>
          </DialogTitle>
          <DialogDescription className="text-xs">
            Review Studio is built for full keyboard navigation and high throughput HITL review.
          </DialogDescription>
        </DialogHeader>

        <div className="divide-y divide-border/60 py-2">
          {SHORTCUTS.map((s, idx) => (
            <div key={idx} className="flex items-center justify-between py-2 text-xs">
              <span className="text-ink">{s.description}</span>
              <kbd className="rounded border border-card-border bg-canvas-2 px-2 py-0.5 font-mono text-xs font-semibold text-ink-muted shadow-2xs">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
