import { NodeData, EdgeData } from "reaflow"; // Import Reaflow types
import { createSelector } from "@reduxjs/toolkit";
import { selectAllNodes, selectAllEdges } from "./selectors";
import { Node as GraphNode, Edge as GraphEdge } from "./graphSlice";

const NODE_W = 260;
const NODE_H = 164;

import { RootState } from "../../store";

const selectGraphNodes = (state: RootState) => selectAllNodes(state);
const selectGraphEdges = (state: RootState) => selectAllEdges(state);

export const selectReaflowGraph = createSelector(
  [selectGraphNodes, selectGraphEdges],
  (
    nodes: GraphNode[],
    edges: GraphEdge[]
  ): { nodes: NodeData[]; edges: EdgeData[] } => {
    // Map GraphNode to Reaflow NodeData, initially without parent
    const rNodesIntermediate = nodes.map((n) => ({
      id: n.id,
      width: NODE_W, // Initial width, layout might override
      height: NODE_H, // Initial height, layout might override
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
        description: `(${n.type}) ${n.nid}`,
        stats: { status: n.status ?? "N/A" },
        showStats: true,
        showError: n.status === "FAILED",
      },
      parent: undefined as string | undefined, // Initialize parent as undefined
    }));

    // Create a map for quick intermediate node lookup
    const rNodeMap = new Map<string, (typeof rNodesIntermediate)[0]>();
    rNodesIntermediate.forEach((node) => rNodeMap.set(node.id, node));

    // Process nested relationships and set parent property
    nodes.forEach((n) => {
      if (n.inner_nodes) {
        n.inner_nodes.forEach((childId) => {
          const childRNode = rNodeMap.get(childId);
          if (childRNode) {
            childRNode.parent = n.id; // Assign parent ID
          }
        });
      }
    });

    // Final nodes array adheres to NodeData[] type
    const rNodes: NodeData[] = rNodesIntermediate;

    // Create edges, adding parent property for nested edges
    const rEdges: EdgeData[] = edges.map((e) => {
      // const sourceNode = nodeMap.get(e.parent);
      // const targetNode = nodeMap.get(e.child);

      // Find the Reaflow parent IDs for source and target
      const sourceRNode = rNodeMap.get(e.parent);
      const targetRNode = rNodeMap.get(e.child);

      const sourceParentId = sourceRNode?.parent;
      const targetParentId = targetRNode?.parent;

      let edgeParent: string | undefined = undefined;
      let className = "edge-hierarchy";

      // Check if edge is internal to a subgraph
      if (sourceParentId && sourceParentId === targetParentId) {
        edgeParent = sourceParentId; // Edge belongs to this parent
        className = "edge-nested"; // Use nested styling
      }

      return {
        id: e.id,
        from: e.parent,
        to: e.child,
        parent: edgeParent,
        className: className,
      };
    });

    return { nodes: rNodes, edges: rEdges };
  }
);
