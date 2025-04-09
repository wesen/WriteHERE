package actions

import (
	"context"

	"github.com/pkg/errors"
)

// --- Built-in Action Implementations ---

// FinishAction indicates the agent has completed its task.
// It expects the final answer as an argument.
type FinishAction struct{}

var _ Action = (*FinishAction)(nil)

func (f *FinishAction) Name() string { return "finish" }
func (f *FinishAction) Description() string {
	return "Signals that the task is complete and provides the final answer."
}
func (f *FinishAction) ParameterSchema() map[string]interface{} {
	return map[string]interface{}{
		"final_answer": map[string]interface{}{
			"type":        "string",
			"description": "The final answer or result of the task.",
			"required":    true,
		},
	}
}
func (f *FinishAction) Execute(ctx context.Context, args map[string]interface{}) (ActionResult, error) {
	finalAnswer, ok := args["final_answer"].(string)
	if !ok {
		return ActionResult{Status: ActionStatusError, Result: map[string]interface{}{"error": "Missing or invalid 'final_answer' argument"}}, errors.New("missing or invalid 'final_answer' argument for FinishAction")
	}
	return ActionResult{
		Status: ActionStatusSuccess,
		Result: map[string]interface{}{
			"final_answer": finalAnswer,
		},
	}, nil
}

// InvalidAction indicates the LLM requested an action that doesn't exist or is invalid.
type InvalidAction struct{}

var _ Action = (*InvalidAction)(nil)

func (i *InvalidAction) Name() string { return "invalid_action" }
func (i *InvalidAction) Description() string {
	return "Used by the agent if the LLM's requested action is not recognized or invalid."
}
func (i *InvalidAction) ParameterSchema() map[string]interface{} {
	// Typically called internally by the agent/executor, not the LLM directly
	return map[string]interface{}{
		"reason": map[string]interface{}{
			"type":        "string",
			"description": "Reason why the action was considered invalid.",
			"required":    false,
		},
	}
}
func (i *InvalidAction) Execute(ctx context.Context, args map[string]interface{}) (ActionResult, error) {
	reason := "Invalid action requested."
	if r, ok := args["reason"].(string); ok {
		reason = r
	}
	return ActionResult{Status: ActionStatusError, Result: map[string]interface{}{"error": reason}}, nil
}

// NoAction indicates the LLM failed to request an action when one was expected.
type NoAction struct{}

var _ Action = (*NoAction)(nil)

func (n *NoAction) Name() string { return "no_action" }
func (n *NoAction) Description() string {
	return "Used by the agent if the LLM failed to output an action when expected."
}
func (n *NoAction) ParameterSchema() map[string]interface{} {
	// Called internally by the agent
	return map[string]interface{}{}
}
func (n *NoAction) Execute(ctx context.Context, args map[string]interface{}) (ActionResult, error) {
	return ActionResult{Status: ActionStatusError, Result: map[string]interface{}{"error": "No action was specified by the LLM."}}, nil
}

// --- Registration ---
func init() {
	RegisterAction(&FinishAction{})
	RegisterAction(&InvalidAction{})
	RegisterAction(&NoAction{})
}
