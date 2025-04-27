package model

import (
	"encoding/json"
)

// Event represents the base event structure
type Event struct {
	EventID   string          `json:"event_id"`
	Timestamp string          `json:"timestamp"`
	EventType string          `json:"event_type"`
	Payload   json.RawMessage `json:"payload"`
	RunID     string          `json:"run_id"`
}

// EventType constants
const (
	EventTypeRunStarted          = "run_started"
	EventTypeRunFinished         = "run_finished"
	EventTypeRunError            = "run_error"
	EventTypeStepStarted         = "step_started"
	EventTypeStepFinished        = "step_finished"
	EventTypeNodeStatusChanged   = "node_status_changed"
	EventTypeLLMCallStarted      = "llm_call_started"
	EventTypeLLMCallCompleted    = "llm_call_completed"
	EventTypeToolInvoked         = "tool_invoked"
	EventTypeToolReturned        = "tool_returned"
	EventTypeNodeCreated         = "node_created"
	EventTypePlanReceived        = "plan_received"
	EventTypeNodeAdded           = "node_added"
	EventTypeEdgeAdded           = "edge_added"
	EventTypeInnerGraphBuilt     = "inner_graph_built"
	EventTypeNodeResultAvailable = "node_result_available"
)

// EventPayload is an interface for event-specific payload types
type EventPayload interface {
	GetType() string
}

// RunStartedPayload represents the payload of a run_started event
type RunStartedPayload struct {
	InputData    json.RawMessage `json:"input_data"`
	Config       json.RawMessage `json:"config"`
	RunMode      string          `json:"run_mode"`
	TimestampUTC string          `json:"timestamp_utc"`
}

func (p RunStartedPayload) GetType() string {
	return EventTypeRunStarted
}

// RunFinishedPayload represents the payload of a run_finished event
type RunFinishedPayload struct {
	TotalSteps        int             `json:"total_steps"`
	DurationSeconds   float64         `json:"duration_seconds"`
	TotalNodes        int             `json:"total_nodes"`
	TotalLLMCalls     int             `json:"total_llm_calls"`
	TotalToolCalls    int             `json:"total_tool_calls"`
	TokenUsageSummary json.RawMessage `json:"token_usage_summary"`
	NodeStatistics    json.RawMessage `json:"node_statistics"`
	SearchStatistics  json.RawMessage `json:"search_statistics,omitempty"`
}

func (p RunFinishedPayload) GetType() string {
	return EventTypeRunFinished
}

// RunErrorPayload represents the payload of a run_error event
type RunErrorPayload struct {
	ErrorType    string          `json:"error_type"`
	ErrorMessage string          `json:"error_message"`
	StackTrace   string          `json:"stack_trace"`
	NodeID       string          `json:"node_id,omitempty"`
	Step         int             `json:"step,omitempty"`
	Context      json.RawMessage `json:"context,omitempty"`
}

func (p RunErrorPayload) GetType() string {
	return EventTypeRunError
}

// StepStartedPayload represents the payload of a step_started event
type StepStartedPayload struct {
	Step     int    `json:"step"`
	NodeID   string `json:"node_id,omitempty"`
	TaskType string `json:"task_type,omitempty"`
	NodeGoal string `json:"node_goal,omitempty"`
	RootID   string `json:"root_id,omitempty"`
}

func (p StepStartedPayload) GetType() string {
	return EventTypeStepStarted
}

// StepFinishedPayload represents the payload of a step_finished event
type StepFinishedPayload struct {
	Step            int     `json:"step"`
	NodeID          string  `json:"node_id,omitempty"`
	ActionName      string  `json:"action_name,omitempty"`
	StatusAfter     string  `json:"status_after,omitempty"`
	DurationSeconds float64 `json:"duration_seconds,omitempty"`
	TaskType        string  `json:"task_type,omitempty"`
	TaskGoal        string  `json:"task_goal,omitempty"`
}

func (p StepFinishedPayload) GetType() string {
	return EventTypeStepFinished
}

// NodeStatusChangedPayload represents the payload of a node_status_changed event
type NodeStatusChangedPayload struct {
	NodeID    string `json:"node_id"`
	NodeGoal  string `json:"node_goal,omitempty"`
	OldStatus string `json:"old_status"`
	NewStatus string `json:"new_status"`
	Step      int    `json:"step,omitempty"`
	TaskType  string `json:"task_type,omitempty"`
}

func (p NodeStatusChangedPayload) GetType() string {
	return EventTypeNodeStatusChanged
}

// LLMCallStartedPayload represents the payload of a llm_call_started event
type LLMCallStartedPayload struct {
	AgentClass    string          `json:"agent_class"`
	Model         string          `json:"model"`
	PromptPreview string          `json:"prompt_preview,omitempty"`
	Prompt        json.RawMessage `json:"prompt,omitempty"`
	Step          int             `json:"step,omitempty"`
	NodeID        string          `json:"node_id,omitempty"`
	TaskType      string          `json:"task_type,omitempty"`
	ActionName    string          `json:"action_name,omitempty"`
}

func (p LLMCallStartedPayload) GetType() string {
	return EventTypeLLMCallStarted
}

// LLMCallCompletedPayload represents the payload of a llm_call_completed event
type LLMCallCompletedPayload struct {
	AgentClass      string          `json:"agent_class"`
	Model           string          `json:"model"`
	DurationSeconds float64         `json:"duration_seconds"`
	ResultSummary   string          `json:"result_summary,omitempty"`
	Response        string          `json:"response,omitempty"`
	Step            int             `json:"step,omitempty"`
	TokenUsage      json.RawMessage `json:"token_usage,omitempty"`
	NodeID          string          `json:"node_id,omitempty"`
	Error           *string         `json:"error"`
	TaskType        string          `json:"task_type,omitempty"`
	ActionName      string          `json:"action_name,omitempty"`
}

func (p LLMCallCompletedPayload) GetType() string {
	return EventTypeLLMCallCompleted
}

// ToolInvokedPayload represents the payload of a tool_invoked event
type ToolInvokedPayload struct {
	ToolName    string `json:"tool_name"`
	ApiName     string `json:"api_name"`
	ArgsSummary string `json:"args_summary,omitempty"`
	NodeID      string `json:"node_id,omitempty"`
	Step        int    `json:"step,omitempty"`
	AgentClass  string `json:"agent_class,omitempty"`
	ToolCallID  string `json:"tool_call_id,omitempty"`
}

func (p ToolInvokedPayload) GetType() string {
	return EventTypeToolInvoked
}

// ToolReturnedPayload represents the payload of a tool_returned event
type ToolReturnedPayload struct {
	ToolName        string  `json:"tool_name"`
	ApiName         string  `json:"api_name"`
	State           string  `json:"state"`
	DurationSeconds float64 `json:"duration_seconds,omitempty"`
	ResultSummary   string  `json:"result_summary,omitempty"`
	NodeID          string  `json:"node_id,omitempty"`
	Error           *string `json:"error"`
	Step            int     `json:"step,omitempty"`
	AgentClass      string  `json:"agent_class,omitempty"`
	ToolCallID      string  `json:"tool_call_id,omitempty"`
}

func (p ToolReturnedPayload) GetType() string {
	return EventTypeToolReturned
}

// NodeCreatedPayload represents the payload of a node_created event
type NodeCreatedPayload struct {
	NodeID            string   `json:"node_id"`
	NodeNID           string   `json:"node_nid"`
	NodeType          string   `json:"node_type"`
	TaskType          string   `json:"task_type"`
	TaskGoal          string   `json:"task_goal"`
	Layer             int      `json:"layer"`
	OuterNodeID       *string  `json:"outer_node_id"`
	RootNodeID        string   `json:"root_node_id"`
	InitialParentNIDs []string `json:"initial_parent_nids,omitempty"`
	Step              *int     `json:"step,omitempty"`
}

func (p NodeCreatedPayload) GetType() string {
	return EventTypeNodeCreated
}

// PlanReceivedPayload represents the payload of a plan_received event
type PlanReceivedPayload struct {
	NodeID   string          `json:"node_id"`
	RawPlan  json.RawMessage `json:"raw_plan"`
	Step     int             `json:"step,omitempty"`
	TaskType string          `json:"task_type,omitempty"`
	TaskGoal string          `json:"task_goal,omitempty"`
}

func (p PlanReceivedPayload) GetType() string {
	return EventTypePlanReceived
}

// NodeAddedPayload represents the payload of a node_added event
type NodeAddedPayload struct {
	GraphOwnerNodeID string `json:"graph_owner_node_id"`
	AddedNodeID      string `json:"added_node_id"`
	AddedNodeNID     string `json:"added_node_nid"`
	Step             int    `json:"step,omitempty"`
	TaskType         string `json:"task_type,omitempty"`
	TaskGoal         string `json:"task_goal,omitempty"`
}

func (p NodeAddedPayload) GetType() string {
	return EventTypeNodeAdded
}

// EdgeAddedPayload represents the payload of an edge_added event
type EdgeAddedPayload struct {
	GraphOwnerNodeID string `json:"graph_owner_node_id"`
	ParentNodeID     string `json:"parent_node_id"`
	ChildNodeID      string `json:"child_node_id"`
	ParentNodeNID    string `json:"parent_node_nid"`
	ChildNodeNID     string `json:"child_node_nid"`
	Step             int    `json:"step,omitempty"`
	TaskType         string `json:"task_type,omitempty"`
	TaskGoal         string `json:"task_goal,omitempty"`
}

func (p EdgeAddedPayload) GetType() string {
	return EventTypeEdgeAdded
}

// InnerGraphBuiltPayload represents the payload of an inner_graph_built event
type InnerGraphBuiltPayload struct {
	NodeID    string   `json:"node_id"`
	NodeCount int      `json:"node_count"`
	EdgeCount int      `json:"edge_count"`
	NodeIDs   []string `json:"node_ids,omitempty"`
	Step      int      `json:"step,omitempty"`
	TaskType  string   `json:"task_type,omitempty"`
	TaskGoal  string   `json:"task_goal,omitempty"`
}

func (p InnerGraphBuiltPayload) GetType() string {
	return EventTypeInnerGraphBuilt
}

// NodeResultAvailablePayload represents the payload of a node_result_available event
type NodeResultAvailablePayload struct {
	NodeID        string          `json:"node_id"`
	ActionName    string          `json:"action_name,omitempty"`
	ResultSummary json.RawMessage `json:"result_summary,omitempty"`
	Step          int             `json:"step,omitempty"`
	TaskType      string          `json:"task_type,omitempty"`
	TaskGoal      string          `json:"task_goal,omitempty"`
}

func (p NodeResultAvailablePayload) GetType() string {
	return EventTypeNodeResultAvailable
}
