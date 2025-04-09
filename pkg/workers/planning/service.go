package planning

import (
	"context"
	"encoding/json"
	"fmt"

	"writehere-go/pkg/events"
	"writehere-go/pkg/llms"
	"writehere-go/pkg/state"

	"github.com/google/uuid"
	"github.com/pkg/errors"
	"github.com/rs/zerolog/log"
)

const WorkerType = "planning-worker"
const defaultLLMModel = "gpt-4o"

// Service implements a worker that handles planning tasks.
type Service struct {
	eventBus  *events.EventBus
	store     state.Store
	llmClient llms.Client
}

// NewService creates a new Planning Worker Service.
func NewService(bus *events.EventBus, store state.Store, llmClient llms.Client) *Service {
	return &Service{
		eventBus:  bus,
		store:     store,
		llmClient: llmClient,
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

// --- Planning Prompt Definitions ---

const systemPrompt = `You are a planning assistant. Your goal is to break down a user's primary goal into smaller, manageable subtasks.
Output the plan as a JSON object containing a single key "subtasks".
The value of "subtasks" should be an array of objects, where each object represents a subtask and has the following keys:
- "goal": A string describing the subtask's objective.
- "type": A string representing the task type (e.g., "EXECUTION", "RESEARCH", "REVIEW"). Use "EXECUTION" for general tasks for now.
- "dependencies": An array of strings, listing the 'goal' of any other subtasks that must be completed *before* this one can start. If there are no dependencies, provide an empty array [].

Example Input Goal: Write a blog post about Go concurrency.
Example Output JSON:
{
  "subtasks": [
	{ "goal": "Research common Go concurrency patterns", "type": "RESEARCH", "dependencies": [] },
	{ "goal": "Outline the blog post structure", "type": "EXECUTION", "dependencies": ["Research common Go concurrency patterns"] },
	{ "goal": "Write the introduction section", "type": "EXECUTION", "dependencies": ["Outline the blog post structure"] },
	{ "goal": "Write the section on Goroutines", "type": "EXECUTION", "dependencies": ["Outline the blog post structure"] },
	{ "goal": "Write the section on Channels", "type": "EXECUTION", "dependencies": ["Outline the blog post structure"] },
	{ "goal": "Write the conclusion", "type": "EXECUTION", "dependencies": ["Outline the blog post structure"] },
	{ "goal": "Review and edit the entire post", "type": "REVIEW", "dependencies": ["Write the introduction section", "Write the section on Goroutines", "Write the section on Channels", "Write the conclusion"] }
  ]
}`

func userPrompt(goal string) string {
	return fmt.Sprintf("Break down the following goal into subtasks:\n\nGoal: %s", goal)
}

// llmPlanResponse defines the structure expected from the LLM's JSON output.
type llmPlanResponse struct {
	Subtasks []struct {
		Goal         string   `json:"goal"`
		Type         string   `json:"type"`
		Dependencies []string `json:"dependencies"`
	} `json:"subtasks"`
}

// --- Helper Function to Publish TaskFailed ---
func (s *Service) publishTaskFailed(ctx context.Context, taskID, rootTaskID, errorMsg string, originalErr error) {
	log.Error().Err(originalErr).Str("task_id", taskID).Msg(errorMsg)
	failedPayload := events.TaskFailedPayload{
		TaskID:     taskID,
		RootTaskID: rootTaskID,
		ErrorInfo:  fmt.Sprintf("%s: %v", errorMsg, originalErr),
	}
	failedEvent := events.NewEvent(events.TaskFailed, WorkerType, failedPayload)
	_ = s.eventBus.Publish(ctx, events.TaskTopic, failedEvent)
}

// handleTaskAssigned processes a TaskAssigned event, calling the LLM for planning.
func (s *Service) handleTaskAssigned(ctx context.Context, event events.Event) error {
	var assignedPayload events.TaskAssignedPayload
	payloadBytes, err := json.Marshal(event.Payload)
	if err != nil {
		log.Error().Err(err).Interface("payload", event.Payload).Msg("Failed to marshal TaskAssigned payload map")
		return errors.Wrap(err, "failed to marshal TaskAssigned payload map for decoding")
	}
	if err := json.Unmarshal(payloadBytes, &assignedPayload); err != nil {
		if p, ok := event.Payload.(events.TaskAssignedPayload); ok {
			assignedPayload = p
		} else {
			log.Error().Err(err).Bytes("payload_bytes", payloadBytes).Msg("Failed to unmarshal TaskAssigned payload")
			return errors.Wrap(err, "failed to unmarshal TaskAssigned payload")
		}
	}

	if assignedPayload.WorkerType != WorkerType {
		return nil
	}

	taskID := assignedPayload.TaskID
	rootTaskID := assignedPayload.RootTaskID
	log.Info().Str("task_id", taskID).Str("worker_type", assignedPayload.WorkerType).Msg("Planning Worker received assigned task")

	startedPayload := events.TaskStartedPayload{
		TaskID:     taskID,
		RootTaskID: rootTaskID,
		WorkerID:   WorkerType,
	}
	startedEvent := events.NewEvent(events.TaskStarted, WorkerType, startedPayload)
	if err := s.eventBus.Publish(ctx, events.TaskTopic, startedEvent); err != nil {
		log.Error().Err(err).Str("task_id", taskID).Msg("Failed to publish TaskStarted event")
	} else {
		log.Info().Str("task_id", taskID).Msg("Published TaskStarted event")
	}

	task, err := s.store.GetTask(ctx, taskID)
	if err != nil {
		s.publishTaskFailed(ctx, taskID, rootTaskID, "failed to fetch task from store", err)
		return errors.Wrapf(err, "failed to fetch task %s from store", taskID)
	}
	if task == nil {
		err := errors.Errorf("task %s assigned but not found in store", taskID)
		s.publishTaskFailed(ctx, taskID, rootTaskID, "task not found", err)
		return err
	}

	log.Info().Str("task_id", task.TaskID).Str("goal", task.Goal).Msg("Starting LLM-based planning")

	llmRequest := llms.ChatCompletionRequest{
		Model: defaultLLMModel,
		Messages: []llms.ChatMessage{
			{Role: "system", Content: systemPrompt},
			{Role: "user", Content: userPrompt(task.Goal)},
		},
		ResponseFormat: &llms.ResponseFormat{Type: "json_object"},
	}

	llmResponse, err := s.llmClient.ChatCompletion(ctx, llmRequest)
	if err != nil {
		s.publishTaskFailed(ctx, taskID, rootTaskID, "LLM chat completion failed", err)
		return errors.Wrap(err, "LLM chat completion failed during planning")
	}

	if len(llmResponse.Choices) == 0 || llmResponse.Choices[0].Message.Content == "" {
		err := errors.New("LLM response was empty or missing content")
		s.publishTaskFailed(ctx, taskID, rootTaskID, "LLM response empty", err)
		return err
	}

	llmResultContent := llmResponse.Choices[0].Message.Content
	log.Info().Str("task_id", taskID).Str("llm_response", llmResultContent).Msg("Received plan from LLM")

	var plan llmPlanResponse
	if err := json.Unmarshal([]byte(llmResultContent), &plan); err != nil {
		s.publishTaskFailed(ctx, taskID, rootTaskID, "Failed to parse LLM JSON response", err)
		return errors.Wrapf(err, "failed to parse LLM JSON response: %s", llmResultContent)
	}

	if len(plan.Subtasks) == 0 {
		log.Warn().Str("task_id", taskID).Msg("LLM generated an empty plan (0 subtasks). Completing task.")
	} else {
		log.Info().Str("task_id", taskID).Int("subtask_count", len(plan.Subtasks)).Msg("Parsed subtasks from LLM response")
	}

	eventSubtasks := make([]events.Subtask, 0, len(plan.Subtasks))
	goalToIDMap := make(map[string]string, len(plan.Subtasks))

	for _, llmSubtask := range plan.Subtasks {
		newID := uuid.New().String()
		goalToIDMap[llmSubtask.Goal] = newID
		eventSubtasks = append(eventSubtasks, events.Subtask{
			TaskID:   newID,
			Goal:     llmSubtask.Goal,
			TaskType: llmSubtask.Type,
		})
	}

	for i, llmSubtask := range plan.Subtasks {
		dependencyIDs := make([]string, 0, len(llmSubtask.Dependencies))
		for _, depGoal := range llmSubtask.Dependencies {
			if depID, ok := goalToIDMap[depGoal]; ok {
				dependencyIDs = append(dependencyIDs, depID)
			} else {
				log.Warn().Str("task_id", taskID).Str("subtask_goal", llmSubtask.Goal).Str("dependency_goal", depGoal).Msg("LLM plan dependency goal not found in generated subtasks. Ignoring dependency.")
			}
		}
		eventSubtasks[i].Dependencies = dependencyIDs
	}

	subtasksPlannedPayload := events.SubtasksPlannedPayload{
		ParentTaskID: task.TaskID,
		RootTaskID:   task.RootTaskID,
		Subtasks:     eventSubtasks,
	}
	subtasksPlannedEvent := events.NewEvent(events.SubtasksPlanned, WorkerType, subtasksPlannedPayload)

	err = s.eventBus.Publish(ctx, events.TaskTopic, subtasksPlannedEvent)
	if err != nil {
		s.publishTaskFailed(ctx, taskID, rootTaskID, "Failed to publish SubtasksPlanned event", err)
		return errors.Wrapf(err, "failed to publish SubtasksPlanned event for task %s", taskID)
	}
	log.Info().Str("task_id", taskID).Int("subtask_count", len(eventSubtasks)).Msg("Published SubtasksPlanned event")

	subtaskIDs := make([]string, len(eventSubtasks))
	for i, st := range eventSubtasks {
		subtaskIDs[i] = st.TaskID
	}
	completedPayload := events.TaskCompletedPayload{
		TaskID:     task.TaskID,
		RootTaskID: task.RootTaskID,
		Result: map[string]interface{}{
			"status":           "Planning complete (LLM)",
			"llm_model_used":   defaultLLMModel,
			"subtask_ids":      subtaskIDs,
			"subtask_count":    len(subtaskIDs),
			"raw_llm_response": llmResultContent,
		},
	}
	completedEvent := events.NewEvent(events.TaskCompleted, WorkerType, completedPayload)

	err = s.eventBus.Publish(ctx, events.TaskTopic, completedEvent)
	if err != nil {
		log.Error().Err(err).Str("task_id", taskID).Msg("Failed to publish TaskCompleted event for planning task, but proceeding")
	} else {
		log.Info().Str("task_id", taskID).Msg("Planning task marked as completed (LLM)")
	}

	return nil
}
