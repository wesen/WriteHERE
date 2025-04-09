package task

import (
	"context"
	"fmt"
	"math/rand"
	"strings"
	"sync"
	"time"

	"writehere-go/internal/models"
	"writehere-go/internal/websocket"
	"writehere-go/pkg/log"

	"github.com/google/uuid"
)

// MockTaskManager manages tasks using mocked behavior.
type MockTaskManager struct {
	taskStore   *models.TaskStore
	wsHub       *websocket.Hub
	mu          sync.Mutex // Mutex for cancelFuncs map
	cancelFuncs map[string]context.CancelFunc
}

// Verify MockTaskManager implements the interface expected by websocket.Hub
var _ websocket.TaskManager = &MockTaskManager{}

// NewMockTaskManager creates a new MockTaskManager.
func NewMockTaskManager(store *models.TaskStore, hub *websocket.Hub) *MockTaskManager {
	return &MockTaskManager{
		taskStore:   store,
		wsHub:       hub,
		cancelFuncs: make(map[string]context.CancelFunc),
	}
}

// GetTask retrieves a task (needed for websocket.TaskManager interface).
func (m *MockTaskManager) GetTask(id string) (*models.Task, bool) {
	return m.taskStore.GetTask(id)
}

// SendInitialData sends the current task state to a newly subscribed client.
func (m *MockTaskManager) SendInitialData(ctx context.Context, taskID string, client *websocket.Client) {
	task, exists := m.GetTask(taskID)
	if !exists {
		log.Log.Warn().Str("taskId", taskID).Msg("Attempted to send initial data for non-existent task")
		// Optionally send an error message back to the client?
		return
	}
	log.Log.Debug().Str("taskId", taskID).Msg("Sending initial task data to new subscriber")
	client.SendTaskUpdate(task)
}

// CreateStoryTask creates a new story task and starts its simulation.
func (m *MockTaskManager) CreateStoryTask(ctx context.Context, prompt, model string) (*models.Task, error) {
	taskID := fmt.Sprintf("story-%s", uuid.NewString()[:8])
	task := models.NewTask(taskID, "story", prompt, model, nil, false) // No search, no forced error
	m.taskStore.AddTask(task)
	log.Log.Info().Str("taskId", taskID).Str("type", "story").Msg("Created new mock story task")

	// Create a context that can be cancelled specifically for this task
	taskCtx, cancel := context.WithCancel(ctx) // Inherit from request context if needed, or use background
	m.storeCancelFunc(taskID, cancel)

	go m.SimulateTaskProgress(taskCtx, task)

	return task, nil
}

// CreateReportTask creates a new report task and starts its simulation.
func (m *MockTaskManager) CreateReportTask(ctx context.Context, prompt, model string, enableSearch bool, searchEngine string) (*models.Task, error) {
	taskID := fmt.Sprintf("report-%s", uuid.NewString()[:8])
	var se *string
	if enableSearch {
		if searchEngine == "" {
			searchEngine = "mock-search" // Default mock search
		}
		se = &searchEngine
	}
	task := models.NewTask(taskID, "report", prompt, model, se, false) // No forced error
	m.taskStore.AddTask(task)
	log.Log.Info().Str("taskId", taskID).Str("type", "report").Bool("searchEnabled", enableSearch).Msg("Created new mock report task")

	// Create a context that can be cancelled specifically for this task
	taskCtx, cancel := context.WithCancel(ctx) // Inherit from request context if needed, or use background
	m.storeCancelFunc(taskID, cancel)

	go m.SimulateTaskProgress(taskCtx, task)

	return task, nil
}

// storeCancelFunc stores the cancel function for a task.
func (m *MockTaskManager) storeCancelFunc(taskID string, cancel context.CancelFunc) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.cancelFuncs[taskID] = cancel
}

// removeCancelFunc removes and returns the cancel function for a task.
func (m *MockTaskManager) removeCancelFunc(taskID string) context.CancelFunc {
	m.mu.Lock()
	defer m.mu.Unlock()
	cancel, exists := m.cancelFuncs[taskID]
	if exists {
		delete(m.cancelFuncs, taskID)
		return cancel
	}
	return nil
}

// StopTask signals a running task simulation to stop using context cancellation.
func (m *MockTaskManager) StopTask(taskID string) error {
	task, exists := m.taskStore.GetTask(taskID)
	if !exists {
		return fmt.Errorf("task %s not found", taskID)
	}

	if task.Status == models.StatusRunning || task.Status == models.StatusStarting {
		log.Log.Info().Str("taskId", taskID).Msg("Sending stop signal (context cancel) to task simulation")
		if cancel := m.removeCancelFunc(taskID); cancel != nil {
			cancel() // Cancel the context
			// The simulation goroutine will handle status update to Stopped
		} else {
			log.Log.Warn().Str("taskId", taskID).Msg("Cancel function not found for running task")
			// Might need to update status directly if cancel func is missing?
			_ = m.taskStore.UpdateTaskStatus(taskID, models.StatusStopped) // Best effort
			m.wsHub.BroadcastTaskUpdate(task)                              // Broadcast the potential direct update
		}
	} else {
		log.Log.Warn().Str("taskId", taskID).Str("status", string(task.Status)).Msg("Cannot stop task, not in a stoppable state")
		return fmt.Errorf("task %s is already %s", taskID, task.Status)
	}
	return nil
}

// DeleteTask stops a task (if running) and removes it from the store.
func (m *MockTaskManager) DeleteTask(taskID string) error {
	// Ensure task exists before attempting to stop/delete
	task, exists := m.taskStore.GetTask(taskID)
	if !exists {
		return fmt.Errorf("task %s not found", taskID)
	}

	// Attempt to stop if running by cancelling its context
	if task.Status == models.StatusRunning || task.Status == models.StatusStarting {
		log.Log.Info().Str("taskId", taskID).Msg("Stopping task via context cancel before deletion")
		if cancel := m.removeCancelFunc(taskID); cancel != nil {
			cancel()
			// Give a brief moment for the simulation to potentially react to stop signal
			time.Sleep(100 * time.Millisecond)
		} else {
			log.Log.Warn().Str("taskId", taskID).Msg("Cancel function not found for running task during delete")
		}
	}

	// Remove from store regardless of stop success
	m.taskStore.DeleteTask(taskID)
	log.Log.Info().Str("taskId", taskID).Msg("Deleted task from store")

	// Ensure cancel func is removed if it wasn't already (e.g., task completed before delete)
	if cancel := m.removeCancelFunc(taskID); cancel != nil {
		// This cancel() might be redundant if already called, but ensures cleanup
		cancel()
	}

	// Optionally notify WebSocket clients about deletion?
	return nil
}

// SimulateTaskProgress simulates the lifecycle of a task, respecting context cancellation.
func (m *MockTaskManager) SimulateTaskProgress(ctx context.Context, task *models.Task) {
	log.Log.Info().Str("taskId", task.ID).Msg("Starting task simulation")
	// Ensure cancel func is removed when simulation ends (normally or via cancel)
	defer func() {
		if cancel := m.removeCancelFunc(task.ID); cancel != nil {
			// Calling cancel() here might be redundant if stopped via StopTask,
			// but ensures cleanup if the goroutine exits for other reasons.
			cancel()
		}
		log.Log.Info().Str("taskId", task.ID).Msg("Task simulation ended")
	}()

	// --- Starting Phase ---
	select {
	case <-ctx.Done(): // Check for cancellation
		m.handleStop(task) // Use handleStop for consistent stopped state update
		return
	case <-time.After(time.Duration(rand.Intn(500)+100) * time.Millisecond): // 100-600ms
		m.updateStatusAndBroadcast(task, models.StatusRunning)
	}

	// --- Running Phase ---
	totalSteps := 5 + rand.Intn(10) // Simulate 5-14 steps
	for i := 0; i < totalSteps; i++ {
		select {
		case <-ctx.Done(): // Check for cancellation
			m.handleStop(task)
			return
		case <-time.After(time.Duration(rand.Intn(1000)+500) * time.Millisecond): // 0.5-1.5 seconds per step
			// Check context again *after* the sleep/wait
			if ctx.Err() != nil {
				m.handleStop(task)
				return
			}

			progress := (i + 1) * 100 / totalSteps
			newGraph := m.updateMockGraph(task.MockGraph, fmt.Sprintf("Step %d completed", i+1))
			newWorkspace := fmt.Sprintf("%s\nProcessed step %d.", task.MockWorkspace, i+1)

			if err := m.taskStore.UpdateTaskMockData(task.ID, progress, newGraph, newWorkspace); err != nil {
				log.Log.Error().Err(err).Str("taskId", task.ID).Msg("Failed to update mock data")
				// Continue simulation or stop?
			}
			// Update local task struct fields AFTER successful store update
			task.MockProgress = progress
			task.MockGraph = newGraph
			task.MockWorkspace = newWorkspace

			m.wsHub.BroadcastTaskUpdate(task)
		}
		// Simulate random intermediate errors (rarely)
		if !task.SimulateError && rand.Intn(100) < 5 { // 5% chance per step
			log.Log.Warn().Str("taskId", task.ID).Msg("Simulating random error during running phase")
			task.SimulateError = true
		}
	}

	// Check context one last time before declaring completion
	if ctx.Err() != nil {
		m.handleStop(task)
		return
	}

	// --- Completion Phase ---
	finalStatus := models.StatusCompleted
	finalResult := fmt.Sprintf("Mock result for %s: %s", task.Type, task.Prompt)
	finalError := ""

	if task.SimulateError {
		finalStatus = models.StatusError
		finalResult = ""
		finalError = "Simulated task error"
		log.Log.Warn().Str("taskId", task.ID).Msg("Simulation ended with simulated error")
	} else {
		log.Log.Info().Str("taskId", task.ID).Msg("Simulation completed successfully")
		// Update mock data one last time for completion
		task.MockProgress = 100
		task.MockGraph = m.updateMockGraph(task.MockGraph, "Task Finished")
		task.MockWorkspace = finalResult // Final workspace is the result
		_ = m.taskStore.UpdateTaskMockData(task.ID, task.MockProgress, task.MockGraph, task.MockWorkspace)
	}

	if err := m.taskStore.UpdateTaskResult(task.ID, finalStatus, finalResult, finalError); err != nil {
		log.Log.Error().Err(err).Str("taskId", task.ID).Msg("Failed to update final task result")
	} else {
		// Update local task state AFTER successful store update
		task.Status = finalStatus
		task.Result = finalResult
		task.Error = finalError
		m.wsHub.BroadcastTaskUpdate(task)
	}
}

// handleStop updates task status when a stop signal (context cancellation) is received.
func (m *MockTaskManager) handleStop(task *models.Task) {
	// Check current status to avoid overwriting a completed/error state if StopTask was called late
	currentTask, exists := m.taskStore.GetTask(task.ID)
	if !exists || (currentTask.Status != models.StatusRunning && currentTask.Status != models.StatusStarting) {
		log.Log.Info().Str("taskId", task.ID).Str("status", string(currentTask.Status)).Msg("Stop signal received, but task already stopped/completed/errored. No update needed.")
		return
	}

	log.Log.Info().Str("taskId", task.ID).Msg("Task simulation received stop signal (context done)")
	finalResult := "Task stopped by user request."
	finalError := ""
	finalStatus := models.StatusStopped

	// Update mock data for stopped state
	// Use the potentially updated local task struct for graph/workspace
	stoppedGraph := m.updateMockGraph(task.MockGraph, "Task Stopped")
	stoppedWorkspace := finalResult
	_ = m.taskStore.UpdateTaskMockData(task.ID, task.MockProgress, stoppedGraph, stoppedWorkspace)

	if err := m.taskStore.UpdateTaskResult(task.ID, finalStatus, finalResult, finalError); err != nil {
		log.Log.Error().Err(err).Str("taskId", task.ID).Msg("Failed to update task result after stop")
	} else {
		// Update local task state AFTER successful store update
		task.Status = finalStatus
		task.Result = finalResult
		task.Error = finalError
		task.MockGraph = stoppedGraph         // Update local graph state
		task.MockWorkspace = stoppedWorkspace // Update local workspace state
		m.wsHub.BroadcastTaskUpdate(task)
	}
}

// updateStatusAndBroadcast updates status in store and notifies WS clients.
func (m *MockTaskManager) updateStatusAndBroadcast(task *models.Task, status models.TaskStatus) {
	if err := m.taskStore.UpdateTaskStatus(task.ID, status); err != nil {
		log.Log.Error().Err(err).Str("taskId", task.ID).Str("newStatus", string(status)).Msg("Failed to update task status")
	} else {
		// Update local task state AFTER successful store update
		task.Status = status
		m.wsHub.BroadcastTaskUpdate(task)
	}
}

// updateMockGraph simulates updating the task graph structure.
// This is a placeholder - a real implementation would be much more complex.
func (m *MockTaskManager) updateMockGraph(currentGraph interface{}, message string) interface{} {
	// Deep copy the map to avoid race conditions if the task struct's map is read elsewhere
	// For mock purposes, a shallow copy might suffice, but deep copy is safer.
	// This simple implementation just modifies in place, assuming mock scenario is fine.
	graphMap, ok := currentGraph.(map[string]interface{})
	if !ok {
		log.Log.Warn().Msg("Current graph is not a map, cannot update")
		// Return a new basic graph on error?
		return map[string]interface{}{"id": "error", "goal": "Graph update failed", "status": "FAILED"}
	}

	// Simulate finding the 'active' node and updating its goal/status
	subTasks, ok := graphMap["sub_tasks"].([]interface{})
	if !ok || len(subTasks) == 0 {
		// No subtasks to update, maybe update root?
		graphMap["goal"] = message   // Update root goal as fallback
		graphMap["status"] = "DOING" // Assume still doing if updating message
		if message == "Task Finished" {
			graphMap["status"] = "FINISH"
		} else if message == "Task Stopped" {
			graphMap["status"] = "FAILED" // Or a custom 'STOPPED' status if defined
		}
		return graphMap
	}

	// Find first non-finished subtask (simplistic)
	updated := false
	for _, subTaskInterface := range subTasks {
		subTask, ok := subTaskInterface.(map[string]interface{})
		if !ok {
			continue
		}
		if status, ok := subTask["status"].(string); ok && status != "FINISH" {
			subTask["goal"] = message
			subTask["status"] = "DOING"
			if message == "Task Finished" {
				subTask["status"] = "FINISH"
			} else if message == "Task Stopped" {
				subTask["status"] = "FAILED"
			}
			updated = true
			break
		}
	}

	// If all subtasks were finished, update the root node status
	if !updated && (message == "Task Finished" || message == "Task Stopped") {
		graphMap["goal"] = message
		graphMap["status"] = "FINISH"
		if message == "Task Stopped" {
			graphMap["status"] = "FAILED"
		}
	}

	graphMap["last_update_message"] = message // Add for debugging

	return graphMap
}

// Helper to truncate prompt for history
func TruncatePrompt(prompt string, maxLength int) string {
	if len(prompt) <= maxLength {
		return prompt
	}
	// Try to truncate at a word boundary
	lastSpace := strings.LastIndex(prompt[:maxLength-3], " ")
	if lastSpace > 0 {
		return prompt[:lastSpace] + "..."
	}
	// Fallback to hard truncate
	return prompt[:maxLength-3] + "..."
}
