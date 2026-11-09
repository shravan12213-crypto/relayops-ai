import * as React from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge as FlowEdge,
  type Node as FlowNode,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  FileWarning,
  Layers,
  Search,
  ShieldAlert,
  User,
  X,
} from "lucide-react";

import { CitationPill } from "@/components/shared/CitationPill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { type GraphNode, type HandoverGraph } from "@/lib/api/handovers";
import { cn } from "@/lib/utils";

// Distinct color assignments per owner
const OWNER_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  "Aarav Kulkarni": {
    bg: "bg-indigo-500/10",
    border: "border-indigo-500/40",
    text: "text-indigo-600 dark:text-indigo-400",
    dot: "#6366f1",
  },
  "Elena Rostova": {
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/40",
    text: "text-emerald-600 dark:text-emerald-400",
    dot: "#10b981",
  },
  "Sarah Chen": {
    bg: "bg-sky-500/10",
    border: "border-sky-500/40",
    text: "text-sky-600 dark:text-sky-400",
    dot: "#0ea5e9",
  },
  "Marcus Vance": {
    bg: "bg-purple-500/10",
    border: "border-purple-500/40",
    text: "text-purple-600 dark:text-purple-400",
    dot: "#a855f7",
  },
  shared: {
    bg: "bg-slate-500/10",
    border: "border-slate-500/40",
    text: "text-slate-600 dark:text-slate-400",
    dot: "#64748b",
  },
};

function getOwnerColor(owner: string) {
  return OWNER_COLORS[owner] || OWNER_COLORS.shared;
}

export type ModuleCustomNode = FlowNode<{ node: GraphNode; isSelected: boolean }, "moduleNode">;

// Custom Module Node for React Flow
function ModuleNode(props: NodeProps<ModuleCustomNode>) {
  const { node, isSelected } = props.data;
  const colors = getOwnerColor(node.owner);

  return (
    <div
      className={cn(
        "relative rounded-xl border bg-card p-3 shadow-sm transition-all duration-150 select-none",
        colors.border,
        isSelected
          ? "ring-2 ring-primary shadow-md border-primary"
          : "hover:shadow-md hover:border-primary/60",
        node.bus_factor_risk === "high" && "ring-1 ring-rose-500/40",
      )}
      style={{ width: "230px" }}
    >
      <Handle type="target" position={Position.Top} className="!bg-primary !w-2.5 !h-2.5" />

      {/* Top badges bar */}
      <div className="flex items-center justify-between gap-1 mb-2">
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
          {node.type}
        </span>

        {/* Bus Factor Risk Badge */}
        {node.bus_factor_risk === "high" && (
          <Badge
            variant="outline"
            className="border-rose-500 bg-rose-500/15 text-rose-600 dark:text-rose-400 text-[9px] gap-1 px-1.5 py-0 font-bold animate-pulse"
          >
            <ShieldAlert className="h-2.5 w-2.5" />
            Bus Factor 1
          </Badge>
        )}

        {/* Undocumented Warning Badge */}
        {node.undocumented && (
          <Badge
            variant="outline"
            className="border-amber-500 bg-amber-500/15 text-amber-700 dark:text-amber-400 text-[9px] gap-1 px-1.5 py-0 font-semibold"
          >
            <FileWarning className="h-2.5 w-2.5" />
            0 Docs
          </Badge>
        )}
      </div>

      {/* Module Title */}
      <div className="flex items-center gap-2">
        <div className="rounded-md bg-primary/10 p-1.5 text-primary">
          <Layers className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <h4 className="text-xs font-bold text-foreground truncate">{node.label}</h4>
          <p className="font-mono text-[10px] text-muted-foreground">
            {node.claims_count} claim{node.claims_count === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      {/* Owner & Commit share */}
      <div className="mt-2.5 rounded-md border border-border/60 bg-muted/30 p-1.5 text-[10px] space-y-1">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1 text-muted-foreground">
            <User className="h-3 w-3" />
            Owner:
          </span>
          <span className={cn("font-medium truncate max-w-[110px]", colors.text)}>
            {node.owner}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Commit share:</span>
          <span className="font-mono font-semibold text-foreground">
            {Math.round(node.commit_share * 100)}%
          </span>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-primary !w-2.5 !h-2.5" />
    </div>
  );
}

const nodeTypes = {
  moduleNode: ModuleNode,
};

// Topological rank layout algorithm
function calculateNodePositions(nodes: GraphNode[]) {
  // Pre-configured rank assignments based on PayFlow service topology
  const rankMap: Record<string, { rank: number; col: number }> = {
    payflow: { rank: 0, col: 0 },
    webhooks: { rank: 1, col: -1 },
    "ledger-sync": { rank: 1, col: 1 },
    billing: { rank: 2, col: 0 },
    auth: { rank: 3, col: 0 },
  };

  const xSpacing = 280;
  const ySpacing = 160;
  const centerX = 400;

  return nodes.map((node, idx) => {
    const layout = rankMap[node.id] || { rank: Math.floor(idx / 2), col: (idx % 2) * 2 - 1 };
    return {
      x: centerX + layout.col * (xSpacing / 2),
      y: 60 + layout.rank * ySpacing,
    };
  });
}

function TopologyFlowInner({
  graph,
  selectedNode,
  onSelectNode,
}: {
  graph: HandoverGraph;
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode | null) => void;
}) {
  const reactFlow = useReactFlow();
  const [searchQuery, setSearchQuery] = React.useState("");

  // Build initial nodes
  const initialNodes: ModuleCustomNode[] = React.useMemo(() => {
    const positions = calculateNodePositions(graph.nodes);
    return graph.nodes.map((node, i) => ({
      id: node.id,
      type: "moduleNode" as const,
      position: positions[i],
      data: {
        node,
        isSelected: selectedNode?.id === node.id,
      },
    }));
  }, [graph.nodes, selectedNode?.id]);

  // Build initial edges
  const initialEdges: FlowEdge[] = React.useMemo(() => {
    return graph.edges.map((e) => {
      const isBlocks = e.type === "BLOCKS";
      return {
        id: e.id,
        source: e.src,
        target: e.dst,
        type: "smoothstep",
        animated: isBlocks,
        style: {
          stroke: isBlocks ? "#ef4444" : "#6366f1",
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isBlocks ? "#ef4444" : "#6366f1",
        },
        label: e.type === "BLOCKS" ? "BLOCKS" : undefined,
        labelStyle: {
          fontSize: 9,
          fontWeight: 700,
          fill: "#ef4444",
        },
      };
    });
  }, [graph.edges]);

  const [nodes, setNodes, onNodesChange] = useNodesState<ModuleCustomNode>(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  // Sync node selection
  React.useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          isSelected: n.id === selectedNode?.id,
        },
      })),
    );
  }, [selectedNode?.id, setNodes]);

  // Search to focus
  const handleSearch = (q: string) => {
    setSearchQuery(q);
    if (!q.trim()) return;

    const matchedNode = graph.nodes.find(
      (n) =>
        n.label.toLowerCase().includes(q.toLowerCase()) ||
        n.owner.toLowerCase().includes(q.toLowerCase()),
    );

    if (matchedNode) {
      onSelectNode(matchedNode);
      const flowNode = nodes.find((n) => n.id === matchedNode.id);
      if (flowNode) {
        reactFlow.setCenter(flowNode.position.x + 115, flowNode.position.y + 70, {
          zoom: 1.2,
          duration: 600,
        });
      }
    }
  };

  return (
    <div className="relative h-full w-full">
      {/* Top Search & Controls Overlay */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
        <div className="relative w-64 shadow-xs">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search module or owner..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="h-8 pl-8 text-xs bg-card/90 backdrop-blur-xs border-border/80"
          />
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => {
          const gn = graph.nodes.find((n) => n.id === node.id);
          onSelectNode(gn || null);
        }}
        onPaneClick={() => onSelectNode(null)}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.5}
        maxZoom={2.0}
      >
        <Background color="#94a3b8" gap={20} size={1} />
        <Controls className="!bg-card !border-border !shadow-sm !rounded-md" />
        <MiniMap
          nodeColor={(n) => {
            const gn = graph.nodes.find((m) => m.id === n.id);
            return gn ? getOwnerColor(gn.owner).dot : "#64748b";
          }}
          className="!bg-card !border-border !rounded-md !shadow-sm"
        />
      </ReactFlow>
    </div>
  );
}

export interface DependencyTopologyProps {
  graph: HandoverGraph;
  className?: string;
}

export function DependencyTopology({ graph, className }: DependencyTopologyProps) {
  const [selectedNode, setSelectedNode] = React.useState<GraphNode | null>(null);

  return (
    <div className={cn("relative flex h-full w-full overflow-hidden select-none", className)}>
      {/* Main Graph Area */}
      <div className="flex-1 min-w-0 h-full">
        <ReactFlowProvider>
          <TopologyFlowInner
            graph={graph}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
          />
        </ReactFlowProvider>
      </div>

      {/* Node Details Inspection Side Panel */}
      {selectedNode && (
        <div className="w-80 border-l border-border/80 bg-card/95 backdrop-blur-xs flex flex-col shadow-lg z-20 animate-in slide-in-from-right-10 duration-200">
          {/* Header */}
          <div className="p-4 border-b border-border/60 flex items-start justify-between gap-2">
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary uppercase">
                  {selectedNode.type}
                </span>

                {selectedNode.bus_factor_risk === "high" && (
                  <Badge variant="outline" className="border-rose-500 bg-rose-500/10 text-rose-600 text-[10px]">
                    Bus Factor 1
                  </Badge>
                )}
              </div>
              <h3 className="text-sm font-bold text-foreground">{selectedNode.label}</h3>
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground"
              onClick={() => setSelectedNode(null)}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>

          {/* Module Metadata Breakdown */}
          <ScrollArea className="flex-1 p-4 space-y-4">
            {/* Bus Factor Warning Card */}
            {selectedNode.bus_factor_risk === "high" && (
              <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 space-y-1 text-xs">
                <div className="flex items-center gap-1.5 font-bold text-rose-600 dark:text-rose-400">
                  <ShieldAlert className="h-4 w-4" />
                  <span>Bus-Factor Risk Warning</span>
                </div>
                <p className="text-muted-foreground leading-snug">
                  Module <strong>{selectedNode.label}</strong> has bus factor 1. Single contributor{" "}
                  <strong>{selectedNode.owner}</strong> holds 100% of commits with 0 architecture documents.
                </p>
              </div>
            )}

            {/* Ownership stats */}
            <div className="rounded-lg border bg-muted/20 p-3 space-y-2 text-xs">
              <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                Ownership & Activity
              </span>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Primary Maintainer:</span>
                  <span className="font-semibold text-foreground">{selectedNode.owner}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Commit Share:</span>
                  <span className="font-mono font-semibold text-foreground">
                    {Math.round(selectedNode.commit_share * 100)}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Documentation:</span>
                  <span className="font-mono text-foreground">
                    {selectedNode.doc_count} doc{selectedNode.doc_count === 1 ? "" : "s"}
                  </span>
                </div>
              </div>
            </div>

            {/* Associated Claims */}
            <div className="space-y-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Verified Claims ({selectedNode.claims.length})
              </span>
              {selectedNode.claims.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No claims mapped to this module.</p>
              ) : (
                <div className="space-y-2">
                  {selectedNode.claims.map((claim) => (
                    <div
                      key={claim.id}
                      className="rounded-lg border border-border/80 bg-background p-2.5 text-xs space-y-1.5"
                    >
                      <p className="font-medium text-foreground leading-snug">{claim.text}</p>
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                        <span className="rounded bg-muted px-1.5 py-0.2 font-mono uppercase">
                          {claim.kind}
                        </span>
                        <CitationPill artifactId={claim.id} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Open Work & Blockers */}
            {selectedNode.open_work.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Open Work ({selectedNode.open_work.length})
                </span>
                <div className="space-y-2">
                  {selectedNode.open_work.map((ow) => (
                    <div
                      key={ow.id}
                      className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5 text-xs space-y-1"
                    >
                      <p className="font-medium text-foreground">{ow.text}</p>
                      <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-500/30">
                        {ow.kind}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </ScrollArea>
        </div>
      )}
    </div>
  );
}
