-- Base events table storing common fields
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,          -- UUID from original event
    run_id TEXT NOT NULL,            -- Groups events by agent run
    event_type TEXT NOT NULL,        -- One of the 14 event types
    timestamp TEXT NOT NULL,         -- ISO format timestamp
    payload JSON NOT NULL,           -- Full event payload as JSON
    node_id TEXT,                    -- Optional link to related node
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table to track runs for easier session management
CREATE TABLE IF NOT EXISTS runs (
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

-- Table to store nodes
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,        -- UUID of the node
    run_id TEXT NOT NULL,            -- Link to parent run
    node_nid TEXT NOT NULL,          -- Hierarchical ID (e.g., "1.2.3")
    node_type TEXT NOT NULL,         -- PLAN_NODE, EXECUTE_NODE, etc.
    task_type TEXT NOT NULL,         -- COMPOSITION, REASONING, etc.
    task_goal TEXT NOT NULL,         -- Node's goal/purpose
    status TEXT NOT NULL,            -- Current node status
    layer INTEGER NOT NULL,          -- Node's depth in the tree
    outer_node_id TEXT,              -- Parent node in hierarchy (if any)
    root_node_id TEXT NOT NULL,      -- Top-level node of this branch
    result JSON,                     -- Node's final output (if any)
    metadata JSON,                   -- Additional node properties
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (outer_node_id) REFERENCES nodes(node_id)
);

-- Table to store node relationships (edges)
CREATE TABLE IF NOT EXISTS edges (
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

-- Table to store raw planning data associated with a node
CREATE TABLE IF NOT EXISTS graph_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,              -- Node that received the plan
    raw_plan JSON NOT NULL,             -- The raw plan data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
);

-- Index for efficient querying
CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_node_id ON events(node_id);
-- Indices for payload fields used for pairing/linking
CREATE INDEX IF NOT EXISTS idx_events_payload_call_id ON events(json_extract(payload, '$.call_id'));
CREATE INDEX IF NOT EXISTS idx_events_payload_tool_call_id ON events(json_extract(payload, '$.tool_call_id'));

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_start_time ON runs(start_time);

CREATE INDEX IF NOT EXISTS idx_nodes_run_id ON nodes(run_id);
CREATE INDEX IF NOT EXISTS idx_nodes_nid ON nodes(node_nid);
CREATE INDEX IF NOT EXISTS idx_nodes_outer ON nodes(outer_node_id);
CREATE INDEX IF NOT EXISTS idx_nodes_root ON nodes(root_node_id);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);

CREATE INDEX IF NOT EXISTS idx_edges_run ON edges(run_id);
CREATE INDEX IF NOT EXISTS idx_edges_parent ON edges(parent_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_child ON edges(child_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_nids ON edges(parent_nid, child_nid);

CREATE INDEX IF NOT EXISTS idx_graph_plans_node ON graph_plans(node_id);

-- View for node status history
CREATE VIEW IF NOT EXISTS node_status_history AS
SELECT
    e.node_id,
    e.run_id,
    e.timestamp,
    json_extract(e.payload, '$.old_status') as old_status,
    json_extract(e.payload, '$.new_status') as new_status
FROM events e
WHERE e.event_type = 'node_status_changed'
ORDER BY e.timestamp;

-- View for node execution timeline
CREATE VIEW IF NOT EXISTS node_execution_timeline AS
SELECT
    n.node_id,
    n.run_id,
    n.node_nid,
    n.task_type,
    n.task_goal,
    MIN(CASE WHEN e.event_type = 'node_created' THEN e.timestamp END) as created_time,
    MIN(CASE WHEN e.event_type = 'step_started' AND json_extract(e.payload, '$.node_id') = n.node_id THEN e.timestamp END) as execution_start,
    MAX(CASE WHEN e.event_type = 'node_result_available' THEN e.timestamp END) as completion_time
FROM nodes n
LEFT JOIN events e ON n.node_id = json_extract(e.payload, '$.node_id') -- Join on payload node_id where available
GROUP BY n.node_id, n.run_id, n.node_nid, n.task_type, n.task_goal; 