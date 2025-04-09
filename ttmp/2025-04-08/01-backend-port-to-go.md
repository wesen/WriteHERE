# WriteHERE: Go Backend Porting Plan

This document outlines the plan and architecture for porting the WriteHERE Python Flask backend server (`backend/server.py`) to Go. The goal is to create a robust, performant, and maintainable backend service using idiomatic Go practices and standard libraries.

## 1. Introduction

The existing backend server provides a REST API and WebSocket interface to manage and monitor the core recursive writing engine. The Go port aims to replicate this functionality, initially with mocked engine interactions, paving the way for integrating the actual Go engine port later.

**Key Technologies:**

- **Language:** Go
- **CLI Framework:** `github.com/spf13/cobra`
- **Logging:** `github.com/rs/zerolog`
- **HTTP Framework:** `github.com/gin-gonic/gin`
- **WebSocket:** `github.com/gorilla/websocket`
- **UUIDs:** `github.com/google/uuid`

## 2. Project Structure

A standard Go project layout will be used:

```
writehere-go/
├── cmd/
│   └── backend/
│       └── main.go       # Cobra entry point & server startup
├── internal/
│   ├── api/              # Gin HTTP handlers and routing setup
│   ├── models/           # Core data structures (Task, TaskStatus, etc.)
│   ├── server/           # HTTP server setup and lifecycle management
│   ├── task/             # Task management logic (mocked initially)
│   └── websocket/        # WebSocket hub, client management, message handling
├── pkg/
│   └── log/              # Logging setup and configuration
├── go.mod
└── go.sum
```

## 3. Libraries Rationale

- **Cobra:** Industry standard for building Go CLI applications, providing flags, subcommands, etc.
- **Zerolog:** High-performance structured JSON logger, excellent for production environments.
- **Gin:** Fast, popular, and well-documented HTTP framework with a good middleware ecosystem.
- **Gorilla WebSocket:** The most widely used and robust WebSocket implementation for Go.
- **Google UUID:** Standard library for generating universally unique identifiers.

## 4. API Endpoint Mapping (Python -> Go)

The following table maps the existing Python API endpoints to their proposed Go counterparts and initial mocked behavior:

| Python Endpoint              | Method | Go Handler (Proposed)       | Mocked Behavior                                              |
| ---------------------------- | ------ | --------------------------- | ------------------------------------------------------------ |
| `/api/generate-story`        | POST   | `api.GenerateStoryHandler`  | Create mock task in store, return task ID, simulate progress |
| `/api/generate-report`       | POST   | `api.GenerateReportHandler` | Create mock task in store, return task ID, simulate progress |
| `/api/status/<task_id>`      | GET    | `api.GetStatusHandler`      | Return current mock status from store                        |
| `/api/result/<task_id>`      | GET    | `api.GetResultHandler`      | Return mock result text when status is "completed"           |
| `/api/task-graph/<task_id>`  | GET    | `api.GetTaskGraphHandler`   | Return static mock graph structure                           |
| `/api/workspace/<task_id>`   | GET    | `api.GetWorkspaceHandler`   | Return static mock article content                           |
| `/api/history`               | GET    | `api.GetHistoryHandler`     | Return list of all mock tasks from store                     |
| `/api/reload`                | POST   | `api.ReloadHandler`         | Log "Reload not implemented" message, return OK              |
| `/api/stop-task/<task_id>`   | POST   | `api.StopTaskHandler`       | Trigger mock task status change to "stopped" in store        |
| `/api/delete-task/<task_id>` | DELETE | `api.DeleteTaskHandler`     | Remove mock task from store                                  |
| `/api/ping`                  | GET    | `api.PingHandler`           | Return simple `{"status": "ok"}`                             |

## 5. WebSocket Event Mapping (Python SocketIO -> Go WebSocket)

WebSocket communication will shift from SocketIO events to JSON messages with a `type` field.

| Python Event          | Direction     | Go WebSocket Message (Proposed)                                                              | Mocked Behavior                                              |
| --------------------- | ------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `connect`             | Client→Server | (handled by Gorilla connect)                                                                 | Log connection established                                   |
| `disconnect`          | Client→Server | (handled by Gorilla disconnect)                                                              | Log connection closed, unregister client                     |
| `subscribe_to_task`   | Client→Server | `{"type": "subscribe", "payload": {"taskId": "..."}}`                                        | Register client for specific task updates, send confirmation |
| `subscription_status` | Server→Client | `{"type": "subscription_status", "payload": {"status": "subscribed", "taskId": "..."}}`      | Sent upon successful subscription registration               |
| `task_update`         | Server→Client | `{"type": "task_update", "payload": {"taskId": "...", "status": "...", "taskGraph": {...}}}` | Sent periodically by mock task simulation                    |
| `connection_test`     | Server→Client | `{"type": "connection_test", "payload": {"message": "Server connected"}}`                    | Sent immediately after a client connects                     |

## 6. Go Data Structures (`internal/models/`)

Initial data structures will represent tasks and manage their state.

```go
package models

import (
    "sync"
    "time"
)

// TaskStatus defines the possible states of a task.
type TaskStatus string

const (
    StatusStarting   TaskStatus = "starting"
    StatusRunning    TaskStatus = "running"
    StatusCompleted  TaskStatus = "completed"
    StatusError      TaskStatus = "error"
    StatusStopped    TaskStatus = "stopped"
)

// Task represents a single writing task.
type Task struct {
    ID           string       `json:"taskId"`
    Type         string       `json:"type"` // "story" or "report"
    Prompt       string       `json:"prompt"`
    Model        string       `json:"model"`
    Status       TaskStatus   `json:"status"`
    Result       string       `json:"result,omitempty"`
    Error        string       `json:"error,omitempty"`
    StartTime    time.Time    `json:"startTime"`
    UpdateTime   time.Time    `json:"updateTime"`
    SearchEngine *string      `json:"searchEngine,omitempty"` // Pointer to allow null

    // -- Mock Simulation Fields --
    // These fields are not exposed via JSON but used internally for simulation
    stopSignal     chan struct{} // Channel to signal stopping the simulation
    MockProgress   int           // Simulated progress percentage
    MockGraph      interface{}   // Placeholder for mock graph data
    MockWorkspace  string        // Placeholder for mock workspace content
    SimulateError  bool          // Flag to force an error state simulation
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
func (ts *TaskStore) AddTask(task *Task) { /* ... implementation ... */ }

// GetTask retrieves a task by ID.
func (ts *TaskStore) GetTask(id string) (*Task, bool) { /* ... implementation ... */ }

// UpdateTask updates an existing task (or specific fields).
func (ts *TaskStore) UpdateTask(task *Task) error { /* ... implementation ... */ }

// DeleteTask removes a task by ID.
func (ts *TaskStore) DeleteTask(id string) { /* ... implementation ... */ }

// ListTasks returns a slice of all tasks.
func (ts *TaskStore) ListTasks() []*Task { /* ... implementation ... */ }

// Helper methods for updating status, result etc. can be added.
```

## 7. Mocking Strategy

The initial implementation will focus on setting up the server structure and API/WebSocket interfaces. The core engine logic will be mocked:

1.  **Task Creation:** API handlers (`GenerateStory`, `GenerateReport`) will create a `models.Task` object, add it to the `TaskStore`, and immediately return the `taskId`.
2.  **Task Simulation:** A separate goroutine will be launched per task (`task.SimulateTaskProgress`). This goroutine will:
    - Periodically update the task's status in the `TaskStore` (e.g., `Starting` -> `Running` -> `Completed`/`Error`/`Stopped`).
    - Generate mock data for `Result`, `MockGraph`, `MockWorkspace` upon completion/error.
    - Send `task_update` messages via the WebSocket hub to subscribed clients at each status change.
    - Listen for a stop signal on the task's `stopSignal` channel.
3.  **Task Management:** The `internal/task` package will house the `MockTaskManager` responsible for creating tasks and starting their simulation goroutines.
4.  **API Handlers:** Handlers will interact primarily with the `TaskStore` to retrieve status, results, etc., and with the `MockTaskManager` to initiate actions like stopping or deleting tasks.

This approach allows testing the API and frontend integration without needing the full recursive engine port.

## 8. Next Steps

Once the mocked backend is functional:

1.  Refine error handling and validation.
2.  Implement authentication/authorization if needed.
3.  Begin porting the core recursive engine logic from Python to Go.
4.  Create a real `TaskManager` implementation in `internal/task` that interacts with the Go engine.
5.  Replace the `MockTaskManager` with the real implementation.
6.  Integrate actual task graph generation and workspace updates.
7.  Add comprehensive tests.
