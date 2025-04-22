# Server-Side Graph State Management and UI Synchronization

## Overview

This document outlines the implementation plan for adding server-side graph state management to the WebSocket server and synchronizing it with the React UI. The goal is to maintain a consistent graph state between server and client, allowing the UI to recover its state on page reloads while continuing to process real-time updates.

## Current Architecture

The system currently has two main components for graph state management:

1. **React/Redux UI (Client-Side)**:

   - Maintains graph state in Redux store using Redux Toolkit
   - Processes events in real-time via WebSocket connection
   - Graph state is lost on page reload
   - Implemented in `ui-react/src/features/events/eventsApi.ts`

2. **WebSocket Server (Server-Side)**:
   - Acts as a Redis event stream relay
   - No current state management
   - Implemented in `recursive/utils/ws_server.py`

## State Structure

The graph state follows this exact structure (matching the React implementation):

```python
{
    "graph": {
        "nodes": {
            "ids": [
                "node-uuid-1",
                "node-uuid-2",
                # ... more node IDs
            ],
            "entities": {
                "node-uuid-1": {
                    "id": "node-uuid-1",
                    "nid": "1",  # Node identifier in the tree
                    "type": "PLAN_NODE",  # PLAN_NODE or EXECUTE_NODE
                    "goal": "Node goal description",
                    "layer": 1,  # Layer in the tree
                    "taskType": "COMPOSITION",  # COMPOSITION, REASONING, or RETRIEVAL
                    "status": "READY"  # Optional status
                },
                # ... more nodes
            }
        },
        "edges": {
            "ids": [
                "parent-uuid-child-uuid",
                # ... more edge IDs
            ],
            "entities": {
                "parent-uuid-child-uuid": {
                    "id": "parent-uuid-child-uuid",
                    "parent": "parent-uuid",
                    "child": "child-uuid"
                },
                # ... more edges
            }
        }
    }
}
```

## Implementation Goals

1. **Server-Side Graph State**:

   - Mirror the Redux store's graph state structure exactly
   - Process the same event types that affect graph state
   - Maintain an in-memory graph structure
   - Persist graph state across client reconnections

2. **REST API**:

   - Expose graph state via HTTP endpoints
   - Allow UI to fetch initial state on load
   - Support querying graph structure and node details

3. **UI Enhancement**:
   - Modify UI to load initial state from REST API
   - Continue processing real-time updates via WebSocket
   - Handle state merging and conflict resolution

## Technical Design

### 1. Server-Side Graph State Manager

We'll create a new Python class `GraphStateManager` that exactly mirrors the Redux store structure:

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class NodeState:
    id: str
    nid: str
    type: str  # PLAN_NODE or EXECUTE_NODE
    goal: str
    layer: int
    taskType: str  # COMPOSITION, REASONING, or RETRIEVAL
    status: Optional[str] = None

@dataclass
class EdgeState:
    id: str  # Computed as f"{parent}-{child}"
    parent: str
    child: str

@dataclass
class NodesState:
    ids: List[str] = field(default_factory=list)
    entities: Dict[str, NodeState] = field(default_factory=dict)

@dataclass
class EdgesState:
    ids: List[str] = field(default_factory=list)
    entities: Dict[str, EdgeState] = field(default_factory=dict)

@dataclass
class GraphState:
    nodes: NodesState = field(default_factory=NodesState)
    edges: EdgesState = field(default_factory=EdgesState)

class GraphStateManager:
    def __init__(self):
        self.state = GraphState()
        self._lock = asyncio.Lock()
```

### 2. Event Processing

The server will process events to maintain this exact state structure:

```python
async def process_event(self, event: dict):
    event_type = event["event_type"]
    payload = event["payload"]

    async with self._lock:
        if event_type == "node_created":
            node = NodeState(
                id=payload["node_id"],
                nid=payload["node_nid"],
                type=payload["node_type"],
                goal=payload["task_goal"],
                layer=payload["layer"],
                taskType=payload["task_type"]
            )
            await self._add_node(node)

        elif event_type == "edge_added":
            edge_id = f"{payload['parent_node_id']}-{payload['child_node_id']}"
            edge = EdgeState(
                id=edge_id,
                parent=payload["parent_node_id"],
                child=payload["child_node_id"]
            )
            await self._add_edge(edge)
```

### 3. REST API Endpoints

FastAPI endpoints that return the exact state structure:

```python
@app.get("/api/graph")
async def get_graph():
    """Return complete graph state matching Redux store structure"""
    return {
        "graph": {
            "nodes": asdict(graph_manager.state.nodes),
            "edges": asdict(graph_manager.state.edges)
        }
    }

@app.get("/api/graph/nodes/{node_id}")
async def get_node(node_id: str):
    """Return specific node details"""
    if node_id in graph_manager.state.nodes.entities:
        return graph_manager.state.nodes.entities[node_id]
    raise HTTPException(status_code=404, detail="Node not found")

@app.get("/api/graph/edges")
async def get_edges():
    """Return all edges"""
    return graph_manager.state.edges.entities

@app.get("/api/graph/edges/{edge_id}")
async def get_edge(edge_id: str):
    """Return specific edge details"""
    if edge_id in graph_manager.state.edges.entities:
        return graph_manager.state.edges.entities[edge_id]
    raise HTTPException(status_code=404, detail="Edge not found")
```

Key endpoints:

- `/api/graph`: Full graph state
- `/api/graph/nodes`: List all nodes
- `/api/graph/nodes/{id}`: Get specific node
- `/api/graph/edges`: List all edges

### 4. UI Integration

The UI integration remains the same, but now we're guaranteed the state structure matches:

```typescript
// New Redux thunk
export const initializeGraphState = createAsyncThunk(
  "graph/initialize",
  async () => {
    const response = await fetch("/api/graph");
    return response.json();
  }
);

// In graph reducer
reducers: {
  initializeState: (state, action) => {
    // Merge server state with any existing state
    return {
      ...state,
      ...action.payload,
      initialized: true,
    };
  };
}
```

## Implementation Steps

1. **Server-Side Development**:

   - [ ] Create dataclass models for state structure
   - [ ] Implement `GraphStateManager` with exact Redux store structure
   - [ ] Add event processing methods
   - [ ] Add REST API endpoints
   - [ ] Add state serialization/deserialization

2. **UI Enhancements**:
   - [ ] Add graph initialization actions
   - [ ] Implement state merging logic
   - [ ] Add loading states for initial fetch
   - [ ] Update event processing to handle initialization

## Resources

- Current WebSocket server: `recursive/utils/ws_server.py`
- UI event handling: `ui-react/src/features/events/eventsApi.ts`
- Event documentation: `ttmp/2025-04-17/04-long-term-document--event-logging-system.md`
- Current state structure: `ttmp/2025-04-21/06-state.json`
