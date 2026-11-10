import { Bot } from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { CopilotChatView } from "./CopilotChatView";

interface CopilotDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  handoverId: string;
  outgoingName?: string;
}

export function CopilotDrawer({
  open,
  onOpenChange,
  handoverId,
  outgoingName,
}: CopilotDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md p-0 flex flex-col h-full">
        <SheetHeader className="p-4 border-b text-left">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-brand-soft p-1.5 text-brand-text">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <SheetTitle className="text-sm font-semibold">Grounded Copilot</SheetTitle>
              <SheetDescription className="text-[11px] text-ink-muted">
                Verified Q&A with citation links and strict clearance filtering.
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="flex-1 overflow-hidden">
          <CopilotChatView
            handoverId={handoverId}
            outgoingName={outgoingName}
            fullHeight
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
