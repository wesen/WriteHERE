# Implementing Visual Nesting for Task Graphs in the UI

## 1. Introduction: The Goal

This document details the implementation of a visually nested graph structure in the Recursive Agent UI. The primary goal was to accurately represent the hierarchical relationship between "outer" planning nodes (PLAN_NODE) and their corresponding "inner" subtask nodes, as defined in the agent's core task graph logic (`recursive/node/abstract.py` and `recursive/graph.py`).

Specifically, we wanted to visually group the inner nodes _within_ a distinct container associated with their outer node, similar to how nested structures are often represented in diagrams. This provides a clearer visual hierarchy than simply drawing standard dependency edges.

_(Example Diagram of Target State - showing node '2' as a container)_
![Target Diagram](./nested-graph-example.png) _(Note: Assumes image is stored alongside markdown)_

## 2. The Challenge: Initial Approach vs. Desired Visuals

Our backend task graph model has two key relationships:

1.  **Dependency**: Parent -> Child (Rendered as standard edges).
2.  **Hierarchy**: Outer Node -> Inner Graph (Nodes within `node.inner_graph`).

The initial UI implementation focused on rendering dependencies as edges. An attempt was made to represent the hierarchy by simply styling the outer nodes differently when they contained inner nodes. However, this didn't create the desired effect of a visual _container_ wrapping the inner nodes. The requirement was to have a clear box drawn _around_ the inner nodes, visually separating them as a distinct subgraph belonging to the outer node.

## 3. The Solution: Virtual Container Nodes

To achieve the desired visual grouping without altering the fundamental data structure from the backend, we introduced the concept of **virtual container nodes** purely within the frontend's data transformation layer (`reaflowAdapter.ts`).

The core idea is:

1.  Keep the original outer and inner nodes as received from the backend events.
2.  For every _original_ outer node that has inner nodes, dynamically insert a _new, virtual_ node into the list of nodes passed to the Reaflow layout engine.
3.  This virtual node is designated as a `container` type.
4.  Structure the parent/child relationships for Reaflow as follows:
    - Virtual Container Node's `parent` = Original Outer Node ID
    - Inner Node's `parent` = Virtual Container Node ID
5.  Edges _between_ inner nodes (within the same container) also have their `parent` property set to the Virtual Container Node ID.
6.  Style the virtual container node distinctively (e.g., as a box) using CSS.
7.  Let Reaflow's layout engine (`ELK`) handle the positioning and sizing, treating the virtual node as a parent container for the inner nodes.

This strategy allows the layout engine to create the visual box effect while keeping the underlying Redux state aligned with the backend's data model.

## 4. Implementation Deep Dive

Here's a breakdown of the code changes:

### 4.1. Tracking Inner Nodes (Backend Event -> Redux State)

- **File**: `ui-react/src/features/graph/graphSlice.ts`
- **Change**: Added an optional `inner_nodes` field (array of strings/node IDs) to the `Node` type definition.

  ```typescript
  // In graphSlice.ts
  export type Node = {
    // ... other fields
    inner_nodes?: string[]; // Array of node IDs part of this node's inner graph
  };
  ```

- **File**: `ui-react/src/features/events/eventsApi.ts`
- **Change**: Modified the WebSocket message handler (`onCacheEntryAdded`) to process the `inner_graph_built` event. When this event is received for a specific `node_id`, we dispatch a `graphNodeUpdated` action to populate the `inner_nodes` array for that node in the Redux store.

  ```typescript
  // In eventsApi.ts (inside ws.onmessage handler)
  case "inner_graph_built": {
    const p = msg.payload as InnerGraphBuiltPayload;
    // Update the parent node with its inner node IDs
    dispatch(
      graphNodeUpdated({
        id: p.node_id,
        changes: {
          inner_nodes: p.node_ids, // Store the list of inner node IDs
        },
      })
    );
    break;
  }
  ```

### 4.2. Adapting Data for Reaflow (`reaflowAdapter.ts`)

- **File**: `ui-react/src/features/graph/reaflowAdapter.ts`
- **Change**: The `selectReaflowGraph` selector was significantly refactored.

  - **Node Processing**:

    1.  Iterate through the original `nodes` from the Redux state.
    2.  For each original node, add it to a `finalNodes` array (which will be passed to Reaflow).
    3.  **Crucially**: If an original node `n` has `n.inner_nodes`, create a _new virtual node_.
        - ID: `${n.id}-container`
        - `parent`: `n.id` (The virtual node is a child of the _original_ node in Reaflow's hierarchy).
        - `data`: Minimal data, with `type: 'container'`.
        - `className`: `'node-container'` for specific CSS targeting.
        - Add this virtual node to `finalNodes`.
    4.  Keep track of the mapping from original outer node ID to its virtual container ID (`virtualNodeMap`).

  - **Parent Adjustment**:

    1.  Iterate through the original `nodes` _again_.
    2.  For each node `n`, determine its _original_ outer node ID (by checking which node's `inner_nodes` contains `n.id`).
    3.  If an outer node is found, retrieve the corresponding virtual container ID from `virtualNodeMap`.
    4.  Find the node `n` in the `finalNodes` array and update its `parent` property to the virtual container ID.

    ```typescript
    // Pseudocode for parent adjustment
    for each originalNode n:
      outerNodeId = find node p where p.inner_nodes includes n.id
      if outerNodeId exists:
        virtualId = virtualNodeMap.get(outerNodeId)
        reaflowNode = finalNodeMap.get(n.id)
        if reaflowNode and virtualId:
          reaflowNode.parent = virtualId
    ```

  - **Edge Processing**:
    1.  Iterate through the original `edges` from Redux.
    2.  For each edge, find the corresponding source and target nodes _in the `finalNodes` array_ (these nodes now have their `parent` property correctly set).
    3.  Check if both the source and target nodes share the _same parent ID_ and if that parent ID corresponds to a _virtual container_ (e.g., ends with `-container`).
    4.  If yes, set the edge's `parent` property to this virtual container ID and assign `className: 'edge-nested'`.
    5.  Otherwise, the edge connects top-level nodes or nodes between containers; leave its `parent` as `undefined` and assign `className: 'edge-hierarchy'`.

### 4.3. Rendering the Virtual Container (`CustomNode.tsx`)

- **File**: `ui-react/src/components/reaflow/CustomNode.tsx`
- **Change**: Added conditional rendering logic.

  - Check if `node.data?.type === 'container'`.
  - If true, render a simple `div` with the class `node-container-wrapper`. This div relies entirely on CSS for its appearance (the box).
  - If false, render the standard node content using the `NodeContent` component, wrapped in a `div` with class `node-wrapper`. Added `node-nested-content` class to the wrapper if the node has a parent (indicating it's inside a container).

  ```typescript
  // In CustomNode.tsx render method
  const isContainer = node.data?.type === 'container';

  return (
    <foreignObject ...>
      {isContainer ? (
         <div className={`node-container-wrapper ${node.className || ''}`} />
      ) : (
        <div className={`node-wrapper ${node.parent ? 'node-nested-content' : ''}`}>
          <NodeContent node={node as MyNodeData} ... />
          {/* Optional Add button logic */}
        </div>
      )}
    </foreignObject>
  );
  ```

### 4.4. Styling the Container and Nested Elements (`ReaflowCanvas.css`)

- **File**: `ui-react/src/components/reaflow/ReaflowCanvas.css`
- **Change**: Added new CSS rules.
  - `.node-container-wrapper`: Defines the appearance of the virtual container box (background, border, border-radius). `pointer-events: none` is important so clicks go through the box to the nodes inside.
  - `.node-nested-content`: A class applied to the wrapper of nodes _inside_ a container. Currently, no specific styles are applied here, but it provides a hook for future styling adjustments if needed (e.g., removing borders that might double up with the container).
  - `.reaflow-edge.edge-nested path`: Styles edges _within_ a container (different color, dashed line).
  - `.reaflow-edge.edge-hierarchy path`: Styles edges _between_ top-level nodes or containers (standard solid grey line).

## 5. Expected Result

With these changes, the graph visualization should now:

1.  Display original outer nodes as standard nodes.
2.  Draw a visually distinct box (the styled virtual container node) positioned by the layout engine around the inner nodes corresponding to an outer node.
3.  Render the inner nodes _inside_ this box.
4.  Draw dashed, differently colored edges (`edge-nested`) between nodes _within_ the same container box.
5.  Draw standard solid edges (`edge-hierarchy`) between top-level nodes or between a node and a container (or between containers, if that hierarchy level exists).

This provides a much clearer and more intuitive representation of the task graph's hierarchical structure.

## 6. Future Considerations

- **Styling**: The container and nested edge styles can be further customized.
- **Deep Nesting**: The current logic assumes one level of virtual nesting. If the backend produces graphs where PLAN_NODEs can be nested within _other_ PLAN_NODEs' inner graphs, the adapter logic might need further recursion or adjustments to handle multi-level virtual containers correctly.
- **Performance**: For extremely large graphs, the extra virtual nodes and processing steps in the adapter could have a minor performance impact, though likely negligible for typical use cases. `createSelector` helps mitigate unnecessary recalculations.
