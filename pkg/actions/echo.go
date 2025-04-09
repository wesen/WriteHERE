package actions

import (
	"context"
	"fmt"
	"strings"

	"github.com/pkg/errors"
)

// EchoAction is a simple example action that echoes back its input.
type EchoAction struct{}

// इंश्योर करें कि EchoAction हमेशा Action इंटरफेस को लागू करता है
var _ Action = &EchoAction{}

func init() {
	RegisterAction(&EchoAction{})
}

func (a *EchoAction) Name() string {
	return "echo"
}

func (a *EchoAction) Description() string {
	return "Echoes back the provided message, optionally repeating it."
}

func (a *EchoAction) ParameterSchema() map[string]interface{} {
	return map[string]interface{}{
		"message": map[string]interface{}{
			"type":        "string",
			"description": "The message to echo back.",
			"required":    true,
		},
		"repeat": map[string]interface{}{
			"type":        "integer",
			"description": "Number of times to repeat the message.",
			"required":    false,
			"default":     1,
		},
	}
}

func (a *EchoAction) Execute(ctx context.Context, args map[string]interface{}) (ActionResult, error) {
	messageVal, ok := args["message"]
	if !ok {
		return ActionResult{Status: ActionStatusFailure, Error: "missing required argument: message"}, errors.New("missing required argument: message")
	}
	message, ok := messageVal.(string)
	if !ok {
		return ActionResult{Status: ActionStatusFailure, Error: "invalid argument type for message: expected string"}, errors.New("invalid argument type for message: expected string")
	}

	repeatVal, ok := args["repeat"]
	if !ok {
		// Use default if not provided
		repeatVal = 1
	}
	repeatFloat, ok := repeatVal.(float64) // JSON numbers often decode as float64
	if !ok {
		repeatInt, okInt := repeatVal.(int)
		if !okInt {
			return ActionResult{Status: ActionStatusFailure, Error: "invalid argument type for repeat: expected integer"}, errors.New("invalid argument type for repeat: expected integer")
		}
		repeatFloat = float64(repeatInt)

	}
	repeat := int(repeatFloat)

	if repeat <= 0 {
		repeat = 1
	}

	resultMessage := strings.Repeat(fmt.Sprintf("%s ", message), repeat)
	resultMessage = strings.TrimSpace(resultMessage) // Remove trailing space

	return ActionResult{
		Status: ActionStatusSuccess,
		Result: map[string]interface{}{
			"echo": resultMessage,
		},
	}, nil
}
