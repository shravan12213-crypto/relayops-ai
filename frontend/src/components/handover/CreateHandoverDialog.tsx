import * as React from "react";
import { Calendar, FileText, Loader2, Sparkles, UserCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateHandover } from "@/lib/api/handovers";
import { useUsers } from "@/lib/api/users";

export interface CreateHandoverDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
}

export function CreateHandoverDialog({ open, onOpenChange, projectId }: CreateHandoverDialogProps) {
  const { data: users, isLoading: usersLoading } = useUsers();
  const createHandover = useCreateHandover(projectId);
  const navigate = useNavigate();

  const [outgoingId, setOutgoingId] = React.useState("");
  const [successorId, setSuccessorId] = React.useState("");
  const [leadId, setLeadId] = React.useState("");
  const [dueDate, setDueDate] = React.useState("");
  const [notes, setNotes] = React.useState("PayFlow payment webhook refactor & idempotency keys");

  // Auto-fill defaults from PayFlow scenario if available
  React.useEffect(() => {
    if (users && users.length > 0) {
      if (!outgoingId) {
        const outgoing = users.find((u) => u.role === "outgoing") || users[0];
        if (outgoing) setOutgoingId(outgoing.id);
      }
      if (!successorId) {
        const successor = users.find((u) => u.role === "successor") || users[1] || users[0];
        if (successor) setSuccessorId(successor.id);
      }
      if (!leadId) {
        const lead = users.find((u) => u.role === "lead") || users[2] || users[0];
        if (lead) setLeadId(lead.id);
      }
    }
  }, [users, outgoingId, successorId, leadId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!outgoingId || !successorId || !leadId) return;

    try {
      const handover = await createHandover.mutateAsync({
        outgoing_user_id: outgoingId,
        successor_user_id: successorId,
        lead_user_id: leadId,
        due_date: dueDate || null,
        notes: notes.trim(),
      });
      onOpenChange(false);
      // Navigate to pipeline run screen for the newly created handover
      navigate(`/handovers/${handover.id}/pipeline`);
    } catch {
      // Error handled by hook toast
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-md bg-primary/10 text-primary">
              <Sparkles className="h-4 w-4" />
            </span>
            <DialogTitle className="text-base font-semibold">
              Create Engineering Handover
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs">
            Initiate a traceable handover package with verified citations and dual sign-off.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {/* Outgoing Engineer */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink flex items-center justify-between">
              <span>Outgoing Contributor / Lead</span>
              <span className="text-[10px] text-ink-muted">Required for dual sign-off</span>
            </label>
            <Select value={outgoingId} onValueChange={setOutgoingId} disabled={usersLoading}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="Select outgoing engineer" />
              </SelectTrigger>
              <SelectContent>
                {users?.map((u) => (
                  <SelectItem key={u.id} value={u.id} className="text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{u.name}</span>
                      <span className="text-ink-muted font-mono text-[10px]">
                        ({u.email})
                      </span>
                      <Badge variant="outline" className="text-[9px] capitalize ml-1">
                        {u.role}
                      </Badge>
                      <SensitivityBadge level={u.clearance} size="sm" />
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Successor */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink flex items-center justify-between">
              <span>Target Successor</span>
              <span className="text-[10px] text-ink-muted">
                Will receive role-scoped view
              </span>
            </label>
            <Select value={successorId} onValueChange={setSuccessorId} disabled={usersLoading}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="Select successor" />
              </SelectTrigger>
              <SelectContent>
                {users?.map((u) => (
                  <SelectItem key={u.id} value={u.id} className="text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{u.name}</span>
                      <span className="text-ink-muted font-mono text-[10px]">
                        ({u.email})
                      </span>
                      <Badge variant="outline" className="text-[9px] capitalize ml-1">
                        {u.role}
                      </Badge>
                      <SensitivityBadge level={u.clearance} size="sm" />
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Lead / Manager */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink flex items-center justify-between">
              <span>Team Lead / Manager</span>
              <span className="text-[10px] text-ink-muted">
                Resolves ambiguities & signs off
              </span>
            </label>
            <Select value={leadId} onValueChange={setLeadId} disabled={usersLoading}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="Select team lead" />
              </SelectTrigger>
              <SelectContent>
                {users?.map((u) => (
                  <SelectItem key={u.id} value={u.id} className="text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{u.name}</span>
                      <span className="text-ink-muted font-mono text-[10px]">
                        ({u.email})
                      </span>
                      <Badge variant="outline" className="text-[9px] capitalize ml-1">
                        {u.role}
                      </Badge>
                      <SensitivityBadge level={u.clearance} size="sm" />
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Due date */}
          <div className="space-y-1.5">
            <label
              htmlFor="due-date-input"
              className="text-xs font-medium text-ink flex items-center gap-1.5"
            >
              <Calendar className="h-3.5 w-3.5 text-ink-muted" />
              <span>Target Completion Date</span>
            </label>
            <Input
              id="due-date-input"
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="h-9 text-xs"
            />
          </div>

          {/* Notes / Scope */}
          <div className="space-y-1.5">
            <label
              htmlFor="notes-input"
              className="text-xs font-medium text-ink flex items-center gap-1.5"
            >
              <FileText className="h-3.5 w-3.5 text-ink-muted" />
              <span>Handover Scope & Notes</span>
            </label>
            <Textarea
              id="notes-input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Describe the modules, active refactor, and handover context..."
              rows={3}
              className="text-xs resize-none"
              required
            />
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={createHandover.isPending || !outgoingId || !successorId || !leadId}
              className="gap-1.5 text-xs"
            >
              {createHandover.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <UserCheck className="h-3.5 w-3.5" />
                  Create & Launch Pipeline
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
