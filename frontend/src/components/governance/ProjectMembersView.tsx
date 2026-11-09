import * as React from "react";
import {
  AlertCircle,
  Loader2,
  RefreshCw,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";

import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { RelativeTime } from "@/components/shared/RelativeTime";
import { SensitivityBadge } from "@/components/shared/SensitivityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/lib/api/auth";
import {
  useAddProjectMember,
  useProjectMembers,
  useRemoveProjectMember,
  useUpdateProjectMember,
  type ProjectMember,
} from "@/lib/api/governance";
import { useProjects } from "@/lib/api/projects";
import { useUsers } from "@/lib/api/users";

export function ProjectMembersView() {
  const { user: currentUser } = useAuth();
  const isLead = currentUser?.role === "lead";

  const { data: projects, isLoading: projectsLoading } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = React.useState<string>("");

  React.useEffect(() => {
    if (projects && projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const {
    data: members,
    isLoading: membersLoading,
    isError: membersError,
    error,
    refetch,
  } = useProjectMembers(selectedProjectId);

  const { data: allUsers } = useUsers();

  const addMutation = useAddProjectMember(selectedProjectId);
  const updateMutation = useUpdateProjectMember(selectedProjectId);
  const removeMutation = useRemoveProjectMember(selectedProjectId);

  // Add Member Dialog state
  const [addDialogOpen, setAddDialogOpen] = React.useState(false);
  const [selectedUserId, setSelectedUserId] = React.useState<string>("");
  const [selectedRole, setSelectedRole] = React.useState<string>("successor");
  const [selectedClearance, setSelectedClearance] = React.useState<number>(1);

  // Remove confirmation state
  const [memberToRemove, setMemberToRemove] = React.useState<ProjectMember | null>(null);

  // Filter available users not already in the project
  const availableUsers = React.useMemo(() => {
    if (!allUsers) return [];
    const memberIds = new Set(members?.map((m) => m.user_id) ?? []);
    return allUsers.filter((u) => !memberIds.has(u.id));
  }, [allUsers, members]);

  const handleOpenAddDialog = () => {
    if (availableUsers.length > 0) {
      setSelectedUserId(availableUsers[0].id);
      setSelectedRole(availableUsers[0].role || "successor");
      setSelectedClearance(availableUsers[0].clearance ?? 1);
    } else {
      setSelectedUserId("");
    }
    setAddDialogOpen(true);
  };

  const handleAddMember = async () => {
    if (!selectedUserId) return;
    await addMutation.mutateAsync({
      user_id: selectedUserId,
      role: selectedRole,
      clearance: selectedClearance,
    });
    setAddDialogOpen(false);
  };

  const handleUpdateRole = async (userId: string, newRole: string) => {
    await updateMutation.mutateAsync({ userId, role: newRole });
  };

  const handleUpdateClearance = async (userId: string, newClearance: number) => {
    await updateMutation.mutateAsync({ userId, clearance: newClearance });
  };

  const handleConfirmRemove = async () => {
    if (!memberToRemove) return;
    await removeMutation.mutateAsync(memberToRemove.user_id);
    setMemberToRemove(null);
  };

  return (
    <div className="space-y-4">
      {/* Project Selector & Actions Card */}
      <Card className="border-border">
        <CardContent className="py-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">
                Select Project:
              </span>
              <Select
                value={selectedProjectId}
                onValueChange={setSelectedProjectId}
                disabled={projectsLoading || !projects || projects.length === 0}
              >
                <SelectTrigger className="h-8 w-60 text-xs">
                  <SelectValue placeholder="Choose a project..." />
                </SelectTrigger>
                <SelectContent>
                  {projects?.map((p) => (
                    <SelectItem key={p.id} value={p.id} className="text-xs">
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                className="h-8 gap-1.5 text-xs"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Refresh
              </Button>
              {isLead && (
                <Button
                  size="sm"
                  onClick={handleOpenAddDialog}
                  disabled={!selectedProjectId || availableUsers.length === 0}
                  className="h-8 gap-1.5 text-xs bg-primary hover:bg-primary/90"
                >
                  <UserPlus className="h-3.5 w-3.5" />
                  Add Team Member
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {!isLead && (
        <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-muted-foreground shrink-0" />
          <span>
            Read-Only Auditor Mode: Only users with the <strong>Project Lead</strong> role can add, modify, or remove project memberships and clearance levels.
          </span>
        </div>
      )}

      {/* Members Table Card */}
      <Card className="border-border">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Users className="h-5 w-5 text-primary" />
                Project Membership & Clearance Management
              </CardTitle>
              <CardDescription className="text-xs">
                Manage team member roles and security clearance limits for this project workspace.
              </CardDescription>
            </div>
            {members && (
              <Badge variant="outline" className="font-mono text-xs bg-muted">
                {members.length} members
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {membersLoading ? (
            <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              Loading project members...
            </div>
          ) : membersError ? (
            <ErrorState
              title="Failed to load project members"
              message={error instanceof Error ? error.message : "Error reading members"}
              onRetry={() => refetch()}
            />
          ) : !members || members.length === 0 ? (
            <EmptyState
              title="No members assigned"
              description="No users are currently assigned to this project."
              action={
                isLead ? (
                  <Button size="sm" onClick={handleOpenAddDialog} className="text-xs">
                    Add First Member
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-border bg-muted/40 font-medium text-muted-foreground">
                  <tr>
                    <th className="py-2.5 px-3">Member</th>
                    <th className="py-2.5 px-3">Email</th>
                    <th className="py-2.5 px-3">Role</th>
                    <th className="py-2.5 px-3">Clearance Level</th>
                    <th className="py-2.5 px-3">Joined</th>
                    {isLead && <th className="py-2.5 px-3 w-16 text-center">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {members.map((member: ProjectMember) => (
                    <tr key={member.user_id} className="hover:bg-muted/20 transition-colors">
                      <td className="py-2.5 px-3 font-semibold text-foreground flex items-center gap-2">
                        <div className="h-7 w-7 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center text-[11px]">
                          {member.name.charAt(0).toUpperCase()}
                        </div>
                        <span>{member.name}</span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-muted-foreground">
                        {member.email}
                      </td>
                      <td className="py-2.5 px-3">
                        {isLead ? (
                          <Select
                            value={member.role}
                            onValueChange={(newRole) => handleUpdateRole(member.user_id, newRole)}
                          >
                            <SelectTrigger className="h-7 w-28 text-xs capitalize">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="lead" className="text-xs">Lead</SelectItem>
                              <SelectItem value="outgoing" className="text-xs">Outgoing</SelectItem>
                              <SelectItem value="successor" className="text-xs">Successor</SelectItem>
                              <SelectItem value="contractor" className="text-xs">Contractor</SelectItem>
                              <SelectItem value="auditor" className="text-xs">Auditor</SelectItem>
                            </SelectContent>
                          </Select>
                        ) : (
                          <Badge variant="outline" className="text-xs capitalize font-medium">
                            {member.role}
                          </Badge>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        {isLead ? (
                          <Select
                            value={member.clearance.toString()}
                            onValueChange={(val) =>
                              handleUpdateClearance(member.user_id, Number(val))
                            }
                          >
                            <SelectTrigger className="h-7 w-36 text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
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
                        ) : (
                          <SensitivityBadge level={member.clearance} size="sm" />
                        )}
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap text-muted-foreground">
                        <RelativeTime date={member.joined_at} />
                      </td>
                      {isLead && (
                        <td className="py-2.5 px-3 text-center">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setMemberToRemove(member)}
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                            title="Remove member"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Member Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <UserPlus className="h-4 w-4 text-primary" />
              Add Member to Project
            </DialogTitle>
            <DialogDescription className="text-xs">
              Assign a registered user to this project with role-based governance and clearance limits.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div>
              <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                Select User
              </label>
              <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Choose a user..." />
                </SelectTrigger>
                <SelectContent>
                  {availableUsers.map((u) => (
                    <SelectItem key={u.id} value={u.id} className="text-xs">
                      {u.name} ({u.email})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  Project Role
                </label>
                <Select value={selectedRole} onValueChange={setSelectedRole}>
                  <SelectTrigger className="h-8 text-xs capitalize">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="lead" className="text-xs">Lead</SelectItem>
                    <SelectItem value="outgoing" className="text-xs">Outgoing</SelectItem>
                    <SelectItem value="successor" className="text-xs">Successor</SelectItem>
                    <SelectItem value="contractor" className="text-xs">Contractor</SelectItem>
                    <SelectItem value="auditor" className="text-xs">Auditor</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                  Security Clearance
                </label>
                <Select
                  value={selectedClearance.toString()}
                  onValueChange={(val) => setSelectedClearance(Number(val))}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0" className="text-xs">Level 0 (Public)</SelectItem>
                    <SelectItem value="1" className="text-xs">Level 1 (Internal)</SelectItem>
                    <SelectItem value="2" className="text-xs">Level 2 (Confidential)</SelectItem>
                    <SelectItem value="3" className="text-xs">Level 3 (Restricted)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <DialogFooter className="mt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAddDialogOpen(false)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleAddMember}
              disabled={!selectedUserId || addMutation.isPending}
              className="text-xs bg-primary hover:bg-primary/90"
            >
              {addMutation.isPending ? "Adding..." : "Add Member"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Confirmation Dialog */}
      <ConfirmDialog
        open={!!memberToRemove}
        onOpenChange={(open) => !open && setMemberToRemove(null)}
        title="Remove Member from Project"
        description={`Are you sure you want to remove ${memberToRemove?.name} (${memberToRemove?.email}) from this project workspace? They will lose access to project handovers.`}
        confirmLabel="Remove Member"
        variant="destructive"
        onConfirm={handleConfirmRemove}
        isLoading={removeMutation.isPending}
      />
    </div>
  );
}
