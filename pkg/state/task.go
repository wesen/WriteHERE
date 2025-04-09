package state

import (
	"time"

	"github.com/google/uuid"
)

// TaskStatus represents the current state of a task
type TaskStatus string

// Possible task statuses
const (
	TaskStatusPendingDeps  TaskStatus = "PENDING_DEPS"
	TaskStatusReady        TaskStatus = "READY"
	TaskStatusAssigned     TaskStatus = "ASSIGNED"
	TaskStatusRunning      TaskStatus = "RUNNING"
	TaskStatusCompleted    TaskStatus = "COMPLETED"
	TaskStatusFailed       TaskStatus = "FAILED"
	TaskStatusPaused       TaskStatus = "PAUSED"
	TaskStatusRetryPending TaskStatus = "RETRY_PENDING"
)

// TaskType represents the type of a task
type TaskType string

// Possible task types
const (
	TaskTypeComposition TaskType = "COMPOSITION"
	TaskTypeReasoning   TaskType = "REASONING"
	TaskTypeRetrieval   TaskType = "RETRIEVAL"
	TaskTypePlanning    TaskType = "PLANNING"
	TaskTypeReflection  TaskType = "REFLECTION"
	TaskTypeAggregation TaskType = "AGGREGATION"
	TaskTypeExecution   TaskType = "EXECUTION"
)

// Task represents a unit of work in the system
type Task struct {
	TaskID               string                 `json:"task_id"`
	ParentTaskID         string                 `json:"parent_task_id,omitempty"`
	RootTaskID           string                 `json:"root_task_id,omitempty"`
	Goal                 string                 `json:"goal"`
	TaskType             TaskType               `json:"task_type"`
	Status               TaskStatus             `json:"status"`
	Dependencies         []string               `json:"dependencies,omitempty"`
	Dependents           []string               `json:"dependents,omitempty"`
	InputData            map[string]interface{} `json:"input_data,omitempty"`
	Result               interface{}            `json:"result,omitempty"`
	ErrorInfo            string                 `json:"error_info,omitempty"`
	AssignedWorkerID     string                 `json:"assigned_worker_id,omitempty"`
	CreatedAt            time.Time              `json:"created_at"`
	UpdatedAt            time.Time              `json:"updated_at"`
	Metadata             map[string]interface{} `json:"metadata,omitempty"`
	DetailedStatus       string                 `json:"detailed_status,omitempty"`
	RequiredCapabilities []string               `json:"required_capabilities,omitempty"`
	AgentState           interface{}            `json:"agent_state,omitempty"`
}

// NewTask creates a new task with a unique ID and other defaults
func NewTask(goal string, taskType TaskType, parentTaskID, rootTaskID string) *Task {
	taskID := uuid.New().String()
	now := time.Now()

	// If this is a root task, set its own ID as the rootTaskID
	if rootTaskID == "" {
		rootTaskID = taskID
	}

	return &Task{
		TaskID:       taskID,
		ParentTaskID: parentTaskID,
		RootTaskID:   rootTaskID,
		Goal:         goal,
		TaskType:     taskType,
		Status:       TaskStatusPendingDeps,
		Dependencies: []string{},
		Dependents:   []string{},
		CreatedAt:    now,
		UpdatedAt:    now,
		Metadata:     make(map[string]interface{}),
	}
}

// IsReady checks if a task is ready to be processed (all dependencies are completed)
func (t *Task) IsReady(completedTaskIDs map[string]bool) bool {
	if t.Status != TaskStatusPendingDeps {
		return false
	}

	for _, depID := range t.Dependencies {
		if !completedTaskIDs[depID] {
			return false
		}
	}

	return true
}

// UpdateStatus changes the task status and updates the UpdatedAt timestamp
func (t *Task) UpdateStatus(status TaskStatus) {
	t.Status = status
	t.UpdatedAt = time.Now()
}
