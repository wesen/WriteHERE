package redis

import (
	"encoding/json"
	"fmt"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/redis/go-redis/v9"
)

// CustomEventUnmarshaller handles the specific format of messages published
// by the Python EventBus, where the entire event is a JSON string under the "json_payload" key
type CustomEventUnmarshaller struct{}

// Unmarshal extracts the event JSON from the Redis stream message
func (u CustomEventUnmarshaller) Unmarshal(values map[string]interface{}) (*message.Message, error) {
	// Get the raw payload value
	payload, ok := values["json_payload"]
	if !ok {
		// Fallback to the default Watermill field, just in case
		payload, ok = values["_watermill_payload"]
		if !ok {
			return nil, fmt.Errorf("message does not contain payload under key 'json_payload' or '_watermill_payload'")
		}
	}

	// Handle different payload types
	var payloadStr string
	switch v := payload.(type) {
	case string:
		payloadStr = v
	case []byte:
		payloadStr = string(v)
	default:
		// Marshal any non-string payload to JSON
		b, err := json.Marshal(v)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal payload to JSON string: %w", err)
		}
		payloadStr = string(b)
	}

	// Create a new Watermill message with the payload
	msgUUID := watermill.NewUUID()
	msg := message.NewMessage(msgUUID, []byte(payloadStr))
	return msg, nil
}

// Marshal implements the RedisStreamMarshaller interface, but is not used
// when the component is a subscriber only
func (u CustomEventUnmarshaller) Marshal(topic string, msg *message.Message) (*redis.XAddArgs, error) {
	// This method is not needed for a subscriber-only implementation
	// However, we provide a basic implementation in case it's used for publishing
	return &redis.XAddArgs{
		Stream: topic,
		Values: map[string]interface{}{
			"json_payload": string(msg.Payload),
		},
	}, nil
}
