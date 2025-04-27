package model

import (
	"encoding/json"
)

// ToNodeCreatedPayload converts raw JSON payload to NodeCreatedPayload
func ToNodeCreatedPayload(data json.RawMessage) (NodeCreatedPayload, bool) {
	var payload NodeCreatedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return NodeCreatedPayload{}, false
	}
	return payload, true
}

// ToNodeStatusChangedPayload converts raw JSON payload to NodeStatusChangedPayload
func ToNodeStatusChangedPayload(data json.RawMessage) (NodeStatusChangedPayload, bool) {
	var payload NodeStatusChangedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return NodeStatusChangedPayload{}, false
	}
	return payload, true
}

// ToNodeResultAvailablePayload converts raw JSON payload to NodeResultAvailablePayload
func ToNodeResultAvailablePayload(data json.RawMessage) (NodeResultAvailablePayload, bool) {
	var payload NodeResultAvailablePayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return NodeResultAvailablePayload{}, false
	}
	return payload, true
}

// ToEdgeAddedPayload converts raw JSON payload to EdgeAddedPayload
func ToEdgeAddedPayload(data json.RawMessage) (EdgeAddedPayload, bool) {
	var payload EdgeAddedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return EdgeAddedPayload{}, false
	}
	return payload, true
}

// ToRunStartedPayload converts raw JSON payload to RunStartedPayload
func ToRunStartedPayload(data json.RawMessage) (RunStartedPayload, bool) {
	var payload RunStartedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return RunStartedPayload{}, false
	}
	return payload, true
}

// ToRunFinishedPayload converts raw JSON payload to RunFinishedPayload
func ToRunFinishedPayload(data json.RawMessage) (RunFinishedPayload, bool) {
	var payload RunFinishedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return RunFinishedPayload{}, false
	}
	return payload, true
}

// ToRunErrorPayload converts raw JSON payload to RunErrorPayload
func ToRunErrorPayload(data json.RawMessage) (RunErrorPayload, bool) {
	var payload RunErrorPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return RunErrorPayload{}, false
	}
	return payload, true
}

// ToStepStartedPayload converts raw JSON payload to StepStartedPayload
func ToStepStartedPayload(data json.RawMessage) (StepStartedPayload, bool) {
	var payload StepStartedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return StepStartedPayload{}, false
	}
	return payload, true
}

// ToStepFinishedPayload converts raw JSON payload to StepFinishedPayload
func ToStepFinishedPayload(data json.RawMessage) (StepFinishedPayload, bool) {
	var payload StepFinishedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return StepFinishedPayload{}, false
	}
	return payload, true
}

// ToLLMCallStartedPayload converts raw JSON payload to LLMCallStartedPayload
func ToLLMCallStartedPayload(data json.RawMessage) (LLMCallStartedPayload, bool) {
	var payload LLMCallStartedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return LLMCallStartedPayload{}, false
	}
	return payload, true
}

// ToLLMCallCompletedPayload converts raw JSON payload to LLMCallCompletedPayload
func ToLLMCallCompletedPayload(data json.RawMessage) (LLMCallCompletedPayload, bool) {
	var payload LLMCallCompletedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return LLMCallCompletedPayload{}, false
	}
	return payload, true
}

// ToToolInvokedPayload converts raw JSON payload to ToolInvokedPayload
func ToToolInvokedPayload(data json.RawMessage) (ToolInvokedPayload, bool) {
	var payload ToolInvokedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return ToolInvokedPayload{}, false
	}
	return payload, true
}

// ToToolReturnedPayload converts raw JSON payload to ToolReturnedPayload
func ToToolReturnedPayload(data json.RawMessage) (ToolReturnedPayload, bool) {
	var payload ToolReturnedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return ToolReturnedPayload{}, false
	}
	return payload, true
}

// ToPlanReceivedPayload converts raw JSON payload to PlanReceivedPayload
func ToPlanReceivedPayload(data json.RawMessage) (PlanReceivedPayload, bool) {
	var payload PlanReceivedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return PlanReceivedPayload{}, false
	}
	return payload, true
}

// ToNodeAddedPayload converts raw JSON payload to NodeAddedPayload
func ToNodeAddedPayload(data json.RawMessage) (NodeAddedPayload, bool) {
	var payload NodeAddedPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return NodeAddedPayload{}, false
	}
	return payload, true
}

// ToInnerGraphBuiltPayload converts raw JSON payload to InnerGraphBuiltPayload
func ToInnerGraphBuiltPayload(data json.RawMessage) (InnerGraphBuiltPayload, bool) {
	var payload InnerGraphBuiltPayload
	err := json.Unmarshal(data, &payload)
	if err != nil {
		return InnerGraphBuiltPayload{}, false
	}
	return payload, true
}
