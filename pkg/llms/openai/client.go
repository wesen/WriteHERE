package openai

import (
	"context"
	"os"
	"writehere-go/pkg/llms" // Import the interface package

	"github.com/pkg/errors"
	openai "github.com/sashabaranov/go-openai"
)

// Client implements the llms.Client interface for OpenAI.
type Client struct {
	openaiClient *openai.Client
}

var _ llms.Client = (*Client)(nil) // Compile-time interface check

// NewClient creates a new OpenAI client.
// It reads the API key from the OPENAI_API_KEY environment variable if apiKey is empty.
func NewClient(apiKey string) *Client {
	if apiKey == "" {
		apiKey = os.Getenv("OPENAI_API_KEY") // Fallback to env var
	}
	// Consider adding a check here to ensure apiKey is not empty and perhaps log a warning or error.
	return &Client{
		openaiClient: openai.NewClient(apiKey),
	}
}

// ChatCompletion performs a chat completion request using the OpenAI API.
func (c *Client) ChatCompletion(ctx context.Context, request llms.ChatCompletionRequest) (llms.ChatCompletionResponse, error) {
	// Convert llms.ChatCompletionRequest to openai.ChatCompletionRequest
	oaMessages := make([]openai.ChatCompletionMessage, len(request.Messages))
	for i, msg := range request.Messages {
		oaMessages[i] = openai.ChatCompletionMessage{
			Role:    msg.Role,
			Content: msg.Content,
		}
	}

	oaRequest := openai.ChatCompletionRequest{
		Model:    request.Model,
		Messages: oaMessages,
	}
	if request.Temperature != nil {
		oaRequest.Temperature = *request.Temperature
	}
	if request.ResponseFormat != nil {
		// Ensure the type is compatible with the library's expected enum type
		oaRequest.ResponseFormat = &openai.ChatCompletionResponseFormat{
			Type: openai.ChatCompletionResponseFormatType(request.ResponseFormat.Type),
		}
	}

	resp, err := c.openaiClient.CreateChatCompletion(ctx, oaRequest)
	if err != nil {
		return llms.ChatCompletionResponse{}, errors.Wrap(err, "OpenAI chat completion failed")
	}

	// Convert openai.ChatCompletionResponse to llms.ChatCompletionResponse
	llmsResp := llms.ChatCompletionResponse{}
	if len(resp.Choices) > 0 {
		// Basic conversion, assuming one choice is sufficient for now
		llmsResp.Choices = []struct {
			Message llms.ChatMessage `json:"message"`
		}{
			{
				Message: llms.ChatMessage{
					Role:    resp.Choices[0].Message.Role,
					Content: resp.Choices[0].Message.Content,
				},
			},
		}
	} else {
		// Handle cases where no choices are returned
		return llms.ChatCompletionResponse{}, errors.New("OpenAI response contained no choices")
	}

	return llmsResp, nil
}
