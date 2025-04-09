package models

import (
	"fmt"
	"sync"
	"time"
)

// TaskStatus defines the possible states of a task.
type TaskStatus string

const (
	StatusStarting  TaskStatus = "starting"
	StatusRunning   TaskStatus = "running"
	StatusCompleted TaskStatus = "completed"
	StatusError     TaskStatus = "error"
	StatusStopped   TaskStatus = "stopped"
)

// Task represents a single writing task.
type Task struct {
	ID           string     `json:"taskId"`
	Type         string     `json:"type"` // "story" or "report"
	Prompt       string     `json:"prompt"`
	Model        string     `json:"model"`
	Status       TaskStatus `json:"status"`
	Result       string     `json:"result,omitempty"`
	Error        string     `json:"error,omitempty"`
	StartTime    time.Time  `json:"startTime"`
	UpdateTime   time.Time  `json:"updateTime"`
	SearchEngine *string    `json:"searchEngine,omitempty"` // Pointer to allow null

	// -- Mock Simulation Fields --
	// StopSignal    chan struct{} // Channel to signal stopping the simulation -- Replaced by context
	MockProgress  int         // Simulated progress percentage
	MockGraph     interface{} // Placeholder for mock graph data
	MockWorkspace string      // Placeholder for mock workspace content
	SimulateError bool        // Flag to force an error state simulation
}

// NewTask creates a new Task instance.
func NewTask(id, taskType, prompt, model string, searchEngine *string, simulateError bool) *Task {
	return &Task{
		ID:           id,
		Type:         taskType,
		Prompt:       prompt,
		Model:        model,
		Status:       StatusStarting,
		StartTime:    time.Now(),
		UpdateTime:   time.Now(),
		SearchEngine: searchEngine,
		// StopSignal:    make(chan struct{}), // Removed
		MockProgress:  0,
		MockGraph:     createMockGraph(id, prompt), // Initial mock graph
		MockWorkspace: "",                          // Initial workspace
		SimulateError: simulateError,
	}
}

// createMockGraph generates a simple mock graph structure.
func createMockGraph(taskID, prompt string) map[string]interface{} {
	return map[string]interface{}{
		"id":        "", // Root node usually has no specific NID in the structure shown
		"goal":      prompt,
		"task_type": "write", // Assuming top-level is always 'write'
		"status":    "DOING", // Initial status
		"node_type": "PLAN_NODE",
		"sub_tasks": []interface{}{
			map[string]interface{}{
				"id":        "0",
				"goal":      "Initializing...",
				"task_type": "think",
				"status":    "READY",
				"node_type": "EXECUTE_NODE",
				"sub_tasks": []interface{}{},
			},
		},
	}
}

// TaskStore provides thread-safe storage for tasks.
type TaskStore struct {
	mu    sync.RWMutex
	tasks map[string]*Task
}

// NewTaskStore creates a new TaskStore.
func NewTaskStore() *TaskStore {
	return &TaskStore{
		tasks: make(map[string]*Task),
	}
}

// AddTask adds a new task to the store.
func (ts *TaskStore) AddTask(task *Task) {
	task.UpdateTime = time.Now()
	task.StartTime = time.Now() // Ensure start time is set on add
	task.Status = StatusStarting
	task.MockProgress = 0
	task.MockGraph = createMockGraph(task.ID, task.Prompt) // Ensure graph is fresh on add
	task.MockWorkspace = ""
	ts.mu.Lock()
	defer ts.mu.Unlock()
	ts.tasks[task.ID] = task
}

// GetTask retrieves a task by ID.
func (ts *TaskStore) GetTask(id string) (*Task, bool) {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	task, exists := ts.tasks[id]
	return task, exists
}

// UpdateTaskStatus updates the status and UpdateTime of a task.
func (ts *TaskStore) UpdateTaskStatus(id string, status TaskStatus) error {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	task, exists := ts.tasks[id]
	if !exists {
		return fmt.Errorf("task %s not found", id)
	}
	task.Status = status
	task.UpdateTime = time.Now()
	return nil
}

// UpdateTaskResult updates the result, error, status, and UpdateTime of a task.
func (ts *TaskStore) UpdateTaskResult(id string, status TaskStatus, result, errMsg string) error {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	task, exists := ts.tasks[id]
	if !exists {
		return fmt.Errorf("task %s not found", id)
	}
	task.Status = status
	task.Result = result
	task.Error = errMsg
	task.UpdateTime = time.Now()
	return nil
}

// UpdateTaskMockData updates mock-specific fields.
func (ts *TaskStore) UpdateTaskMockData(id string, progress int, graph interface{}, workspace string) error {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	task, exists := ts.tasks[id]
	if !exists {
		return fmt.Errorf("task %s not found", id)
	}
	task.MockProgress = progress
	task.MockGraph = graph
	task.MockWorkspace = workspace
	task.UpdateTime = time.Now()
	return nil
}

// DeleteTask removes a task by ID.
func (ts *TaskStore) DeleteTask(id string) {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	delete(ts.tasks, id)
}

// ListTasks returns a slice of all tasks, sorted by StartTime descending.
func (ts *TaskStore) ListTasks() []*Task {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	tasks := make([]*Task, 0, len(ts.tasks))
	for _, task := range ts.tasks {
		tasks = append(tasks, task)
	}
	// Sort by StartTime descending (newest first)
	// TODO: Consider if sorting is needed or if frontend handles it
	return tasks
}

// --- Helper functions for API responses ---

// TaskStatusResponse is the structure for the /api/status/<task_id> endpoint.
type TaskStatusResponse struct {
	TaskID       string     `json:"taskId"`
	Status       TaskStatus `json:"status"`
	Error        string     `json:"error,omitempty"`
	ElapsedTime  float64    `json:"elapsedTime"`
	Model        string     `json:"model"`
	SearchEngine *string    `json:"searchEngine,omitempty"`
	// TODO: Add progress if needed
}

// TaskResultResponse is the structure for the /api/result/<task_id> endpoint.
type TaskResultResponse struct {
	TaskID       string  `json:"taskId"`
	Result       string  `json:"result"`
	Model        string  `json:"model"`
	SearchEngine *string `json:"searchEngine,omitempty"`
}

// TaskGraphResponse is the structure for the /api/task-graph/<task_id> endpoint.
type TaskGraphResponse struct {
	TaskID    string      `json:"taskId"`
	TaskGraph interface{} `json:"taskGraph"`
}

// WorkspaceResponse is the structure for the /api/workspace/<task_id> endpoint.
type WorkspaceResponse struct {
	TaskID    string `json:"taskId"`
	Workspace string `json:"workspace"`
}

// HistoryItem represents a single item in the /api/history response.
type HistoryItem struct {
	TaskID    string `json:"taskId"`
	Prompt    string `json:"prompt"` // Truncated prompt
	Type      string `json:"type"`
	CreatedAt string `json:"createdAt"` // Formatted date string
}

// HistoryResponse is the structure for the /api/history endpoint.
type HistoryResponse struct {
	History []HistoryItem `json:"history"`
}

// GenerateStoryRequest is the structure for the /api/generate-story request body.
type GenerateStoryRequest struct {
	Prompt  string            `json:"prompt" binding:"required"`
	Model   string            `json:"model" binding:"required"`
	APIKeys map[string]string `json:"apiKeys" binding:"required"` // Not used in mock
}

// GenerateReportRequest is the structure for the /api/generate-report request body.
type GenerateReportRequest struct {
	Prompt       string            `json:"prompt" binding:"required"`
	Model        string            `json:"model" binding:"required"`
	APIKeys      map[string]string `json:"apiKeys" binding:"required"` // Not used in mock
	EnableSearch bool              `json:"enableSearch"`
	SearchEngine string            `json:"searchEngine"`
}

// TaskCreationResponse is the common response structure for task creation endpoints.
type TaskCreationResponse struct {
	TaskID string `json:"taskId"`
	Status string `json:"status"` // e.g., "started"
}

// SimpleResponse is used for endpoints like reload, stop, delete.
type SimpleResponse struct {
	Status  string `json:"status"`
	Message string `json:"message,omitempty"`
	Error   string `json:"error,omitempty"`
}

// PingResponse is used for the /api/ping endpoint.
type PingResponse struct {
	Status  string `json:"status"`
	Message string `json:"message"`
	Version string `json:"version"`
}
