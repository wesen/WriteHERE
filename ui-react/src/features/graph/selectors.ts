import { createSelector } from "@reduxjs/toolkit";
import { RootState } from "../../store";
import { nodeAdapter, edgeAdapter } from "./graphSlice"; // Import adapters

// Basic entity adapter selectors
export const {
  selectAll: selectAllNodesData,
  selectById: selectNodeById,
  selectIds: selectNodeIds,
} = nodeAdapter.getSelectors((state: RootState) => state.graph.nodes);

export const {
  selectAll: selectAllEdgesData,
  selectById: selectEdgeById,
  selectIds: selectEdgeIds,
} = edgeAdapter.getSelectors((state: RootState) => state.graph.edges);

// Wrap selectAll to ensure it returns an empty array if the slice doesn't exist yet
export const selectAllNodes = createSelector(
  (state: RootState) => state.graph?.nodes,
  (nodesState) =>
    nodesState ? nodeAdapter.getSelectors().selectAll(nodesState) : []
);

export const selectAllEdges = createSelector(
  (state: RootState) => state.graph?.edges,
  (edgesState) =>
    edgesState ? edgeAdapter.getSelectors().selectAll(edgesState) : []
);

// Specialized selectors
export const selectChildren = (id: string) =>
  createSelector(
    selectAllEdges,
    selectAllNodes,
    (edges, nodes) =>
      edges
        .filter((edge) => edge.parent === id)
        .map((edge) => nodes.find((node) => node.id === edge.child))
        // .filter(Boolean) // Filter out undefined nodes if a child node referenced by an edge doesn't exist (optional, depends on desired strictness)
        .filter((node): node is NonNullable<typeof node> => !!node) // Type-safe filtering
  );

export const selectParents = (id: string) =>
  createSelector(
    selectAllEdges,
    selectAllNodes,
    (edges, nodes) =>
      edges
        .filter((edge) => edge.child === id)
        .map((edge) => nodes.find((node) => node.id === edge.parent))
        // .filter(Boolean)
        .filter((node): node is NonNullable<typeof node> => !!node) // Type-safe filtering
  );
