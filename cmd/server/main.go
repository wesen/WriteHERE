package main

import (
	"context"
	"encoding/json"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/pkg/errors"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
	"golang.org/x/sync/errgroup"

	"writehere-go/internal/db"
	"writehere-go/internal/redis"
	"writehere-go/internal/server"
	"writehere-go/internal/state"
	"writehere-go/pkg/model"
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

	// HTTP server options
	httpListenAddr string
	staticFilesDir string
	reloadSession  bool

	// State manager options
	maxEventHistorySize int

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

	// Add flags for HTTP server
	rootCmd.Flags().StringVar(&httpListenAddr, "http-listen-addr", ":9999", "HTTP server listen address")
	rootCmd.Flags().StringVar(&staticFilesDir, "static-files-dir", "./ui-react/dist", "Path to static UI files")
	rootCmd.Flags().BoolVar(&reloadSession, "reload-session", false, "Reload state from the latest session in the database")

	// Add flags for state managers
	rootCmd.Flags().IntVar(&maxEventHistorySize, "max-event-history", 1000, "Maximum number of events to keep in memory")

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
		Str("http_listen_addr", httpListenAddr).
		Str("log_level", logLevel).
		Bool("reload_session", reloadSession).
		Msg("Starting WriteHERE server")

	// Setup graceful shutdown context
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Setup signal handling
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		sig := <-signals
		logger.Info().Str("signal", sig.String()).Msg("Received shutdown signal, cancelling context")
		cancel()
	}()

	// Initialize database manager
	dbManager, err := db.NewDatabaseManager(dbPath)
	if err != nil {
		return errors.Wrap(err, "failed to initialize database manager")
	}
	defer dbManager.Close()

	// Initialize state managers
	eventManager := state.NewEventManager(logger, maxEventHistorySize)
	graphManager := state.NewGraphManager(logger)

	// If reload_session is enabled, load state from the database
	if reloadSession {
		logger.Info().Msg("Reloading latest session from database...")
		// Load graph state first (nodes and edges)
		graphData, err := dbManager.GetLatestRunGraph(ctx)
		if err != nil {
			logger.Warn().Err(err).Msg("Failed to load graph state from database")
		} else {
			// Convert DB nodes/edges to state manager format
			graphNodes := make([]state.GraphNode, 0, len(graphData.Nodes))
			graphEdges := make([]state.GraphEdge, 0, len(graphData.Edges))

			// Convert nodes
			for nodeID, nodeJSON := range graphData.Nodes {
				var node struct {
					ID          string          `json:"id"`
					NID         string          `json:"nid"`
					Type        string          `json:"type"`
					TaskType    string          `json:"task_type"`
					Goal        string          `json:"goal"`
					Status      string          `json:"status"`
					Layer       int             `json:"layer"`
					OuterNodeID string          `json:"outer_node_id"`
					RootNodeID  string          `json:"root_node_id"`
					Result      json.RawMessage `json:"result"`
					Metadata    json.RawMessage `json:"metadata"`
				}
				if err := json.Unmarshal(nodeJSON, &node); err != nil {
					logger.Warn().Err(err).Str("node_id", nodeID).Msg("Failed to unmarshal node JSON")
					continue
				}
				graphNodes = append(graphNodes, state.GraphNode{
					NodeID:      node.ID,
					NodeNID:     node.NID,
					NodeType:    node.Type,
					TaskType:    node.TaskType,
					TaskGoal:    node.Goal,
					Status:      node.Status,
					Layer:       node.Layer,
					OuterNodeID: node.OuterNodeID,
					RootNodeID:  node.RootNodeID,
					Result:      node.Result,
					Metadata:    node.Metadata,
				})
			}

			// Convert edges
			for _, edgeJSON := range graphData.Edges {
				var edge struct {
					ID        string          `json:"id"`
					ParentID  string          `json:"parent_id"`
					ChildID   string          `json:"child_id"`
					ParentNID string          `json:"parent_nid"`
					ChildNID  string          `json:"child_nid"`
					Metadata  json.RawMessage `json:"metadata"`
				}
				if err := json.Unmarshal(edgeJSON, &edge); err != nil {
					logger.Warn().Err(err).Msg("Failed to unmarshal edge JSON")
					continue
				}
				graphEdges = append(graphEdges, state.GraphEdge{
					ID:           edge.ID,
					ParentNodeID: edge.ParentID,
					ChildNodeID:  edge.ChildID,
					ParentNID:    edge.ParentNID,
					ChildNID:     edge.ChildNID,
					Metadata:     edge.Metadata,
				})
			}

			// Load state
			graphManager.LoadStateFromDB(graphNodes, graphEdges)
		}

		// Load events
		eventData, err := dbManager.GetLatestRunEvents(ctx)
		if err != nil {
			logger.Warn().Err(err).Msg("Failed to load events from database")
		} else {
			// Convert DB events to model.Event objects
			events := make([]model.Event, 0, len(eventData.Events))
			for _, eventJSON := range eventData.Events {
				var event model.Event
				if err := json.Unmarshal(eventJSON, &event); err != nil {
					logger.Warn().Err(err).Msg("Failed to unmarshal event JSON")
					continue
				}
				events = append(events, event)
			}
			eventManager.LoadStateFromDB(events)
		}
	}

	// Setup HTTP server configuration
	httpConfig := server.DefaultHTTPServerConfig()
	httpConfig.ListenAddr = httpListenAddr
	httpConfig.StaticFilesDir = staticFilesDir
	httpConfig.ReloadSession = reloadSession

	// Initialize HTTP server
	httpServer := server.NewHTTPServer(httpConfig, logger, eventManager, graphManager)

	// Create a custom message handler that updates state managers and broadcasts to WebSocket clients
	messageHandler := func(msg *message.Message) error {
		// Pass to the DB manager for storage
		if err := dbManager.HandleMessage(msg); err != nil {
			return err // NACK if DB storage fails
		}

		// Parse the event from the message payload
		var event model.Event
		if err := json.Unmarshal(msg.Payload, &event); err != nil {
			// Log error but ACK, as DB storage succeeded
			logger.Error().Err(err).Str("message_uuid", msg.UUID).Msg("Failed to unmarshal event for state update, but DB storage succeeded. ACKing message.")
			return nil
		}

		// Update in-memory state with the parsed event
		eventManager.AddEvent(event)
		graphManager.ProcessEvent(event)

		// Broadcast the raw event to WebSocket clients
		httpServer.BroadcastEvent(msg.Payload)

		return nil // ACK
	}

	// Setup Redis router configuration
	routerConfig := redis.DefaultRouterConfig()
	routerConfig.RedisURL = redisURL
	routerConfig.RedisPassword = redisPassword
	routerConfig.RedisDB = redisDB
	routerConfig.RedisMaxRetries = redisMaxRetries
	routerConfig.RedisDialTimeout = redisDialTimeout
	routerConfig.StreamName = streamName
	routerConfig.ConsumerGroup = consumerGroup
	routerConfig.ConsumerName = consumerName
	routerConfig.ClaimMinIdleTime = claimMinIdleTime
	routerConfig.BlockTime = blockTime
	routerConfig.MaxIdleTime = maxIdleTime
	routerConfig.NackResendSleep = nackResendSleep
	routerConfig.CommitOffsetAfter = commitOffsetAfter
	routerConfig.AckWait = ackWait

	// Create the Redis router
	router, err := redis.NewRouter(
		ctx,
		routerConfig,
		logger,
		messageHandler, // Pass the combined handler
	)
	if err != nil {
		return errors.Wrap(err, "failed to create Redis router")
	}

	// Use errgroup to manage the main goroutines
	g, gCtx := errgroup.WithContext(ctx)

	// Start the HTTP server (which includes the WebSocket hub)
	httpServer.Start(g, gCtx)

	// Start the Redis router
	g.Go(func() error {
		logger.Info().Msg("Starting Redis router")
		err := router.Run(gCtx)
		if err != nil {
			logger.Error().Err(err).Msg("Redis router run failed")
		}
		return err // Return the error to the errgroup
	})

	// Wait for the first error or context cancellation
	if err := g.Wait(); err != nil {
		logger.Error().Err(err).Msg("Server encountered an error")
	}

	// Context was cancelled (either by signal or error in a goroutine)
	logger.Info().Msg("Server shutting down...")

	// Close the router explicitly (gives Watermill time to finish processing)
	// HTTP server shutdown is handled by its own goroutine within httpServer.Start
	if err := router.Close(); err != nil {
		logger.Error().Err(err).Msg("Failed to close router gracefully")
	} else {
		logger.Info().Msg("Router closed gracefully")
	}

	logger.Info().Msg("Server shut down complete.")
	return err // Return the error that caused the shutdown, or nil if shutdown was graceful
}
