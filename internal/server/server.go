package server

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"

	"writehere-go/internal/api"
	"writehere-go/internal/models"
	"writehere-go/internal/task"
	"writehere-go/internal/websocket"
	"writehere-go/pkg/log"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"golang.org/x/sync/errgroup"
)

// Config holds the server configuration.
type Config struct {
	Port     int
	LogLevel string
}

// Run sets up and starts the backend server, managing its lifecycle with the provided context.
func Run(ctx context.Context, cfg Config) error {
	log.Log.Info().Int("port", cfg.Port).Msg("Starting backend server")

	// Set Gin mode based on log level (optional)
	if cfg.LogLevel != "debug" {
		gin.SetMode(gin.ReleaseMode)
	} else {
		gin.SetMode(gin.DebugMode)
	}

	// Use errgroup for managing concurrent operations
	eg, groupCtx := errgroup.WithContext(ctx)

	// Initialize components
	taskStore := models.NewTaskStore()
	// Pass the group context to the Hub
	wsHub := websocket.NewHub(groupCtx, nil) // Hub needs task manager
	taskManager := task.NewMockTaskManager(taskStore, wsHub)
	wsHub.TaskManager = taskManager // Assign task manager to hub (must implement new interface)
	apiHandler := api.NewAPI(taskManager, taskStore, wsHub)

	// Start WebSocket Hub in a managed goroutine
	eg.Go(func() error {
		return wsHub.Run()
	})

	// Setup Gin router
	router := gin.New()

	// Middleware
	router.Use(gin.Recovery())         // Recover from panics
	router.Use(GinZerologMiddleware()) // Custom logger middleware using Zerolog
	// CORS configuration - adjust allowed origins in production
	router.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"http://localhost:3000", "*"}, // Allow dev frontend and potentially others
		AllowMethods:     []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Accept", "Authorization"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	// Register API routes
	apiHandler.RegisterRoutes(router)

	// Setup HTTP server
	srv := &http.Server{
		Addr:    fmt.Sprintf(":%d", cfg.Port),
		Handler: router,
		// Add timeouts for production hardening
		// ReadTimeout:  5 * time.Second,
		// WriteTimeout: 10 * time.Second,
		// IdleTimeout:  120 * time.Second,
	}

	// Start HTTP server listener in a managed goroutine
	eg.Go(func() error {
		log.Log.Info().Msgf("Server listening on %s", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Log.Error().Err(err).Msg("HTTP server ListenAndServe error")
			return fmt.Errorf("http server listen and serve: %w", err)
		}
		log.Log.Info().Msg("HTTP server listener stopped")
		return nil
	})

	// Goroutine to handle graceful shutdown of the HTTP server
	eg.Go(func() error {
		<-groupCtx.Done() // Wait for context cancellation (from main or other goroutine error)
		log.Log.Info().Msg("Shutdown signal received, attempting graceful HTTP server shutdown...")

		// Create a deadline for the shutdown
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		if err := srv.Shutdown(shutdownCtx); err != nil {
			log.Log.Error().Err(err).Msg("HTTP server graceful shutdown failed")
			return fmt.Errorf("http server shutdown: %w", err)
		}
		log.Log.Info().Msg("HTTP server gracefully stopped")
		return nil
	})

	// Wait for all goroutines in the group to complete
	if err := eg.Wait(); err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, http.ErrServerClosed) {
		log.Log.Error().Err(err).Msg("Error group encountered an error during shutdown")
		return err // Propagate error
	}

	log.Log.Info().Msg("Server exiting cleanly")
	return nil
}

// GinZerologMiddleware creates a Gin middleware for logging requests with Zerolog.
func GinZerologMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		rawQuery := c.Request.URL.RawQuery

		// Process request
		c.Next()

		// Log request details
		latency := time.Since(start)
		clientIP := c.ClientIP()
		method := c.Request.Method
		statusCode := c.Writer.Status()
		// errorMessage := c.Errors.ByType(gin.ErrorTypePrivate).String()
		bodySize := c.Writer.Size()

		logEvent := log.Log.Info()
		if statusCode >= 500 {
			logEvent = log.Log.Error() //.Str("errors", errorMessage)
		} else if statusCode >= 400 {
			logEvent = log.Log.Warn()
		}

		if rawQuery != "" {
			path = path + "?" + rawQuery
		}

		logEvent.Str("method", method).
			Str("path", path).
			Int("status", statusCode).
			Dur("latency", latency).
			Str("client_ip", clientIP).
			Int("body_size", bodySize).
			Msg("Request completed")
	}
}
