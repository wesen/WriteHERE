I'll merge these two documents into one comprehensive, engaging guide that preserves all the information while explaining the concepts clearly.

# Streaming Node Changes → Building a Graph Store in Redux Toolkit

_A comprehensive guide to creating a real-time, normalized graph store that syncs automatically with your WebSocket event stream_

## 1. Why Create a Dedicated Graph Slice?

Your event list in `eventsApi` serves as an append-only log - perfect for audit trails and history UIs. However, components that need the current graph state (visualizations, progress bars, critical-path calculations) shouldn't have to replay that entire log on every render.

A dedicated graph slice offers several key advantages:

- **O(1) Lookup Performance**: Get nodes and relationships instantly by ID instead of scanning through event arrays
- **Cleaner Separation of Concerns**: Keep your event log as an immutable audit trail while using the graph slice as an in-memory database for views
- **Automatic Synchronization**: Updates to the graph state happen directly in the WebSocket message handler, with no additional middleware required

**RTK concept**: Multiple slices can coexist in the same store, each handling distinct responsibilities. This follows Redux Toolkit's "single-source-of-truth" principle while optimizing for different access patterns.

## 2. Designing a Normalized Data Model with Entity Adapters

Redux Toolkit's `createEntityAdapter` provides a standardized way to store normalized data with automatic CRUD operations:

```ts
// features/graph/graphSlice.ts
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
  initialState,
  reducers: {
    nodeAdded: (state, action: PayloadAction<Node>) => {
      nodes.addOne(state.nodes, action.payload);
    },
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

export { nodes as nodeAdapter, edges as edgeAdapter };
```

Entity adapters provide:

- Normalized storage with `ids` and `entities` fields
- Built-in operations like `addOne`, `updateOne`, `removeOne`, etc.
- Helper selectors like `selectAll`, `selectById`, etc.

> **Tip:** if you care only about "latest node state", `nodeUpdated` can be replaced with `nodes.upsertOne`, letting each event overwrite the previous snapshot.

## 3. Wiring the Graph Updates Directly in `onCacheEntryAdded`

The key insight: instead of using a separate middleware to listen for RTK Query cache updates, we can dispatch graph actions directly from the WebSocket message handler in `onCacheEntryAdded`:

```ts
// features/events/eventsApi.ts  (only the changed bits shown)
import {
  nodeAdded as graphNodeAdded,
  nodeUpdated as graphNodeUpdated,
  edgeAdded as graphEdgeAdded,
} from "../graph/graphSlice";

export const eventsApi = createApi({
  // ...(your unchanged config)...
  endpoints: (builder) => ({
    getEvents: builder.query<
      { events: AgentEvent[]; status: ConnectionStatus },
      void
    >({
      query: () => "/api/events",

      async onCacheEntryAdded(
        _,
        { updateCachedData, cacheEntryRemoved, dispatch }
      ) {
        // WebSocket setup...
        const ws = new WebSocket(`ws://${window.location.host}/ws/events`);

        // Connection status updates...
        ws.onopen = () => {
          updateCachedData((draft) => {
            draft.status = "Connected";
          });
        };

        // Message handling with graph state updates
        ws.onmessage = (event) => {
          let msg: AgentEvent;
          try {
            msg = JSON.parse(event.data);
          } catch (e) {
            console.error("bad JSON", event.data);
            return;
          }

          /* 1️⃣  keep the audit log */
          updateCachedData((draft) => {
            draft.events.unshift(msg);
            if (draft.events.length > 200) draft.events.length = 200;
          });

          /* 2️⃣  mirror graph‑relevant events */
          switch (msg.event_type) {
            case "node_created": {
              const p = msg.payload;
              dispatch(
                graphNodeAdded({
                  id: p.node_id,
                  nid: p.node_nid,
                  type: p.node_type,
                  goal: p.task_goal,
                  layer: p.layer,
                  taskType: p.task_type,
                })
              );
              break;
            }
            case "node_added": {
              // "node_added" only tells you that a *graph* gained a node.
              // If you actually know the node details from elsewhere you can
              // upsert here; otherwise ignore.
              break;
            }
            case "edge_added": {
              const p = msg.payload;
              dispatch(
                graphEdgeAdded({
                  id: `${p.parent_node_id}-${p.child_node_id}`,
                  parent: p.parent_node_id,
                  child: p.child_node_id,
                })
              );
              break;
            }
            case "node_status_changed": {
              const p = msg.payload;
              dispatch(
                graphNodeUpdated({
                  id: p.node_id,
                  changes: { status: p.new_status },
                })
              );
              break;
            }
          }
        };

        // Cleanup on unmount
        await cacheEntryRemoved;
        ws.close();
      },
    }),
  }),
});

export const { useGetEventsQuery } = eventsApi;
```

This approach:

- Processes each event exactly once, as it arrives
- Keeps the graph update logic directly alongside the event processing code
- Avoids the need for additional middleware configuration
- Still maintains separation of concerns between the event log and graph state

## 4. Store Configuration

When configuring your store, simply add the graph reducer:

```ts
// store.ts
import { configureStore } from "@reduxjs/toolkit";
import { eventsApi } from "./features/events/eventsApi";
import graphReducer from "./features/graph/graphSlice";

export const store = configureStore({
  reducer: {
    [eventsApi.reducerPath]: eventsApi.reducer,
    graph: graphReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(eventsApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
```

Note that we only need to include the `eventsApi.middleware` - no additional graph-specific middleware is required.

## 5. Creating Memoized Selectors

Entity adapters provide basic selectors, but you can create more specialized ones:

```ts
// features/graph/selectors.ts
import { createSelector } from "@reduxjs/toolkit";
import { RootState } from "../../store";

// Basic entity adapter selectors
export const {
  selectAll: selectAllNodes,
  selectById: selectNodeById,
  selectIds: selectNodeIds,
} = nodes.getSelectors((state: RootState) => state.graph.nodes);

export const {
  selectAll: selectAllEdges,
  selectById: selectEdgeById,
  selectIds: selectEdgeIds,
} = edges.getSelectors((state: RootState) => state.graph.edges);

// Specialized selectors
export const selectChildren = (id: string) =>
  createSelector(selectAllEdges, selectAllNodes, (edges, nodes) =>
    edges
      .filter((edge) => edge.parent === id)
      .map((edge) => nodes.find((node) => node.id === edge.child))
      .filter(Boolean)
  );

export const selectParents = (id: string) =>
  createSelector(selectAllEdges, selectAllNodes, (edges, nodes) =>
    edges
      .filter((edge) => edge.child === id)
      .map((edge) => nodes.find((node) => node.id === edge.parent))
      .filter(Boolean)
  );
```

These selectors provide:

- Memoization to prevent recalculation when inputs haven't changed
- Type safety for your components
- Stable references that prevent unnecessary re-renders

## 6. Using the Graph in Components

Here's a simple component that renders the entire graph for debugging:

```tsx
import { useAppSelector } from "../../store";
import { selectAllNodes, selectAllEdges } from "../graph/selectors";

export const GraphDebugPanel = () => {
  const nodes = useAppSelector(selectAllNodes);
  const edges = useAppSelector(selectAllEdges);
  return (
    <pre style={{ maxHeight: 400, overflowY: "auto" }}>
      {JSON.stringify({ nodes, edges }, null, 2)}
    </pre>
  );
};
```

You could also create more specialized components that use specific selectors:

```tsx
const NodeBadge = ({ id }: { id: string }) => {
  const node = useAppSelector((state) => selectNodeById(state, id));
  return (
    <span className={`badge bg-${statusColor(node?.status)}`}>
      {node?.nid || id}
    </span>
  );
};
```

## 7. Why the "Inside-Endpoint" Pattern Works Well

This direct approach has several advantages specific to this use case:

1. **One hop, no action-scanning** – You already process each WebSocket message once when it arrives. No need to re-process it via middleware.
2. **Colocation of related logic** – All graph fan-out logic lives next to the transport code, so future contributors see everything in one file.
3. **Simplicity** – No extra middleware configuration or action scanning is required.

While middleware is great when _many different_ parts of the app care about the same actions, here only the graph cares about these specific events. The direct approach keeps the architecture simpler and more explicit.

## 8. File Layout Recap

Your new graph feature requires just two main files:

```
src/
└── features/
    ├── events/
    │   └── eventsApi.ts       ← WebSocket + graph dispatch
    └── graph/
        ├── graphSlice.ts      ← state + reducers + actions
        └── selectors.ts       ← memoized read helpers
```

This follows RTK's colocation philosophy by keeping domain files together in a "Feature Folder" pattern.

## 9. Next Steps

Now that you have a single-source-of-truth graph that stays synced with the incoming event stream in real-time, you can:

1. **Visualize the Graph**: Connect your graph selectors to a visualization library like Reaflow, React Flow, D3, or Sigma to create dynamic network visualizations
2. **Calculate Derived Data**: Create additional selectors that compute critical paths, progress percentages, or other metrics
3. **Add Specialized Entity Operations**: Add custom reducer cases for more complex graph operations like subtree deletion or path analysis
4. **Explore RTK Query Streaming**: Read the "Streaming Updates" guide to further optimize your real-time data flow

Your graph store is now only about 70 lines of code, yet provides a fully type-safe, normalized, and automatically synchronized view of your node graph!

This architecture keeps your existing RTK-Query WebSocket intact, adds zero boilerplate outside the graph slice, and delivers O(1) lookup performance for all your graph-dependent components.
