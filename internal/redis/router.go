package redis

import (
	"context"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill-redisstream/pkg/redisstream"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/ThreeDotsLabs/watermill/message/router/middleware"
	"github.com/ThreeDotsLabs/watermill/message/router/plugin"
	"github.com/pkg/errors"
	"github.com/redis/go-redis/v9"
	"github.com/rs/zerolog"
)

// RouterConfig holds configuration for the message router
type RouterConfig struct {
	// Redis connection options
	RedisURL         string
	RedisPassword    string
	RedisDB          int
	RedisMaxRetries  int
	RedisDialTimeout time.Duration

	// Stream subscription options
	StreamName        string
	ConsumerGroup     string
	ConsumerName      string
	ClaimMinIdleTime  time.Duration
	BlockTime         time.Duration
	MaxIdleTime       time.Duration
	NackResendSleep   time.Duration
	CommitOffsetAfter time.Duration

	// Processing options
	AckWait time.Duration
}

// DefaultRouterConfig returns a RouterConfig with reasonable defaults
func DefaultRouterConfig() RouterConfig {
	return RouterConfig{
		RedisURL:          "localhost:6379",
		RedisPassword:     "",
		RedisDB:           0,
		RedisMaxRetries:   3,
		RedisDialTimeout:  time.Second * 5,
		StreamName:        "agent_events",
		ConsumerGroup:     "go_server_group",
		ConsumerName:      "go_server_consumer",
		ClaimMinIdleTime:  time.Minute * 1,
		BlockTime:         time.Second * 1,
		MaxIdleTime:       time.Minute * 5,
		NackResendSleep:   time.Second * 2,
		CommitOffsetAfter: time.Second * 10,
		AckWait:           time.Second * 30,
	}
}

// WatermillLogger is an adapter to use zerolog with Watermill
type WatermillLogger struct {
	logger zerolog.Logger
}

// NewWatermillLogger creates a new WatermillLogger
func NewWatermillLogger(logger zerolog.Logger) *WatermillLogger {
	return &WatermillLogger{
		logger: logger.With().Str("component", "watermill").Logger(),
	}
}

// Error logs an error message
func (l *WatermillLogger) Error(msg string, err error, fields watermill.LogFields) {
	event := l.logger.Error().Err(err)
	for k, v := range fields {
		event = event.Interface(k, v)
	}
	event.Msg(msg)
}

// Info logs an info message
func (l *WatermillLogger) Info(msg string, fields watermill.LogFields) {
	event := l.logger.Info()
	for k, v := range fields {
		event = event.Interface(k, v)
	}
	event.Msg(msg)
}

// Debug logs a debug message
func (l *WatermillLogger) Debug(msg string, fields watermill.LogFields) {
	event := l.logger.Debug()
	for k, v := range fields {
		event = event.Interface(k, v)
	}
	event.Msg(msg)
}

// Trace logs a trace message
func (l *WatermillLogger) Trace(msg string, fields watermill.LogFields) {
	event := l.logger.Trace()
	for k, v := range fields {
		event = event.Interface(k, v)
	}
	event.Msg(msg)
}

// With returns a new WatermillLogger with the given fields appended
func (l *WatermillLogger) With(fields watermill.LogFields) watermill.LoggerAdapter {
	loggerContext := l.logger.With()
	for k, v := range fields {
		loggerContext = loggerContext.Interface(k, v)
	}
	return &WatermillLogger{logger: loggerContext.Logger()}
}

// MessageHandler is a function that processes a message and returns an error if processing fails
type MessageHandler func(msg *message.Message) error

// NewRouter creates a new message router connected to Redis
func NewRouter(
	ctx context.Context,
	config RouterConfig,
	logger zerolog.Logger,
	handlers ...MessageHandler,
) (*message.Router, error) {
	watermillLogger := NewWatermillLogger(logger)

	// Create Redis client
	redisClient := redis.NewClient(&redis.Options{
		Addr:        config.RedisURL,
		Password:    config.RedisPassword,
		DB:          config.RedisDB,
		MaxRetries:  config.RedisMaxRetries,
		DialTimeout: config.RedisDialTimeout,
	})

	// Test Redis connection
	if err := redisClient.Ping(ctx).Err(); err != nil {
		return nil, errors.Wrap(err, "failed to connect to Redis")
	}

	// Create Redis subscriber
	subscriber, err := redisstream.NewSubscriber(
		redisstream.SubscriberConfig{
			Client:          redisClient,
			Unmarshaller:    CustomEventUnmarshaller{},
			ConsumerGroup:   config.ConsumerGroup,
			Consumer:        config.ConsumerName,
			BlockTime:       config.BlockTime,
			MaxIdleTime:     config.MaxIdleTime,
			NackResendSleep: config.NackResendSleep,
		},
		watermillLogger,
	)
	if err != nil {
		return nil, errors.Wrap(err, "failed to create Redis subscriber")
	}

	// Create router
	router, err := message.NewRouter(message.RouterConfig{
		CloseTimeout: time.Second * 30,
	}, watermillLogger)
	if err != nil {
		return nil, errors.Wrap(err, "failed to create message router")
	}

	// Add router plugins and middlewares
	router.AddPlugin(plugin.SignalsHandler)
	router.AddMiddleware(middleware.Recoverer)
	router.AddMiddleware(middleware.CorrelationID)
	router.AddMiddleware(middleware.Timeout(config.AckWait))

	// Register all handlers to the same Redis Stream topic
	for i, handler := range handlers {
		handlerIndex := i // Capture for closure
		handlerFunc := handler

		router.AddHandler(
			// Handler name must be unique
			watermill.NewUUID(),
			// Topic to subscribe
			config.StreamName,
			// Subscriber
			subscriber,
			// No publishing needed, just consume
			"",
			nil,
			// Message handler function
			func(msg *message.Message) ([]*message.Message, error) {
				// This handler function adapts the MessageHandler signature to Watermill's expected format
				err := handlerFunc(msg)
				if err != nil {
					logger.Error().
						Err(err).
						Int("handler_index", handlerIndex).
						Str("message_uuid", msg.UUID).
						Msg("Handler returned error, will NACK message")
					return nil, err // NACK
				}
				// No outgoing messages, just ACK
				return nil, nil
			},
		)
	}

	return router, nil
}
