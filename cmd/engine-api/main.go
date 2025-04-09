package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"writehere-go/pkg/events"
	"writehere-go/pkg/scheduler"
	"writehere-go/pkg/state"
	"writehere-go/pkg/workers/execution"
	"writehere-go/pkg/workers/planning"

	"github.com/pkg/errors"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
	"golang.org/x/sync/errgroup"
)

var (
	port          int
	logLevel      string
	prettyLogging bool
)

func main() {
	rootCmd := &cobra.Command{
		Use:   "engine-api",
		Short: "WriteHERE Engine API Gateway",
		Long:  `API Gateway for the WriteHERE recursive engine using an event-driven architecture.`,
		RunE:  run,
	}

	// Define flags
	rootCmd.PersistentFlags().IntVarP(&port, "port", "p", 8080, "Port to run the API server on")
	rootCmd.PersistentFlags().StringVarP(&logLevel, "log-level", "l", "info", "Log level (debug, info, warn, error)")
	rootCmd.PersistentFlags().BoolVar(&prettyLogging, "pretty", false, "Enable pretty logging")

	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}

func run(cmd *cobra.Command, args []string) error {
	// Set up logging
	level, err := zerolog.ParseLevel(logLevel)
	if err != nil {
		return errors.Wrap(err, "invalid log level")
	}
	zerolog.SetGlobalLevel(level)

	if prettyLogging {
		log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr, TimeFormat: time.RFC3339})
	}

	// Create a cancellable context
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Set up signal handling
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigCh
		log.Info().Msg("Received shutdown signal")
		cancel()
	}()

	// Initialize the event bus
	eventBus, err := events.NewEventBus(ctx, log.Logger)
	if err != nil {
		return errors.Wrap(err, "failed to create event bus")
	}

	// Initialize the state store and service
	store := state.NewInMemoryStore()
	stateService, err := state.NewService(ctx, store, eventBus, log.Logger)
	if err != nil {
		return errors.Wrap(err, "failed to create state service")
	}

	// Initialize the Scheduler Service
	schedulerService := scheduler.NewService(eventBus, store)

	// Initialize Worker Services
	planningWorker := planning.NewService(eventBus, store)
	executionWorker := execution.NewService(eventBus, store)

	// Create HTTP server
	router := http.NewServeMux()

	// Task submission endpoint
	router.HandleFunc("/api/tasks", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var request struct {
			Goal     string                 `json:"goal"`
			TaskType string                 `json:"task_type"`
			Metadata map[string]interface{} `json:"metadata,omitempty"`
		}

		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		taskType := state.TaskType(request.TaskType)
		if taskType == "" {
			taskType = state.TaskTypeComposition
		}

		taskID, err := stateService.CreateRootTask(r.Context(), request.Goal, taskType, request.Metadata)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"task_id": taskID,
		})
	})

	// Task status endpoint
	router.HandleFunc("/api/tasks/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		taskID := r.URL.Path[len("/api/tasks/"):]
		if taskID == "" {
			http.Error(w, "Task ID required", http.StatusBadRequest)
			return
		}

		task, err := stateService.GetTask(r.Context(), taskID)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(task)
	})

	// Task tree endpoint (get all tasks in a tree)
	router.HandleFunc("/api/tasks/root/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		rootTaskID := r.URL.Path[len("/api/tasks/root/"):]
		if rootTaskID == "" {
			http.Error(w, "Root task ID required", http.StatusBadRequest)
			return
		}

		tasks, err := stateService.GetTasksByRoot(r.Context(), rootTaskID)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(tasks)
	})

	// Start the HTTP server
	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", port),
		Handler: router,
	}

	// Use errgroup to manage goroutines
	g, gCtx := errgroup.WithContext(ctx)

	// Start the State Service
	g.Go(func() error {
		return stateService.Start(gCtx)
	})

	// Start the Scheduler Service
	g.Go(func() error {
		return schedulerService.Start(gCtx)
	})

	// Start the Planning Worker Service
	g.Go(func() error {
		return planningWorker.Start(gCtx)
	})

	// Start the Execution Worker Service
	g.Go(func() error {
		return executionWorker.Start(gCtx)
	})

	// Start the HTTP server
	g.Go(func() error {
		log.Info().Int("port", port).Msg("Starting API server")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			return errors.Wrap(err, "server error")
		}
		return nil
	})

	// Handle server shutdown
	g.Go(func() error {
		<-gCtx.Done()
		log.Info().Msg("Shutting down server")

		shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer shutdownCancel()

		return server.Shutdown(shutdownCtx)
	})

	// Wait for all goroutines to complete
	if err := g.Wait(); err != nil {
		if !errors.Is(err, context.Canceled) {
			log.Error().Err(err).Msg("Error during service execution or shutdown")
			return errors.Wrap(err, "service error")
		}
		log.Info().Msg("Services shut down due to context cancellation")
	}

	log.Info().Msg("Application shut down gracefully")
	return nil
}
