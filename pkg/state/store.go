package state

import (
	"context"
	"sync"

	"github.com/pkg/errors"
)

// Store defines the interface for task state storage
type Store interface {
	// Task operations
	CreateTask(ctx context.Context, task *Task) error
	GetTask(ctx context.Context, taskID string) (*Task, error)
	UpdateTask(ctx context.Context, task *Task) error
	DeleteTask(ctx context.Context, taskID string) error
	ListTasks(ctx context.Context, filter map[string]interface{}) ([]*Task, error)

	// Dependency operations
	AddDependency(ctx context.Context, taskID, dependencyID string) error
	RemoveDependency(ctx context.Context, taskID, dependencyID string) error
	GetDependents(ctx context.Context, taskID string) ([]string, error)

	// Query operations
	GetTasksByStatus(ctx context.Context, status TaskStatus) ([]*Task, error)
	GetTasksByRootID(ctx context.Context, rootTaskID string) ([]*Task, error)
	GetReadyTasks(ctx context.Context) ([]*Task, error)
}

// InMemoryStore is a simple in-memory implementation of the Store interface
type InMemoryStore struct {
	tasks map[string]*Task
	mu    sync.RWMutex
}

// NewInMemoryStore creates a new in-memory state store
func NewInMemoryStore() *InMemoryStore {
	return &InMemoryStore{
		tasks: make(map[string]*Task),
	}
}

// CreateTask adds a new task to the store
func (s *InMemoryStore) CreateTask(ctx context.Context, task *Task) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.tasks[task.TaskID]; exists {
		return errors.Errorf("task with ID %s already exists", task.TaskID)
	}

	s.tasks[task.TaskID] = task
	return nil
}

// GetTask retrieves a task by ID
func (s *InMemoryStore) GetTask(ctx context.Context, taskID string) (*Task, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	task, exists := s.tasks[taskID]
	if !exists {
		return nil, errors.Errorf("task with ID %s not found", taskID)
	}

	return task, nil
}

// UpdateTask updates an existing task
func (s *InMemoryStore) UpdateTask(ctx context.Context, task *Task) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.tasks[task.TaskID]; !exists {
		return errors.Errorf("task with ID %s not found", task.TaskID)
	}

	s.tasks[task.TaskID] = task
	return nil
}

// DeleteTask removes a task from the store
func (s *InMemoryStore) DeleteTask(ctx context.Context, taskID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.tasks[taskID]; !exists {
		return errors.Errorf("task with ID %s not found", taskID)
	}

	delete(s.tasks, taskID)
	return nil
}

// ListTasks retrieves tasks matching a filter
func (s *InMemoryStore) ListTasks(ctx context.Context, filter map[string]interface{}) ([]*Task, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// For simplicity, this in-memory implementation ignores filters
	// A real implementation would filter based on the provided criteria
	var result []*Task
	for _, task := range s.tasks {
		result = append(result, task)
	}

	return result, nil
}

// AddDependency adds a dependency to a task
func (s *InMemoryStore) AddDependency(ctx context.Context, taskID, dependencyID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, exists := s.tasks[taskID]
	if !exists {
		return errors.Errorf("task with ID %s not found", taskID)
	}

	dependency, exists := s.tasks[dependencyID]
	if !exists {
		return errors.Errorf("dependency task with ID %s not found", dependencyID)
	}

	// Check if the dependency already exists
	for _, dep := range task.Dependencies {
		if dep == dependencyID {
			// Already exists, nothing to do
			return nil
		}
	}

	// Add the dependency to the task
	task.Dependencies = append(task.Dependencies, dependencyID)

	// Add the task to the dependency's dependents
	dependency.Dependents = append(dependency.Dependents, taskID)

	return nil
}

// RemoveDependency removes a dependency from a task
func (s *InMemoryStore) RemoveDependency(ctx context.Context, taskID, dependencyID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	task, exists := s.tasks[taskID]
	if !exists {
		return errors.Errorf("task with ID %s not found", taskID)
	}

	dependency, exists := s.tasks[dependencyID]
	if !exists {
		return errors.Errorf("dependency task with ID %s not found", dependencyID)
	}

	// Remove the dependency from the task
	for i, dep := range task.Dependencies {
		if dep == dependencyID {
			task.Dependencies = append(task.Dependencies[:i], task.Dependencies[i+1:]...)
			break
		}
	}

	// Remove the task from the dependency's dependents
	for i, dep := range dependency.Dependents {
		if dep == taskID {
			dependency.Dependents = append(dependency.Dependents[:i], dependency.Dependents[i+1:]...)
			break
		}
	}

	return nil
}

// GetDependents retrieves the IDs of tasks that depend on the given task
func (s *InMemoryStore) GetDependents(ctx context.Context, taskID string) ([]string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	task, exists := s.tasks[taskID]
	if !exists {
		return nil, errors.Errorf("task with ID %s not found", taskID)
	}

	return task.Dependents, nil
}

// GetTasksByStatus retrieves all tasks with the given status
func (s *InMemoryStore) GetTasksByStatus(ctx context.Context, status TaskStatus) ([]*Task, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var result []*Task
	for _, task := range s.tasks {
		if task.Status == status {
			result = append(result, task)
		}
	}

	return result, nil
}

// GetTasksByRootID retrieves all tasks with the given root task ID
func (s *InMemoryStore) GetTasksByRootID(ctx context.Context, rootTaskID string) ([]*Task, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var result []*Task
	for _, task := range s.tasks {
		if task.RootTaskID == rootTaskID {
			result = append(result, task)
		}
	}

	return result, nil
}

// GetReadyTasks finds tasks that are ready to be executed
func (s *InMemoryStore) GetReadyTasks(ctx context.Context) ([]*Task, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var result []*Task

	// First, identify completed tasks
	completedTaskIDs := make(map[string]bool)
	for id, task := range s.tasks {
		if task.Status == TaskStatusCompleted {
			completedTaskIDs[id] = true
		}
	}

	// Then find pending tasks with all dependencies satisfied
	for _, task := range s.tasks {
		if task.IsReady(completedTaskIDs) {
			result = append(result, task)
		}
	}

	return result, nil
}
