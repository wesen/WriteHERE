import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path: str = "events.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        logger.info(f"Initializing DatabaseManager with path: {self.db_path}")
        self._ensure_db()

    def _ensure_db(self):
        """Creates database and tables if they don't exist."""
        logger.info(f"Ensuring database schema exists at {self.db_path}")
        create_tables_sql = """
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
            -- Cannot have FK to root_node_id as it might not exist yet during insert
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

        -- Index for efficient querying
        CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_events_node_id ON events(node_id);

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
        """

        create_views_sql = """
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
        """

        try:
            # Ensure directory exists
            db_file = Path(self.db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            logger.info("Database connection established.")
            # Enable foreign keys and WAL mode for better concurrency
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode=WAL")
            logger.info("Foreign keys and WAL mode enabled.")
            # Create tables
            self.conn.executescript(create_tables_sql)
            logger.info("Tables created or verified.")
            # Create views
            self.conn.executescript(create_views_sql)
            logger.info("Views created or verified.")
            self.conn.commit()
            logger.info("Database schema initialized successfully.")
        except sqlite3.Error as e:
            logger.error(
                f"SQLite error during database initialization: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing database: {e}", exc_info=True)
            raise

    def store_event(self, event: Dict):
        """Stores a single event and updates related tables."""
        if not self.conn:
            logger.error("Database connection is not available. Cannot store event.")
            return

        event_type = event.get("event_type")
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        node_id = payload.get("node_id")  # Node ID might be in payload for some events

        if not run_id:
            logger.warning(f"Event missing run_id: {event.get('event_id')}")
            # Decide if we should still store it or skip
            # For now, let's skip if run_id is missing
            return

        # Insert event first
        try:
            event_sql = """
            INSERT INTO events (event_id, run_id, event_type, timestamp, payload, node_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            self.conn.execute(
                event_sql,
                (
                    event.get("event_id"),
                    run_id,
                    event_type,
                    event.get("timestamp"),
                    json.dumps(payload),  # Store original payload
                    node_id,  # Store node_id if present in payload
                ),
            )
            # logger.debug(f"Stored event: {event.get('event_id')} ({event_type})")
        except sqlite3.Error as e:
            logger.error(
                f"Error storing event {event.get('event_id')}: {e}", exc_info=True
            )
            # Don't raise - we don't want to break the main event flow

        # Handle specific event types to update other tables
        try:
            if event_type == "run_started":
                self._handle_run_started(event)
            elif event_type == "run_finished":
                self._handle_run_finished(event)
            elif event_type == "run_error":
                self._handle_run_error(event)
            elif event_type == "node_created":
                self._handle_node_created(event)
            elif event_type == "node_status_changed":
                # Also update node table status
                self._handle_node_status_changed(event)
            elif event_type == "node_result_available":
                # Also update node table result
                self._handle_node_result_available(event)
            elif event_type == "edge_added":
                self._handle_edge_added(event)

            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(
                f"Error processing event side effects ({event_type}, ID: {event.get('event_id')}): {e}",
                exc_info=True,
            )
            try:
                self.conn.rollback()  # Rollback changes from this event's side effects
            except sqlite3.Error as rb_err:
                logger.error(f"Error rolling back transaction: {rb_err}")

    def _handle_run_started(self, event: Dict):
        """Creates a new run record."""
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        timestamp = event.get("timestamp")
        # Check if root_node_id is available in the run_started payload?
        # Assuming not for now, will be set later if needed.
        sql = """
        INSERT INTO runs (run_id, start_time, status)
        VALUES (?, ?, 'running')
        ON CONFLICT(run_id) DO UPDATE SET
            start_time = excluded.start_time,
            status = excluded.status,
            updated_at = CURRENT_TIMESTAMP
        """
        if self.conn:
            self.conn.execute(sql, (run_id, timestamp))
            logger.info(f"Run started/updated in DB: {run_id}")
        else:
            logger.error(
                "Database connection is not available. Cannot store run started event."
            )

    def _handle_run_finished(self, event: Dict):
        """Updates run record on successful completion."""
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        timestamp = event.get("timestamp")
        sql = """
        UPDATE runs
        SET status = 'completed',
            end_time = ?,
            total_steps = ?,
            total_nodes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE run_id = ?
        """
        if self.conn:
            self.conn.execute(
                sql,
                (
                    timestamp,
                    payload.get("total_steps"),
                    payload.get("total_nodes"),
                    run_id,
                ),
            )
            logger.info(f"Run finished in DB: {run_id}")
        else:
            logger.error(
                "Database connection is not available. Cannot store run finished event."
            )

    def _handle_run_error(self, event: Dict):
        """Updates run record on error."""
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        timestamp = event.get("timestamp")
        sql = """
        UPDATE runs
        SET status = 'error',
            end_time = ?,
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE run_id = ?
        """
        if self.conn:
            self.conn.execute(sql, (timestamp, payload.get("error_message"), run_id))
            logger.warning(f"Run error recorded in DB: {run_id}")
        else:
            logger.error(
                "Database connection is not available. Cannot store run error event."
            )

    def _handle_node_created(self, event: Dict):
        """Inserts a new node record."""
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        node_id = payload.get("node_id")

        if not node_id:
            logger.warning(
                f"node_created event missing node_id: {event.get('event_id')}"
            )
            return

        # Determine initial status - assume 'READY' or extract if available
        initial_status = payload.get("initial_status", "READY")  # Default assumption

        sql = """
        INSERT INTO nodes (node_id, run_id, node_nid, node_type, task_type, task_goal, status, layer, outer_node_id, root_node_id, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(node_id) DO UPDATE SET
            node_nid = excluded.node_nid,
            node_type = excluded.node_type,
            task_type = excluded.task_type,
            task_goal = excluded.task_goal,
            -- Don't overwrite status, layer, etc. on conflict? Or should we? Depends on idempotency needs. Let's update.
            status = excluded.status,
            layer = excluded.layer,
            outer_node_id = excluded.outer_node_id,
            root_node_id = excluded.root_node_id,
            metadata = excluded.metadata,
            updated_at = CURRENT_TIMESTAMP
            -- run_id should not change
        """
        # Extract metadata if needed - for now, just store full payload? No, extract known fields.
        metadata = {
            k: v
            for k, v in payload.items()
            if k
            not in [
                "node_id",
                "run_id",
                "node_nid",
                "node_type",
                "task_type",
                "task_goal",
                "status",
                "layer",
                "outer_node_id",
                "root_node_id",
                "result",
            ]
        }

        if self.conn:
            self.conn.execute(
                sql,
                (
                    node_id,
                    run_id,
                    payload.get("node_nid"),
                    payload.get("node_type"),
                    payload.get("task_type"),
                    payload.get("task_goal"),
                    initial_status,  # Use initial status
                    payload.get("layer"),
                    payload.get("outer_node_id"),
                    payload.get("root_node_id"),  # Assuming root_node_id is in payload
                    json.dumps(metadata) if metadata else None,
                ),
            )
            logger.debug(f"Node created/updated in DB: {node_id}")
        else:
            logger.error(
                "Database connection is not available. Cannot store node created event."
            )

        # If this is the root node (layer 0), update the run record
        if payload.get("layer") == 0:
            update_run_sql = "UPDATE runs SET root_node_id = ? WHERE run_id = ?"
            if self.conn:
                self.conn.execute(update_run_sql, (node_id, run_id))
                logger.info(f"Set root_node_id for run {run_id} to {node_id}")
            else:
                logger.error(
                    "Database connection is not available. Cannot store node created event."
                )

    def _handle_node_status_changed(self, event: Dict):
        """Updates node status."""
        payload = event.get("payload", {})
        node_id = payload.get("node_id")
        new_status = payload.get("new_status")

        if not node_id or not new_status:
            logger.warning(
                f"node_status_changed event missing node_id or new_status: {event.get('event_id')}"
            )
            return

        sql = """
        UPDATE nodes
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE node_id = ?
        """
        if self.conn:
            cursor = self.conn.execute(sql, (new_status, node_id))
            if cursor.rowcount == 0:
                logger.warning(
                    f"Tried to update status for non-existent node_id {node_id} from event {event.get('event_id')}"
                )
            else:
                logger.debug(f"Node status updated in DB: {node_id} -> {new_status}")
        else:
            logger.error(
                "Database connection is not available. Cannot store node status changed event."
            )

    def _handle_node_result_available(self, event: Dict):
        """Updates node result."""
        payload = event.get("payload", {})
        node_id = payload.get("node_id")
        # Assuming the result is in the payload, maybe under 'result' or 'result_summary'?
        # Let's assume the *full* result should be stored if available, otherwise summary.
        result_data = payload.get("result", payload.get("result_summary"))

        if not node_id:
            logger.warning(
                f"node_result_available event missing node_id: {event.get('event_id')}"
            )
            return

        sql = """
        UPDATE nodes
        SET result = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE node_id = ?
        """
        if self.conn:
            cursor = self.conn.execute(
                sql,
                (json.dumps(result_data) if result_data is not None else None, node_id),
            )
            if cursor.rowcount == 0:
                logger.warning(
                    f"Tried to update result for non-existent node_id {node_id} from event {event.get('event_id')}"
                )
            else:
                logger.debug(f"Node result updated in DB: {node_id}")
        else:
            logger.error(
                "Database connection is not available. Cannot store node result available event."
            )

    def _handle_edge_added(self, event: Dict):
        """Inserts a new edge record."""
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        parent_node_id = payload.get("parent_node_id")
        child_node_id = payload.get("child_node_id")

        if not all([run_id, parent_node_id, child_node_id]):
            logger.warning(
                f"edge_added event missing required IDs: {event.get('event_id')}"
            )
            return

        sql = """
        INSERT INTO edges (run_id, parent_node_id, child_node_id, parent_nid, child_nid, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        # Extract metadata if needed
        metadata = {
            k: v
            for k, v in payload.items()
            if k
            not in [
                "run_id",
                "parent_node_id",
                "child_node_id",
                "parent_nid",
                "child_nid",
            ]
        }

        if self.conn:
            self.conn.execute(
                sql,
                (
                    run_id,
                    parent_node_id,
                    child_node_id,
                    payload.get("parent_node_nid"),
                    payload.get("child_node_nid"),
                    json.dumps(metadata) if metadata else None,
                ),
            )
            logger.debug(
                f"Edge added in DB: {payload.get('parent_node_nid')} -> {payload.get('child_node_nid')}"
            )
        else:
            logger.error(
                "Database connection is not available. Cannot store edge added event."
            )

    def get_latest_run_events(self) -> List[Dict]:
        """Retrieves all events from the latest run (non-error)."""
        if not self.conn:
            return []
        sql = """
        SELECT e.event_id, e.run_id, e.event_type, e.timestamp, e.payload
        FROM events e
        JOIN (
            SELECT run_id
            FROM runs
            ORDER BY start_time DESC
            LIMIT 1
        ) latest_run ON e.run_id = latest_run.run_id
        ORDER BY e.timestamp ASC, e.id ASC -- Use id as tie-breaker for same timestamp
        """
        try:
            cursor = self.conn.execute(sql)
            events = []
            for row in cursor:
                try:
                    payload = json.loads(row[4]) if row[4] else {}
                    event = {
                        "event_id": row[0],
                        "run_id": row[1],
                        "event_type": row[2],
                        "timestamp": row[3],
                        "payload": payload,
                    }
                    events.append(event)
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to decode payload for event {row[0]} in latest run."
                    )
            logger.info(f"Retrieved {len(events)} events for the latest run.")
            return events
        except sqlite3.Error as e:
            logger.error(f"Error retrieving latest run events: {e}", exc_info=True)
            return []

    def get_latest_run_graph(self) -> Tuple[List[Dict], List[Dict]]:
        """Retrieves nodes and edges from the latest run."""
        if not self.conn:
            return [], []
        nodes_sql = """
        SELECT n.node_id, n.run_id, n.node_nid, n.node_type, n.task_type, n.task_goal, n.status, n.layer, n.outer_node_id, n.root_node_id, n.result, n.metadata
        FROM nodes n
        JOIN (
             SELECT run_id FROM runs ORDER BY start_time DESC LIMIT 1
        ) latest_run ON n.run_id = latest_run.run_id
        """
        edges_sql = """
        SELECT e.parent_node_id, e.child_node_id, e.parent_nid, e.child_nid, e.metadata
        FROM edges e
        JOIN (
             SELECT run_id FROM runs ORDER BY start_time DESC LIMIT 1
        ) latest_run ON e.run_id = latest_run.run_id
        """
        nodes = []
        edges = []
        try:
            # Fetch nodes
            cursor_nodes = self.conn.execute(nodes_sql)
            node_cols = [desc[0] for desc in cursor_nodes.description]
            for row in cursor_nodes:
                node = dict(zip(node_cols, row))
                # Decode JSON fields
                if node.get("result"):
                    node["result"] = json.loads(node["result"])
                if node.get("metadata"):
                    node["metadata"] = json.loads(node["metadata"])
                nodes.append(node)

            # Fetch edges
            cursor_edges = self.conn.execute(edges_sql)
            edge_cols = [desc[0] for desc in cursor_edges.description]
            for row in cursor_edges:
                edge = dict(zip(edge_cols, row))
                # Decode JSON fields
                if edge.get("metadata"):
                    edge["metadata"] = json.loads(edge["metadata"])
                edges.append(edge)

            logger.info(
                f"Retrieved {len(nodes)} nodes and {len(edges)} edges for the latest run."
            )
            return nodes, edges
        except sqlite3.Error as e:
            logger.error(f"Error retrieving latest run graph: {e}", exc_info=True)
            return [], []
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from graph data: {e}", exc_info=True)
            # Return partially loaded data? Or empty? Let's return empty for safety.
            return [], []

    def close(self):
        """Closes the database connection."""
        if self.conn:
            try:
                # Commit any pending changes and optimize before closing
                self.conn.commit()
                # Optional: Optimize DB on close? Might be slow.
                # logger.info("Optimizing database before closing...")
                # self.conn.execute("PRAGMA optimize;")
                self.conn.close()
                self.conn = None
                logger.info("Database connection closed successfully.")
            except sqlite3.Error as e:
                logger.error(f"Error closing database connection: {e}", exc_info=True)


# Example usage (for testing)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    )
    db_manager = DatabaseManager("test_run_events.db")

    # Simulate events
    run_id = "run-" + Path("test_run_events.db").stem  # Example run ID

    run_start_event = {
        "event_id": "evt-run-start",
        "run_id": run_id,
        "event_type": "run_started",
        "timestamp": "2024-01-01T10:00:00Z",
        "payload": {"config": "test"},
    }
    node1_created_event = {
        "event_id": "evt-node1-create",
        "run_id": run_id,
        "event_type": "node_created",
        "timestamp": "2024-01-01T10:00:01Z",
        "payload": {
            "node_id": "node-1",
            "node_nid": "1",
            "node_type": "PLAN",
            "task_type": "ROOT",
            "task_goal": "Root Goal",
            "layer": 0,
            "root_node_id": "node-1",
            "status": "READY",
        },
    }
    node2_created_event = {
        "event_id": "evt-node2-create",
        "run_id": run_id,
        "event_type": "node_created",
        "timestamp": "2024-01-01T10:00:02Z",
        "payload": {
            "node_id": "node-2",
            "node_nid": "1.1",
            "node_type": "EXECUTE",
            "task_type": "SUBTASK",
            "task_goal": "Sub Goal",
            "layer": 1,
            "root_node_id": "node-1",
            "outer_node_id": "node-1",
            "status": "READY",
        },
    }
    edge_added_event = {
        "event_id": "evt-edge-add",
        "run_id": run_id,
        "event_type": "edge_added",
        "timestamp": "2024-01-01T10:00:03Z",
        "payload": {
            "parent_node_id": "node-1",
            "child_node_id": "node-2",
            "parent_nid": "1",
            "child_nid": "1.1",
        },
    }
    node2_status_event = {
        "event_id": "evt-node2-status",
        "run_id": run_id,
        "event_type": "node_status_changed",
        "timestamp": "2024-01-01T10:00:04Z",
        "payload": {"node_id": "node-2", "old_status": "READY", "new_status": "DOING"},
    }
    run_finish_event = {
        "event_id": "evt-run-finish",
        "run_id": run_id,
        "event_type": "run_finished",
        "timestamp": "2024-01-01T10:00:05Z",
        "payload": {"total_steps": 10, "total_nodes": 2},
    }

    logger.info("Storing simulated events...")
    db_manager.store_event(run_start_event)
    db_manager.store_event(node1_created_event)
    db_manager.store_event(node2_created_event)
    db_manager.store_event(edge_added_event)
    db_manager.store_event(node2_status_event)
    db_manager.store_event(run_finish_event)
    logger.info("Finished storing events.")

    logger.info("Retrieving latest run events...")
    latest_events = db_manager.get_latest_run_events()
    logger.info(f"Retrieved {len(latest_events)} events.")
    # for event in latest_events: logger.info(event)

    logger.info("Retrieving latest run graph...")
    latest_nodes, latest_edges = db_manager.get_latest_run_graph()
    logger.info(f"Retrieved {len(latest_nodes)} nodes and {len(latest_edges)} edges.")
    # logger.info("Nodes:")
    # for node in latest_nodes: logger.info(node)
    # logger.info("Edges:")
    # for edge in latest_edges: logger.info(edge)

    db_manager.close()
    # Clean up test db
    # Path("test_run_events.db").unlink()
