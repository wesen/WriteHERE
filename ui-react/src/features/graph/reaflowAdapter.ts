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
    const finalNodes: NodeData[] = [];
    const virtualNodeMap = new Map<string, string>(); // Original Parent ID -> Virtual Container ID

    // Process original nodes and create virtual containers
    nodes.forEach((n) => {
      // Add the original node
      finalNodes.push({
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
          description: `(${n.type}) ${n.nid}`,
          stats: { status: n.status ?? "N/A" },
          showStats: true,
          showError: n.status === "FAILED",
        },
        parent: undefined, // Will be adjusted later if it's an inner node
      });

      // If this node has inner nodes, create a virtual container
      if (n.inner_nodes && n.inner_nodes.length > 0) {
        const virtualId = `${n.id}-container`;
        virtualNodeMap.set(n.id, virtualId);
        finalNodes.push({
          id: virtualId,
          // width/height determined by layout
          parent: n.id, // Virtual node is child of original node
          data: {
            type: "container",
            title: "",
            description: "",
            stats: {},
            showStats: false,
            showError: false,
          }, // Minimal data
          className: "node-container", // Add class for styling
        });
      }
    });

    // Create a map for final nodes for easy lookup
    const finalNodeMap = new Map<string, NodeData>();
    finalNodes.forEach((node) => finalNodeMap.set(node.id, node));

    // Adjust parenting for inner nodes
    nodes.forEach((n) => {
      // Find which original node is the outer node for this one.
      // This requires iterating to find which node's inner_nodes includes 'n.id'.
      let outerNodeId: string | undefined = undefined;
      for (const [potentialOuterId, innerNodeIds] of nodes
        .filter((p) => p.inner_nodes)
        .map((p) => [p.id, p.inner_nodes] as [string, string[]])) {
        if (innerNodeIds.includes(n.id)) {
          outerNodeId = potentialOuterId;
          break;
        }
      }

      if (outerNodeId) {
        const virtualContainerId = virtualNodeMap.get(outerNodeId);
        const nodeToUpdate = finalNodeMap.get(n.id);
        // XXX probably where to check for null parent
        if (nodeToUpdate && virtualContainerId) {
          nodeToUpdate.parent = virtualContainerId;
        }
      }
    });

    // Create edges, adjusting parent for nested edges
    const rEdges: EdgeData[] = edges.map((e) => {
      const sourceNode = finalNodeMap.get(e.parent);
      const targetNode = finalNodeMap.get(e.child);

      let edgeParent: string | undefined = undefined;
      let className = "edge-hierarchy";

      // If both source and target are children of the *same* virtual container node
      if (
        sourceNode?.parent &&
        sourceNode.parent === targetNode?.parent &&
        sourceNode.parent.endsWith("-container")
      ) {
        edgeParent = sourceNode.parent; // Assign container id as edge parent
        className = "edge-nested";
      }

      return {
        id: e.id,
        from: e.parent,
        to: e.child,
        parent: edgeParent,
        className: className,
      };
    });

    return { nodes: finalNodes, edges: rEdges };
  }
);
