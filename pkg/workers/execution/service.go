package execution

import (
	"context"
	"encoding/json"
	"fmt"

	"writehere-go/pkg/actions" // Import actions package
	"writehere-go/pkg/events"
	"writehere-go/pkg/state"

	"github.com/pkg/errors"
	"github.com/rs/zerolog/log"
)

const WorkerType = "execution-worker"

// Service implements a worker that handles execution tasks (e.g., composition, reasoning).
type Service struct {
	eventBus       *events.EventBus
	store          state.Store
	actionExecutor *actions.ActionExecutor
	// Add any execution-specific dependencies here, like LLM clients, ReAct agent logic etc.
}

// NewService creates a new Execution Worker Service.
func NewService(bus *events.EventBus, store state.Store) *Service {
	return &Service{
		eventBus:       bus,
		store:          store,
		actionExecutor: actions.NewActionExecutor(), // Initialize the action executor
	}
}

// Start subscribes the execution worker to TaskAssigned events and begins processing.
func (s *Service) Start(ctx context.Context) error {
	log.Info().Str("worker_type", WorkerType).Msg("Starting Execution Worker Service")

	// Subscribe specifically to TaskAssigned events
	err := s.eventBus.Subscribe(ctx, events.TaskTopic, events.TaskAssigned, s.handleTaskAssigned)
	if err != nil {
		return errors.Wrap(err, "failed to subscribe to task topic for TaskAssigned events")
	}

	log.Info().Str("worker_type", WorkerType).Msg("Execution Worker Service started and subscribed to TaskAssigned events")

	// Keep the service running until context is cancelled
	<-ctx.Done()
	log.Info().Str("worker_type", WorkerType).Msg("Execution Worker Service shutting down")
	return nil
}

// handleTaskAssigned processes a TaskAssigned event for execution tasks.
func (s *Service) handleTaskAssigned(ctx context.Context, event events.Event) error {
	var assignedPayload events.TaskAssignedPayload
	// Payload extraction needs refinement
	payloadBytes, err := json.Marshal(event.Payload)
	if err != nil {
		return errors.Wrap(err, "failed to marshal TaskAssigned payload map for decoding")
	}
	if err := json.Unmarshal(payloadBytes, &assignedPayload); err != nil {
		// Attempt decoding if Payload is already the correct struct type
		if p, ok := event.Payload.(events.TaskAssignedPayload); ok {
			assignedPayload = p
		} else {
			return errors.Wrap(err, "failed to unmarshal TaskAssigned payload")
		}
	}

	// Filter: Check if this task is for this worker type
	if assignedPayload.WorkerType != WorkerType {
		return nil // Not for us, ACK implicitly handled by caller
	}

	log.Info().Str("task_id", assignedPayload.TaskID).Str("worker_type", assignedPayload.WorkerType).Msg("Execution Worker received assigned task")

	// Fetch the full task details
	task, err := s.store.GetTask(ctx, assignedPayload.TaskID)
	if err != nil {
		return errors.Wrapf(err, "failed to fetch task %s from store", assignedPayload.TaskID)
	}
	if task == nil {
		return errors.Errorf("task %s assigned but not found in store", assignedPayload.TaskID)
	}

	// --- STUBBED LOGIC ---
	log.Info().Str("task_id", task.TaskID).Str("goal", task.Goal).Str("task_type", string(task.TaskType)).Msg("Processing execution task (STUBBED)")

	// Example: If it's a composition task, maybe try the echo action
	var result interface{} = "Execution complete (stubbed)"
	if task.TaskType == state.TaskTypeComposition {
		log.Info().Str("task_id", task.TaskID).Msg("Attempting echo action (STUBBED)")
		// Example action execution - replace with actual agent logic later
		args := map[string]interface{}{
			"message": fmt.Sprintf("Echoing for task %s: %s", task.TaskID, task.Goal),
			"repeat":  2,
		}
		actionResult, execErr := s.actionExecutor.ExecuteAction(ctx, "echo", args)
		if execErr != nil {
			log.Error().Err(execErr).Str("task_id", task.TaskID).Str("action", "echo").Msg("Echo action failed")
			// Decide how to handle action failure - fail the task?
			// For now, publish TaskFailed
			failedPayload := events.TaskFailedPayload{
				TaskID:     task.TaskID,
				RootTaskID: task.RootTaskID,
				ErrorInfo:  fmt.Sprintf("Action 'echo' failed: %v", execErr),
			}
			failedEvent := events.NewEvent(events.TaskFailed, WorkerType, failedPayload)
			if pubErr := s.eventBus.Publish(ctx, events.TaskTopic, failedEvent); pubErr != nil {
				log.Error().Err(pubErr).Str("task_id", task.TaskID).Msg("Failed to publish TaskFailed event after action failure")
				// Return the original execution error, potentially wrapped
				return errors.Wrapf(execErr, "echo action failed and failed to publish TaskFailed event: %v", pubErr)
			}
			return nil // TaskFailed event published, consider this handled
		} else {
			log.Info().Str("task_id", task.TaskID).Interface("result", actionResult.Result).Msg("Echo action succeeded")
			result = actionResult.Result // Use the action's result
		}
	}

	// --- STUBBED OUTPUT ---
	completedPayload := events.TaskCompletedPayload{
		TaskID:     task.TaskID,
		RootTaskID: task.RootTaskID,
		Result:     result, // Use the result from action or stub
	}
	completedEvent := events.NewEvent(events.TaskCompleted, WorkerType, completedPayload)

	err = s.eventBus.Publish(ctx, events.TaskTopic, completedEvent)
	if err != nil {
		return errors.Wrapf(err, "failed to publish TaskCompleted event for execution task %s", task.TaskID)
	}

	log.Info().Str("task_id", task.TaskID).Msg("Execution task marked as completed (STUBBED)")
	// TODO: Implement actual execution logic (ReAct agent, LLM calls, action execution based on plan)
	// TODO: Update task status appropriately (e.g., RUNNING, PLUGIN_RUNNING, LLM_PENDING)

	return nil
}
