import {
  createSlice,
  createEntityAdapter,
  EntityState,
  Update,
  PayloadAction,
  createAsyncThunk,
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
  initialized: boolean;
  loading: boolean;
  error: string | null;
}

/* ——— Normalised adapters ——— */
const nodes = createEntityAdapter<Node>();
const edges = createEntityAdapter<Edge>();

// Define initial state using the explicit type
const initialState: GraphSliceState = {
  nodes: nodes.getInitialState(),
  edges: edges.getInitialState(),
  initialized: false,
  loading: false,
  error: null,
};

// Async thunk to initialize graph state from the server
export const initializeGraphState = createAsyncThunk(
  "graph/initialize",
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetch("/api/graph");
      if (!response.ok) {
        throw new Error(`Error fetching graph state: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : "Unknown error"
      );
    }
  }
);

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
    // Manual initialization action (can be used for testing)
    initializeState: (state, action: PayloadAction<any>) => {
      if (action.payload?.graph) {
        // Extract nodes
        if (action.payload.graph.nodes) {
          state.nodes = action.payload.graph.nodes;
        }

        // Extract edges
        if (action.payload.graph.edges) {
          state.edges = action.payload.graph.edges;
        }
      }
      state.initialized = true;
    },
    clearGraph: (state) => {
      state.nodes = nodes.getInitialState();
      state.edges = edges.getInitialState();
      state.initialized = true;
      state.loading = false;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(initializeGraphState.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(initializeGraphState.fulfilled, (state, action) => {
        state.loading = false;

        // Only replace state if we got valid data
        if (action.payload?.graph) {
          // Extract nodes
          if (action.payload.graph.nodes) {
            state.nodes = action.payload.graph.nodes;
          }

          // Extract edges
          if (action.payload.graph.edges) {
            state.edges = action.payload.graph.edges;
          }

          state.initialized = true;
        }
      })
      .addCase(initializeGraphState.rejected, (state, action) => {
        state.loading = false;
        state.error =
          (action.payload as string) || "Failed to load graph state";
      });
  },
});

export const {
  nodeAdded,
  nodeUpdated,
  edgeAdded,
  initializeState,
  clearGraph,
} = slice.actions;
export default slice.reducer;

// Export the adapters themselves if needed elsewhere, though usually selectors are preferred
export { nodes as nodeAdapter, edges as edgeAdapter };
