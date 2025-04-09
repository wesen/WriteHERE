package planning

import (
	"context"
	"encoding/json"

	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/go-go-golems/writehere-go/pkg/events"
	"github.com/go-go-golems/writehere-go/pkg/state"
	"github.com/pkg/errors"
	"github.com/rs/zerolog/log"
)

const WorkerType = "planning-worker"

// Service implements a worker that handles planning tasks.
type Service struct {
	eventBus events.EventBus
	store    state.Store
	// Add any planning-specific dependencies here, like LLM clients
}

// NewService creates a new Planning Worker Service.
func NewService(bus events.EventBus, store state.Store) *Service {
	return &Service{
		eventBus: bus,
		store:    store,
	}
}

// Start subscribes the planning worker to TaskAssigned events and begins processing.
func (s *Service) Start(ctx context.Context) error {
	log.Info().Str("worker_type", WorkerType).Msg("Starting Planning Worker Service")

	// Subscribe to TaskAssigned events
	messages, err := s.eventBus.Subscribe(ctx, events.TaskTopic) // Subscribing to the general task topic
	if err != nil {
		return errors.Wrap(err, "failed to subscribe to task topic")
	}

	go s.processMessages(ctx, messages)

	log.Info().Str("worker_type", WorkerType).Msg("Planning Worker Service started and subscribed to events")
	return nil
}

func (s *Service) processMessages(ctx context.Context, messages <-chan *message.Message) {
	for msg := range messages {
		select {
		case <-ctx.Done():
			log.Info().Str("worker_type", WorkerType).Msg("Context cancelled, stopping message processing")
			return
		default:
			evt, err := events.EventFromMessage(msg)
			if err != nil {
				log.Error().Err(err).Str("message_uuid", msg.UUID).Msg("Failed to unmarshal event from message")
				msg.Nack()
				continue
			}

			// Only handle TaskAssigned events
			if evt.EventType != events.TaskAssigned {
				msg.Ack()
				continue
			}

			err = s.handleTaskAssigned(ctx, evt)
			if err != nil {
				log.Error().Err(err).Str("event_id", evt.EventID).Msg("Failed to handle TaskAssigned event")
				msg.Nack() // Nack on error to allow for retries
			} else {
				msg.Ack()
			}
		}
	}
	log.Info().Str("worker_type", WorkerType).Msg("Planning Worker message processing loop finished")
}

// handleTaskAssigned processes a TaskAssigned event.
func (s *Service) handleTaskAssigned(ctx context.Context, event events.Event) error {
	var assignedPayload events.TaskAssignedPayload
	payloadBytes, err := json.Marshal(event.Payload)
	if err != nil {
		return errors.Wrap(err, "failed to marshal TaskAssigned payload for decoding")
	}
	if err := json.Unmarshal(payloadBytes, &assignedPayload); err != nil {
		return errors.Wrap(err, "failed to unmarshal TaskAssigned payload")
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
