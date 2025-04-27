package main

import (
	"context"
	"encoding/json"
	"os"
	"os/signal"
	"syscall"

	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"

	"writehere-go/internal/redis" // Use full module path for internal package
	"writehere-go/pkg/model"     // Use full module path for pkg package
)

func main() {
	// Setup zerolog with caller info and output to console (pretty, not JSON)
	consoleWriter := zerolog.ConsoleWriter{Out: os.Stdout, TimeFormat: "2006-01-02 15:04:05"}
	logger := zerolog.New(consoleWriter).With().Timestamp().Caller().Logger()
	log.Logger = logger

	// Get default router configuration
	routerConfig := redis.DefaultRouterConfig()
	// TODO: Allow overriding config via environment variables or flags

	// Create Watermill logger adapter
	// This is created internally by redis.NewRouter now, so we don't need it here
	// watermillLogger := redis.NewWatermillLogger(logger)

	// Define the handler function
	printMessageHandler := func(msg *message.Message) error {
		var event model.Event
		if err := json.Unmarshal(msg.Payload, &event); err != nil {
			logger.Error().Err(err).Str("message_id", msg.UUID).Msg("Failed to unmarshal event payload")
			// Acknowledge the message even if unmarshalling fails, to avoid infinite retries
			// Alternatively, configure a dead-letter queue in the router
			msg.Ack()
			return nil // Return nil to avoid NACKing
		}

		logger.Info().
			Str("message_id", msg.UUID).
			Str("event_id", event.EventID).
			Str("run_id", event.RunID).
			Str("event_type", event.EventType).
			Str("timestamp", event.Timestamp).
			RawJSON("payload", event.Payload).
			Msg("Received event")

		// Acknowledge the message that it has been processed.
		msg.Ack()
		return nil
	}

	// Setup graceful shutdown context
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)

	// Create the router using the internal package
	router, err := redis.NewRouter(
		ctx, // Pass the context for graceful shutdown
		routerConfig,
		logger,              // Pass the base zerolog logger
		printMessageHandler, // Pass our defined handler
	)
	if err != nil {
		logger.Fatal().Err(err).Msg("Failed to create Redis router")
	}

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
