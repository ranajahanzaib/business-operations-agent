import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo, useState } from "react";

type EventRecord = {
  id: number;
  kind: string;
  payload: Record<string, unknown>;
  created_at?: string;
};

export default function WorkflowGraph({
  events,
  status,
}: {
  events: EventRecord[];
  status: string;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const visible = useMemo(() => events.slice(-12), [events]);
  const { nodes, edges } = useMemo(() => {
    const graphNodes: Node[] = visible.map((event, index) => ({
      id: String(event.id),
      position: { x: index * 190, y: index % 2 ? 35 : 0 },
      data: { label: event.kind.replaceAll("_", " ") },
      style: {
        borderRadius: 8,
        border:
          event.id === selectedId ? "2px solid #4e719f" : "1px solid #dce3eb",
        background: event.kind === "failure" ? "#fff0ed" : "#fff",
        color: event.kind === "failure" ? "#ad594c" : "#34465f",
        fontSize: 11,
        padding: "11px 14px",
        textTransform: "capitalize",
        boxShadow: "0 2px 8px #1c2a3a0b",
      },
    }));
    if (graphNodes.length === 0) {
      graphNodes.push({
        id: "created",
        position: { x: 0, y: 0 },
        data: { label: "Run created" },
        style: {
          borderRadius: 8,
          border: "1px solid #dce3eb",
          background: "#fff",
          padding: "11px 14px",
        },
      });
    }
    const graphEdges: Edge[] = graphNodes.slice(1).map((node, index) => ({
      id: `e-${graphNodes[index].id}-${node.id}`,
      source: graphNodes[index].id,
      target: node.id,
      animated:
        status === "planning" || status === "running" || status === "applying",
      style: { stroke: "#91a5bd", strokeWidth: 1.5 },
    }));
    return { nodes: graphNodes, edges: graphEdges };
  }, [visible, selectedId, status]);
  const selected = visible.find((event) => event.id === selectedId);

  return (
    <>
      <div
        className="workflow-graph"
        role="region"
        aria-label={`Workflow graph showing ${events.length} recorded events`}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesConnectable={false}
          nodesDraggable={false}
          elementsSelectable
          zoomOnDoubleClick={false}
          onNodeClick={(_, node) => setSelectedId(Number(node.id) || null)}
        >
          <Background color="#e7ebef" gap={18} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {selected && (
        <section
          className="graph-event-detail"
          aria-label="Selected workflow event details"
        >
          <div className="graph-event-heading">
            <b>{selected.kind.replaceAll("_", " ")}</b>
            <span>
              {selected.created_at
                ? new Date(selected.created_at).toLocaleString()
                : `Event ${selected.id}`}
            </span>
          </div>
          <pre>{JSON.stringify(selected.payload, null, 2)}</pre>
        </section>
      )}
    </>
  );
}
