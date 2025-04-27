package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill-redisstream/pkg/redisstream"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/redis/go-redis/v9"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

// SimplePayloadUnmarshaller assumes the message payload is stored under the key "payload"
// in the Redis stream message and generates a UUID locally.
type SimplePayloadUnmarshaller struct{}

// Unmarshal implements the watermill.Unmarshaller interface.
func (s SimplePayloadUnmarshaller) Unmarshal(values map[string]interface{}) (*message.Message, error) {
	log.Info().Msgf("Unmarshal values: %v", values)
	payload, ok := values["json_payload"]
	if !ok {
		// Fallback check for the default watermill field, just in case
		payload, ok = values["_watermill_payload"]
		if !ok {
			return nil, fmt.Errorf("message does not contain payload under key 'json_payload' or '%s'", "_watermill_payload")
		}
		log.Warn().Msg("Found payload under default key '_watermill_payload' instead of 'json_payload'")
	}

	var payloadStr string
	switch v := payload.(type) {
	case string:
		payloadStr = v
	default:
		// Marshal to JSON string
		b, err := json.Marshal(v)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal payload to JSON string: %w", err)
		}
		payloadStr = string(b)
	}

	if !ok {
		// Fallback check for the default watermill field, just in case
		payloadStrWP, okWP := values["_watermill_payload"].(string)
		if !okWP {
			return nil, fmt.Errorf("message does not contain string payload under key 'json_payload' or '%s'", "_watermill_payload")
		}
		log.Warn().Msg("Found payload under default key '_watermill_payload' instead of 'json_payload'")
		payloadStr = payloadStrWP
	}

	msgUUID := watermill.NewUUID()
	msg := message.NewMessage(msgUUID, []byte(payloadStr))
	// No metadata is extracted from the Redis message itself
	return msg, nil
}

// Marshal implements the watermill.Marshaller interface.
// We don't need marshalling for this subscriber-only example.
func (s SimplePayloadUnmarshaller) Marshal(topic string, msg *message.Message) (*redis.XAddArgs, error) {
	panic("SimplePayloadUnmarshaller Marshal not implemented/needed for subscriber")
}

var (
	// Default configuration, can be overridden by environment variables
	redisAddr     = getEnv("REDIS_ADDR", "localhost:6379")
	streamName    = getEnv("REDIS_STREAM_NAME", "agent_events")
	consumerGroup = getEnv("REDIS_CONSUMER_GROUP", "go_listener_group")
)

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func main() {
	// Setup zerolog with caller info and output to console (pretty, not JSON)
	consoleWriter := zerolog.ConsoleWriter{Out: os.Stdout, TimeFormat: "2006-01-02 15:04:05"}
	logger := zerolog.New(consoleWriter).With().Timestamp().Caller().Logger()
	log.Logger = logger
	_logger := zerolog.New(consoleWriter).With().Timestamp().Logger()
	watermillLogger := watermill.NewStdLoggerWithOut(_logger.With().Str("component", "watermill").Logger(), true, false)

	// Configure Redis client
	redisClient := redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})
	defer func() {
		if err := redisClient.Close(); err != nil {
			logger.Error().Err(err).Msg("Failed to close Redis client")
		}
	}()

	// Create Watermill subscriber
	subscriber, err := redisstream.NewSubscriber(
		redisstream.SubscriberConfig{
			Client:        redisClient,
			Unmarshaller:  SimplePayloadUnmarshaller{}, // Use our custom one
			ConsumerGroup: consumerGroup,
			// Increase buffer size for potentially high throughput
			NackResendSleep: time.Second * 5, // Wait 5s before resending NACKed message
			MaxIdleTime:     time.Minute * 2, // Close idle connections faster
		},
		watermillLogger,
	)
	if err != nil {
		logger.Fatal().Err(err).Msg("Failed to create Redis subscriber")
	}

	// Create Watermill router
	router, err := message.NewRouter(message.RouterConfig{}, watermillLogger)
	if err != nil {
		logger.Fatal().Err(err).Msg("Failed to create router")
	}

	// Define the handler function
	printMessageHandler := func(msg *message.Message) error {
		logger.Info().
			Str("message_id", msg.UUID).
			Str("payload", string(msg.Payload)).
			Msg("Received message")
		// Acknowledge the message that it has been processed.
		msg.Ack()
		return nil
	}

	// Add the handler to the router
	router.AddHandler(
		"redis_event_printer", // Handler name
		streamName,            // Subscribe topic
		subscriber,
		"",  // Publish topic (empty string as we don't publish)
		nil, // Publisher (nil as we don't publish)
		func(msg *message.Message) ([]*message.Message, error) {
			err := printMessageHandler(msg)
			return nil, err // Return no messages to publish
		},
	)

	// Setup graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)

	// Run the router in a separate goroutine
	go func() {
		if err := router.Run(ctx); err != nil {
			logger.Error().Err(err).Msg("Router run failed")
			cancel() // Ensure shutdown on router error
		}
	}()

	// Wait for shutdown signal
	select {
	case sig := <-signals:
		logger.Info().Str("signal", sig.String()).Msg("Received shutdown signal")
	case <-ctx.Done():
		logger.Info().Msg("Router context cancelled, shutting down")
	}

	logger.Info().Msg("Shutting down router...")
	if err := router.Close(); err != nil {
		logger.Error().Err(err).Msg("Failed to close router gracefully")
	} else {
		logger.Info().Msg("Router closed gracefully")
	}

	logger.Info().Msg("Listener shut down complete.")
}
