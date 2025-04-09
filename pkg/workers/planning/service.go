package planning

import (
	"context"
	"encoding/json"

	"writehere-go/pkg/events"
	"writehere-go/pkg/state"

	"github.com/pkg/errors"
	"github.com/rs/zerolog/log"
)

const WorkerType = "planning-worker"

// Service implements a worker that handles planning tasks.
type Service struct {
	eventBus *events.EventBus
	store    state.Store
	// Add any planning-specific dependencies here, like LLM clients
}

// NewService creates a new Planning Worker Service.
func NewService(bus *events.EventBus, store state.Store) *Service {
	return &Service{
		eventBus: bus,
		store:    store,
	}
}

// Start subscribes the planning worker to TaskAssigned events and begins processing.
func (s *Service) Start(ctx context.Context) error {
	log.Info().Str("worker_type", WorkerType).Msg("Starting Planning Worker Service")

	// Subscribe specifically to TaskAssigned events
	err := s.eventBus.Subscribe(ctx, events.TaskTopic, events.TaskAssigned, s.handleTaskAssigned)
	if err != nil {
		return errors.Wrap(err, "failed to subscribe to task topic for TaskAssigned events")
	}

	log.Info().Str("worker_type", WorkerType).Msg("Planning Worker Service started and subscribed to TaskAssigned events")

	// Keep the service running until context is cancelled
	<-ctx.Done()
	log.Info().Str("worker_type", WorkerType).Msg("Planning Worker Service shutting down")
	return nil
}

// handleTaskAssigned processes a TaskAssigned event.
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
		// Not for us, silently ignore and ACK
		return nil
	}

	log.Info().Str("task_id", assignedPayload.TaskID).Str("worker_type", assignedPayload.WorkerType).Msg("Planning Worker received assigned task")

	// Fetch the full task details (needed for actual planning logic later)
	task, err := s.store.GetTask(ctx, assignedPayload.TaskID)
	if err != nil {
		return errors.Wrapf(err, "failed to fetch task %s from store", assignedPayload.TaskID)
	}
	if task == nil {
		return errors.Errorf("task %s assigned but not found in store", assignedPayload.TaskID)
	}

	// --- STUBBED LOGIC ---
	log.Info().Str("task_id", task.TaskID).Str("goal", task.Goal).Msg("Processing planning task (STUBBED)")

	// Simulate processing delay (optional)
	// time.Sleep(2 * time.Second)

	// --- STUBBED OUTPUT ---
	// For now, immediately mark the planning task as completed.
	// Later, this will publish SubtasksPlanned first, then TaskCompleted.
	completedPayload := events.TaskCompletedPayload{
		TaskID:     task.TaskID,
		RootTaskID: task.RootTaskID,
		Result: map[string]interface{}{ // Provide a stub result
			"status":   "Planning complete (stubbed)",
			"subtasks": []string{}, // No subtasks generated in stub
		},
	}
	completedEvent := events.NewEvent(events.TaskCompleted, WorkerType, completedPayload)

	err = s.eventBus.Publish(ctx, events.TaskTopic, completedEvent)
	if err != nil {
		return errors.Wrapf(err, "failed to publish TaskCompleted event for planning task %s", task.TaskID)
	}

	log.Info().Str("task_id", task.TaskID).Msg("Planning task marked as completed (STUBBED)")
	// TODO: Implement actual planning logic (call LLMs, generate subtasks)
	// TODO: Update task status to RUNNING when starting, possibly via an event?

	return nil
}
