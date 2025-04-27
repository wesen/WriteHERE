package db

import (
	"context"
	"database/sql"
	"embed"
	"encoding/json"
	"fmt"

	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/pkg/errors"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"

	_ "github.com/mattn/go-sqlite3"
)

// Schema contains all SQL statements for creating the database schema
//
//go:embed schema.sql
var Schema embed.FS

// DatabaseManager handles all interactions with the SQLite database
type DatabaseManager struct {
	db     *sql.DB
	logger zerolog.Logger
}

// NewDatabaseManager creates a new DatabaseManager with the given database path
func NewDatabaseManager(dbPath string) (*DatabaseManager, error) {
	logger := log.With().Str("component", "database_manager").Logger()
	logger.Info().Str("db_path", dbPath).Msg("Initializing database manager")

	// Connect to the database
	db, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL&_foreign_keys=ON")
	if err != nil {
		return nil, errors.Wrap(err, "failed to open SQLite database")
	}

	// Test the connection
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, errors.Wrap(err, "failed to ping SQLite database")
	}

	// Configure database
	db.SetMaxOpenConns(1) // SQLite supports only one writer at a time
	db.SetMaxIdleConns(1)

	manager := &DatabaseManager{
		db:     db,
		logger: logger,
	}

	// Ensure schema exists
	if err := manager.ensureSchema(); err != nil {
		db.Close()
		return nil, errors.Wrap(err, "failed to ensure database schema")
	}

	return manager, nil
}

// ensureSchema creates all necessary tables, indexes and views if they don't exist
func (m *DatabaseManager) ensureSchema() error {
	m.logger.Info().Msg("Ensuring database schema exists")

	schemaBytes, err := Schema.ReadFile("schema.sql")
	if err != nil {
		return errors.Wrap(err, "failed to read schema.sql")
	}

	_, err = m.db.Exec(string(schemaBytes))
	if err != nil {
		return errors.Wrap(err, "failed to execute schema SQL")
	}

	m.logger.Info().Msg("Database schema initialized successfully")
	return nil
}

// Close closes the database connection
func (m *DatabaseManager) Close() error {
	return m.db.Close()
}

// Event represents the base event structure
type Event struct {
	EventID   string          `json:"event_id"`
	Timestamp string          `json:"timestamp"`
	EventType string          `json:"event_type"`
	Payload   json.RawMessage `json:"payload"`
	RunID     string          `json:"run_id"`
}

// HandleMessage processes a Watermill message containing an event
func (m *DatabaseManager) HandleMessage(msg *message.Message) error {
	// Parse the event from the message payload
	var event Event
	if err := json.Unmarshal(msg.Payload, &event); err != nil {
		return errors.Wrap(err, "failed to unmarshal event")
	}

	// Store the event in the database
	if err := m.StoreEvent(&event); err != nil {
		return errors.Wrap(err, "failed to store event")
	}

	return nil
}

// StoreEvent stores an event in the database and updates related tables
func (m *DatabaseManager) StoreEvent(event *Event) error {
	// Begin a transaction
	tx, err := m.db.Begin()
	if err != nil {
		return errors.Wrap(err, "failed to begin transaction")
	}
	defer func() {
		if err != nil {
			tx.Rollback()
		}
	}()

	// Extract node_id from payload if present
	var nodeID *string
	var payloadMap map[string]interface{}
	if err := json.Unmarshal(event.Payload, &payloadMap); err == nil {
		if nid, ok := payloadMap["node_id"].(string); ok {
			nodeID = &nid
		}
	}

	// Insert the event
	_, err = tx.Exec(
		`INSERT INTO events 
        (event_id, run_id, event_type, timestamp, payload, node_id) 
        VALUES (?, ?, ?, ?, ?, ?)`,
		event.EventID, event.RunID, event.EventType, event.Timestamp, event.Payload, nodeID,
	)
	if err != nil {
		return errors.Wrap(err, "failed to insert event")
	}

	// Process the event based on its type
	err = m.processEventByType(tx, event)
	if err != nil {
		return errors.Wrap(err, "failed to process event by type")
	}

	// Commit the transaction
	if err = tx.Commit(); err != nil {
		return errors.Wrap(err, "failed to commit transaction")
	}

	return nil
}

// processEventByType handles event-specific logic based on event type
func (m *DatabaseManager) processEventByType(tx *sql.Tx, event *Event) error {
	switch event.EventType {
	case "run_started":
		return m.handleRunStarted(tx, event)
	case "run_finished":
		return m.handleRunFinished(tx, event)
	case "run_error":
		return m.handleRunError(tx, event)
	case "node_created":
		return m.handleNodeCreated(tx, event)
	case "node_status_changed":
		return m.handleNodeStatusChanged(tx, event)
	case "node_result_available":
		return m.handleNodeResultAvailable(tx, event)
	case "edge_added":
		return m.handleEdgeAdded(tx, event)
	case "plan_received":
		return m.handlePlanReceived(tx, event)
	default:
		// No specific handling needed for other event types
		return nil
	}
}

// handleRunStarted processes a run_started event
func (m *DatabaseManager) handleRunStarted(tx *sql.Tx, event *Event) error {
	var payload struct {
		TimestampUTC string `json:"timestamp_utc"`
	}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return errors.Wrap(err, "failed to unmarshal run_started payload")
	}

	_, err := tx.Exec(
		`INSERT INTO runs (run_id, start_time, status, created_at, updated_at)
        VALUES (?, ?, 'running', datetime('now'), datetime('now'))`,
		event.RunID, payload.TimestampUTC,
	)
	return err
}

// handleRunFinished processes a run_finished event
func (m *DatabaseManager) handleRunFinished(tx *sql.Tx, event *Event) error {
	var payload struct {
		TotalSteps int `json:"total_steps"`
		TotalNodes int `json:"total_nodes"`
	}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return errors.Wrap(err, "failed to unmarshal run_finished payload")
	}

	_, err := tx.Exec(
		`UPDATE runs 
        SET end_time = ?, status = 'completed', total_steps = ?, total_nodes = ?, updated_at = datetime('now')
        WHERE run_id = ?`,
		event.Timestamp, payload.TotalSteps, payload.TotalNodes, event.RunID,
	)
	return err
}

// handleRunError processes a run_error event
func (m *DatabaseManager) handleRunError(tx *sql.Tx, event *Event) error {
	var payload struct {
		ErrorMessage string `json:"error_message"`
	}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return errors.Wrap(err, "failed to unmarshal run_error payload")
	}

	_, err := tx.Exec(
		`UPDATE runs 
        SET end_time = ?, status = 'error', error_message = ?, updated_at = datetime('now')
        WHERE run_id = ?`,
		event.Timestamp, payload.ErrorMessage, event.RunID,
	)
	return err
}

// handleNodeCreated processes a node_created event
func (m *DatabaseManager) handleNodeCreated(tx *sql.Tx, event *Event) error {
	var payload struct {
		NodeID      string          `json:"node_id"`
		NodeNID     string          `json:"node_nid"`
		NodeType    string          `json:"node_type"`
		TaskType    string          `json:"task_type"`
		TaskGoal    string          `json:"task_goal"`
		Layer       int             `json:"layer"`
		OuterNodeID *string         `json:"outer_node_id"`
		RootNodeID  string          `json:"root_node_id"`
		Metadata    json.RawMessage `json:"metadata,omitempty"`
	}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return errors.Wrap(err, "failed to unmarshal node_created payload")
	}

	// If this is a root node, update the run's root_node_id
	if payload.Layer == 0 {
		_, err := tx.Exec(
			`UPDATE runs SET root_node_id = ?, updated_at = datetime('now') WHERE run_id = ?`,
			payload.NodeID, event.RunID,
		)
		if err != nil {
			return errors.Wrap(err, "failed to update run with root node")
		}
	}

	_, err := tx.Exec(
		`INSERT INTO nodes 
        (node_id, run_id, node_nid, node_type, task_type, task_goal, status, layer, outer_node_id, root_node_id, metadata)
        VALUES (?, ?, ?, ?, ?, ?, 'NOT_READY', ?, ?, ?, ?)`,
		payload.NodeID, event.RunID, payload.NodeNID, payload.NodeType, payload.TaskType,
		payload.TaskGoal, payload.Layer, payload.OuterNodeID, payload.RootNodeID, payload.Metadata,
	)
	return err
}

// handleNodeStatusChanged processes a node_status_changed event
func (m *DatabaseManager) handleNodeStatusChanged(tx *sql.Tx, event *Event) error {
	var payload struct {
		NodeID    string `json:"node_id"`
		NewStatus string `json:"new_status"`
	}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return errors.Wrap(err, "failed to unmarshal node_status_changed payload")
	}

	_, err := tx.Exec(
		`UPDATE nodes 
        SET status = ?, updated_at = datetime('now')
        WHERE node_id = ?`,
		payload.NewStatus, payload.NodeID,
	)
	return err
}

// handleNodeResultAvailable processes a node_result_available event
func (m *DatabaseManager) handleNodeResultAvailable(tx *sql.Tx, event *Event) error {
	var payload struct {
		NodeID        string          `json:"node_id"`
		ResultSummary json.RawMessage `json:"result_summary"`
	}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return errors.Wrap(err, "failed to unmarshal node_result_available payload")
	}

	_, err := tx.Exec(
		`UPDATE nodes 
        SET result = ?, updated_at = datetime('now')
        WHERE node_id = ?`,
		payload.ResultSummary, payload.NodeID,
	)
	return err
}

// handleEdgeAdded processes an edge_added event
func (m *DatabaseManager) handleEdgeAdded(tx *sql.Tx, event *Event) error {
	var payload struct {
		ParentNodeID string          `json:"parent_node_id"`
		ChildNodeID  string          `json:"child_node_id"`
		ParentNID    string          `json:"parent_node_nid"`
		ChildNID     string          `json:"child_node_nid"`
		Metadata     json.RawMessage `json:"metadata,omitempty"`
	}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return errors.Wrap(err, "failed to unmarshal edge_added payload")
	}

	_, err := tx.Exec(
		`INSERT INTO edges 
        (run_id, parent_node_id, child_node_id, parent_nid, child_nid, metadata)
        VALUES (?, ?, ?, ?, ?, ?)`,
		event.RunID, payload.ParentNodeID, payload.ChildNodeID, payload.ParentNID, payload.ChildNID, payload.Metadata,
	)
	return err
}

// handlePlanReceived processes a plan_received event
func (m *DatabaseManager) handlePlanReceived(tx *sql.Tx, event *Event) error {
	var payload struct {
		NodeID  string          `json:"node_id"`
		RawPlan json.RawMessage `json:"raw_plan"`
	}
	if err := json.Unmarshal(event.Payload, &payload); err != nil {
		return errors.Wrap(err, "failed to unmarshal plan_received payload")
	}

	_, err := tx.Exec(
		`INSERT INTO graph_plans 
        (run_id, node_id, raw_plan)
        VALUES (?, ?, ?)`,
		event.RunID, payload.NodeID, payload.RawPlan,
	)
	return err
}

// GraphData holds the complete set of nodes and edges for a run
type GraphData struct {
	Nodes map[string]json.RawMessage `json:"nodes"`
	Edges []json.RawMessage          `json:"edges"`
}

// GetLatestRunGraph retrieves the graph structure (nodes and edges) for the latest run
func (m *DatabaseManager) GetLatestRunGraph(ctx context.Context) (*GraphData, error) {
	// Get the latest run ID
	var runID string
	err := m.db.QueryRowContext(ctx, `
        SELECT run_id FROM runs 
        ORDER BY start_time DESC 
        LIMIT 1
    `).Scan(&runID)
	if err != nil {
		if err == sql.ErrNoRows {
			// No runs found
			return &GraphData{
				Nodes: make(map[string]json.RawMessage),
				Edges: []json.RawMessage{},
			}, nil
		}
		return nil, errors.Wrap(err, "failed to get latest run ID")
	}

	return m.GetRunGraph(ctx, runID)
}

// GetRunGraph retrieves the graph structure for a specific run
func (m *DatabaseManager) GetRunGraph(ctx context.Context, runID string) (*GraphData, error) {
	data := &GraphData{
		Nodes: make(map[string]json.RawMessage),
		Edges: []json.RawMessage{},
	}

	// Get all nodes for the run
	nodeRows, err := m.db.QueryContext(ctx, `
        SELECT json_object(
            'id', node_id,
            'nid', node_nid,
            'type', node_type,
            'task_type', task_type,
            'goal', task_goal,
            'status', status,
            'layer', layer,
            'outer_node_id', outer_node_id,
            'root_node_id', root_node_id,
            'result', result,
            'metadata', metadata
        ) AS node_json,
        node_id
        FROM nodes
        WHERE run_id = ?
    `, runID)
	if err != nil {
		return nil, errors.Wrap(err, "failed to query nodes")
	}
	defer nodeRows.Close()

	for nodeRows.Next() {
		var nodeJSON []byte
		var nodeID string
		if err := nodeRows.Scan(&nodeJSON, &nodeID); err != nil {
			return nil, errors.Wrap(err, "failed to scan node row")
		}
		data.Nodes[nodeID] = nodeJSON
	}
	if err := nodeRows.Err(); err != nil {
		return nil, errors.Wrap(err, "error iterating node rows")
	}

	// Get all edges for the run
	edgeRows, err := m.db.QueryContext(ctx, `
        SELECT json_object(
            'id', id,
            'parent_id', parent_node_id,
            'child_id', child_node_id,
            'parent_nid', parent_nid,
            'child_nid', child_nid,
            'metadata', metadata
        ) AS edge_json
        FROM edges
        WHERE run_id = ?
    `, runID)
	if err != nil {
		return nil, errors.Wrap(err, "failed to query edges")
	}
	defer edgeRows.Close()

	for edgeRows.Next() {
		var edgeJSON []byte
		if err := edgeRows.Scan(&edgeJSON); err != nil {
			return nil, errors.Wrap(err, "failed to scan edge row")
		}
		data.Edges = append(data.Edges, edgeJSON)
	}
	if err := edgeRows.Err(); err != nil {
		return nil, errors.Wrap(err, "error iterating edge rows")
	}

	return data, nil
}

// EventData holds events for a specific run
type EventData struct {
	Events []json.RawMessage `json:"events"`
}

// GetLatestRunEvents retrieves the events for the latest run
func (m *DatabaseManager) GetLatestRunEvents(ctx context.Context) (*EventData, error) {
	// Get the latest run ID
	var runID string
	err := m.db.QueryRowContext(ctx, `
        SELECT run_id FROM runs 
        ORDER BY start_time DESC 
        LIMIT 1
    `).Scan(&runID)
	if err != nil {
		if err == sql.ErrNoRows {
			// No runs found
			return &EventData{
				Events: []json.RawMessage{},
			}, nil
		}
		return nil, errors.Wrap(err, "failed to get latest run ID")
	}

	return m.GetRunEvents(ctx, runID)
}

// GetRunEvents retrieves the events for a specific run
func (m *DatabaseManager) GetRunEvents(ctx context.Context, runID string) (*EventData, error) {
	// Get all events for the run
	rows, err := m.db.QueryContext(ctx, `
        SELECT json_object(
            'event_id', event_id,
            'timestamp', timestamp,
            'event_type', event_type,
            'payload', json(payload),
            'run_id', run_id
        ) AS event_json
        FROM events
        WHERE run_id = ?
        ORDER BY timestamp ASC
    `, runID)
	if err != nil {
		return nil, errors.Wrap(err, "failed to query events")
	}
	defer rows.Close()

	data := &EventData{
		Events: []json.RawMessage{},
	}

	for rows.Next() {
		var eventJSON []byte
		if err := rows.Scan(&eventJSON); err != nil {
			return nil, errors.Wrap(err, "failed to scan event row")
		}
		data.Events = append(data.Events, eventJSON)
	}
	if err := rows.Err(); err != nil {
		return nil, errors.Wrap(err, "error iterating event rows")
	}

	return data, nil
}

// GetNodeDetails retrieves detailed information for a specific node
func (m *DatabaseManager) GetNodeDetails(ctx context.Context, nodeID string) (json.RawMessage, error) {
	var nodeJSON []byte
	err := m.db.QueryRowContext(ctx, `
        SELECT json_object(
            'id', node_id,
            'nid', node_nid,
            'type', node_type,
            'task_type', task_type,
            'goal', task_goal,
            'status', status,
            'layer', layer,
            'outer_node_id', outer_node_id,
            'root_node_id', root_node_id,
            'result', result,
            'metadata', metadata,
            'created_at', created_at,
            'updated_at', updated_at
        ) AS node_json
        FROM nodes
        WHERE node_id = ?
    `, nodeID).Scan(&nodeJSON)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("node not found: %s", nodeID)
		}
		return nil, errors.Wrap(err, "failed to get node details")
	}

	return nodeJSON, nil
}

// GetEdgeDetails retrieves detailed information for a specific edge
func (m *DatabaseManager) GetEdgeDetails(ctx context.Context, edgeID int) (json.RawMessage, error) {
	var edgeJSON []byte
	err := m.db.QueryRowContext(ctx, `
        SELECT json_object(
            'id', id,
            'parent_id', parent_node_id,
            'child_id', child_node_id,
            'parent_nid', parent_nid,
            'child_nid', child_nid,
            'metadata', metadata,
            'created_at', created_at
        ) AS edge_json
        FROM edges
        WHERE id = ?
    `, edgeID).Scan(&edgeJSON)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("edge not found: %d", edgeID)
		}
		return nil, errors.Wrap(err, "failed to get edge details")
	}

	return edgeJSON, nil
}
