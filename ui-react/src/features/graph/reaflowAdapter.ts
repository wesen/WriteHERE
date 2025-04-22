import { MyNodeData } from "../../components/reaflow/CustomNode";
import { createSelector } from "@reduxjs/toolkit";
import { selectAllNodes, selectAllEdges } from "./selectors";
import { Node as GraphNode, Edge as GraphEdge } from "./graphSlice";

const NODE_W = 260;
const NODE_H = 164;

import { RootState } from "../../app/store";

const selectGraphNodes = (state: RootState) => selectAllNodes(state);
const selectGraphEdges = (state: RootState) => selectAllEdges(state);

export const selectReaflowGraph = createSelector(
  [selectGraphNodes, selectGraphEdges],
  (nodes: GraphNode[], edges: GraphEdge[]) => {
    const rNodes: MyNodeData[] = nodes.map((n) => ({
      id: n.id,
      width: NODE_W,
      height: NODE_H,
      data: {
        type:
          n.taskType === "COMPOSITION"
            ? "goal"
            : n.layer === 0
            ? "goal"
            : n.layer === 1
            ? "subtask"
            : "action",
        title: n.goal,
        description: `(${n.type})`,
        stats: { status: n.status ?? "N/A" },
        showStats: true,
        showError: n.status === "FAILED",
      },
    }));

    const rEdges = edges.map((e) => ({
      id: e.id,
      from: e.parent,
      to: e.child,
      className: "edge-hierarchy",
    }));

    return { nodes: rNodes, edges: rEdges };
  }
);
