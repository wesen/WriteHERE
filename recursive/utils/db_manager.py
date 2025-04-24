import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

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

            # Add graph_plans table
            self.conn.execute(
                """
            CREATE TABLE IF NOT EXISTS graph_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                raw_plan JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (node_id) REFERENCES nodes(node_id)
            )"""
            )
            # Add index for graph_plans
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_graph_plans_node ON graph_plans(node_id)"
            )

            self.conn.commit()
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
        # Node ID might be in payload for some events, or directly in the node table for node-specific events
        node_id = payload.get("node_id")

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
                    node_id,  # Store node_id if present in payload for filtering/joining
                ),
            )
            # logger.debug(f"Stored event: {event.get('event_id')} ({event_type})")
        except sqlite3.Error as e:
            logger.error(
                f"Error storing event {event.get('event_id')}: {e}", exc_info=True
            )
            # Don't raise - we don't want to break the main event flow

        # Handle specific event types to update other tables (runs, nodes, edges, graph_plans)
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
                self._handle_node_status_changed(event)
            elif event_type == "node_result_available":
                self._handle_node_result_available(event)
            elif event_type == "edge_added":
                self._handle_edge_added(event)
            elif event_type == "plan_received":
                self._handle_plan_received(event)
            # Add handler for inner_graph_built
            elif event_type == "inner_graph_built":
                self._handle_inner_graph_built(event)
            # node_added no longer needs specific DB handler

            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(
                f"Error processing event side effects ({event_type}, ID: {event.get('event_id')}): {e}",
                exc_info=True,
            )
            try:
                if self.conn:  # Check conn before rollback
                    self.conn.rollback()  # Rollback changes from this event's side effects
            except sqlite3.Error as rb_err:
                logger.error(f"Error rolling back transaction: {rb_err}")

    def _handle_run_started(self, event: Dict):
        """Creates a new run record."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot store run started event."
            )
            return
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        timestamp = event.get("timestamp")
        sql = """
        INSERT INTO runs (run_id, start_time, status)
        VALUES (?, ?, 'running')
        ON CONFLICT(run_id) DO UPDATE SET
            start_time = excluded.start_time,
            status = excluded.status,
            updated_at = CURRENT_TIMESTAMP
        """
        self.conn.execute(sql, (run_id, timestamp))
        logger.info(f"Run started/updated in DB: {run_id}")

    def _handle_run_finished(self, event: Dict):
        """Updates run record on successful completion."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot store run finished event."
            )
            return
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

    def _handle_run_error(self, event: Dict):
        """Updates run record on error."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot store run error event."
            )
            return
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
        self.conn.execute(sql, (timestamp, payload.get("error_message"), run_id))
        logger.warning(f"Run error recorded in DB: {run_id}")

    def _handle_node_created(self, event: Dict):
        """Inserts a new node record."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot store node created event."
            )
            return
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        node_id = payload.get("node_id")

        if not node_id:
            logger.warning(
                f"node_created event missing node_id: {event.get('event_id')}"
            )
            return

        initial_status = payload.get("initial_status", "READY")  # Default assumption

        sql = """
        INSERT INTO nodes (node_id, run_id, node_nid, node_type, task_type, task_goal, status, layer, outer_node_id, root_node_id, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(node_id) DO UPDATE SET
            node_nid = excluded.node_nid,
            node_type = excluded.node_type,
            task_type = excluded.task_type,
            task_goal = excluded.task_goal,
            status = excluded.status,
            layer = excluded.layer,
            outer_node_id = excluded.outer_node_id,
            root_node_id = excluded.root_node_id,
            metadata = excluded.metadata,
            updated_at = CURRENT_TIMESTAMP
        """
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

        self.conn.execute(
            sql,
            (
                node_id,
                run_id,
                payload.get("node_nid"),
                payload.get("node_type"),
                payload.get("task_type"),
                payload.get("task_goal"),
                initial_status,
                payload.get("layer"),
                payload.get("outer_node_id"),
                payload.get("root_node_id"),
                json.dumps(metadata) if metadata else None,
            ),
        )
        logger.debug(f"Node created/updated in DB: {node_id}")

        # If this is the root node (layer 0), update the run record
        if payload.get("layer") == 0:
            update_run_sql = "UPDATE runs SET root_node_id = ? WHERE run_id = ?"
            self.conn.execute(update_run_sql, (node_id, run_id))
            logger.info(f"Set root_node_id for run {run_id} to {node_id}")

    def _handle_node_status_changed(self, event: Dict):
        """Updates node status."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot store node status changed event."
            )
            return
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
        cursor = self.conn.execute(sql, (new_status, node_id))
        if cursor.rowcount == 0:
            logger.warning(
                f"Tried to update status for non-existent node_id {node_id} from event {event.get('event_id')}"
            )
        else:
            logger.debug(f"Node status updated in DB: {node_id} -> {new_status}")

    def _handle_node_result_available(self, event: Dict):
        """Updates node result."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot store node result available event."
            )
            return
        payload = event.get("payload", {})
        node_id = payload.get("node_id")
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

    def _handle_edge_added(self, event: Dict):
        """Inserts a new edge record."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot store edge added event."
            )
            return
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
        self.conn.execute(
            sql,
            (
                run_id,
                parent_node_id,
                child_node_id,
                payload.get("parent_nid"),
                payload.get("child_nid"),
                json.dumps(metadata) if metadata else None,
            ),
        )
        logger.debug(
            f"Edge added in DB: {payload.get('parent_nid')} -> {payload.get('child_nid')}"
        )

    def _handle_inner_graph_built(self, event: Dict[str, Any]) -> None:
        """Handle inner_graph_built event by updating node relationships."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot handle inner_graph_built event."
            )
            return
        payload = event.get("payload", {})
        outer_node_id = payload.get("node_id")
        inner_node_ids = payload.get("node_ids", [])

        if not outer_node_id or not inner_node_ids:
            logger.warning(
                f"inner_graph_built event missing node_id or node_ids: {event.get('event_id')}"
            )
            return

        # Update all inner nodes to point to this outer node
        # Use parameter substitution for security
        placeholders = ",".join("?" * len(inner_node_ids))
        update_sql = f"""
            UPDATE nodes
            SET outer_node_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE node_id IN ({placeholders})
        """

        params = [outer_node_id] + inner_node_ids

        try:
            cursor = self.conn.execute(update_sql, params)
            if cursor.rowcount != len(inner_node_ids):
                logger.warning(
                    f"Expected to update {len(inner_node_ids)} inner nodes for outer node {outer_node_id}, but updated {cursor.rowcount}. Event: {event.get('event_id')}"
                )
            logger.debug(
                f"Updated outer_node_id for {cursor.rowcount} inner nodes of {outer_node_id}."
            )
        except sqlite3.Error as e:
            logger.error(
                f"Error updating inner nodes for {outer_node_id}: {e}", exc_info=True
            )
            # Raise here to trigger rollback in store_event
            raise

    def _handle_plan_received(self, event: Dict):
        """Handle plan_received event by storing the raw plan data in graph_plans table."""
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot store plan received event."
            )
            return
        payload = event.get("payload", {})
        run_id = event.get("run_id")
        node_id = payload.get("node_id")
        raw_plan = payload.get("raw_plan", [])

        if not all([run_id, node_id]):
            logger.warning(f"Missing required fields in plan_received event: {event}")
            return

        self.conn.execute(
            "INSERT INTO graph_plans (run_id, node_id, raw_plan) VALUES (?, ?, ?)",
            (run_id, node_id, json.dumps(raw_plan)),
        )
        logger.debug(f"Plan received stored in DB for node: {node_id}")

    def get_latest_run_events(self) -> List[Dict]:
        """Get all events from the latest run, ordered by timestamp.
        This is primarily used for the EventStateManager and broadcasting history.
        Graph state reconstruction should use get_latest_run_graph.
        """
        if not self.conn:
            logger.error(
                "Database connection is not available. Cannot retrieve events."
            )
            return []
        try:
            # Get the latest run_id
            cursor = self.conn.execute(
                "SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1"
            )
            result = cursor.fetchone()
            if not result:
                return []

            latest_run_id = result[0]

            # Get all events for this run, ordered primarily by timestamp
            # Maybe put run_started first, then order by timestamp?
            cursor = self.conn.execute(
                """
                SELECT * FROM events 
                WHERE run_id = ? 
                ORDER BY 
                    CASE event_type WHEN 'run_started' THEN 0 ELSE 1 END, 
                    timestamp ASC, 
                    id ASC -- Tie-breaker
                """,
                (latest_run_id,),
            )

            events = []
            # Use fetchall and process rows for potentially better performance
            rows = cursor.fetchall()
            for row_tuple in rows:
                # Convert row tuple to dictionary using column names
                row = dict(zip([desc[0] for desc in cursor.description], row_tuple))
                try:
                    payload = json.loads(row["payload"]) if row["payload"] else {}
                    event = {
                        "event_id": row["event_id"],
                        "run_id": row["run_id"],
                        "event_type": row["event_type"],
                        "timestamp": row["timestamp"],
                        "payload": payload,
                        # Add other base fields if needed, e.g., node_id from event table
                        "node_id": row.get("node_id"),
                    }
                    events.append(event)
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to decode payload for event {row['event_id']} in run {latest_run_id}."
                    )
                except KeyError as e:
                    logger.warning(
                        f"Missing expected key {e} in event row for run {latest_run_id}: {row}"
                    )

            return events
        except sqlite3.Error as e:
            logger.error(f"Error retrieving latest run events: {e}", exc_info=True)
            return []

    def get_latest_run_graph(self) -> Tuple[List[Dict], List[Dict]]:
        """Retrieves nodes and edges from the latest run."""
        if not self.conn:
            logger.error("Database connection is not available. Cannot retrieve graph.")
            return [], []

        latest_run_id = None
        try:
            cursor = self.conn.execute(
                "SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1"
            )
            result = cursor.fetchone()
            if result:
                latest_run_id = result[0]
            else:
                logger.info("No runs found in the database.")
                return [], []
        except sqlite3.Error as e:
            logger.error(f"Error retrieving latest run_id: {e}", exc_info=True)
            return [], []

        nodes_sql = """
        SELECT * FROM nodes WHERE run_id = ? ORDER BY layer, node_nid
        """
        edges_sql = """
        SELECT * FROM edges WHERE run_id = ? ORDER BY created_at
        """
        nodes = []
        edges = []
        try:
            # Fetch nodes
            cursor_nodes = self.conn.execute(nodes_sql, (latest_run_id,))
            node_cols = [desc[0] for desc in cursor_nodes.description]
            for row_tuple in cursor_nodes.fetchall():
                node = dict(zip(node_cols, row_tuple))
                # Decode JSON fields
                if node.get("result"):
                    try:
                        node["result"] = json.loads(node["result"])
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to decode result JSON for node {node['node_id']}"
                        )
                        node["result"] = (
                            None  # Or keep as string? Set to None for consistency.
                        )
                if node.get("metadata"):
                    try:
                        node["metadata"] = json.loads(node["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to decode metadata JSON for node {node['node_id']}"
                        )
                        node["metadata"] = {}  # Default to empty dict
                nodes.append(node)

            # Fetch edges
            cursor_edges = self.conn.execute(edges_sql, (latest_run_id,))
            edge_cols = [desc[0] for desc in cursor_edges.description]
            for row_tuple in cursor_edges.fetchall():
                edge = dict(zip(edge_cols, row_tuple))
                # Decode JSON fields
                if edge.get("metadata"):
                    try:
                        edge["metadata"] = json.loads(edge["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to decode metadata JSON for edge {edge['id']}"
                        )
                        edge["metadata"] = {}  # Default to empty dict
                edges.append(edge)

            logger.info(
                f"Retrieved {len(nodes)} nodes and {len(edges)} edges for the latest run ({latest_run_id})."
            )
            return nodes, edges
        except sqlite3.Error as e:
            logger.error(
                f"Error retrieving latest run graph for run {latest_run_id}: {e}",
                exc_info=True,
            )
            return [], []
        except (
            json.JSONDecodeError
        ) as e:  # Should be caught per-field now, but keep as safety net
            logger.error(
                f"Error decoding JSON from graph data for run {latest_run_id}: {e}",
                exc_info=True,
            )
            return [], []  # Return empty for safety

    def close(self):
        """Closes the database connection."""
        if self.conn:
            try:
                self.conn.commit()  # Ensure any final changes are committed
                self.conn.close()
                self.conn = None
                logger.info("Database connection closed successfully.")
            except sqlite3.Error as e:
                logger.error(f"Error closing database connection: {e}", exc_info=True)


# Example usage (for testing) - Keep this updated
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    )
    # Use a unique DB for testing each run? Or clear it?
    test_db_path = "test_run_events.db"
    # If the test DB exists, remove it for a clean run
    db_file = Path(test_db_path)
    if db_file.exists():
        db_file.unlink()

    db_manager = DatabaseManager(test_db_path)

    # Simulate events
    run_id = "test-run-123"

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
    plan_received_event = {
        "event_id": "evt-plan-recv",
        "run_id": run_id,
        "event_type": "plan_received",
        "timestamp": "2024-01-01T10:00:02.5Z",
        "payload": {"node_id": "node-1", "raw_plan": [{"id": 1, "goal": "Sub Goal"}]},
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
    db_manager.store_event(plan_received_event)  # Store plan event
    db_manager.store_event(edge_added_event)
    db_manager.store_event(node2_status_event)
    db_manager.store_event(run_finish_event)
    logger.info("Finished storing events.")

    logger.info("Retrieving latest run events...")
    latest_events = db_manager.get_latest_run_events()
    logger.info(f"Retrieved {len(latest_events)} events.")
    # for event in latest_events: logger.info(json.dumps(event, indent=2))

    logger.info("Retrieving latest run graph...")
    latest_nodes, latest_edges = db_manager.get_latest_run_graph()
    logger.info(f"Retrieved {len(latest_nodes)} nodes and {len(latest_edges)} edges.")
    # logger.info("Nodes:")
    # for node in latest_nodes: logger.info(json.dumps(node, indent=2))
    # logger.info("Edges:")
    # for edge in latest_edges: logger.info(json.dumps(edge, indent=2))

    db_manager.close()
    logger.info(f"Test completed. Database saved to {test_db_path}")
