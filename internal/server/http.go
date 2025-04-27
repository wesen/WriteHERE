package server

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"path"
	"time"

	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
	"github.com/rs/zerolog"
	"golang.org/x/sync/errgroup"

	"writehere-go/internal/state"
)

// HTTPServerConfig contains all configuration for the HTTP server
type HTTPServerConfig struct {
	ListenAddr     string
	StaticFilesDir string
	ReloadSession  bool
}

// DefaultHTTPServerConfig returns a config with sensible defaults
func DefaultHTTPServerConfig() HTTPServerConfig {
	return HTTPServerConfig{
		ListenAddr:     ":9999",
		StaticFilesDir: "./ui-react/dist",
		ReloadSession:  false,
	}
}

// HTTPServer encapsulates the HTTP/WebSocket server functionality
type HTTPServer struct {
	server       *http.Server
	router       *mux.Router
	wsHub        *WSHub
	logger       zerolog.Logger
	config       HTTPServerConfig
	eventManager *state.EventManager
	graphManager *state.GraphManager
}

// NewHTTPServer creates a new HTTP server with the given config
func NewHTTPServer(
	config HTTPServerConfig,
	logger zerolog.Logger,
	eventManager *state.EventManager,
	graphManager *state.GraphManager,
) *HTTPServer {
	router := mux.NewRouter()

	// Create the WebSocket hub
	hub := NewWSHub(logger.With().Str("component", "ws_hub").Logger())

	server := &http.Server{
		Addr:         config.ListenAddr,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	httpServer := &HTTPServer{
		server:       server,
		router:       router,
		wsHub:        hub,
		logger:       logger.With().Str("component", "http_server").Logger(),
		config:       config,
		eventManager: eventManager,
		graphManager: graphManager,
	}

	// Set up all routes
	httpServer.setupRoutes()

	return httpServer
}

// setupRoutes initializes all HTTP and WebSocket routes
func (s *HTTPServer) setupRoutes() {
	// API routes
	api := s.router.PathPrefix("/api").Subrouter()

	// GET /api/events
	api.HandleFunc("/events", s.handleGetEvents).Methods("GET")

	// GET /api/graph
	api.HandleFunc("/graph", s.handleGetGraph).Methods("GET")

	// GET /api/graph/nodes
	api.HandleFunc("/graph/nodes", s.handleGetNodes).Methods("GET")

	// GET /api/graph/nodes/{id}
	api.HandleFunc("/graph/nodes/{id}", s.handleGetNode).Methods("GET")

	// GET /api/graph/edges
	api.HandleFunc("/graph/edges", s.handleGetEdges).Methods("GET")

	// GET /api/graph/edges/{id}
	api.HandleFunc("/graph/edges/{id}", s.handleGetEdge).Methods("GET")

	// WebSocket endpoint
	s.router.HandleFunc("/ws/events", s.handleWebSocket)

	// Static file server
	// This needs to be last as it has a catch-all route
	s.setupStaticFileServer()
}

// setupStaticFileServer configures serving of static files
func (s *HTTPServer) setupStaticFileServer() {
	// Serve static files
	fs := http.FileServer(http.Dir(s.config.StaticFilesDir))

	// Custom file handler that falls back to index.html for SPA routing
	fileHandler := func(w http.ResponseWriter, r *http.Request) {
		// Try to serve the file directly
		filePath := path.Join(s.config.StaticFilesDir, r.URL.Path)
		_, err := os.Stat(filePath)

		if os.IsNotExist(err) {
			// File doesn't exist, serve index.html instead
			r.URL.Path = "/"
		}

		fs.ServeHTTP(w, r)
	}

	// Catch-all route for static files
	s.router.PathPrefix("/").Handler(http.HandlerFunc(fileHandler))
}

// Start launches the HTTP server and WebSocket hub using errgroup
func (s *HTTPServer) Start(g *errgroup.Group, ctx context.Context) {
	// Start the WebSocket hub
	g.Go(func() error {
		return s.wsHub.Run(ctx)
	})

	// Start the HTTP server
	g.Go(func() error {
		s.logger.Info().Str("addr", s.server.Addr).Msg("Starting HTTP server")
		if err := s.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			s.logger.Error().Err(err).Msg("HTTP server ListenAndServe error")
			return err
		}
		return nil
	})

	// Goroutine to handle graceful shutdown of HTTP server on context cancellation
	g.Go(func() error {
		<-ctx.Done()
		s.logger.Info().Msg("HTTP server context cancelled, initiating shutdown...")
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second) // Give 10 seconds for shutdown
		defer cancel()

		if err := s.server.Shutdown(shutdownCtx); err != nil {
			s.logger.Error().Err(err).Msg("HTTP server graceful shutdown failed")
			return err
		}
		s.logger.Info().Msg("HTTP server shutdown complete")
		return nil
	})
}

// API Handlers

// handleGetEvents returns all events from the EventManager
func (s *HTTPServer) handleGetEvents(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"status": "Connected",
		"events": s.eventManager.GetEvents(),
	}

	writeJSONResponse(w, response)
}

// handleGetGraph returns the complete graph from the GraphManager
func (s *HTTPServer) handleGetGraph(w http.ResponseWriter, r *http.Request) {
	nodes := s.graphManager.GetNodes()
	edges := s.graphManager.GetEdges()

	response := map[string]interface{}{
		"graph": map[string]interface{}{
			"nodes": nodes,
			"edges": edges,
		},
	}

	writeJSONResponse(w, response)
}

// handleGetNodes returns all nodes from the GraphManager
func (s *HTTPServer) handleGetNodes(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"nodes": s.graphManager.GetNodes(),
	}

	writeJSONResponse(w, response)
}

// handleGetNode returns a specific node by ID
func (s *HTTPServer) handleGetNode(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	nodeID := vars["id"]

	node, ok := s.graphManager.GetNode(nodeID)
	if !ok {
		http.Error(w, "Node not found", http.StatusNotFound)
		return
	}

	writeJSONResponse(w, node)
}

// handleGetEdges returns all edges from the GraphManager
func (s *HTTPServer) handleGetEdges(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"edges": s.graphManager.GetEdges(),
	}

	writeJSONResponse(w, response)
}

// handleGetEdge returns a specific edge by ID
func (s *HTTPServer) handleGetEdge(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	edgeID := vars["id"]

	edge, ok := s.graphManager.GetEdge(edgeID)
	if !ok {
		http.Error(w, "Edge not found", http.StatusNotFound)
		return
	}

	writeJSONResponse(w, edge)
}

// WebSocket configuration
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	// Allow all origins
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

// handleWebSocket upgrades HTTP connections to WebSocket
func (s *HTTPServer) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		s.logger.Error().Err(err).Msg("Failed to upgrade to WebSocket")
		return
	}

	// Create a new client and register it with the hub
	client := &Client{
		hub:  s.wsHub,
		conn: conn,
		send: make(chan []byte, 256),
		addr: conn.RemoteAddr().String(),
	}

	s.wsHub.register <- client

	// Start client read/write pumps
	go client.writePump()
	go client.readPump()

	// If reload session is enabled, send historical events
	if s.config.ReloadSession && len(s.eventManager.GetEvents()) > 0 {
		s.logger.Info().
			Int("event_count", len(s.eventManager.GetEvents())).
			Str("client_addr", conn.RemoteAddr().String()).
			Msg("Sending historical events to new client")

		// Send each historical event to the client
		for _, event := range s.eventManager.GetEvents() {
			// Marshal the event to JSON
			eventJSON, err := json.Marshal(event)
			if err != nil {
				s.logger.Error().Err(err).Msg("Failed to marshal historical event")
				continue
			}

			// Send to just this client, not via the hub broadcast
			client.send <- eventJSON
		}
	}
}

// BroadcastEvent sends an event to all connected WebSocket clients
func (s *HTTPServer) BroadcastEvent(eventJSON []byte) {
	// Use non-blocking send to avoid blocking the message handler if the hub is busy
	select {
	case s.wsHub.broadcast <- eventJSON:
	default:
		s.logger.Warn().Msg("WebSocket hub broadcast channel is full, dropping message")
	}
}

// Utility Functions

// writeJSONResponse writes a JSON response with the appropriate headers
func writeJSONResponse(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")

	err := json.NewEncoder(w).Encode(data)
	if err != nil {
		http.Error(w, "Error encoding JSON response", http.StatusInternalServerError)
	}
}
