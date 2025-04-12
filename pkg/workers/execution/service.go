package execution

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time" // Added for potential delays/timeouts

	"writehere-go/pkg/actions" // Import actions package
	"writehere-go/pkg/events"
	"writehere-go/pkg/llms" // Added LLM client import
	"writehere-go/pkg/state"

	"github.com/pkg/errors"
	"github.com/rs/zerolog/log"
)

const WorkerType = "execution-worker"
const defaultLLMModel = "gpt-4o" // Or make this configurable
const maxTurns = 10              // Max iterations for ReAct loop

// Service implements a worker that handles execution tasks using a ReAct agent pattern.
type Service struct {
	eventBus       *events.EventBus
	store          state.Store
	actionExecutor *actions.ActionExecutor
	llmClient      llms.Client // Added LLM client field
	// Add any execution-specific dependencies here, like LLM clients, ReAct agent logic etc.
}

// NewService creates a new Execution Worker Service.
func NewService(bus *events.EventBus, store state.Store, llmClient llms.Client) *Service { // Added llmClient param
	return &Service{
		eventBus:       bus,
		store:          store,
		actionExecutor: actions.NewActionExecutor(), // Initialize the action executor
		llmClient:      llmClient,                   // Store the LLM client
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

// --- Helper Function to Publish TaskFailed ---
func (s *Service) publishTaskFailed(ctx context.Context, taskID, rootTaskID, errorMsg string, originalErr error) {
	log.Error().Err(originalErr).Str("task_id", taskID).Msg(errorMsg)
	failedPayload := events.TaskFailedPayload{
		TaskID:     taskID,
		RootTaskID: rootTaskID,
		ErrorInfo:  fmt.Sprintf("%s: %v", errorMsg, originalErr),
	}
	failedEvent := events.NewEvent(events.TaskFailed, WorkerType, failedPayload)
	// Best effort to publish failure event
	_ = s.eventBus.Publish(ctx, events.TaskTopic, failedEvent)
}

// --- ReAct Agent Logic ---

// reactHistoryItem stores one turn of the ReAct loop.
type reactHistoryItem struct {
	Thought    string                `json:"thought,omitempty"`
	ActionName string                `json:"action_name,omitempty"`
	ActionArgs map[string]interface{} `json:"action_args,omitempty"`
	Observation string                `json:"observation,omitempty"` // Result of the action
}

// Define the prompt structure
const reactSystemPrompt = `You are a helpful assistant that thinks step-by-step to achieve a goal using available tools.
Follow the ReAct (Reason + Act) framework:
1.  **Thought:** Briefly explain your reasoning and plan for the next step towards the goal.
2.  **Action:** Choose **one** of the available actions to execute. Output the action invocation as a JSON object with keys "action_name" and "action_args" (which should be another JSON object). Valid action names are listed below. If you believe the task is complete, use the "finish" action.

Available Actions are provided in the user prompt.
Respond **only** with a JSON object containing "thought" and "action" keys. Do not add any preamble or explanation outside the JSON structure.

Example Response Format:
{
  "thought": "I need to find out the capital of France.",
  "action": {
	"action_name": "search",
	"action_args": {
	  "query": "capital of France"
	}
  }
}

Another example (finishing):
{
    "thought": "I have found the answer. The capital of France is Paris.",
    "action": {
        "action_name": "finish",
        "action_args": {
            "final_answer": "The capital of France is Paris."
        }
    }
}`

func constructReActUserPrompt(goal string, history []reactHistoryItem, actionSchemas string) string {
	var historyStr strings.Builder
	for i, item := range history {
		historyStr.WriteString(fmt.Sprintf("Turn %d:\n", i+1))
		if item.Thought != "" {
			historyStr.WriteString(fmt.Sprintf("Thought: %s\n", item.Thought))
		}
		if item.ActionName != "" {
			argsJSON, _ := json.Marshal(item.ActionArgs)
			historyStr.WriteString(fmt.Sprintf("Action: {\"action_name\": \"%s\", \"action_args\": %s}\n", item.ActionName, string(argsJSON)))
		}
		if item.Observation != "" {
			historyStr.WriteString(fmt.Sprintf("Observation: %s\n", item.Observation))
		}
		historyStr.WriteString("---\n")
	}

	return fmt.Sprintf("Goal: %s\n\n%s\n\nHistory:\n%s\nWhat is your next thought and action?",
		goal, actionSchemas, historyStr.String())
}

// Define structs to parse LLM's JSON response
type llmAction struct {
	ActionName string                 `json:"action_name"`
	ActionArgs map[string]interface{} `json:"action_args"`
}
type llmReActResponse struct {
	Thought string     `json:"thought"`
	Action  *llmAction `json:"action"` // Pointer to handle potential null/missing action
}

// Regular expression to extract JSON block from LLM response
var jsonRegex = regexp.MustCompile(`(?s)` + "```json" + `(.*)` + "```" + ``)

func parseLLMReActResponse(llmOutput string) (llmReActResponse, error) {
	var response llmReActResponse

	// Attempt to find JSON block first
	match := jsonRegex.FindStringSubmatch(llmOutput)
	jsonStr := llmOutput // Assume raw output is JSON
	if len(match) > 1 {
		jsonStr = strings.TrimSpace(match[1])
	}

	if err := json.Unmarshal([]byte(jsonStr), &response); err != nil {
		return llmReActResponse{}, errors.Wrapf(err, "failed to unmarshal LLM response JSON: %s", jsonStr)
	}

	if response.Action == nil {
		// If parsing succeeded but action is nil, it means the LLM didn't provide one.
		return response, errors.New("LLM response did not contain an 'action' field")
	}

	return response, nil
}

// handleTaskAssigned implements the ReAct loop for execution tasks.
func (s *Service) handleTaskAssigned(ctx context.Context, event events.Event) error {
	// --- Payload Extraction and Filtering (Same as before) ---
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
		return nil // Not for us
	}
	taskID := assignedPayload.TaskID
	rootTaskID := assignedPayload.RootTaskID
	log.Info().Str("task_id", taskID).Str("worker_type", assignedPayload.WorkerType).Msg("Execution Worker received assigned task")

	// --- Publish TaskStarted Event (Same as before) ---
	startedPayload := events.TaskStartedPayload{TaskID: taskID, RootTaskID: rootTaskID, WorkerID: WorkerType}
	startedEvent := events.NewEvent(events.TaskStarted, WorkerType, startedPayload)
	if err := s.eventBus.Publish(ctx, events.TaskTopic, startedEvent); err != nil {
		log.Error().Err(err).Str("task_id", taskID).Msg("Failed to publish TaskStarted event (proceeding anyway)")
	} else {
		log.Info().Str("task_id", taskID).Msg("Published TaskStarted event")
	}

	// --- Fetch Task Details ---
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

	// --- ReAct Loop ---
	log.Info().Str("task_id", taskID).Str("goal", task.Goal).Msg("Starting ReAct loop")
	history := make([]reactHistoryItem, 0, maxTurns)
	finalResult := make(map[string]interface{}) // Store the final result from FinishAction
	var loopErr error

	// Get action schemas once at the beginning
	actionSchemas := s.actionExecutor.GetActionSchemas()

	for turn := 0; turn < maxTurns; turn++ {
		log.Info().Str("task_id", taskID).Int("turn", turn+1).Msg("ReAct Turn Start")

		// 1. Construct Prompt
		userPrompt := constructReActUserPrompt(task.Goal, history, actionSchemas)
		llmRequest := llms.ChatCompletionRequest{
			Model: defaultLLMModel,
			Messages: []llms.ChatMessage{
				{Role: "system", Content: reactSystemPrompt},
				{Role: "user", Content: userPrompt},
			},
			// Temperature might be lower for ReAct, e.g., 0.2
		}

		// 2. Call LLM
		llmResponse, err := s.llmClient.ChatCompletion(ctx, llmRequest)
		if err != nil {
			loopErr = errors.Wrap(err, "LLM call failed within ReAct loop")
			log.Error().Err(loopErr).Str("task_id", taskID).Int("turn", turn+1).Msg("LLM Error")
			break // Exit loop on LLM error
		}
		if len(llmResponse.Choices) == 0 || llmResponse.Choices[0].Message.Content == "" {
			loopErr = errors.New("LLM response was empty")
			log.Error().Err(loopErr).Str("task_id", taskID).Int("turn", turn+1).Msg("LLM Error")
			break
		}
		llmOutput := llmResponse.Choices[0].Message.Content
		log.Debug().Str("task_id", taskID).Int("turn", turn+1).Str("llm_output", llmOutput).Msg("LLM Response Received")

		// 3. Parse LLM Response
		reactResp, err := parseLLMReActResponse(llmOutput)
		if err != nil {
			log.Warn().Err(err).Str("task_id", taskID).Int("turn", turn+1).Str("llm_output", llmOutput).Msg("Failed to parse LLM ReAct response, attempting NoAction")
			// Treat parsing failure or missing action as NoAction
			reactResp.Action = &llmAction{ActionName: "no_action", ActionArgs: map[string]interface{}{}}
		}

		currentTurn := reactHistoryItem{Thought: reactResp.Thought}

		// 4. Execute Action
		actionName := reactResp.Action.ActionName
		actionArgs := reactResp.Action.ActionArgs
		currentTurn.ActionName = actionName
		currentTurn.ActionArgs = actionArgs

		actionResult, execErr := s.actionExecutor.ExecuteAction(ctx, actionName, actionArgs)
		if execErr != nil {
			// Log error but continue loop, observation will contain the error message
			log.Error().Err(execErr).Str("task_id", taskID).Int("turn", turn+1).Str("action", actionName).Msg("Action execution failed")
			currentTurn.Observation = fmt.Sprintf("Error executing action %s: %v", actionName, execErr)
			// Optionally: break loop on certain action errors?
		} else {
			// Format observation from result (assuming result is map[string]interface{})
			// TODO: Improve observation formatting based on action result types
			resultBytes, _ := json.MarshalIndent(actionResult.Result, "", "  ")
			currentTurn.Observation = string(resultBytes)
			log.Info().Str("task_id", taskID).Int("turn", turn+1).Str("action", actionName).Str("observation", currentTurn.Observation).Msg("Action executed")
		}

		// 5. Update History
		history = append(history, currentTurn)

		// 6. Check for Finish
		if actionResult.Status == actions.ActionStatusFinished {
			log.Info().Str("task_id", taskID).Int("turn", turn+1).Msg("Finish action detected. Exiting ReAct loop.")
			// Extract final answer from result data if possible
			if data, ok := actionResult.Result.(map[string]interface{}); ok {
				if answer, ok := data["final_answer"].(string); ok {
					finalResult["final_answer"] = answer
				}
			}
			if _, ok := finalResult["final_answer"]; !ok {
                // If finish action didn't provide the answer in the expected key, use the raw observation
                finalResult["final_answer"] = currentTurn.Observation
            }
			break // Exit loop successfully
		}

		// Check context cancellation
		if ctx.Err() != nil {
			loopErr = ctx.Err()
			log.Warn().Str("task_id", taskID).Msg("Context cancelled during ReAct loop")
			break
		}
	}

	// --- End ReAct Loop ---

	// Determine final status and result
	var finalStatus string
	if loopErr != nil {
		finalStatus = fmt.Sprintf("ReAct loop failed: %v", loopErr)
		s.publishTaskFailed(ctx, taskID, rootTaskID, finalStatus, loopErr)
		return nil // Failure already published
	} else if len(history) >= maxTurns && finalResult["final_answer"] == nil {
		finalStatus = "Reached max turns without finishing."
		log.Warn().Str("task_id", taskID).Msg(finalStatus)
		// Consider this a failure or partial success?
		// Let's treat as failure for now.
		s.publishTaskFailed(ctx, taskID, rootTaskID, finalStatus, errors.New(finalStatus))
		return nil
	} else {
		finalStatus = "ReAct loop completed successfully."
		log.Info().Str("task_id", taskID).Msg(finalStatus)
		// Use the final_answer extracted from FinishAction if available
		if _, ok := finalResult["final_answer"]; !ok {
            // Fallback if finish action result wasn't parsed correctly
            if len(history) > 0 {
                finalResult["final_answer"] = history[len(history)-1].Observation
            } else {
                 finalResult["final_answer"] = "Loop finished without providing an answer."
            }
        }
	}

	// Include history in the final result for debugging/tracing
	finalResult["status"] = finalStatus
	finalResult["react_history"] = history

	// --- Publish TaskCompleted Event ---
	completedPayload := events.TaskCompletedPayload{
		TaskID:     taskID,
		RootTaskID: rootTaskID,
		Result:     finalResult, // Include history and final answer
	}
	completedEvent := events.NewEvent(events.TaskCompleted, WorkerType, completedPayload)

	err = s.eventBus.Publish(ctx, events.TaskTopic, completedEvent)
	if err != nil {
		// Log error, but the task technically finished its execution attempt.
		log.Error().Err(err).Str("task_id", taskID).Msg("Failed to publish TaskCompleted event after ReAct loop")
		// Don't return the error here, let the caller handle ACK
	}

	log.Info().Str("task_id", taskID).Msg("Execution task ReAct processing finished.")
	return nil
}
