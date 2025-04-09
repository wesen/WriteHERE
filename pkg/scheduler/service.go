package scheduler

import (
	"context"
	"encoding/json"

	"writehere-go/pkg/events"
	"writehere-go/pkg/state"

	"github.com/pkg/errors"
	"github.com/rs/zerolog/log"
)

// Service is responsible for listening to TaskReady events and assigning them
// to appropriate worker types by publishing TaskAssigned events.
type Service struct {
	eventBus *events.EventBus
	store    state.Store
	// workerTypeMapping maps state.TaskType to the string identifier of the worker type
	workerTypeMapping map[state.TaskType]string
}

// NewService creates a new Scheduler Service.
func NewService(bus *events.EventBus, store state.Store) *Service {
	// Define the mapping from task types to worker type strings
	// This should likely be configurable later
	mapping := map[state.TaskType]string{
		state.TaskTypePlanning:    "planning-worker",
		state.TaskTypeExecution:   "execution-worker",
		state.TaskTypeComposition: "execution-worker", // Example: Composition handled by execution worker
		state.TaskTypeReflection:  "reflection-worker",
		state.TaskTypeAggregation: "aggregation-worker",
		state.TaskTypeRetrieval:   "retrieval-worker",
		state.TaskTypeReasoning:   "execution-worker", // Example: Reasoning handled by execution worker
	}

	return &Service{
		eventBus:          bus,
		store:             store,
		workerTypeMapping: mapping,
	}
}

// Start subscribes the scheduler to TaskReady events and begins processing.
func (s *Service) Start(ctx context.Context) error {
	log.Info().Msg("Starting Scheduler Service")

	// Subscribe specifically to TaskReady events
	err := s.eventBus.Subscribe(ctx, events.TaskTopic, events.TaskReady, s.handleTaskReady)
	if err != nil {
		return errors.Wrap(err, "failed to subscribe to task topic for TaskReady events")
	}

	log.Info().Msg("Scheduler Service started and subscribed to TaskReady events")

	// Keep the service running until context is cancelled
	<-ctx.Done()
	log.Info().Msg("Scheduler Service shutting down")
	return nil
}

// handleTaskReady processes a TaskReady event.
func (s *Service) handleTaskReady(ctx context.Context, event events.Event) error {
	log.Debug().Str("event_id", event.EventID).Msg("Handling TaskReady event")

	// Payload extraction needs refinement as EventFromMessage doesn't decode nested payload
	var payload events.TaskReadyPayload
	payloadBytes, err := json.Marshal(event.Payload)
	if err != nil {
		return errors.Wrap(err, "failed to marshal TaskReady payload map for decoding")
	}
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		// Attempt decoding if Payload is already the correct struct type (e.g., from direct call)
		if p, ok := event.Payload.(events.TaskReadyPayload); ok {
			payload = p
		} else {
			return errors.Wrap(err, "failed to unmarshal TaskReady payload")
		}
	}

	log.Info().Str("task_id", payload.TaskID).Msg("Processing TaskReady event")

	// 1. Fetch task details from the store
	task, err := s.store.GetTask(ctx, payload.TaskID)
	if err != nil {
		return errors.Wrapf(err, "failed to fetch task %s from store", payload.TaskID)
	}
	if task == nil {
		return errors.Errorf("task %s not found in store", payload.TaskID)
	}

	// 2. Determine the target worker type
	workerType, ok := s.workerTypeMapping[task.TaskType]
	if !ok {
		log.Warn().Str("task_id", task.TaskID).Str("task_type", string(task.TaskType)).Msg("No worker type mapping found for task type")
		// Decide how to handle - fail the task? assign to default? For now, return error.
		return errors.Errorf("no worker type mapping defined for task type: %s", task.TaskType)
	}

	log.Info().Str("task_id", task.TaskID).Str("worker_type", workerType).Msg("Determined worker type for task")

	// 3. Publish TaskAssigned event
	assignedPayload := events.TaskAssignedPayload{
		TaskID:     task.TaskID,
		RootTaskID: task.RootTaskID,
		WorkerType: workerType,
	}

	assignedEvent := events.NewEvent(events.TaskAssigned, "scheduler-service", assignedPayload)

	err = s.eventBus.Publish(ctx, events.TaskTopic, assignedEvent)
	if err != nil {
		return errors.Wrapf(err, "failed to publish TaskAssigned event for task %s", task.TaskID)
	}

	log.Info().Str("task_id", task.TaskID).Str("worker_type", workerType).Msg("Published TaskAssigned event")

	// Optional: Update task state to ASSIGNED here or let the worker do it?
	// Decision: Let the worker update state upon starting to process.
	// This avoids potential races if the worker picks up the message before the state update propagates.

	return nil
}
