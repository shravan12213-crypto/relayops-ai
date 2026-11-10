import {
  Bot,
  CheckCircle2,
  ChevronDown,
  Download,
  FileCode,
  FileText,
  GitBranch,
  Printer,
  Send,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

import { CopyButton } from "@/components/shared/CopyButton";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { getExportUrl, useDeliverHandover, type HandoverView } from "@/lib/api/portal";

interface PortalHeaderProps {
  handoverView: HandoverView;
  outgoingName: string;
  leadName: string;
  handoverDate?: string | null;
  acknowledgedCount: number;
  totalSectionsCount: number;
  progressPct: number;
  onOpenCopilot: () => void;
  isLead: boolean;
}

export function PortalHeader({
  handoverView,
  outgoingName,
  leadName,
  handoverDate,
  acknowledgedCount,
  totalSectionsCount,
  progressPct,
  onOpenCopilot,
  isLead,
}: PortalHeaderProps) {
  const deliverMutation = useDeliverHandover();
  const shortHash = handoverView.hash ? `${handoverView.hash.slice(0, 12)}...` : "";

  const handlePrint = () => {
    window.print();
  };

  const handleDownload = (format: "json" | "md" | "html") => {
    const url = getExportUrl(handoverView.handover_id, format);
    window.open(url, "_blank");
  };

  // Readiness / comprehension ring dimensions
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (progressPct / 100) * circumference;

  return (
    <div className="space-y-4 rounded-xl border bg-card p-5 shadow-sm print:border-none print:shadow-none print:p-0">
      {/* Top row: Title & Action buttons */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-bold tracking-tight text-ink">
              Handover Portal: {outgoingName}
            </h1>
            <div className="inline-flex items-center gap-1.5 rounded-full border border-verified/30 bg-verified/10 px-2.5 py-0.5 text-xs font-semibold text-verified">
              <ShieldCheck className="h-3.5 w-3.5" />
              Verified Handover
            </div>
          </div>
          <p className="text-xs text-ink-muted">
            Target Completion:{" "}
            <span className="font-medium text-ink">
              {handoverDate ? new Date(handoverDate).toLocaleDateString() : "Active Transition"}
            </span>{" "}
            · Version v{handoverView.version}
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap print:hidden">
          {/* Visualizations link */}
          <Button asChild variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
            <Link to={`/handovers/${handoverView.handover_id}/visualizations`}>
              <GitBranch className="h-3.5 w-3.5 text-brand-text" />
              Timeline & Topology
            </Link>
          </Button>

          {/* Copilot Sheet trigger */}
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenCopilot}
            className="h-8 gap-1.5 text-xs border-brand text-brand-text hover:bg-brand-soft"
          >
            <Bot className="h-3.5 w-3.5" />
            Ask Copilot
          </Button>

          {/* Export Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
                <Download className="h-3.5 w-3.5" />
                Export
                <ChevronDown className="h-3 w-3 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="text-xs">
              <DropdownMenuItem onClick={() => handleDownload("md")} className="gap-2">
                <FileText className="h-3.5 w-3.5" />
                Export Markdown (.md)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleDownload("json")} className="gap-2">
                <FileCode className="h-3.5 w-3.5" />
                Export JSON (.json)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handlePrint} className="gap-2">
                <Printer className="h-3.5 w-3.5" />
                Print / Save as PDF
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Lead Deliver Action */}
          {isLead && handoverView.status === "signed" && (
            <Button
              size="sm"
              onClick={() => deliverMutation.mutate(handoverView.handover_id)}
              disabled={deliverMutation.isPending}
              className="h-8 gap-1.5 text-xs bg-primary text-primary-foreground"
            >
              <Send className="h-3.5 w-3.5" />
              Deliver Handover
            </Button>
          )}
        </div>
      </div>

      {/* Subtle Confetti-Free Delivered State Celebration */}
      {handoverView.status === "delivered" && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between rounded-lg border border-verified/40 bg-verified/10 px-4 py-2.5 text-xs text-ink animate-in fade-in-50 duration-300">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-4 w-4 text-verified shrink-0" />
            <div>
              <span className="font-semibold text-verified">Handover Officially Delivered</span>
              <span className="text-ink-muted ml-2 text-[11px] hidden sm:inline">
                Dual sign-offs verified. Successor active onboarding and execution plan unlocked.
              </span>
            </div>
          </div>
          <span className="self-start sm:self-center rounded-full bg-verified/20 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-verified uppercase tracking-wider">
            Sealed v{handoverView.version}
          </span>
        </div>
      )}

      {/* Trust Strip & Readiness Progress Ring */}
      <div className="flex flex-col gap-4 border-t pt-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Trust Strip */}
        <div className="flex items-center gap-3 text-xs flex-wrap">
          <div className="flex items-center gap-1.5 rounded-md bg-canvas-2 px-2.5 py-1 text-ink-muted">
            <UserCheck className="h-3.5 w-3.5 text-verified" />
            <span>
              Signed by:{" "}
              <strong className="text-ink">
                {outgoingName} & {leadName}
              </strong>
            </span>
          </div>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1.5 rounded-md bg-canvas-2 px-2.5 py-1 font-mono text-[11px] text-ink-muted">
                  <span>Hash: {shortHash}</span>
                  <CopyButton value={handoverView.hash} title="Copy SHA-256 seal" />
                </div>
              </TooltipTrigger>
              <TooltipContent className="font-mono text-[10px] max-w-xs break-all">
                {handoverView.hash}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {handoverView.status === "delivered" && (
            <div className="flex items-center gap-1 rounded-md bg-verified/10 px-2 py-0.5 text-[11px] font-medium text-verified">
              <CheckCircle2 className="h-3 w-3" />
              Delivered to Successor
            </div>
          )}
        </div>

        {/* Readiness / Comprehension Progress Ring */}
        <div className="flex items-center gap-3 print:hidden">
          <div className="text-right">
            <p className="text-xs font-semibold text-ink">
              Comprehension: {Math.round(progressPct)}%
            </p>
            <p className="text-[10px] text-ink-muted">
              {acknowledgedCount} of {totalSectionsCount} sections read
            </p>
          </div>

          <div className="relative h-12 w-12 shrink-0">
            <svg className="h-12 w-12 -rotate-90" viewBox="0 0 48 48">
              <circle
                cx="24"
                cy="24"
                r={radius}
                className="stroke-muted"
                strokeWidth="4"
                fill="none"
              />
              <circle
                cx="24"
                cy="24"
                r={radius}
                className="stroke-verified transition-all duration-500 ease-out"
                strokeWidth="4"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                fill="none"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-ink">
              {Math.round(progressPct)}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
