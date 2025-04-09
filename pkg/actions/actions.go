package actions

import (
	"context"
	"fmt"
	"sync"
)

// ActionStatus represents the outcome of an action execution.
type ActionStatus string

const (
	ActionStatusSuccess ActionStatus = "success"
	ActionStatusFailure ActionStatus = "failure"
	ActionStatusRunning ActionStatus = "running" // Potentially for long-running actions
	ActionStatusPending ActionStatus = "pending" // Potentially for long-running actions
	ActionStatusError   ActionStatus = "error"   // Potentially for long-running actions
)

// Action represents a unit of work that can be executed, similar to a tool or function call.
// It defines its parameters and executes logic based on provided arguments.
type Action interface {
	// Name returns the unique identifier for the action.
	Name() string
	// Description provides a human-readable explanation of what the action does.
	Description() string
	// ParameterSchema defines the expected input arguments for the action,
	// typically following a structure like JSON Schema.
	ParameterSchema() map[string]interface{}
	// Execute performs the action's logic with the given arguments.
	// It takes a context for cancellation and returns a result and potential error.
	Execute(ctx context.Context, args map[string]interface{}) (ActionResult, error)
}

// ActionResult holds the outcome of an action's execution.
type ActionResult struct {
	Status ActionStatus           `json:"status"`
	Result map[string]interface{} `json:"result,omitempty"` // Output data if successful
	Error  string                 `json:"error,omitempty"`  // Error message if failed
}

// --- Action Registry ---

var (
	actionRegistry = make(map[string]Action)
	registryMutex  = &sync.RWMutex{}
)

// RegisterAction adds an action to the global registry.
// It is typically called from the init() function of action implementations.
// Panics if an action with the same name is already registered.
func RegisterAction(action Action) {
	registryMutex.Lock()
	defer registryMutex.Unlock()

	name := action.Name()
	if _, exists := actionRegistry[name]; exists {
		panic(fmt.Sprintf("action with name '%s' already registered", name))
	}
	actionRegistry[name] = action
}

// GetAction retrieves an action from the registry by its name.
// Returns the action and true if found, otherwise nil and false.
func GetAction(name string) (Action, bool) {
	registryMutex.RLock()
	defer registryMutex.RUnlock()

	action, exists := actionRegistry[name]
	return action, exists
}

// ListActions returns a list of names of all registered actions.
func ListActions() []string {
	registryMutex.RLock()
	defer registryMutex.RUnlock()

	names := make([]string, 0, len(actionRegistry))
	for name := range actionRegistry {
		names = append(names, name)
	}
	return names
}
