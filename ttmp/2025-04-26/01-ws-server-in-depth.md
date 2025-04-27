# WebSocket Server for Recursive Agent Event Logging: Technical Specification

This document provides a comprehensive description of the WebSocket server used in the Recursive Agent Event Logging System, including its API endpoints, event types, database schema, and behavior. The specification is intended to guide a complete port of the server to Go as a drop-in replacement.

## 1. System Overview

The WebSocket server (`ws_server.py`) serves as the central component of the event logging system, with the following responsibilities:

1. Listen to a Redis stream for real-time agent events
2. Store events in a SQLite database
3. Maintain in-memory state of events and graph structure
4. Serve a React UI via static files
5. Provide API endpoints for querying event and graph data
6. Stream events to connected WebSocket clients

## 2. Configuration

### 2.1 Configuration Parameters

The server uses the following configuration parameters, defined in `ServerConfig`:

| Parameter       | Type    | Default                | Environment Variable   | Description                               |
|-----------------|---------|------------------------|------------------------|-------------------------------------------|
| redis_url       | string  | "redis://localhost:6379/0" | REDIS_URL         | URL for Redis connection                  |
| event_stream    | string  | "agent_events"        | EVENT_STREAM           | Redis stream name to read from            |
| host            | string  | "0.0.0.0"             | WS_HOST                | Host to bind server to                    |
| port            | int     | 9999                  | WS_PORT                | Port to bind server to                    |
| db_path         | string  | "runs/events.db"      | SQLITE_DB_PATH         | Path to SQLite database                   |
| reload_session  | bool    | false                 | RELOAD_LATEST_SESSION  | Whether to load latest session on startup |
| log_level       | string  | "INFO"                | LOG_LEVEL              | Server log level                          |
| debug           | bool    | false                 | DEBUG                  | Enable debug mode                         |

## 3. API Endpoints

### 3.1 WebSocket Endpoint

| Endpoint     | Type     | Description                               |
|--------------|----------|-------------------------------------------|
| `/ws/events` | WebSocket | Main event stream endpoint                |

WebSocket clients connect to this endpoint to receive real-time events. When a new client connects:
1. The server accepts the connection
2. If `reload_session=true`, the server sends historical events from the latest run (loaded from DB)
3. The server adds the client to the active connections set
4. The server listens for disconnect events (no request handling)
5. All future events from Redis are broadcasted to this client

### 3.2 HTTP API Endpoints

| Endpoint                | Method | Description                                  |
|-------------------------|--------|----------------------------------------------|
| `/api/events`           | GET    | Get all events in EventStateManager          |
| `/api/graph`            | GET    | Get complete graph state                     |
| `/api/graph/nodes`      | GET    | Get all nodes in GraphStateManager           |
| `/api/graph/nodes/{id}` | GET    | Get a specific node by ID                    |
| `/api/graph/edges`      | GET    | Get all edges in GraphStateManager           |
| `/api/graph/edges/{id}` | GET    | Get a specific edge by ID                    |
| `/{path}`               | GET    | Serve React UI static files or index.html    |

## 4. Database Schema

The SQLite database schema consists of four tables:

### 4.1 `events` Table
```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,          -- UUID from original event
    run_id TEXT NOT NULL,            -- Groups events by agent run
    event_type TEXT NOT NULL,        -- One of the event types
    timestamp TEXT NOT NULL,         -- ISO format timestamp
    payload JSON NOT NULL,           -- Full event payload as JSON
    node_id TEXT,                    -- Optional link to related node (from payload)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_run_id ON events(run_id);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_node_id ON events(node_id);
```

### 4.2 `runs` Table
```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,        -- From run_started event
    end_time TEXT,                   -- From run_finished event
    status TEXT NOT NULL,            -- 'running', 'completed', 'error'
    total_steps INTEGER,
    total_nodes INTEGER,
    error_message TEXT,              -- If status is 'error'
    root_node_id TEXT,               -- Link to root node of the run
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_runs_start_time ON runs(start_time);
```

### 4.3 `nodes` Table
```sql
CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,        -- UUID of the node
    run_id TEXT NOT NULL,            -- Link to parent run
    node_nid TEXT NOT NULL,          -- Hierarchical ID (e.g., "1.2.3")
    node_type TEXT NOT NULL,         -- PLAN_NODE, EXECUTE_NODE, etc.
    task_type TEXT NOT NULL,         -- COMPOSITION, REASONING, etc.
    task_goal TEXT NOT NULL,         -- Node's goal/purpose
    status TEXT NOT NULL,            -- Current node status (updated by events)
    layer INTEGER NOT NULL,          -- Node's depth in the tree
    outer_node_id TEXT,              -- Parent node in hierarchy (if any)
    root_node_id TEXT NOT NULL,      -- Top-level node of this branch
    result JSON,                     -- Node's final output (if any, updated by events)
    metadata JSON,                   -- Additional node properties from creation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (outer_node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_nodes_run_id ON nodes(run_id);
CREATE INDEX idx_nodes_nid ON nodes(node_nid);
CREATE INDEX idx_nodes_outer ON nodes(outer_node_id);
CREATE INDEX idx_nodes_root ON nodes(root_node_id);
CREATE INDEX idx_nodes_status ON nodes(status);
```

### 4.4 `edges` Table
```sql
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,            -- Link to parent run
    parent_node_id TEXT NOT NULL,    -- Source node
    child_node_id TEXT NOT NULL,     -- Target node
    parent_nid TEXT NOT NULL,        -- Parent's hierarchical ID
    child_nid TEXT NOT NULL,         -- Child's hierarchical ID
    metadata JSON,                   -- Edge properties (if any)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (parent_node_id) REFERENCES nodes(node_id),
    FOREIGN KEY (child_node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_edges_run ON edges(run_id);
CREATE INDEX idx_edges_parent ON edges(parent_node_id);
CREATE INDEX idx_edges_child ON edges(child_node_id);
CREATE INDEX idx_edges_nids ON edges(parent_nid, child_nid);
```

## 5. Event Types

The system uses 16 event types, defined as:

1. `run_started` - When an agent run begins
2. `run_finished` - When an agent run completes successfully 
3. `run_error` - When an agent run encounters an error
4. `step_started` - When a new execution step begins
5. `step_finished` - When an execution step completes
6. `node_status_changed` - When a node transitions to a new status
7. `llm_call_started` - When an LLM API call begins
8. `llm_call_completed` - When an LLM API call completes
9. `tool_invoked` - When a tool is invoked by an agent
10. `tool_returned` - When a tool returns a result
11. `node_created` - When a new node is instantiated
12. `plan_received` - When a node receives a raw plan before graph building
13. `node_added` - When a node is added to a graph instance
14. `edge_added` - When an edge is added between nodes
15. `inner_graph_built` - When a node finishes building its inner graph
16. `node_result_available` - When a node computes its final result

### 5.1 Event Schema

All events follow this common schema:

```json
{
  "event_id": "uuid-string",
  "timestamp": "2025-04-16T10:30:45.123Z",
  "event_type": "one_of_event_types",
  "payload": {
    /* Event-specific data fields */
  },
  "run_id": "agent-run-uuid"
}
```

### 5.2 Event Payload Examples

#### run_started
```json
{
  "input_data": {
    "filename": "path/to/input.jsonl",
    "data": [
      { "id": "task-1", "prompt": "..." },
      { "id": "task-2", "prompt": "..." }
    ]
  },
  "config": {
    "model": "gpt-4o",
    "engine_backend": "google",
    /* Other configuration properties */
  },
  "run_mode": "report|story",
  "timestamp_utc": "2025-04-22T10:00:00.000Z"
}
```

#### step_started
```json
{
  "step": 42,
  "node_id": "node-uuid-string",
  "task_type": "REASONING",
  "node_goal": "Analyze customer feedback data",
  "root_id": "root-node-uuid-string"
}
```

#### node_created
```json
{
  "node_id": "uuid-string",
  "node_nid": "1.2",
  "node_type": "PLAN_NODE",
  "task_type": "COMPOSITION",
  "task_goal": "Goal description...",
  "layer": 2,
  "outer_node_id": "uuid-string" | null,
  "root_node_id": "uuid-string", 
  "initial_parent_nids": ["1.1", "0.3"],
  "step": 42
}
```

#### edge_added
```json
{
  "graph_owner_node_id": "uuid-string",
  "parent_node_id": "uuid-string",
  "child_node_id": "uuid-string",
  "parent_node_nid": "1.2",
  "child_node_nid": "1.3",
  "step": 42
}
```

## 6. State Managers

The server maintains two in-memory state managers:

### 6.1 EventStateManager

Stores the most recent events for the current run (or loaded from DB on startup).

```python
class EventStateManager:
    def __init__(self, max_events: int = 200):
        self.state = EventState()  # Contains events list
        self.max_events = max_events
        self._lock = asyncio.Lock()

    async def add_event(self, event: dict): ...
    async def clear_events(self): ...
    async def get_events(self, limit: Optional[int] = None) -> List[dict]: ...
    def get_state(self) -> dict: ...
```

The `get_state()` method returns a dictionary with format:
```json
{
  "status": "Connected",
  "events": [
    /* List of event objects, newest first */
  ]
}
```

### 6.2 GraphStateManager

Maintains the current graph structure of nodes and edges, updated by relevant events or loaded directly from DB on startup.

```python
class GraphStateManager:
    def __init__(self):
        self.state = GraphState()  # Contains nodes and edges
        self._lock = asyncio.Lock()

    async def load_state_from_db(self, nodes_data: List[Dict], edges_data: List[Dict]): ...
    async def process_event(self, event: dict): ...
    async def _handle_node_created(self, payload: dict): ...
    async def _handle_node_status_changed(self, payload: dict): ...
    async def _handle_edge_added(self, payload: dict): ...
    async def _add_node(self, node: NodeState): ...
    async def _add_edge(self, edge: EdgeState): ...
    def get_graph_state(self): ...
    def get_node(self, node_id: str): ...
    def get_edge(self, edge_id: str): ...
    def get_nodes(self): ...
    def get_edges(self): ...
```

The `get_graph_state()` method returns a dictionary with format:
```json
{
  "graph": {
    "nodes": {
      "ids": ["node1", "node2", ...],
      "entities": {
        "node1": {
          "id": "node1",
          "nid": "1.2",
          "type": "PLAN_NODE",
          "goal": "Goal description...",
          "layer": 2,
          "taskType": "COMPOSITION",
          "status": "DOING"
        },
        /* More nodes */
      }
    },
    "edges": {
      "ids": ["node1-node2", ...],
      "entities": {
        "node1-node2": {
          "id": "node1-node2",
          "parent": "node1",
          "child": "node2"
        },
        /* More edges */
      }
    }
  }
}
```

## 7. Server Lifecycle

### 7.1 Startup Sequence

1. Initialize configuration from environment variables
2. Set up logging
3. Initialize the database connection and ensure schema exists
4. If `reload_session=true`:
   a. Load the latest run's graph structure (nodes, edges) directly from DB
   b. Populate `GraphStateManager` with this data
   c. Load the latest run's events from DB
   d. Populate `EventStateManager` with these events
   e. Store events for broadcasting to new clients
5. Connect to Redis
6. Start the Redis listener task in the background
7. Start serving the FastAPI app (with static files and API endpoints)

### 7.2 Redis Listener Behavior

The Redis listener runs as a background task that:

1. Listens to the Redis stream (XREAD) starting from latest message
2. For each event received:
   a. Stores the event in the SQLite database
   b. Updates the in-memory `EventStateManager`
   c. Updates the in-memory `GraphStateManager` for graph-relevant events
   d. Broadcasts the raw event string to all connected WebSocket clients
3. Handles disconnections and reconnection attempts with backoff
4. Continues until the server shuts down

### 7.3 Shutdown Sequence

1. Cancel the Redis listener task
2. Close the database connection
3. Close all WebSocket connections

## 8. Client Communication

### 8.1 WebSocket Message Format

Messages sent over WebSocket are raw JSON strings representing individual events. The UI is expected to parse these strings into JSON objects.

Example message:
```json
{
  "event_id": "uuid-string",
  "timestamp": "2025-04-16T10:30:45.123Z",
  "event_type": "node_status_changed",
  "payload": {
    "node_id": "node-uuid-string",
    "node_goal": "Generate conclusion paragraph",
    "old_status": "PLANNING",
    "new_status": "DOING",
    "step": 42,
    "task_type": "COMPOSITION"
  },
  "run_id": "agent-run-uuid"
}
```

### 8.2 WebSocket Connection Flow

1. Client connects to `/ws/events`
2. Server accepts the connection
3. If `reload_session=true` and historical events are available, server sends each historical event to the client
4. Server adds client to active connections
5. Server broadcasts all future events from Redis to the client
6. Server detects disconnection and removes client from active connections

## 9. Error Handling

The server implements error handling at multiple levels:

1. Redis connection errors: Attempt reconnection with backoff
2. JSON decode errors: Log error and continue to next event
3. Database errors: Log error, attempt to continue; rollback transactions if needed
4. WebSocket client errors: Remove problematic clients from active connections
5. Server startup errors: Log critical errors, prevent server from starting in bad state

## 10. Implementation Notes for Go Port

### 10.1 Key Dependencies

The Python implementation uses these key libraries:
- FastAPI for HTTP/WebSocket server
- Redis/redis.asyncio for Redis stream access
- SQLite for database
- Uvicorn for ASGI server

For a Go implementation, consider:
- pure http server for HTTP routing
- gorilla/websocket for WebSocket support
- go-redis for Redis operations
- SQLite3 driver for Go
- zerolog for structured logging
- cobra for CLI
- errgroup for concurrent operations
