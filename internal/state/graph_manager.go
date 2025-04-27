package state

import (
	"encoding/json"
	"sync"

	"github.com/rs/zerolog"

	"writehere-go/pkg/model"
)

// GraphNode represents a node in the graph
type GraphNode struct {
	NodeID      string          `json:"node_id"`
	NodeNID     string          `json:"node_nid"`
	NodeType    string          `json:"node_type"`
	TaskType    string          `json:"task_type"`
	TaskGoal    string          `json:"task_goal"`
	Status      string          `json:"status"`
	Layer       int             `json:"layer"`
	OuterNodeID string          `json:"outer_node_id,omitempty"`
	RootNodeID  string          `json:"root_node_id"`
	Result      json.RawMessage `json:"result,omitempty"`
	Metadata    json.RawMessage `json:"metadata,omitempty"`
}

// GraphEdge represents an edge in the graph
type GraphEdge struct {
	ID           string          `json:"id"`
	ParentNodeID string          `json:"parent_node_id"`
	ChildNodeID  string          `json:"child_node_id"`
	ParentNID    string          `json:"parent_nid"`
	ChildNID     string          `json:"child_nid"`
	Metadata     json.RawMessage `json:"metadata,omitempty"`
}

// GraphManager manages the in-memory state of the graph structure
type GraphManager struct {
	nodes     map[string]GraphNode // node_id -> node
	edges     map[string]GraphEdge // edge_id -> edge
	nodeIDs   []string             // ordered list of node IDs
	edgeIDs   []string             // ordered list of edge IDs
	rootNodes map[string]string    // run_id -> root_node_id
	mutex     sync.RWMutex
	logger    zerolog.Logger
}

// NewGraphManager creates a new graph manager
func NewGraphManager(logger zerolog.Logger) *GraphManager {
	return &GraphManager{
		nodes:     make(map[string]GraphNode),
		edges:     make(map[string]GraphEdge),
		nodeIDs:   make([]string, 0),
		edgeIDs:   make([]string, 0),
		rootNodes: make(map[string]string),
		mutex:     sync.RWMutex{},
		logger:    logger.With().Str("component", "graph_manager").Logger(),
	}
}

// AddNode adds a node to the graph
func (m *GraphManager) AddNode(node GraphNode) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Add or update the node
	_, exists := m.nodes[node.NodeID]
	m.nodes[node.NodeID] = node

	// Add to IDs list if it's new
	if !exists {
		m.nodeIDs = append(m.nodeIDs, node.NodeID)
	}

	// If this is a root node, track it
	if node.Layer == 0 || node.OuterNodeID == "" {
		m.rootNodes[node.RootNodeID] = node.NodeID
	}
}

// AddEdge adds an edge to the graph
func (m *GraphManager) AddEdge(edge GraphEdge) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Create a synthetic ID if not provided
	if edge.ID == "" {
		edge.ID = edge.ParentNodeID + "->" + edge.ChildNodeID
	}

	// Add or update the edge
	_, exists := m.edges[edge.ID]
	m.edges[edge.ID] = edge

	// Add to IDs list if it's new
	if !exists {
		m.edgeIDs = append(m.edgeIDs, edge.ID)
	}
}

// UpdateNodeStatus updates the status of a node
func (m *GraphManager) UpdateNodeStatus(nodeID string, status string) bool {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Find the node
	node, exists := m.nodes[nodeID]
	if !exists {
		return false
	}

	// Update the status
	node.Status = status
	m.nodes[nodeID] = node

	return true
}

// UpdateNodeResult updates the result of a node
func (m *GraphManager) UpdateNodeResult(nodeID string, result json.RawMessage) bool {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Find the node
	node, exists := m.nodes[nodeID]
	if !exists {
		return false
	}

	// Update the result
	node.Result = result
	m.nodes[nodeID] = node

	return true
}

// GetNodes returns a copy of all nodes
func (m *GraphManager) GetNodes() map[string]GraphNode {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	// Create a copy to avoid external modification
	nodesCopy := make(map[string]GraphNode, len(m.nodes))
	for id, node := range m.nodes {
		nodesCopy[id] = node
	}

	return nodesCopy
}

// GetEdges returns a copy of all edges
func (m *GraphManager) GetEdges() map[string]GraphEdge {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	// Create a copy to avoid external modification
	edgesCopy := make(map[string]GraphEdge, len(m.edges))
	for id, edge := range m.edges {
		edgesCopy[id] = edge
	}

	return edgesCopy
}

// GetNode returns a specific node by ID
func (m *GraphManager) GetNode(nodeID string) (GraphNode, bool) {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	node, exists := m.nodes[nodeID]
	return node, exists
}

// GetEdge returns a specific edge by ID
func (m *GraphManager) GetEdge(edgeID string) (GraphEdge, bool) {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	edge, exists := m.edges[edgeID]
	return edge, exists
}

// GetNodesByRunID returns all nodes for a specific run
func (m *GraphManager) GetNodesByRunID(runID string) []GraphNode {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	// Find the root node ID for this run
	rootNodeID, exists := m.rootNodes[runID]
	if !exists {
		return []GraphNode{}
	}

	// Get all nodes with matching root_node_id
	nodes := make([]GraphNode, 0)
	for _, node := range m.nodes {
		if node.RootNodeID == rootNodeID {
			nodes = append(nodes, node)
		}
	}

	return nodes
}

// GetEdgesByRunID returns all edges for a specific run's nodes
func (m *GraphManager) GetEdgesByRunID(runID string) []GraphEdge {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	// Find the root node ID for this run
	rootNodeID, exists := m.rootNodes[runID]
	if !exists {
		return []GraphEdge{}
	}

	// First, collect all node IDs that belong to this run
	runNodeIDs := make(map[string]bool)
	for _, node := range m.nodes {
		if node.RootNodeID == rootNodeID {
			runNodeIDs[node.NodeID] = true
		}
	}

	// Get all edges where both parent and child are in this run
	edges := make([]GraphEdge, 0)
	for _, edge := range m.edges {
		if runNodeIDs[edge.ParentNodeID] && runNodeIDs[edge.ChildNodeID] {
			edges = append(edges, edge)
		}
	}

	return edges
}

// Clear removes all graph data
func (m *GraphManager) Clear() {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Reset all collections
	m.nodes = make(map[string]GraphNode)
	m.edges = make(map[string]GraphEdge)
	m.nodeIDs = make([]string, 0)
	m.edgeIDs = make([]string, 0)
	m.rootNodes = make(map[string]string)
}

// ProcessEvent updates the graph state based on the event type
func (m *GraphManager) ProcessEvent(event model.Event) {
	// Handle different event types that affect graph state
	switch event.EventType {
	case model.EventTypeRunStarted:
		// Nothing to do here, we don't have a node ID yet

	case model.EventTypeNodeCreated:
		if payload, ok := model.ToNodeCreatedPayload(event.Payload); ok {
			outerNodeID := ""
			if payload.OuterNodeID != nil {
				outerNodeID = *payload.OuterNodeID
			}
			node := GraphNode{
				NodeID:      payload.NodeID,
				NodeNID:     payload.NodeNID,
				NodeType:    payload.NodeType,
				TaskType:    payload.TaskType,
				TaskGoal:    payload.TaskGoal,
				Status:      "NOT_READY", // Initial status
				Layer:       payload.Layer,
				OuterNodeID: outerNodeID, // Dereference the pointer
				RootNodeID:  payload.RootNodeID,
			}
			m.AddNode(node)
		}

	case model.EventTypeNodeStatusChanged:
		if payload, ok := model.ToNodeStatusChangedPayload(event.Payload); ok {
			m.UpdateNodeStatus(payload.NodeID, payload.NewStatus)
		}

	case model.EventTypeNodeResultAvailable:
		if payload, ok := model.ToNodeResultAvailablePayload(event.Payload); ok {
			// Check if ResultSummary is not nil and not empty
			if len(payload.ResultSummary) > 0 {
				// Directly use the json.RawMessage
				m.UpdateNodeResult(payload.NodeID, payload.ResultSummary)
			}
		}

	case model.EventTypeEdgeAdded:
		if payload, ok := model.ToEdgeAddedPayload(event.Payload); ok {
			edge := GraphEdge{
				ParentNodeID: payload.ParentNodeID,
				ChildNodeID:  payload.ChildNodeID,
				ParentNID:    payload.ParentNodeNID,
				ChildNID:     payload.ChildNodeNID,
			}
			m.AddEdge(edge)
		}
	}
}

// LoadStateFromDB populates the graph manager with nodes and edges from the database
func (m *GraphManager) LoadStateFromDB(nodes []GraphNode, edges []GraphEdge) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Reset current state
	m.nodes = make(map[string]GraphNode, len(nodes))
	m.edges = make(map[string]GraphEdge, len(edges))
	m.nodeIDs = make([]string, 0, len(nodes))
	m.edgeIDs = make([]string, 0, len(edges))
	m.rootNodes = make(map[string]string)

	// Add each node from the database
	for _, node := range nodes {
		m.nodes[node.NodeID] = node
		m.nodeIDs = append(m.nodeIDs, node.NodeID)

		// Track root nodes
		if node.Layer == 0 || node.OuterNodeID == "" {
			m.rootNodes[node.RootNodeID] = node.NodeID
		}
	}

	// Add each edge from the database
	for _, edge := range edges {
		// Create a synthetic ID if not provided
		if edge.ID == "" {
			edge.ID = edge.ParentNodeID + "->" + edge.ChildNodeID
		}

		m.edges[edge.ID] = edge
		m.edgeIDs = append(m.edgeIDs, edge.ID)
	}

	m.logger.Info().
		Int("node_count", len(m.nodes)).
		Int("edge_count", len(m.edges)).
		Int("root_node_count", len(m.rootNodes)).
		Msg("Loaded graph state from database")
}
