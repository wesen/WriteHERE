import {
  createSlice,
  createEntityAdapter,
  EntityState,
  Update,
  PayloadAction,
} from "@reduxjs/toolkit";

/* ——— Domain models ——— */
export type Node = {
  id: string; // node_id coming from the backend
  nid: string; // node_nid
  type: string;
  goal: string;
  layer: number;
  taskType: string;
  status?: string; // NOT_READY, READY, ...
};

export type Edge = {
  id: string; // `${parent_node_id}-${child_node_id}`
  parent: string; // parent_node_id
  child: string; // child_node_id
};

/* ——— Define Slice State Type --- */
interface GraphSliceState {
  nodes: EntityState<Node, string>;
  edges: EntityState<Edge, string>;
}

/* ——— Normalised adapters ——— */
const nodes = createEntityAdapter<Node>();
const edges = createEntityAdapter<Edge>();

// Define initial state using the explicit type
const initialState: GraphSliceState = {
  nodes: nodes.getInitialState(),
  edges: edges.getInitialState(),
};

const slice = createSlice({
  name: "graph",
  initialState, // Use the explicitly typed initial state
  reducers: {
    // Provide full reducer functions that call the adapter methods
    nodeAdded: (state, action: PayloadAction<Node>) => {
      nodes.addOne(state.nodes, action.payload);
    },
    // Use Update<Node> which defaults the second param to string (matching Node['id'])
    nodeUpdated: (state, action: PayloadAction<Update<Node, string>>) => {
      nodes.updateOne(state.nodes, action.payload);
    },
    edgeAdded: (state, action: PayloadAction<Edge>) => {
      edges.addOne(state.edges, action.payload);
    },
  },
});

export const { nodeAdded, nodeUpdated, edgeAdded } = slice.actions;
export default slice.reducer;

// Export the adapters themselves if needed elsewhere, though usually selectors are preferred
export { nodes as nodeAdapter, edges as edgeAdapter };
