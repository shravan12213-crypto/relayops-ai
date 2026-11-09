import * as React from "react";
import { ArrowLeft, GitBranch } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { CopilotChatView } from "@/components/portal/CopilotChatView";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useHandover } from "@/lib/api/handovers";
import { useUsers } from "@/lib/api/users";

export function CopilotPage() {
  const { handoverId } = useParams<{ handoverId: string }>();
  const { data: handover } = useHandover(handoverId);
  const { data: users } = useUsers();

  const outgoingName = React.useMemo(() => {
    if (users && handover) {
      const u = users.find((x) => x.id === handover.outgoing_user_id);
      if (u) return u.name;
    }
    return "Aarav Kulkarni";
  }, [users, handover]);

  React.useEffect(() => {
    document.title = `Grounded Copilot — ${outgoingName} Handover`;
  }, [outgoingName]);

  if (!handoverId) return null;

  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      <PageHeader
        title="Handover Copilot (Full View)"
        description={`Interactive Q&A assistant grounded strictly in verified artifacts from ${outgoingName}'s handover.`}
        actions={
          <div className="flex items-center gap-2">
            <Button asChild variant="outline" size="sm" className="gap-1.5 text-xs h-8">
              <Link to={`/handovers/${handoverId}/portal`}>
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to Portal
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm" className="gap-1.5 text-xs h-8">
              <Link to={`/handovers/${handoverId}/visualizations`}>
                <GitBranch className="h-3.5 w-3.5 text-primary" />
                Timeline & Topology
              </Link>
            </Button>
          </div>
        }
      />

      <Card className="border-border shadow-sm overflow-hidden">
        <CardContent className="p-0">
          <CopilotChatView
            handoverId={handoverId}
            outgoingName={outgoingName}
            fullHeight={false}
          />
        </CardContent>
      </Card>
    </div>
  );
}
