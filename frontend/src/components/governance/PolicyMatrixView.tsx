import * as React from "react";
import { Check, Info, Minus, Shield } from "lucide-react";

import { ErrorState } from "@/components/shared/ErrorState";
import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePolicyMatrix, type PolicyMatrixRule } from "@/lib/api/governance";

export function PolicyMatrixView() {
  const { data, isLoading, isError, error, refetch } = usePolicyMatrix();
  const [selectedRole, setSelectedRole] = React.useState<string>("ALL");
  const [selectedClearance, setSelectedClearance] = React.useState<string>("ALL");

  const rules = React.useMemo(() => {
    if (!data?.rules) return [];
    return data.rules.filter((r) => {
      if (selectedRole !== "ALL" && r.role !== selectedRole) return false;
      if (selectedClearance !== "ALL" && r.clearance !== Number(selectedClearance)) return false;
      return true;
    });
  }, [data, selectedRole, selectedClearance]);

  return (
    <div className="space-y-4">
      {/* Policy Philosophy Card */}
      <Card className="border-card-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Shield className="h-5 w-5 text-brand-text" />
            Input-Filtered Access Control Matrix
          </CardTitle>
          <CardDescription className="text-xs">
            Derived directly from <code className="font-mono text-[11px] bg-canvas-2 px-1.5 py-0.5 rounded">backend/app/policy.py</code>.
            Access control is enforced <strong>before retrieval and before LLM prompting</strong>, ensuring restricted context is never leaked.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="rounded-lg border border-card-border bg-canvas-2 p-3 text-xs leading-relaxed text-ink-muted flex items-start gap-2.5">
            <Info className="h-4 w-4 text-brand-text shrink-0 mt-0.5" />
            <div>
              <span>
                <strong>Non-Negotiable Policy Invariant:</strong> Handover claims and evidence artifacts are scoped by the viewer's active Role and Security Clearance (0–3).
                Contractors cannot see credentials or escalations. Auditors see metadata, scorecards, and verifiable audit chains without raw claim bodies.
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filter Bar */}
      <Card className="border-card-border">
        <CardContent className="py-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-ink-muted">Filter Role:</span>
              <Select value={selectedRole} onValueChange={setSelectedRole}>
                <SelectTrigger className="h-8 w-36 text-xs">
                  <SelectValue placeholder="All Roles" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL" className="text-xs">
                    All Roles
                  </SelectItem>
                  {data?.roles.map((r) => (
                    <SelectItem key={r} value={r} className="text-xs capitalize">
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-ink-muted">Clearance:</span>
              <Select value={selectedClearance} onValueChange={setSelectedClearance}>
                <SelectTrigger className="h-8 w-36 text-xs">
                  <SelectValue placeholder="All Levels" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL" className="text-xs">
                    All Levels
                  </SelectItem>
                  <SelectItem value="0" className="text-xs">
                    Level 0 (Public)
                  </SelectItem>
                  <SelectItem value="1" className="text-xs">
                    Level 1 (Internal)
                  </SelectItem>
                  <SelectItem value="2" className="text-xs">
                    Level 2 (Confidential)
                  </SelectItem>
                  <SelectItem value="3" className="text-xs">
                    Level 3 (Restricted)
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {(selectedRole !== "ALL" || selectedClearance !== "ALL") && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSelectedRole("ALL");
                  setSelectedClearance("ALL");
                }}
                className="h-8 text-xs text-ink-muted hover:text-ink ml-auto"
              >
                Reset Filters
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Matrix Table */}
      <Card className="border-card-border">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-ink-muted">
            Loading authorization matrix rules...
          </div>
        ) : isError ? (
          <div className="p-6">
            <ErrorState
              title="Failed to load policy matrix"
              message={error instanceof Error ? error.message : "Error reading policy rules"}
              onRetry={() => refetch()}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-card-border bg-canvas-2 font-medium text-ink-muted">
                <tr>
                  <th className="py-2.5 px-3">Role</th>
                  <th className="py-2.5 px-3">Clearance</th>
                  <th className="py-2.5 px-3 text-center">Unverified</th>
                  <th className="py-2.5 px-3 text-center">Conflicts</th>
                  <th className="py-2.5 px-3 text-center">Ambiguities</th>
                  <th className="py-2.5 px-3 text-center">Credentials</th>
                  <th className="py-2.5 px-3 text-center">Export</th>
                  <th className="py-2.5 px-3 text-center">Sign-off</th>
                  <th className="py-2.5 px-3">Max Sensitivity</th>
                  <th className="py-2.5 px-3">Access Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-card-border">
                {rules.map((rule: PolicyMatrixRule, idx: number) => (
                  <tr key={`${rule.role}-${rule.clearance}-${idx}`} className="hover:bg-canvas-2 transition-colors">
                    <td className="py-2.5 px-3 font-semibold capitalize text-ink">
                      <Badge variant="outline" className="text-xs">
                        {rule.role}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3">
                      <SensitivityBadge level={rule.clearance} size="sm" />
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <PermissionIndicator allowed={rule.can_view_unverified} />
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <PermissionIndicator allowed={rule.can_view_conflicts} />
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <PermissionIndicator allowed={rule.can_view_ambiguities} />
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <PermissionIndicator allowed={rule.can_view_credentials} />
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <PermissionIndicator allowed={rule.can_export} />
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <PermissionIndicator allowed={rule.can_signoff} />
                    </td>
                    <td className="py-2.5 px-3">
                      <SensitivityBadge level={rule.max_claim_sensitivity} size="sm" />
                    </td>
                    <td className="py-2.5 px-3 text-ink-muted text-[11px] max-w-xs">
                      {rule.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function PermissionIndicator({ allowed }: { allowed: boolean }) {
  if (allowed) {
    return (
      <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-verified/15 text-verified" title="Permitted">
        <Check className="h-3 w-3 stroke-[2.5]" />
      </span>
    );
  }
  return (
    <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-canvas-2 text-ink-faint" title="Restricted / Not Allowed">
      <Minus className="h-3 w-3" />
    </span>
  );
}
