# Event and Graph Visualization System in Recursive Agent

## Overview

The Recursive Agent's visualization system is a modern React-based application that provides real-time monitoring of agent execution through two main views:

1. An event stream table showing detailed execution events
2. A dynamic task graph visualization showing the hierarchical structure of tasks

The system is built using React, Redux Toolkit, and Bootstrap, with real-time updates via WebSocket connections. It visualizes the complex task decomposition and execution process of the Recursive Agent.

## Architecture

### Core Technologies

- **Frontend Framework**: React with TypeScript
- **State Management**: Redux Toolkit
- **UI Components**: React Bootstrap
- **Graph Visualization**: Reaflow library
- **Real-time Updates**: WebSocket connection
- **Styling**: CSS with Bootstrap classes

### Data Flow

```typescript
// 1. WebSocket Event Reception
ws.onmessage = (event) => {
  const msg: AgentEvent = JSON.parse(event.data);

  // Update event list
  updateCachedData((draft) => {
    draft.events.push(msg);
  });

  // Update graph state based on event type
  switch (msg.event_type) {
    case "node_created":
      dispatch(
        graphNodeAdded({
          /* node data */
        })
      );
      break;
    case "edge_added":
      dispatch(
        graphEdgeAdded({
          /* edge data */
        })
      );
      break;
    case "node_status_changed":
      dispatch(
        graphNodeUpdated({
          /* node update data */
        })
      );
      break;
    case "run_started":
      dispatch(graphClearGraph());
      break;
    // ... other event types might be handled for graph state later
  }
};
```

## Event Visualization

### Event Types and Display

The system handles various event types, each with its own visual representation:

```typescript
const eventTypeConfig = {
  step_started: { icon: Play, color: "text-blue-500" },
  node_created: { icon: GitCommit, color: "text-purple-500" },
  plan_received: { icon: FileCode, color: "text-teal-500" },
  node_added: { icon: PlusCircle, color: "text-green-500" },
  edge_added: { icon: GitFork, color: "text-indigo-500" },
  inner_graph_built: { icon: Network, color: "text-blue-500" },
  // ... other event types
};
```

### Event Table Features

- Real-time updates
- Clickable rows for detailed information
- Color-coded event types
- Timestamp formatting
- Node ID linking
- Status indicators

### Event Detail Views

Each event type has a specialized detail view showing relevant information:

- **Node Creation Events**: Shows node ID, type, layer, and relationships
- **Edge Events**: Visualizes parent-child relationships
- **Plan Events**: Displays the planning structure
- **Status Change Events**: Shows state transitions
- **LLM Call Events**: Details about model interactions

## Graph Visualization

### Node Representation

Nodes in the graph are rendered using a custom component that displays:

```typescript
interface MyNodeData {
  id: string;
  data: {
    type: string; // Determined dynamically: 'goal', 'subtask', or 'action' based on taskType and layer
    title: string; // task goal
    description: string; // additional info (e.g., node type like PLAN_NODE)
    stats: {
      status: string; // NOT_READY, READY, DOING, etc.
    };
    showStats: boolean;
    showError: boolean;
  };
}
```

### Graph Layout

The graph uses a hierarchical layout with the following configuration:

```typescript
const layout: ElkCanvasLayoutOptions = {
  "elk.algorithm": "layered",
  "elk.direction": "DOWN",
  "elk.spacing.nodeNode": "100",
  "elk.layered.spacing.nodeNodeBetweenLayers": "100",
};
```

### State Management

The graph state is managed using Redux with normalized entities:

```typescript
interface GraphSliceState {
  nodes: EntityState<Node>;
  edges: EntityState<Edge>;
  initialized: boolean;
  loading: boolean;
  error: string | null;
}
```

### Interactive Features

- Pannable and zoomable canvas
- Clickable nodes with detailed information modals
- Real-time status updates
- Visual indicators for node states
- Edge visualization showing task dependencies

### Rendering the Graph with Reaflow

The heart of the graph visualization is the `Reaflow` library, which provides a declarative way to render complex graphs using React.

**1. The Canvas:**

The `<Canvas>` component from `Reaflow` acts as the main container for the graph. It orchestrates the layout and rendering of nodes and edges.

```typescript
// In GraphCanvas.tsx
import { Canvas, Node, Edge } from "reaflow";

<Canvas
  direction="DOWN" // Specifies layout direction
  fit // Automatically fits the graph to the container
  pannable // Allows users to pan the canvas
  zoomable // Enables zooming
  nodes={nodes} // Array of node data adapted for Reaflow
  edges={edges} // Array of edge data adapted for Reaflow
  layoutOptions={layout} // ELK layout configuration
  node={
    <Node>
      {(p) => (
        // Uses our custom component to render each node
        <CustomNode
          nodeProps={p}
          selectedNode={selectedNodeId}
          onNodeClick={onNodeClick}
        />
      )}
    </Node>
  }
  edge={<Edge />} // Uses default Reaflow edge rendering
/>;
```

**2. Data Adaptation:**

Reaflow requires nodes and edges in a specific format. We use a selector (`selectReaflowGraph` in `reaflowAdapter.ts`) powered by `createSelector` from Redux Toolkit to efficiently transform our normalized Redux state into the structure Reaflow expects.

```typescript
// In reaflowAdapter.ts
export const selectReaflowGraph = createSelector(
  [selectGraphNodes, selectGraphEdges],
  (nodes: GraphNode[], edges: GraphEdge[]) => {
    const rNodes: MyNodeData[] = nodes.map((n) => ({
      id: n.id,
      width: NODE_W,
      height: NODE_H,
      data: {
        /* Mapped node properties */
      },
    }));

    const rEdges = edges.map((e) => ({
      id: e.id,
      from: e.parent,
      to: e.child,
    }));

    return { nodes: rNodes, edges: rEdges };
  }
);
```

This ensures that the `GraphCanvas` component only re-renders when the underlying graph data actually changes.

**3. Custom Node Rendering:**

Instead of using Reaflow's default node rendering, we employ a custom React component (`CustomNode.tsx`). This gives us full control over the appearance and behavior of each node. It uses SVG's `<foreignObject>` tag to allow rendering standard HTML elements (like divs, paragraphs, icons) within the SVG canvas used by Reaflow.

```typescript
// In CustomNode.tsx
export const CustomNode: React.FC<CustomNodeProps> = ({ nodeProps, ... }) => {
  const { node } = nodeProps;
  const width = node.width || NODE_WIDTH;
  const height = node.height || NODE_HEIGHT;

  return (
    <foreignObject x={0} y={0} width={width} height={height}>
      <div className="node-wrapper">
        {/* Renders node details, icon, status, error indicators */}
        <NodeContent
          node={node}
          selected={isSelected}
          onClick={() => onNodeClick(node.id)}
        />
        {/* Optional: Add button for future interactions */}
      </div>
    </foreignObject>
  );
};
```

The `CustomNode` component uses the `node.data` (transformed from our Redux state) to display:

- Node title (task goal)
- Node type and description
- An icon based on the node type (`nodeConfig.ts`)
- Current status (e.g., "DOING", "FINISH")
- An error badge if the status is "FAILED"

**4. Layout Engine (ELK):**

Reaflow integrates with the Eclipse Layout Kernel (ELK) to automatically arrange nodes and edges. We configure it for a layered, top-down hierarchy.

```typescript
// In GraphCanvas.tsx
const layout: ElkCanvasLayoutOptions = {
  "elk.algorithm": "layered",
  "elk.direction": "DOWN",
  "elk.spacing.nodeNode": "100",
  "elk.layered.spacing.nodeNodeBetweenLayers": "100",
};
```

ELK handles the complex task of positioning nodes to minimize edge crossings and create a readable layout, which is automatically applied by the `<Canvas>` component.

**5. Interaction:**

The `<Canvas>` component manages user interactions:

- **Clicking a Node**: Triggers the `onNodeClick` callback, which updates the selected node state and displays the `NodeDetailModal`.
- **Panning/Zooming**: Handled natively by the `<Canvas>` component's built-in capabilities.

This combination of Reaflow's core components, custom rendering, data adaptation, and the ELK layout engine allows us to create a dynamic and informative visualization of the agent's task graph.

## Real-time Updates

### WebSocket Integration

The system maintains a WebSocket connection to receive live updates:

1. **Connection Management**:

   ```typescript
   // In eventsApi.ts
   ws = new WebSocket("ws://localhost:9999/ws/events");
   ws.onmessage = (event) => {
     // Process incoming events
     // Update both event list and graph state
   };
   ```

2. **Event Processing Pipeline**:
   - Event reception
   - Type validation
   - State updates
   - UI refresh

### Graph State Updates

The system updates the graph state stored in Redux in response to specific events received via WebSocket or initial fetch. This ensures the graph visualization accurately reflects the agent's progress:

- **`run_started`**: Clears the existing graph state (nodes and edges) to prepare for visualizing a new run (`graphClearGraph` action).
- **`node_created`**: Adds a new node to the Redux store (`graphNodeAdded` action).
- **`edge_added`**: Adds a new edge (dependency) between nodes in the store (`graphEdgeAdded` action).
- **`node_status_changed`**: Updates the `status` field of an existing node in the store (`graphNodeUpdated` action).

Other events like `plan_received` or `inner_graph_built`, while important for understanding the agent's logic and displayed in the event table/modals, do not currently directly modify the graph's node/edge structure within the Redux state after initial creation.

### Displaying Event Details with Modals

To provide in-depth information about specific events or graph nodes without cluttering the main interface, the system utilizes modal dialogs.

**1. General Event Details (`EventDetailModal.tsx`):**

When a user clicks on a row in the main event table (`EventTable.tsx`), an `EventDetailModal` is displayed. This modal provides a comprehensive view of the selected event.

```typescript
// Triggered from EventTable.tsx
<tr key={event.event_id} onClick={() => handleRowClick(event)}>
  {/* ... table cells ... */}
</tr>;

// Inside EventTable.tsx
const [selectedEvent, setSelectedEvent] = useState<AgentEvent | null>(null);
const handleRowClick = (event: AgentEvent) => {
  setSelectedEvent(event);
};

// Render the modal
{
  selectedEvent && (
    <EventDetailModal
      show={!!selectedEvent}
      onHide={() => setSelectedEvent(null)}
      event={selectedEvent}
    />
  );
}
```

The `EventDetailModal` component renders:

- **Common Event Data**: Event ID, Timestamp, Event Type, Step, Node ID (if applicable).
- **Specific Payload Details**: It uses type guards (`isEventType`) to determine the exact type of the event and then renders a specific section tailored to that event's payload. For example, for an `llm_call_completed` event, it shows the agent class, model, duration, token usage, and the actual response.
- **Code Highlighting**: For payloads containing code or structured data (like prompts, results, or plans), it uses a code highlighter component for better readability.

```typescript
// Inside EventDetailModal.tsx - renderSummaryContent function
if (isEventType("llm_call_completed")(event)) {
  return (
    <>
      {/* Render LLM call details */}
      <CodeHighlighter code={JSON.stringify(event.payload.response, null, 2)} />
    </>
  );
} else if (isEventType("plan_received")(event)) {
  return (
    <>
      {/* Render Plan details */}
      <CodeHighlighter code={JSON.stringify(event.payload.raw_plan, null, 2)} />
    </>
  );
}
// ... other event types
```

**2. Node-Specific Details (`NodeDetailModal.tsx`):**

When a user clicks on a node within the `GraphCanvas`, a different modal, `NodeDetailModal`, is shown. This modal focuses specifically on the selected node and aggregates relevant information.

```typescript
// Triggered from GraphCanvas.tsx
<CustomNode
  nodeProps={p}
  selectedNode={selectedNodeId}
  onNodeClick={onNodeClick} // Callback to show modal
/>;

// Inside GraphCanvas.tsx
const onNodeClick = useCallback((id: string) => {
  setSelectedNodeId(id);
  setShowNodeModal(true);
}, []);

// Render the modal
{
  selectedNodeId && (
    <NodeDetailModal
      show={showNodeModal}
      onHide={() => {
        /* hide logic */
      }}
      nodeId={selectedNodeId}
    />
  );
}
```

The `NodeDetailModal` displays:

- **Node Information**: Fetches node details (ID, NID, Goal, Type, Status) from the Redux store using the `selectNodeById` selector.
- **Related Events List**: It filters the global event list (fetched via `useGetEventsQuery`) to find all events associated with the selected `nodeId` (including events where it's the primary node, owner, parent, or child).
- **Event Detail Pane**: It includes an embedded `NodeEventDetailPane` component. When a user clicks on an event in the related events list within the modal, this pane displays the detailed payload information for _that specific event_, similar to how `EventDetailModal` renders details.

```typescript
// Inside NodeDetailModal.tsx
const node = useSelector((state: RootState) => selectNodeById(state, nodeId));
const { data: eventsData } = useGetEventsQuery();

// Filter events related to this node
const nodeEvents = useMemo(() => {
  return eventsData.events.filter(event => /* related to nodeId */);
}, [eventsData, nodeId]);

return (
  <Modal show={show} onHide={onHide}>
    {/* Display node details */}
    <ListGroup>
      {nodeEvents.map(event => (
        <ListGroup.Item key={event.event_id} onClick={() => setSelectedEvent(event)}>
          {/* Event summary */}
        </ListGroup.Item>
      ))}
    </ListGroup>
    {selectedEvent && <NodeEventDetailPane event={selectedEvent} />}
  </Modal>
);
```

This two-modal approach provides both a general event exploration path (starting from the table) and a node-centric exploration path (starting from the graph), allowing users to delve into the agent's execution details effectively.

### Modal Navigation Stack

To provide a more seamless exploration experience, the system implements a modal stack navigation pattern that allows users to navigate through related entities without losing context. This pattern is implemented using Redux for state management and React components for the UI.

#### Modal Stack Architecture

The modal stack is managed through a dedicated Redux slice that maintains a stack of modal descriptors:

```typescript
// In modalStackSlice.ts
export interface ModalDescriptor {
  type: "node" | "event";
  params: { nodeId?: string; eventId?: string };
}

interface ModalState {
  stack: ModalDescriptor[];
}

const modalStackSlice = createSlice({
  name: "modalStack",
  initialState: { stack: [] },
  reducers: {
    pushModal(state, action: PayloadAction<ModalDescriptor>) {
      state.stack.push(action.payload);
    },
    popModal(state) {
      state.stack.pop();
    },
    replaceTop(state, action: PayloadAction<ModalDescriptor>) {
      if (state.stack.length)
        state.stack[state.stack.length - 1] = action.payload;
      else state.stack.push(action.payload);
    },
    clearStack(state) {
      state.stack = [];
    },
  },
});
```

#### Modal Manager Component

A central `ModalManager` component handles the rendering of modals based on the current state of the modal stack:

```typescript
// In ModalManager.tsx
export const ModalManager: React.FC = () => {
  const dispatch = useAppDispatch();
  const stack = useAppSelector((s) => s.modalStack.stack);
  const top = stack[stack.length - 1];

  // Handle browser back button for modal navigation
  useEffect(() => {
    const handlePopState = () => {
      if (stack.length > 0) {
        dispatch(popModal());
      }
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [dispatch, stack.length]);

  // Push state to history when a modal is added
  useEffect(() => {
    if (stack.length > 0) {
      window.history.pushState({ modalStack: true }, "");
    }
  }, [stack.length]);

  if (!top) return null; // nothing to show

  const onHide = () => {
    // When explicitly closing the modal, clear the entire stack
    dispatch(clearStack());
    // Also clear browser history states we've added
    const historyDepth = stack.length;
    for (let i = 0; i < historyDepth; i++) {
      window.history.back();
    }
  };

  const onBack = () => dispatch(popModal());

  const onNodeClick = (nodeId: string) => {
    dispatch(pushModal({ type: "node", params: { nodeId } }));
  };

  const onEventClick = (eventId: string) => {
    dispatch(pushModal({ type: "event", params: { eventId } }));
  };

  switch (top.type) {
    case "node":
      return (
        <NodeDetailModal
          show
          onHide={onHide}
          nodeId={top.params.nodeId!}
          onNodeClick={onNodeClick}
          onEventClick={onEventClick}
          hasPrevious={stack.length > 1}
          onBack={onBack}
        />
      );
    case "event":
      // Find the event by its ID
      const event = eventsData?.events.find(
        (e) => e.event_id === top.params.eventId
      );
      if (!event) return null;

      return (
        <EventDetailModal
          show
          onHide={onHide}
          event={event}
          onNodeClick={onNodeClick}
          hasPrevious={stack.length > 1}
          onBack={onBack}
        />
      );
  }
};
```

#### Modal Integration

Both the `NodeDetailModal` and `EventDetailModal` components are enhanced with navigation capabilities:

1. **Clickable Node IDs**: Node IDs across the UI are rendered as clickable buttons, allowing navigation to node details.
2. **Back Navigation**: Each modal includes a back button (when applicable) to return to the previous modal in the stack.
3. **Browser History Integration**: The modal stack integrates with the browser's history, enabling back/forward navigation with browser controls.

```typescript
// Example of clickable node rendering in NodeDetailModal.tsx
const renderClickableNodeId = (
  nodeId: string,
  label?: string,
  truncate: boolean = true
) => {
  const displayText = truncate ? `${nodeId.substring(0, 8)}...` : nodeId;

  return onNodeClick ? (
    <Button
      variant="link"
      className="p-0 text-decoration-none"
      onClick={() => onNodeClick(nodeId)}
    >
      {label || displayText}
    </Button>
  ) : (
    label || displayText
  );
};
```

#### User Interaction Flow

The modal stack system enables fluid navigation through related entities:

1. **Entry Points**: Users can enter the modal navigation system by:
   - Clicking on a node in the graph canvas
   - Clicking on an event row in the event table
2. **Navigation Within Modals**: Once within a modal, users can:

   - Click on any node ID to view that node's details
   - Click on an event from a node's related events to view that event
   - Click the back button to return to the previous modal
   - Click the close button to exit the entire modal stack

3. **Browser Integration**: The system integrates with browser navigation:
   - Browser back button pops the top modal from the stack
   - Each modal push adds a history entry, enabling forward navigation
   - Closing the modal clears relevant history entries

#### Benefits of the Modal Stack Approach

This navigation pattern offers several advantages:

1. **Contextual Exploration**: Users can explore related entities without losing context or their place in the exploration flow.
2. **Reduced UI Clutter**: Instead of opening multiple modals or windows, the stack approach keeps the interface clean.
3. **Intuitive Navigation**: The back button pattern matches common web navigation patterns.
4. **History Support**: Integration with browser history provides consistent navigation behavior.
5. **Centralized State Management**: The Redux-based approach keeps modal state predictable and maintainable.

## Best Practices for Development

### Adding New Event Types

1. Define the event payload interface in `eventsApi.ts`
2. Add event type to the configuration in `EventTable.tsx`
3. Implement the detail view in `EventDetailModal.tsx`
4. Update graph state handling if needed

### Customizing Node Visualization

1. Modify `CustomNode.tsx` for visual changes
2. Update `nodeConfig.ts` for styling rules
3. Adjust layout parameters in `GraphCanvas.tsx`

### State Management Guidelines

1. Use Redux actions for all state changes
2. Maintain normalized state structure
3. Use selectors for derived data
4. Handle WebSocket events consistently
