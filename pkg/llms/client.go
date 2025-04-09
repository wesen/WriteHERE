package llms

import "context"

// ChatMessage represents a single message in a chat completion request/response.
type ChatMessage struct {
	Role    string `json:"role"` // e.g., "system", "user", "assistant"
	Content string `json:"content"`
}

// ResponseFormat specifies the desired output format (e.g., JSON).
type ResponseFormat struct {
	Type string `json:"type"` // e.g., "json_object"
}

// ChatCompletionRequest defines the structure for requesting a chat completion.
type ChatCompletionRequest struct {
	Model       string        `json:"model"`
	Messages    []ChatMessage `json:"messages"`
	Temperature *float32      `json:"temperature,omitempty"`
	// Add other common parameters like MaxTokens, Stop, etc. if needed
	ResponseFormat *ResponseFormat `json:"response_format,omitempty"` // For JSON mode
}

// ChatCompletionResponse defines the structure of the response from a chat completion.
type ChatCompletionResponse struct {
	Choices []struct {
		Message ChatMessage `json:"message"`
	} `json:"choices"`
	// Include usage info if needed (e.g., token counts)
}

// Client is the interface for interacting with a language model.
type Client interface {
	ChatCompletion(ctx context.Context, request ChatCompletionRequest) (ChatCompletionResponse, error)
}
