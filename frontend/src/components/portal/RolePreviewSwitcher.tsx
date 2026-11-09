import { Eye, FileCheck2, Info, ShieldAlert, Sparkles, UserCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";

export type PortalRole = "maintainer" | "junior" | "contractor" | "auditor";

interface RolePreviewSwitcherProps {
  currentRole: PortalRole;
  onRoleChange: (role: PortalRole) => void;
  isLead: boolean;
  actualUserRole: string;
  effectiveClearance: number;
}

const ROLES: Array<{
  id: PortalRole;
  label: string;
  icon: typeof UserCheck;
  description: string;
}> = [
  {
    id: "maintainer",
    label: "Maintainer",
    icon: UserCheck,
    description: "Full technical view with verified architecture claims and runbooks.",
  },
  {
    id: "junior",
    label: "Junior",
    icon: Sparkles,
    description: "Includes architectural glossary with 'Why It Matters' rationale.",
  },
  {
    id: "contractor",
    label: "Contractor",
    icon: ShieldAlert,
    description: "Clearance <= 1. Credentials, compensation, and escalations masked.",
  },
  {
    id: "auditor",
    label: "Auditor",
    icon: FileCheck2,
    description: "Scorecard, cryptographic audit chain, and signatures. No claim bodies.",
  },
];

export function RolePreviewSwitcher({
  currentRole,
  onRoleChange,
  isLead,
  actualUserRole,
  effectiveClearance,
}: RolePreviewSwitcherProps) {
  // If not lead, display quiet view badge without preview switcher
  if (!isLead) {
    return (
      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground">
        <Eye className="h-3.5 w-3.5 text-primary" />
        <span>
          Viewing as <strong className="capitalize text-foreground">{actualUserRole}</strong>
        </span>
        <Badge variant="outline" className="text-[10px]">
          Clearance Level {effectiveClearance}
        </Badge>
      </div>
    );
  }

  const activeRoleConfig = ROLES.find((r) => r.id === currentRole) ?? ROLES[0];

  return (
    <div className="space-y-2">
      {/* Segmented Control */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
            <Eye className="h-3.5 w-3.5 text-primary" />
            Lead Role Preview:
          </span>
          <div className="inline-flex rounded-lg border bg-muted/40 p-1 text-xs">
            {ROLES.map((role) => {
              const Icon = role.icon;
              const isActive = currentRole === role.id;
              return (
                <button
                  key={role.id}
                  type="button"
                  onClick={() => onRoleChange(role.id)}
                  className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                    isActive
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                  }`}
                  aria-pressed={isActive}
                >
                  <Icon className="h-3 w-3" />
                  {role.label}
                </button>
              );
            })}
          </div>
        </div>

        <Badge variant="outline" className="text-[10px]">
          Effective Clearance: Level {effectiveClearance}
        </Badge>
      </div>

      {/* Preview Warning Banner */}
      {currentRole !== "maintainer" && (
        <div
          role="status"
          className={`flex items-start gap-2.5 rounded-lg border p-2.5 text-xs transition-colors ${
            currentRole === "contractor"
              ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200"
              : currentRole === "auditor"
                ? "border-primary/30 bg-primary/10 text-primary-900 dark:text-primary-100"
                : "border-blue-500/30 bg-blue-500/10 text-blue-900 dark:text-blue-200"
          }`}
        >
          <Info className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <p className="font-semibold">
              Previewing as <span className="capitalize">{currentRole}</span>
            </p>
            <p className="text-[11px] opacity-90">{activeRoleConfig.description}</p>
          </div>
        </div>
      )}
    </div>
  );
}
