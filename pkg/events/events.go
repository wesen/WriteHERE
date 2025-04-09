package events

import (
	"encoding/json"
	"time"

	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/google/uuid"
	"github.com/pkg/errors"
)

// EventType represents the type of an event in the system
type EventType string

// Define all event types
const (
	TaskSubmitted       EventType = "TaskSubmitted"
	TaskReady           EventType = "TaskReady"
	TaskAssigned        EventType = "TaskAssigned"
	TaskStarted         EventType = "TaskStarted"
	TaskCompleted       EventType = "TaskCompleted"
	TaskFailed          EventType = "TaskFailed"
	TaskResultAvailable EventType = "TaskResultAvailable"
	SubtasksPlanned     EventType = "SubtasksPlanned"
)

// Event represents the common structure of all events in the system
type Event struct {
	EventID       string      `json:"event_id"`
	EventType     EventType   `json:"event_type"`
	Timestamp     time.Time   `json:"timestamp"`
	SourceService string      `json:"source_service"`
	Payload       interface{} `json:"payload"`
}

// NewEvent creates a new event with the given type and payload
func NewEvent(eventType EventType, sourceService string, payload interface{}) Event {
	return Event{
		EventID:       uuid.New().String(),
		EventType:     eventType,
		Timestamp:     time.Now(),
		SourceService: sourceService,
		Payload:       payload,
	}
}

// ToMessage converts an Event to a Watermill message
func (e Event) ToMessage() (*message.Message, error) {
	payload, err := json.Marshal(e)
	if err != nil {
		return nil, errors.Wrap(err, "failed to marshal event")
	}

	msg := message.NewMessage(e.EventID, payload)
	msg.Metadata.Set("event_type", string(e.EventType))

	return msg, nil
}

// EventFromMessage converts a Watermill message back to an Event
func EventFromMessage(msg *message.Message) (Event, error) {
	var event Event
	if err := json.Unmarshal(msg.Payload, &event); err != nil {
		return Event{}, errors.Wrap(err, "failed to unmarshal event")
	}
	return event, nil
}

// Payloads for different event types

// TaskSubmittedPayload represents the data for a TaskSubmitted event
type TaskSubmittedPayload struct {
	TaskID     string                 `json:"task_id"`
	RootTaskID string                 `json:"root_task_id,omitempty"`
	Goal       string                 `json:"goal"`
	TaskType   string                 `json:"task_type"`
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
}

// TaskReadyPayload represents the data for a TaskReady event
type TaskReadyPayload struct {
	TaskID     string `json:"task_id"`
	RootTaskID string `json:"root_task_id,omitempty"`
}

// TaskAssignedPayload represents the data for a TaskAssigned event
type TaskAssignedPayload struct {
	TaskID     string `json:"task_id"`
	RootTaskID string `json:"root_task_id,omitempty"`
	WorkerType string `json:"worker_type"`
	WorkerID   string `json:"worker_id"`
}

// TaskStartedPayload represents the data for a TaskStarted event
type TaskStartedPayload struct {
	TaskID     string `json:"task_id"`
	RootTaskID string `json:"root_task_id,omitempty"`
	WorkerID   string `json:"worker_id,omitempty"` // Optional: ID of the specific worker instance
}

// TaskCompletedPayload represents the data for a TaskCompleted event
type TaskCompletedPayload struct {
	TaskID     string      `json:"task_id"`
	RootTaskID string      `json:"root_task_id,omitempty"`
	Result     interface{} `json:"result"`
}

// TaskFailedPayload represents the data for a TaskFailed event
type TaskFailedPayload struct {
	TaskID     string `json:"task_id"`
	RootTaskID string `json:"root_task_id,omitempty"`
	ErrorInfo  string `json:"error_info"`
}

// SubtasksPlannedPayload represents the data for a SubtasksPlanned event
type SubtasksPlannedPayload struct {
	ParentTaskID string    `json:"parent_task_id"`
	RootTaskID   string    `json:"root_task_id,omitempty"`
	Subtasks     []Subtask `json:"subtasks"`
}

// Subtask represents a single subtask created during planning
type Subtask struct {
	TaskID       string   `json:"task_id"`
	Goal         string   `json:"goal"`
	TaskType     string   `json:"task_type"`
	Dependencies []string `json:"dependencies,omitempty"`
}
