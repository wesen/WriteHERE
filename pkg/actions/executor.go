package actions

import (
	"context"
	"fmt"
	"strings"

	"github.com/pkg/errors"
	"github.com/rs/zerolog/log"
)

// ActionExecutor manages and executes registered actions.
type ActionExecutor struct {
	registry map[string]Action
}

// NewActionExecutor creates a new executor, initializing it with
// the actions currently in the global actionRegistry.
func NewActionExecutor() *ActionExecutor {
	// Create a copy of the registry to avoid concurrency issues if the global
	// registry were modified later (though it typically isn't after init).
	registryCopy := make(map[string]Action)
	for name, action := range actionRegistry {
		registryCopy[name] = action
	}

	log.Info().Int("action_count", len(registryCopy)).Msg("ActionExecutor initialized")
	return &ActionExecutor{
		registry: registryCopy,
	}
}

// GetActionSchemas returns a formatted string describing all registered actions,
// suitable for inclusion in an LLM prompt.
func (e *ActionExecutor) GetActionSchemas() string {
	var builder strings.Builder
	builder.WriteString("Available Actions:\n")
	for name, action := range e.registry {
		builder.WriteString(fmt.Sprintf("- Action: %s\n", name))
		builder.WriteString(fmt.Sprintf("  Description: %s\n", action.Description()))
		params := action.ParameterSchema()
		if len(params) > 0 {
			builder.WriteString("  Parameters:\n")
			for paramName, schema := range params {
				schemaMap, ok := schema.(map[string]interface{})
				if !ok {
					log.Warn().Str("action", name).Str("param", paramName).Msg("Invalid parameter schema format")
					continue
				}
				paramType := schemaMap["type"].(string)
				paramDesc := schemaMap["description"].(string)
				required := schemaMap["required"].(bool)
				builder.WriteString(fmt.Sprintf("    - %s (type: %s, required: %t): %s\n", paramName, paramType, required, paramDesc))
			}
		} else {
			builder.WriteString("  Parameters: None\n")
		}
		builder.WriteString("\n")
	}
	return builder.String()
}

// ExecuteAction finds and executes the action specified by name with the given arguments.
func (e *ActionExecutor) ExecuteAction(ctx context.Context, actionName string, args map[string]interface{}) (ActionResult, error) {
	action, exists := e.registry[actionName]
	if !exists {
		log.Warn().Str("action_name", actionName).Msg("Attempted to execute non-existent action")
		// Optionally execute InvalidAction here or let the caller handle it
		return ActionResult{Status: ActionStatusError, Result: map[string]interface{}{"error": fmt.Sprintf("Action '%s' not found.", actionName)}}, errors.Errorf("action '%s' not found", actionName)
	}

	log.Info().Str("action_name", actionName).Interface("args", args).Msg("Executing action")

	// TODO: Add argument validation against action.ParameterSchema() here
	// For now, pass args directly
	result, err := action.Execute(ctx, args)
	if err != nil {
		log.Error().Err(err).Str("action_name", actionName).Msg("Action execution failed")
		// Return error status result, but maybe not the internal error itself unless needed
		if result.Status == "" { // Ensure status is set even on error
			result.Status = ActionStatusError
		}
		if result.Result == nil {
			result.Result = map[string]interface{}{"error": fmt.Sprintf("Error executing action '%s': %v", actionName, err)}
		}
		return result, errors.Wrapf(err, "failed to execute action '%s'", actionName)
	}

	log.Info().Str("action_name", actionName).Str("status", string(result.Status)).Msg("Action execution completed")
	return result, nil
}
