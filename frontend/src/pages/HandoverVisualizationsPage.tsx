import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  GitFork,
  Workflow,
} from "lucide-react";

import { DecisionTimeline } from "@/components/timeline/DecisionTimeline";
import { DependencyTopology } from "@/components/topology/DependencyTopology";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useHandover,
  useHandoverGraph,
  useHandoverTimeline,
} from "@/lib/api/handovers";

export function HandoverVisualizationsPage() {
  const { handoverId = "" } = useParams<{ handoverId: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  // Determine active tab from route path
  const isTopologyRoute = location.pathname.endsWith("/topology");
  const activeTab = isTopologyRoute ? "topology" : "timeline";

  const { data: handover } = useHandover(handoverId);
  const { data: graph, isLoading: graphLoading } = useHandoverGraph(handoverId);
  const { data: timeline, isLoading: timelineLoading } = useHandoverTimeline(handoverId);

  const handleTabChange = (val: string) => {
    if (val === "topology") {
      navigate(`/handovers/${handoverId}/topology`);
    } else {
      navigate(`/handovers/${handoverId}/timeline`);
    }
  };

  return (
    <div className="flex h-full w-full flex-col bg-canvas select-none overflow-hidden">
      {/* Top Header Bar */}
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-card-border px-4 bg-card backdrop-blur-xs">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
            <Link to={`/handovers/${handoverId}/review`} title="Return to Review Studio">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>

          <div className="flex items-center gap-2">
            <h1 className="text-xs font-semibold text-ink uppercase tracking-wider">
              Handover Visualizations
            </h1>
            <span className="text-ink-faint">•</span>
            <span className="text-xs font-medium text-ink-muted truncate max-w-[240px]">
              {handover?.notes || `Handover ${handoverId.slice(0, 8)}`}
            </span>
          </div>
        </div>

        {/* Tab Switcher in Header */}
        <div className="flex items-center gap-2">
          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList className="h-8 bg-canvas-2 p-0.5">
              <TabsTrigger
                value="timeline"
                className="h-7 gap-1.5 px-3 text-xs data-[state=active]:bg-card"
              >
                <Workflow className="h-3.5 w-3.5 text-brand-text" />
                <span>Decision Timeline</span>
              </TabsTrigger>
              <TabsTrigger
                value="topology"
                className="h-7 gap-1.5 px-3 text-xs data-[state=active]:bg-card"
              >
                <GitFork className="h-3.5 w-3.5 text-brand-text" />
                <span>Dependency Map</span>
                {graph?.nodes.some((n) => n.bus_factor_risk === "high") && (
                  <span className="ml-0.5 rounded-full bg-danger-soft text-conflict px-1 text-[9px] font-mono font-bold">
                    !
                  </span>
                )}
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="h-4 w-px bg-border/60 mx-1" />

          <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5" asChild>
            <Link to={`/handovers/${handoverId}/review`}>
              <span>Review Studio</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* Main Visualizations Body */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === "timeline" ? (
          timelineLoading ? (
            <div className="flex h-full items-center justify-center p-8 space-y-4">
              <div className="space-y-2 text-center">
                <Skeleton className="h-8 w-64 mx-auto" />
                <Skeleton className="h-48 w-96 mx-auto rounded-xl" />
                <p className="text-xs text-ink-muted">Rendering decision swimlanes...</p>
              </div>
            </div>
          ) : timeline ? (
            <DecisionTimeline timeline={timeline} className="h-full" />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-ink-muted">
              No timeline data available for this handover.
            </div>
          )
        ) : graphLoading ? (
          <div className="flex h-full items-center justify-center p-8">
            <div className="space-y-2 text-center">
              <Skeleton className="h-8 w-64 mx-auto" />
              <Skeleton className="h-64 w-96 mx-auto rounded-xl" />
              <p className="text-xs text-ink-muted">Computing topological layout...</p>
            </div>
          </div>
        ) : graph ? (
          <DependencyTopology graph={graph} className="h-full" />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-ink-muted">
            No topology graph data available for this handover.
          </div>
        )}
      </div>
    </div>
  );
}
export default HandoverVisualizationsPage;
