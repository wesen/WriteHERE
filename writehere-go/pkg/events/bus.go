package events

import (
	"context"
	"sync"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/ThreeDotsLabs/watermill/message/router/middleware"
	"github.com/ThreeDotsLabs/watermill/pubsub/gochannel"
	"github.com/pkg/errors"
	"github.com/rs/zerolog"
)

// EventBus represents the event bus system
type EventBus struct {
	router          *message.Router
	publisher       message.Publisher
	subscriber      message.Subscriber
	logger          zerolog.Logger
	watermillLogger watermill.LoggerAdapter
	handlerRegistry map[EventType][]message.HandlerFunc
	mu              sync.RWMutex
}

// NewEventBus creates a new event bus with an in-memory gochannel
func NewEventBus(ctx context.Context, logger zerolog.Logger) (*EventBus, error) {
	// Create a watermill logger adapter
	watermillLogger := watermill.NewStdLogger(false, false)

	// Create the publisher and subscriber
	pubSub := gochannel.NewGoChannel(
		gochannel.Config{
			Persistent: true, // Ensures messages aren't lost between restarts
		},
		watermillLogger,
	)

	// Create the router
	router, err := message.NewRouter(message.RouterConfig{}, watermillLogger)
	if err != nil {
		return nil, errors.Wrap(err, "failed to create router")
	}

	// Add middleware
	router.AddMiddleware(
		// Recoverer handles panics from handlers
		middleware.Recoverer,

		// CorrelationID adds a correlation ID to the message metadata
		middleware.CorrelationID,

		// Retry middleware helps with transient errors
		middleware.Retry{
			MaxRetries:      3,
			InitialInterval: 1 * time.Second,
			Logger:          watermillLogger,
		}.Middleware,
	)

	bus := &EventBus{
		router:          router,
		publisher:       pubSub,
		subscriber:      pubSub,
		logger:          logger,
		watermillLogger: watermillLogger,
		handlerRegistry: make(map[EventType][]message.HandlerFunc),
	}

	// Start the router in a goroutine
	go func() {
		if err := router.Run(ctx); err != nil {
			logger.Error().Err(err).Msg("router error")
		}
	}()

	return bus, nil
}

// Publish sends an event to the event bus
func (b *EventBus) Publish(ctx context.Context, topic string, event Event) error {
	b.logger.Debug().
		Str("event_id", event.EventID).
		Str("event_type", string(event.EventType)).
		Str("topic", topic).
		Msg("publishing event")

	msg, err := event.ToMessage()
	if err != nil {
		return errors.Wrap(err, "failed to convert event to message")
	}

	if err := b.publisher.Publish(topic, msg); err != nil {
		return errors.Wrap(err, "failed to publish message")
	}

	return nil
}

// Subscribe registers a handler for a specific event type on a topic
func (b *EventBus) Subscribe(ctx context.Context, topic string, eventType EventType, handler func(context.Context, Event) error) error {
	b.logger.Debug().
		Str("event_type", string(eventType)).
		Str("topic", topic).
		Msg("subscribing to event")

	// Create a message handler that filters by event type
	handlerFunc := func(msg *message.Message) ([]*message.Message, error) {
		event, err := EventFromMessage(msg)
		if err != nil {
			return nil, errors.Wrap(err, "failed to parse event from message")
		}

		// Skip if this message is not the event type we're looking for
		if event.EventType != eventType {
			return nil, nil
		}

		// Call the user-provided handler
		if err := handler(ctx, event); err != nil {
			return nil, errors.Wrap(err, "handler error")
		}

		return nil, nil
	}

	// Register the handler
	b.mu.Lock()
	defer b.mu.Unlock()
	b.handlerRegistry[eventType] = append(b.handlerRegistry[eventType], handlerFunc)

	b.router.AddHandler(
		string(eventType), // Handler name (must be unique)
		topic,             // Topic
		b.subscriber,      // Subscriber
		topic+"_out",      // Publishing topic (not used in this case)
		b.publisher,       // Publisher
		handlerFunc,       // Handler function
	)

	return nil
}

// Close stops the event bus and releases resources
func (b *EventBus) Close() error {
	if err := b.router.Close(); err != nil {
		return errors.Wrap(err, "failed to close router")
	}

	if err := b.publisher.Close(); err != nil {
		return errors.Wrap(err, "failed to close publisher")
	}

	if err := b.subscriber.Close(); err != nil {
		return errors.Wrap(err, "failed to close subscriber")
	}

	return nil
}

// Topics for the event bus
const (
	TaskTopic = "tasks"
)
