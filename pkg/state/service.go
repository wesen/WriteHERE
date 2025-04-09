package state

import (
	"context"
	"encoding/json"
	"fmt"

	"writehere-go/pkg/events"

	"github.com/pkg/errors"
	"github.com/rs/zerolog"
	"golang.org/x/sync/errgroup"
)

// Service manages the state of tasks and handles events
type Service struct {
	store       Store
	eventBus    *events.EventBus
	logger      zerolog.Logger
	serviceName string
}

// NewService creates a new state service
func NewService(ctx context.Context, store Store, eventBus *events.EventBus, logger zerolog.Logger) (*Service, error) {
	service := &Service{
		store:       store,
		eventBus:    eventBus,
		logger:      logger,
		serviceName: "state-service",
	}

	return service, nil
}

func (s *Service) Start(ctx context.Context) error {
	// Subscribe to relevant events
	if err := s.subscribeToEvents(ctx); err != nil {
		return errors.Wrap(err, "failed to subscribe to events")
	}

	return nil
}

// subscribeToEvents sets up subscriptions for the events the service needs to handle
func (s *Service) subscribeToEvents(ctx context.Context) error {
	// Create an error group for concurrent subscriptions
	g, ctx := errgroup.WithContext(ctx)

	// Handle TaskSubmitted events
	g.Go(func() error {
		return s.eventBus.Subscribe(ctx, events.TaskTopic, events.TaskSubmitted, s.handleTaskSubmitted)
	})

	// Handle TaskCompleted events
	g.Go(func() error {
		return s.eventBus.Subscribe(ctx, events.TaskTopic, events.TaskCompleted, s.handleTaskCompleted)
	})

	// Handle TaskFailed events
	g.Go(func() error {
		return s.eventBus.Subscribe(ctx, events.TaskTopic, events.TaskFailed, s.handleTaskFailed)
	})

	// Handle SubtasksPlanned events
	g.Go(func() error {
		return s.eventBus.Subscribe(ctx, events.TaskTopic, events.SubtasksPlanned, s.handleSubtasksPlanned)
	})

	// Handle TaskStarted events
	g.Go(func() error {
		return s.eventBus.Subscribe(ctx, events.TaskTopic, events.TaskStarted, s.handleTaskStarted)
	})

	// Wait for all subscriptions to complete or error
	return g.Wait()
}

// handleTaskSubmitted processes TaskSubmitted events
func (s *Service) handleTaskSubmitted(ctx context.Context, event events.Event) error {
	s.logger.Debug().
		Str("event_id", event.EventID).
		Msg("Handling TaskSubmitted event")

	// Extract the payload
	payload, ok := event.Payload.(events.TaskSubmittedPayload)
	if !ok {
		return errors.New("invalid payload for TaskSubmitted event")
	}

	// Create a new task from the event data
	task := NewTask(
		payload.Goal,
		TaskType(payload.TaskType),
		"", // No parent for root tasks
		payload.RootTaskID,
	)

	// If task ID is provided in the payload, use it
	if payload.TaskID != "" {
		task.TaskID = payload.TaskID
	}

	// Set the task as READY if it has no dependencies
	if len(task.Dependencies) == 0 {
		task.Status = TaskStatusReady
	}

	// Add metadata if provided
	if payload.Metadata != nil {
		task.Metadata = payload.Metadata
	}

	// Store the task
	if err := s.store.CreateTask(ctx, task); err != nil {
		return errors.Wrap(err, "failed to create task")
	}

	// If the task is already ready, emit a TaskReady event
	if task.Status == TaskStatusReady {
		readyEvent := events.NewEvent(
			events.TaskReady,
			s.serviceName,
			events.TaskReadyPayload{
				TaskID:     task.TaskID,
				RootTaskID: task.RootTaskID,
			},
		)

		if err := s.eventBus.Publish(ctx, events.TaskTopic, readyEvent); err != nil {
			return errors.Wrap(err, "failed to publish TaskReady event")
		}
	}

	return nil
}

// handleTaskCompleted processes TaskCompleted events
func (s *Service) handleTaskCompleted(ctx context.Context, event events.Event) error {
	s.logger.Debug().
		Str("event_id", event.EventID).
		Msg("Handling TaskCompleted event")

	// Extract the payload
	payload, ok := event.Payload.(events.TaskCompletedPayload)
	if !ok {
		return errors.New("invalid payload for TaskCompleted event")
	}

	// Get the task from the store
	task, err := s.store.GetTask(ctx, payload.TaskID)
	if err != nil {
		return errors.Wrap(err, "failed to get task")
	}

	// Update task status and result
	task.Status = TaskStatusCompleted
	task.Result = payload.Result

	// Save the updated task
	if err := s.store.UpdateTask(ctx, task); err != nil {
		return errors.Wrap(err, "failed to update task")
	}

	// Check dependents to see if any are now ready
	if err := s.checkDependents(ctx, task.TaskID); err != nil {
		return errors.Wrap(err, "failed to check dependents")
	}

	return nil
}

// handleTaskFailed processes TaskFailed events
func (s *Service) handleTaskFailed(ctx context.Context, event events.Event) error {
	s.logger.Debug().
		Str("event_id", event.EventID).
		Msg("Handling TaskFailed event")

	// Extract the payload
	payload, ok := event.Payload.(events.TaskFailedPayload)
	if !ok {
		return errors.New("invalid payload for TaskFailed event")
	}

	// Get the task from the store
	task, err := s.store.GetTask(ctx, payload.TaskID)
	if err != nil {
		return errors.Wrap(err, "failed to get task")
	}

	// Update task status and error info
	task.Status = TaskStatusFailed
	task.ErrorInfo = payload.ErrorInfo

	// Save the updated task
	if err := s.store.UpdateTask(ctx, task); err != nil {
		return errors.Wrap(err, "failed to update task")
	}

	return nil
}

// handleSubtasksPlanned processes SubtasksPlanned events
func (s *Service) handleSubtasksPlanned(ctx context.Context, event events.Event) error {
	s.logger.Debug().
		Str("event_id", event.EventID).
		Msg("Handling SubtasksPlanned event")

	// Extract the payload
	payload, ok := event.Payload.(events.SubtasksPlannedPayload)
	if !ok {
		return errors.New("invalid payload for SubtasksPlanned event")
	}

	// Get the parent task
	parentTask, err := s.store.GetTask(ctx, payload.ParentTaskID)
	if err != nil {
		return errors.Wrap(err, "failed to get parent task")
	}

	// Create tasks for each subtask in the payload
	for _, subtaskInfo := range payload.Subtasks {
		subtask := NewTask(
			subtaskInfo.Goal,
			TaskType(subtaskInfo.TaskType),
			parentTask.TaskID,
			parentTask.RootTaskID,
		)

		// Use the provided task ID if any
		if subtaskInfo.TaskID != "" {
			subtask.TaskID = subtaskInfo.TaskID
		}

		// Add dependencies
		subtask.Dependencies = subtaskInfo.Dependencies

		// Set initial status based on dependencies
		if len(subtask.Dependencies) == 0 {
			subtask.Status = TaskStatusReady
		} else {
			subtask.Status = TaskStatusPendingDeps
		}

		// Store the subtask
		if err := s.store.CreateTask(ctx, subtask); err != nil {
			return errors.Wrap(err, fmt.Sprintf("failed to create subtask %s", subtask.TaskID))
		}

		// Set up dependency relationships
		for _, depID := range subtaskInfo.Dependencies {
			if err := s.store.AddDependency(ctx, subtask.TaskID, depID); err != nil {
				return errors.Wrap(err, "failed to add dependency")
			}
		}

		// If the subtask is ready, emit a TaskReady event
		if subtask.Status == TaskStatusReady {
			readyEvent := events.NewEvent(
				events.TaskReady,
				s.serviceName,
				events.TaskReadyPayload{
					TaskID:     subtask.TaskID,
					RootTaskID: subtask.RootTaskID,
				},
			)

			if err := s.eventBus.Publish(ctx, events.TaskTopic, readyEvent); err != nil {
				return errors.Wrap(err, "failed to publish TaskReady event")
			}
		}
	}

	return nil
}

// handleTaskStarted processes TaskStarted events
func (s *Service) handleTaskStarted(ctx context.Context, event events.Event) error {
	s.logger.Debug().
		Str("event_id", event.EventID).
		Msg("Handling TaskStarted event")

	// Extract payload
	payloadBytes, err := json.Marshal(event.Payload)
	if err != nil {
		return errors.Wrap(err, "failed to marshal TaskStarted payload map for decoding")
	}
	var payload events.TaskStartedPayload
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		if p, ok := event.Payload.(events.TaskStartedPayload); ok {
			payload = p
		} else {
			return errors.Wrap(err, "failed to unmarshal TaskStarted payload")
		}
	}

	// Get the task from the store
	task, err := s.store.GetTask(ctx, payload.TaskID)
	if err != nil {
		// It's possible the task was deleted between assignment and start, log warning
		s.logger.Warn().Err(err).Str("task_id", payload.TaskID).Msg("Failed to get task for TaskStarted event")
		return nil // Don't treat as a fatal error for the handler
	}
	if task == nil {
		s.logger.Warn().Str("task_id", payload.TaskID).Msg("Task not found for TaskStarted event")
		return nil
	}

	// Update task status to RUNNING
	// TODO: Consider adding assigned_worker_id from payload to task here?
	task.Status = TaskStatusRunning
	task.AssignedWorkerID = payload.WorkerID // Store worker ID if provided

	// Save the updated task
	if err := s.store.UpdateTask(ctx, task); err != nil {
		return errors.Wrap(err, "failed to update task status to RUNNING")
	}

	s.logger.Info().Str("task_id", task.TaskID).Str("worker_id", task.AssignedWorkerID).Msg("Task status updated to RUNNING")
	return nil
}

// checkDependents checks if any dependent tasks are now ready after a task completes
func (s *Service) checkDependents(ctx context.Context, taskID string) error {
	// Get the list of dependent tasks
	dependents, err := s.store.GetDependents(ctx, taskID)
	if err != nil {
		return errors.Wrap(err, "failed to get dependents")
	}

	// Create a map of completed tasks for efficient lookup
	completedTasks := map[string]bool{taskID: true}

	// Check each dependent
	for _, depID := range dependents {
		// Get the dependent task
		task, err := s.store.GetTask(ctx, depID)
		if err != nil {
			return errors.Wrap(err, "failed to get dependent task")
		}

		// Check if all dependencies are complete
		if task.IsReady(completedTasks) {
			// Update the task status
			task.Status = TaskStatusReady
			if err := s.store.UpdateTask(ctx, task); err != nil {
				return errors.Wrap(err, "failed to update task status")
			}

			// Emit a TaskReady event
			readyEvent := events.NewEvent(
				events.TaskReady,
				s.serviceName,
				events.TaskReadyPayload{
					TaskID:     task.TaskID,
					RootTaskID: task.RootTaskID,
				},
			)

			if err := s.eventBus.Publish(ctx, events.TaskTopic, readyEvent); err != nil {
				return errors.Wrap(err, "failed to publish TaskReady event")
			}
		}
	}

	return nil
}

// CreateRootTask creates a new root task and emits a TaskSubmitted event
func (s *Service) CreateRootTask(ctx context.Context, goal string, taskType TaskType, metadata map[string]interface{}) (string, error) {
	// Create a new task with a unique ID
	task := NewTask(goal, taskType, "", "")

	// Emit a TaskSubmitted event
	submitEvent := events.NewEvent(
		events.TaskSubmitted,
		s.serviceName,
		events.TaskSubmittedPayload{
			TaskID:     task.TaskID,
			RootTaskID: task.TaskID, // Root task is its own root
			Goal:       goal,
			TaskType:   string(taskType),
			Metadata:   metadata,
		},
	)

	if err := s.eventBus.Publish(ctx, events.TaskTopic, submitEvent); err != nil {
		return "", errors.Wrap(err, "failed to publish TaskSubmitted event")
	}

	return task.TaskID, nil
}

// GetTask retrieves a task by ID
func (s *Service) GetTask(ctx context.Context, taskID string) (*Task, error) {
	return s.store.GetTask(ctx, taskID)
}

// GetTasksByRoot retrieves all tasks for a given root task
func (s *Service) GetTasksByRoot(ctx context.Context, rootTaskID string) ([]*Task, error) {
	return s.store.GetTasksByRootID(ctx, rootTaskID)
}
