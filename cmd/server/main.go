package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/pkg/errors"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"

	"writehere-go/internal/db"
	"writehere-go/internal/redis"
)

var (
	// Redis connection options
	redisURL         string
	redisPassword    string
	redisDB          int
	redisMaxRetries  int
	redisDialTimeout time.Duration

	// Stream subscription options
	streamName        string
	consumerGroup     string
	consumerName      string
	claimMinIdleTime  time.Duration
	blockTime         time.Duration
	maxIdleTime       time.Duration
	nackResendSleep   time.Duration
	commitOffsetAfter time.Duration
	ackWait           time.Duration

	// Database options
	dbPath string

	// Logging options
	logLevel string
)

func main() {
	rootCmd := &cobra.Command{
		Use:   "server",
		Short: "WriteHERE server with database manager",
		Long:  `A server that handles WriteHERE events and stores them in a SQLite database.`,
		RunE:  runServer,
	}

	// Add flags for Redis connection
	rootCmd.Flags().StringVar(&redisURL, "redis-url", "localhost:6379", "Redis server URL")
	rootCmd.Flags().StringVar(&redisPassword, "redis-password", "", "Redis server password")
	rootCmd.Flags().IntVar(&redisDB, "redis-db", 0, "Redis database number")
	rootCmd.Flags().IntVar(&redisMaxRetries, "redis-max-retries", 3, "Maximum number of Redis connection retries")
	rootCmd.Flags().DurationVar(&redisDialTimeout, "redis-dial-timeout", 5*time.Second, "Redis connection timeout")

	// Add flags for stream configuration
	rootCmd.Flags().StringVar(&streamName, "stream-name", "agent_events", "Redis stream name to subscribe to")
	rootCmd.Flags().StringVar(&consumerGroup, "consumer-group", "go_server_group", "Redis consumer group name")
	rootCmd.Flags().StringVar(&consumerName, "consumer-name", "go_server_consumer", "Redis consumer name")
	rootCmd.Flags().DurationVar(&claimMinIdleTime, "claim-min-idle-time", time.Minute, "Minimum idle time before claiming messages")
	rootCmd.Flags().DurationVar(&blockTime, "block-time", time.Second, "Block time for Redis XREADGROUP")
	rootCmd.Flags().DurationVar(&maxIdleTime, "max-idle-time", 5*time.Minute, "Maximum idle time for consumer")
	rootCmd.Flags().DurationVar(&nackResendSleep, "nack-resend-sleep", 2*time.Second, "Sleep time before retrying NACK'd message")
	rootCmd.Flags().DurationVar(&commitOffsetAfter, "commit-offset-after", 10*time.Second, "Interval between committing offsets")
	rootCmd.Flags().DurationVar(&ackWait, "ack-wait", 30*time.Second, "Time to wait for ACK before timing out")

	// Add flag for database path
	rootCmd.Flags().StringVar(&dbPath, "db-path", "./writehere.db", "Path to SQLite database file")

	// Add flag for log level
	rootCmd.Flags().StringVar(&logLevel, "log-level", "info", "Log level (trace, debug, info, warn, error, fatal, panic)")

	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func runServer(cmd *cobra.Command, args []string) error {
	// Setup logger with level from flag
	level, err := zerolog.ParseLevel(logLevel)
	if err != nil {
		return errors.Wrap(err, "invalid log level")
	}
	zerolog.SetGlobalLevel(level)

	// Setup pretty console logging
	consoleWriter := zerolog.ConsoleWriter{Out: os.Stdout, TimeFormat: "2006-01-02 15:04:05"}
	logger := zerolog.New(consoleWriter).With().Timestamp().Caller().Logger()
	log.Logger = logger

	logger.Info().
		Str("redis_url", redisURL).
		Str("db_path", dbPath).
		Str("log_level", logLevel).
		Str("stream_name", streamName).
		Str("consumer_group", consumerGroup).
		Str("consumer_name", consumerName).
		Msg("Starting WriteHERE server")

	// Initialize database manager
	dbManager, err := db.NewDatabaseManager(dbPath)
	if err != nil {
		return errors.Wrap(err, "failed to initialize database manager")
	}
	defer dbManager.Close()

	// Setup Redis router configuration
	routerConfig := redis.DefaultRouterConfig()

	// Redis connection options
	routerConfig.RedisURL = redisURL
	routerConfig.RedisPassword = redisPassword
	routerConfig.RedisDB = redisDB
	routerConfig.RedisMaxRetries = redisMaxRetries
	routerConfig.RedisDialTimeout = redisDialTimeout

	// Stream subscription options
	routerConfig.StreamName = streamName
	routerConfig.ConsumerGroup = consumerGroup
	routerConfig.ConsumerName = consumerName
	routerConfig.ClaimMinIdleTime = claimMinIdleTime
	routerConfig.BlockTime = blockTime
	routerConfig.MaxIdleTime = maxIdleTime
	routerConfig.NackResendSleep = nackResendSleep
	routerConfig.CommitOffsetAfter = commitOffsetAfter

	// Processing options
	routerConfig.AckWait = ackWait

	// Setup graceful shutdown context
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)

	// Create the router using the internal package with database manager handler
	router, err := redis.NewRouter(
		ctx,
		routerConfig,
		logger,
		dbManager.HandleMessage, // Use database manager as message handler
	)
	if err != nil {
		return errors.Wrap(err, "failed to create Redis router")
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

	logger.Info().Msg("Server shut down complete.")
	return nil
}
