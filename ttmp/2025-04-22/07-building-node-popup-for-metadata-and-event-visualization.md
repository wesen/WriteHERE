# Building Node Metadata & Event Visualization Popup in the Graph UI

## 1. Purpose and Scope

This document explains how to implement a feature in the event-logging UI that allows users to click on a node in the graph visualization and view a modal popup containing:

- Node metadata (ID, type, goal, status, etc.)
- All events related to that specific node (e.g., status changes, LLM/tool calls)
- Rich event details, similar to the existing event detail modal

This is intended for developers working on the `ui-react` frontend, and assumes familiarity with React, Redux Toolkit, and TypeScript.
**Your task is to implement this modal functionality, following the guidance and steps outlined below. You'll be working primarily with React components and Redux state.**

---

## 2. Big Picture Context

The Recursive Agent Event Logging System provides real-time visibility into agent execution using a Redis-based event bus, a FastAPI WebSocket server, and a React/Redux UI. The UI visualizes both the event stream and the evolving task graph.

**Key architectural points:**

- The backend emits events (see `ttmp/2025-04-17/04-long-term-document--event-logging-system.md`) for all major agent actions, including node/graph lifecycle, LLM/tool calls, and status changes.
- The frontend receives these events via WebSocket and stores them in Redux (see `eventsApi.ts`).
- The graph state (nodes/edges) is mirrored in Redux (`graphSlice.ts`) and adapted for visualization with Reaflow (`reaflowAdapter.ts`).

---

## 3. Relevant Files and Functions

- **Graph Visualization**

  - `ui-react/src/components/GraphCanvas.tsx`: (Relevant because: it's where the graph lives and where node selection originates). Renders the graph using Reaflow. Handles node selection **and triggers the `NodeDetailModal`**.
  - `ui-react/src/components/reaflow/CustomNode.tsx`: (Relevant because: it renders individual nodes and needs to trigger the selection). Renders individual nodes. Handles node click events, **passing the node ID up**.
  - `ui-react/src/features/graph/graphSlice.ts`: (Relevant because: it defines the structure of node data in Redux). Redux slice for graph nodes/edges and their metadata.
  - `ui-react/src/features/graph/reaflowAdapter.ts`: (Relevant because: it shows how graph data is prepared for display). Adapts graph state for Reaflow Canvas.
  - `ui-react/src/features/graph/selectors.ts`: (Relevant because: it provides functions to get node data from Redux). Selectors for accessing node/edge data from Redux.

- **Event Data**

  - `ui-react/src/features/events/eventsApi.ts`: (Relevant because: it manages fetching/storing all events and defines their types). RTK Query API for event stream; stores all events in Redux. Defines event types and payloads.
  - `ui-react/src/components/EventDetailModal.tsx`: (Relevant because: it provided a template for displaying detailed event information). Modal for displaying detailed event info **(used as a reference for adapting logic)**.

- **New Modal Components**

  - `ui-react/src/components/NodeDetailModal.tsx`: **(New)** (Relevant because: this is the main modal component). Displays node metadata and a list of related events. Uses `NodeEventDetailPane` for event details.
  - `ui-react/src/components/NodeEventDetailPane.tsx`: **(New)** (Relevant because: it displays the details of a single selected event). Renders the details of a selected `AgentEvent`, adapting logic from `EventDetailModal`.

- **Store**
  - `ui-react/src/app/store.ts`: (Relevant because: it shows how the Redux store is configured and defines the `RootState` type needed for selectors). Combines reducers and exports `RootState` type for selectors. **Note:** Linter showed path issue, ensure it's correct (`../app/store` vs `ui-react/src/store.ts`).

---

## 4. Data Flow and Architecture

- **Node Click**: User clicks a node in the graph (`CustomNode` → `GraphCanvas`).
- **Selection State**: The selected node ID is stored in local state in `GraphCanvas`.
- **Modal Trigger**: When a node is selected, a modal is shown.
- **Node Metadata**: Node metadata is retrieved from Redux (`graphSlice`, via selectors).
- **Node Events**: All events in Redux (`eventsApi.events`) are filtered for those related to the selected node.
- **Modal Content**: The modal displays:
  - Node metadata (ID, type, goal, status, etc.)
  - A list/table of related events (with summary info: timestamp, type)
  - When an event in the list is clicked, show a detail pane (reusing logic from `EventDetailModal`)

---

## 5. Key Technical Insights

- **Node Metadata**: Each node in Redux (`graphSlice.ts`) has fields: `id`, `nid`, `type`, `goal`, `layer`, `taskType`, `status`. Use selectors from `graph/selectors.ts` to retrieve this data.
- **Event Filtering**: Filtering events for a specific node requires checking several fields in the event payload, as a node can be involved in events in different ways.
  - You need to filter the `eventsData.events` array retrieved via the `useGetEventsQuery` hook.
  - Check the following fields within `event.payload` to see if they match the `selectedNodeId`:
    - `node_id`: The most common field, indicating the primary node involved.
    - `added_node_id` (for `node_added` events)
    - `parent_node_id` (for `edge_added` events)
    - `child_node_id` (for `edge_added` events)
    - `graph_owner_node_id` (for `node_added`, `edge_added`, `inner_graph_built` events, if showing graph modification context on the owner node is desired).
  - **Hint:** Start with a simple helper function like `getNodeRelatedEvents(allEvents, nodeId)` inside your modal component. Use `React.useMemo` to avoid re-filtering on every render.
- **Event Types**: Refer to `eventsApi.ts` and the long-term doc (`ttmp/2025-04-17/04-long-term-document--event-logging-system.md`) for all event types and their payload structures.
- **Modal UI Reuse**: The existing `EventDetailModal.tsx` contains useful logic for rendering different event types in detail.
  - **Important:** Do **not** reuse the whole `EventDetailModal` component directly, as it's a complete modal itself.
  - **Instead:** Create a _new_ component (e.g., `NodeEventDetailPane.tsx`) responsible for displaying the details of a _single_ selected event _within_ your new `NodeDetailModal`.
  - You should **copy and adapt** the relevant rendering logic (like the `renderSummaryContent` function and the switch/if structure for handling different event types) from `EventDetailModal.tsx` into your new `NodeEventDetailPane.tsx` component. Remove the outer `Modal` parts and props (`show`, `onHide`, etc.) from the copied code.

---

## 6. Implementation Steps Overview

Follow these general steps. Focus on getting each part working before moving to the next.

1.  **[X] Add Modal State and Trigger in `GraphCanvas.tsx`**:

    - Add `useState` hooks for `selectedNodeId` (string or null) and `showNodeModal` (boolean).
    - Modify the existing node click handler passed to `CustomNode` to update this state and show the modal.

    ```tsx
    // In GraphCanvas.tsx
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [showNodeModal, setShowNodeModal] = useState(false);

    const handleNodeClick = useCallback((id: string) => {
      // Updated signature
      console.log("Node clicked:", id); // Good for debugging
      setSelectedNodeId(id);
      setShowNodeModal(true);
    }, []);
    // Pass handleNodeClick to CustomNode
    ```

    - Conditionally render your new modal component (`NodeDetailModal`) below the `<Canvas>`, passing necessary props (`selectedNodeId`, `showNodeModal`, `onHide`).

2.  **[X] Create `NodeDetailModal.tsx` Component**:

    - Create the file and a basic functional component accepting props: `show`, `onHide`, `nodeId`.
    - Use `react-bootstrap` `Modal` as the container.
    - Initially, just display the `nodeId` inside to verify the trigger works.

3.  **[X] Fetch and Display Node Metadata**:

    - Inside `NodeDetailModal`, use `useSelector` and `selectNodeById` (from `graph/selectors.ts`) to get the node data based on the `nodeId` prop. Handle the case where the node might not be found yet.
    - Display the key node fields (`id`, `nid`, `type`, `goal`, `status`, etc.) in the `Modal.Body` using `Card`, `Row`, `Col`, etc.

4.  **[X] Fetch, Filter, and List Events**:

    - Inside `NodeDetailModal`, use `useGetEventsQuery` to get all events.
    - Implement the event filtering logic (as described in Section 5) using `useMemo` to get `nodeEvents`. Sort events newest first.
    - Add a section/tab to the modal to display the `nodeEvents` using `ListGroup`. Map over them, showing summary info (timestamp, type) and making each item clickable.
    - Add `useState` for `selectedEvent` (type `AgentEvent | null`). Update this state when an event list item is clicked.

5.  **[X] Implement Event Detail Pane**:
    - Create a new component `NodeEventDetailPane.tsx`.
    - Copy and adapt the event rendering logic from `EventDetailModal.tsx` into this new component, making it accept a single `event` prop. Remove modal-specific wrapper code.
    - In `NodeDetailModal`, conditionally render `NodeEventDetailPane` when `selectedEvent` is not null, passing the `selectedEvent` to it.

---

## 7. Implementation Tips and Potential Challenges

- **State Management:** Carefully consider where state should live. `selectedNodeId` likely belongs in `GraphCanvas`, while `selectedEvent` for the detail pane might live within `NodeDetailModal`.
- **Event Filtering Logic:** Getting the filtering logic right is crucial. Test it thoroughly with different event types where the node ID might be in different payload fields (e.g., `node_id`, `parent_node_id`). Start simple and refine.
- **Component Reuse:** Adapting the logic from `EventDetailModal.tsx` requires careful copying and modification, not direct import/reuse of the whole component. Focus on extracting the core rendering parts for individual events.
- **Performance:** Filtering a large list of events on every render can be slow. Using `React.useMemo` is a good first step. If performance becomes an issue later, a memoized Redux selector could be implemented.
- **Styling:** Use `react-bootstrap` components (like `Tabs`, `ListGroup`, `Card`) to structure the modal content clearly.
- **Debugging:** Use `console.log` liberally (e.g., `console.log({ node, nodeEvents, selectedEvent })`) and leverage React DevTools to inspect props, state, and Redux store contents.
- **Getting Stuck:** If you spend more than 30-60 minutes blocked on a specific issue, don't hesitate to ask for help or take a short break ("TOUCH GRASS"). Explain what you've tried and where you're seeing the problem.

---

## 8. Next Steps for Developers

- [x] Implement the steps outlined in Section 6.
- [ ] Fix remaining linter errors (e.g., import paths like `../app/store`, unused variables).
- [ ] Test the modal functionality thoroughly with various event types and node scenarios.
- [ ] Style the modal for clarity and usability (e.g., improve layout, potentially add tabs for metadata/events/details if needed).
- [ ] (Optional Refactor): Consider moving the event filtering logic into a memoized Redux selector if performance becomes a concern.
- [ ] (Optional Refactor): Add more detailed event rendering (e.g., full prompt/response viewers) to `NodeEventDetailPane` if required, potentially by further adapting logic from `EventDetailModal` or creating new sub-components.
- [ ] Document any new components or complex helper functions created (already done for the main components).

---

## 9. Key Resources

- [ttmp/2025-04-17/04-long-term-document--event-logging-system.md](../2025-04-17/04-long-term-document--event-logging-system.md): Full event system architecture and event type reference.
- `ui-react/src/features/events/eventsApi.ts`: Event types, event store, and RTK Query logic.
- `ui-react/src/features/graph/graphSlice.ts`: Node/edge state and actions.
- `ui-react/src/features/graph/selectors.ts`: Node/edge selectors.
- `ui-react/src/components/EventDetailModal.tsx`: Event detail modal UI logic (for adaptation).
- `ui-react/src/components/GraphCanvas.tsx`, `CustomNode.tsx`: Graph rendering and node click handling.
- `ui-react/src/components/NodeDetailModal.tsx`: **(New)** The main modal component.
- `ui-react/src/components/NodeEventDetailPane.tsx`: **(New)** Renders details for a single event.

---

## 10. Saving Future Research

- Save all future research, findings, and design notes in `ttmp/YYYY-MM-DD/0X-XXX.md` as per project conventions.
