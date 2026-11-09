import * as React from "react";
import {
  Calendar,
  Clock,
  FileCode,
  FileText,
  Filter,
  GitCommit,
  GitPullRequest,
  List,
  MessageSquare,
  Workflow,
  ZoomIn,
  ZoomOut,
  RotateCcw,
} from "lucide-react";

import { useEvidenceDrawer } from "@/components/shared/evidence-drawer-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type HandoverTimeline, type TimelineEvent } from "@/lib/api/handovers";
import { cn } from "@/lib/utils";

export interface DecisionTimelineProps {
  timeline: HandoverTimeline;
  className?: string;
}

export function DecisionTimeline({ timeline, className }: DecisionTimelineProps) {
  const { openEvidenceDrawer } = useEvidenceDrawer();

  // Filter state
  const [selectedTopic, setSelectedTopic] = React.useState<string>("all");
  const [selectedTimeRange, setSelectedTimeRange] = React.useState<string>("all");
  const [viewMode, setViewMode] = React.useState<"swimlane" | "list">("swimlane");
  const [zoomLevel, setZoomLevel] = React.useState<number>(1);
  const [hoveredEventId, setHoveredEventId] = React.useState<string | null>(null);

  const containerRef = React.useRef<HTMLDivElement>(null);

  // Filter events
  const filteredEvents = React.useMemo(() => {
    let evs = timeline.events;

    if (selectedTopic !== "all") {
      evs = evs.filter((e) => e.topic.toLowerCase() === selectedTopic.toLowerCase());
    }

    if (selectedTimeRange === "last_30_days") {
      const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      evs = evs.filter((e) => new Date(e.timestamp) >= cutoff);
    } else if (selectedTimeRange === "feb_2026") {
      evs = evs.filter((e) => {
        const d = new Date(e.timestamp);
        return d.getFullYear() === 2026 && d.getMonth() === 1;
      });
    }

    return evs;
  }, [timeline.events, selectedTopic, selectedTimeRange]);

  // Distinct topics present in filtered events
  const activeTopics = React.useMemo(() => {
    const set = new Set<string>();
    filteredEvents.forEach((e) => set.add(e.topic));
    return Array.from(set);
  }, [filteredEvents]);

  // Compute time bounds for x-axis
  const { minTime, maxTime } = React.useMemo(() => {
    if (filteredEvents.length === 0) {
      const now = Date.now();
      return { minTime: now - 30 * 24 * 60 * 60 * 1000, maxTime: now };
    }
    const times = filteredEvents.map((e) => new Date(e.timestamp).getTime());
    const min = Math.min(...times);
    const max = Math.max(...times);
    // Add 5% padding on both sides
    const span = Math.max(max - min, 24 * 60 * 60 * 1000);
    return { minTime: min - span * 0.08, maxTime: max + span * 0.08 };
  }, [filteredEvents]);

  const timeSpan = Math.max(maxTime - minTime, 1);

  // Group events by topic
  const eventsByTopic = React.useMemo(() => {
    const map = new Map<string, TimelineEvent[]>();
    activeTopics.forEach((t) => map.set(t, []));
    filteredEvents.forEach((e) => {
      const list = map.get(e.topic) || [];
      list.push(e);
      map.set(e.topic, list);
    });
    return map;
  }, [activeTopics, filteredEvents]);

  // Calculate event coordinate on x-axis
  const getX = React.useCallback(
    (timestamp: string, width: number) => {
      const t = new Date(timestamp).getTime();
      const ratio = (t - minTime) / timeSpan;
      return Math.max(40, Math.min(width - 240, 40 + ratio * (width - 280)));
    },
    [minTime, timeSpan],
  );

  const getEventIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "pr":
        return GitPullRequest;
      case "commit":
        return GitCommit;
      case "slack":
      case "chat":
        return MessageSquare;
      case "adr":
      case "rfc":
        return FileCode;
      default:
        return FileText;
    }
  };

  const handleNodeClick = (event: TimelineEvent) => {
    const primaryEvidence =
      event.evidence && event.evidence.length > 0 ? event.evidence[0] : null;

    openEvidenceDrawer({
      artifact_id: primaryEvidence?.artifact_id || event.id,
      snippet: event.text,
      source_uri: event.source_uri || undefined,
      source_type: event.source_type || event.type,
      title: event.label,
    });
  };

  // Dimensions
  const laneHeight = 130;
  const canvasWidth = Math.max(1000, 1000 * zoomLevel);
  const canvasHeight = Math.max(400, activeTopics.length * laneHeight + 60);

  // Retained links between visible events
  const retainedLinks = React.useMemo(() => {
    const visibleIds = new Set(filteredEvents.map((e) => e.id));
    return timeline.links.filter(
      (lnk) => visibleIds.has(lnk.src_id) && visibleIds.has(lnk.dst_id),
    );
  }, [timeline.links, filteredEvents]);

  // Event positions map for SVG curve drawing
  const eventPositions = React.useMemo(() => {
    const pos = new Map<string, { x: number; y: number }>();
    activeTopics.forEach((topic, laneIndex) => {
      const evs = eventsByTopic.get(topic) || [];
      const laneY = 50 + laneIndex * laneHeight + laneHeight / 2;
      evs.forEach((e) => {
        const x = getX(e.timestamp, canvasWidth);
        pos.set(e.id, { x: x + 100, y: laneY });
      });
    });
    return pos;
  }, [activeTopics, eventsByTopic, canvasWidth, laneHeight, getX]);

  return (
    <div className={cn("flex h-full flex-col bg-background select-none", className)}>
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/80 p-3 bg-card/60 backdrop-blur-xs">
        {/* Left: Filters */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 text-muted-foreground font-medium">
            <Filter className="h-3.5 w-3.5" />
            <span>Topic:</span>
          </div>
          <Select value={selectedTopic} onValueChange={setSelectedTopic}>
            <SelectTrigger className="h-7 text-xs w-44 bg-background">
              <SelectValue placeholder="All Topics" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Topics ({timeline.topics.length})</SelectItem>
              {timeline.topics.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="h-4 w-px bg-border/60 mx-1" />

          <div className="flex items-center gap-1.5 text-muted-foreground font-medium">
            <Calendar className="h-3.5 w-3.5" />
            <span>Range:</span>
          </div>
          <Select value={selectedTimeRange} onValueChange={setSelectedTimeRange}>
            <SelectTrigger className="h-7 text-xs w-36 bg-background">
              <SelectValue placeholder="All Time" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Full Project Time</SelectItem>
              <SelectItem value="feb_2026">February 2026</SelectItem>
              <SelectItem value="last_30_days">Recent 30 Days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Right: View Mode & Zoom Controls */}
        <div className="flex items-center gap-2">
          {viewMode === "swimlane" && (
            <div className="flex items-center gap-1 border rounded-md p-0.5 bg-background">
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.25))}
                title="Zoom in"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                onClick={() => setZoomLevel((z) => Math.max(0.75, z - 0.25))}
                title="Zoom out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                onClick={() => setZoomLevel(1)}
                title="Reset zoom"
              >
                <RotateCcw className="h-3 w-3" />
              </Button>
              <span className="font-mono text-[10px] text-muted-foreground px-1">
                {Math.round(zoomLevel * 100)}%
              </span>
            </div>
          )}

          {/* Toggle Visual vs Accessible List */}
          <div className="flex items-center rounded-md border p-0.5 bg-background">
            <Button
              size="sm"
              variant={viewMode === "swimlane" ? "default" : "ghost"}
              className="h-6 px-2 text-xs gap-1"
              onClick={() => setViewMode("swimlane")}
            >
              <Workflow className="h-3 w-3" />
              <span>Swimlane</span>
            </Button>
            <Button
              size="sm"
              variant={viewMode === "list" ? "default" : "ghost"}
              className="h-6 px-2 text-xs gap-1"
              onClick={() => setViewMode("list")}
            >
              <List className="h-3 w-3" />
              <span>List View</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Main Timeline View */}
      <div className="flex-1 min-h-0 overflow-auto bg-muted/20" ref={containerRef}>
        {viewMode === "list" ? (
          /* Text-Equivalent Accessible List View */
          <div className="max-w-4xl mx-auto p-6 space-y-6">
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-foreground">
                Chronological Decision Ledger (Accessible View)
              </h3>
              <p className="text-xs text-muted-foreground">
                Chronological listing of technical architecture choices, supersessions, and conflicts.
              </p>
            </div>

            <div className="space-y-4">
              {filteredEvents.map((ev) => (
                <div
                  key={ev.id}
                  onClick={() => handleNodeClick(ev)}
                  className={cn(
                    "rounded-xl border bg-card p-4 shadow-2xs space-y-2 cursor-pointer transition-all hover:border-primary/50",
                    ev.status === "superseded" && "opacity-60 bg-muted/30 border-dashed",
                    ev.status === "conflict" && "border-rose-500/50 bg-rose-500/5",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px]",
                          ev.status === "conflict"
                            ? "border-rose-500 text-rose-600 bg-rose-500/10"
                            : ev.status === "superseded"
                              ? "border-muted-foreground text-muted-foreground line-through"
                              : "border-verified/40 text-verified bg-verified/10",
                        )}
                      >
                        {ev.status === "superseded"
                          ? "Superseded"
                          : ev.status === "conflict"
                            ? "Contemporaneous Conflict"
                            : "Active Decision"}
                      </Badge>
                      <span className="font-semibold text-xs text-foreground">{ev.topic}</span>
                    </div>

                    <div className="flex items-center gap-2 text-muted-foreground text-[11px] font-mono">
                      <Clock className="h-3 w-3" />
                      <span>{new Date(ev.timestamp).toLocaleString()}</span>
                    </div>
                  </div>

                  <h4 className={cn("text-xs font-semibold text-foreground", ev.status === "superseded" && "line-through text-muted-foreground")}>
                    {ev.label}
                  </h4>

                  <p className="text-xs text-muted-foreground leading-relaxed">{ev.text}</p>

                  <div className="flex items-center justify-between pt-2 border-t border-border/40 text-[11px] text-muted-foreground">
                    <span>Author: {ev.author || "Engineering Team"}</span>
                    <span className="font-mono">Authority: {ev.authority.toFixed(1)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          /* Visual Interactive Swimlane Canvas */
          <div
            style={{ width: `${canvasWidth}px`, height: `${canvasHeight}px` }}
            className="relative min-w-full min-h-full p-6 select-none"
          >
            {/* SVG Connecting Links Layer */}
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full z-10"
              style={{ width: `${canvasWidth}px`, height: `${canvasHeight}px` }}
            >
              <defs>
                {/* Arrowhead marker for SUPERSEDES */}
                <marker
                  id="arrow-supersedes"
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#6366f1" />
                </marker>
                {/* Red marker for CONFLICT */}
                <marker
                  id="arrow-conflict"
                  viewBox="0 0 10 10"
                  refX="5"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto"
                >
                  <circle cx="5" cy="5" r="3" fill="#ef4444" />
                </marker>
              </defs>

              {retainedLinks.map((lnk) => {
                const p1 = eventPositions.get(lnk.src_id);
                const p2 = eventPositions.get(lnk.dst_id);
                if (!p1 || !p2) return null;

                const isConflict = lnk.type === "CONFLICT";
                const isHovered =
                  hoveredEventId === lnk.src_id || hoveredEventId === lnk.dst_id;

                // Smooth bezier curve
                const dx = p2.x - p1.x;
                const pathD = `M ${p1.x} ${p1.y} C ${p1.x + dx * 0.5} ${p1.y}, ${p2.x - dx * 0.5} ${p2.y}, ${p2.x} ${p2.y}`;

                return (
                  <g key={lnk.id}>
                    <path
                      d={pathD}
                      fill="none"
                      stroke={isConflict ? "#ef4444" : "#6366f1"}
                      strokeWidth={isHovered ? 2.5 : 2}
                      strokeDasharray={isConflict ? "6 4" : undefined}
                      markerEnd={isConflict ? "url(#arrow-conflict)" : "url(#arrow-supersedes)"}
                      opacity={isHovered ? 1 : 0.8}
                    />

                    {/* Midpoint Label badge */}
                    <foreignObject
                      x={(p1.x + p2.x) / 2 - 45}
                      y={(p1.y + p2.y) / 2 - 12}
                      width={90}
                      height={24}
                    >
                      <div
                        className={cn(
                          "flex items-center justify-center rounded-full px-2 py-0.5 text-[9px] font-mono font-bold shadow-xs border",
                          isConflict
                            ? "bg-rose-500 text-white border-rose-600 animate-pulse"
                            : "bg-indigo-600 text-white border-indigo-700",
                        )}
                      >
                        {isConflict ? "CONFLICT" : "SUPERSEDES"}
                      </div>
                    </foreignObject>
                  </g>
                );
              })}
            </svg>

            {/* Swimlanes */}
            <div className="space-y-4">
              {activeTopics.map((topic) => {
                const laneEvents = eventsByTopic.get(topic) || [];

                return (
                  <div
                    key={topic}
                    style={{ minHeight: `${laneHeight - 16}px` }}
                    className="relative rounded-xl border border-border/60 bg-card/40 backdrop-blur-xs p-3 transition-colors hover:bg-card/60"
                  >
                    {/* Lane Label Header */}
                    <div className="flex items-center gap-2 mb-2">
                      <span className="rounded bg-primary/10 px-2 py-0.5 font-semibold text-xs text-primary">
                        {topic}
                      </span>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {laneEvents.length} event{laneEvents.length === 1 ? "" : "s"}
                      </span>
                    </div>

                    {/* Timeline Event Cards in Lane */}
                    <div className="relative h-20">
                      {laneEvents.map((ev) => {
                        const x = getX(ev.timestamp, canvasWidth);
                        const isSuperseded = ev.status === "superseded";
                        const isConflict = ev.status === "conflict";
                        const Icon = getEventIcon(ev.type);

                        return (
                          <div
                            key={ev.id}
                            style={{ left: `${x}px`, top: "2px" }}
                            onMouseEnter={() => setHoveredEventId(ev.id)}
                            onMouseLeave={() => setHoveredEventId(null)}
                            onClick={() => handleNodeClick(ev)}
                            className={cn(
                              "absolute w-56 rounded-lg border bg-card p-2.5 shadow-xs transition-all duration-150 cursor-pointer z-20 hover:scale-102 hover:shadow-md",
                              isSuperseded &&
                                "opacity-50 border-dashed border-muted-foreground/60 bg-muted/40",
                              isConflict &&
                                "border-rose-500 bg-rose-500/10 shadow-rose-500/10 ring-1 ring-rose-500/30",
                              !isSuperseded && !isConflict && "border-border/90 hover:border-primary",
                            )}
                          >
                            <div className="flex items-center justify-between gap-1 mb-1">
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1 font-mono text-[9px] font-bold uppercase",
                                  isConflict
                                    ? "text-rose-600 dark:text-rose-400"
                                    : isSuperseded
                                      ? "text-muted-foreground line-through"
                                      : "text-primary",
                                )}
                              >
                                <Icon className="h-3 w-3 shrink-0" />
                                <span className="truncate">{ev.type}</span>
                              </span>

                              <span className="font-mono text-[9px] text-muted-foreground">
                                {new Date(ev.timestamp).toLocaleDateString(undefined, {
                                  month: "short",
                                  day: "numeric",
                                })}
                              </span>
                            </div>

                            <h5
                              className={cn(
                                "text-xs font-semibold text-foreground line-clamp-1",
                                isSuperseded && "line-through text-muted-foreground",
                              )}
                              title={ev.label}
                            >
                              {ev.label}
                            </h5>

                            <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5 leading-snug">
                              {ev.text}
                            </p>

                            <div className="mt-1.5 flex items-center justify-between text-[9px] text-muted-foreground border-t border-border/40 pt-1">
                              <span className="truncate max-w-[100px]">{ev.author}</span>
                              <span className="font-mono font-semibold">
                                Auth {ev.authority.toFixed(1)}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Footer Legend */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border/80 px-4 py-2 text-xs bg-card/60">
        <div className="flex flex-wrap items-center gap-4 text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-verified" />
            <span>Active Decision</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-muted-foreground opacity-50" />
            <span className="line-through">Superseded Decision</span>
          </div>

          <div className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400 font-semibold">
            <span className="inline-block h-2 w-2 rounded-full bg-rose-500 animate-ping" />
            <span>Contemporaneous Conflict</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 bg-indigo-500" />
            <span>SUPERSEDES Link</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 border-t border-dashed border-rose-500" />
            <span>CONFLICT Link</span>
          </div>
        </div>

        <span className="text-[11px] text-muted-foreground">
          Click any node to inspect real evidence snippet
        </span>
      </div>
    </div>
  );
}
