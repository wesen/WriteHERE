package server

import (
	"context"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/rs/zerolog"
)

const (
	// Time allowed to write a message to the peer.
	writeWait = 10 * time.Second

	// Time allowed to read the next pong message from the peer.
	pongWait = 60 * time.Second

	// Send pings to peer with this period. Must be less than pongWait.
	pingPeriod = (pongWait * 9) / 10

	// Maximum message size allowed from peer.
	maxMessageSize = 512 * 1024 // 512KB
)

// Client represents a WebSocket client connection
type Client struct {
	hub  *WSHub
	conn *websocket.Conn
	send chan []byte
	addr string
}

// WSHub maintains the set of active clients and broadcasts messages to them
type WSHub struct {
	// Registered clients
	clients map[*Client]bool

	// Inbound messages from clients (not currently used in our implementation)
	messages chan []byte

	// Register requests from clients
	register chan *Client

	// Unregister requests from clients
	unregister chan *Client

	// Broadcast messages to all clients
	broadcast chan []byte

	// Logger
	logger zerolog.Logger

	// Mutex for thread-safe access to clients map
	mutex sync.RWMutex

	// Context for managing shutdown
	ctx    context.Context
	cancel context.CancelFunc
}

// NewWSHub creates a new WebSocket hub
func NewWSHub(logger zerolog.Logger) *WSHub {
	ctx, cancel := context.WithCancel(context.Background())
	return &WSHub{
		clients:    make(map[*Client]bool),
		messages:   make(chan []byte),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		broadcast:  make(chan []byte, 256), // Buffered broadcast channel
		logger:     logger,
		mutex:      sync.RWMutex{},
		ctx:        ctx,
		cancel:     cancel,
	}
}

// Run starts the WebSocket hub and listens for context cancellation
func (h *WSHub) Run(parentCtx context.Context) error {
	h.logger.Info().Msg("Starting WebSocket hub")
	defer h.logger.Info().Msg("WebSocket hub stopped")

	// Link hub's context to the parent context
	go func() {
		<-parentCtx.Done()
		h.logger.Info().Msg("Parent context cancelled, stopping WebSocket hub")
		h.Stop() // Initiate hub shutdown when parent context is done
	}()

	for {
		select {
		case client := <-h.register:
			// Register new client
			h.mutex.Lock()
			if !h.isShuttingDown() {
				h.clients[client] = true
				h.logger.Debug().Str("addr", client.addr).Msg("Client connected")
			}
			h.mutex.Unlock()

		case client := <-h.unregister:
			// Unregister client
			h.mutex.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send) // Close the send channel *before* logging
				h.logger.Debug().Str("addr", client.addr).Msg("Client disconnected")
			}
			h.mutex.Unlock()

		case message := <-h.messages:
			// Handle inbound message from client (not used in current implementation)
			h.logger.Debug().Int("bytes", len(message)).Msg("Received message from client")

		case message := <-h.broadcast:
			// Broadcast message to all clients
			h.mutex.RLock()
			if h.isShuttingDown() {
				h.mutex.RUnlock()
				continue // Don't broadcast if shutting down
			}
			clientCount := 0
			for client := range h.clients {
				select {
				case client.send <- message:
					clientCount++
				default:
					// Client send buffer is full, assume it's dead or slow
					h.logger.Warn().Str("addr", client.addr).Msg("Client send buffer full, disconnecting")
					// Unregistering requires a write lock, so we do it outside the RLock
					go func(c *Client) {
						h.unregister <- c
					}(client)
				}
			}
			h.mutex.RUnlock()

			if clientCount > 0 {
				h.logger.Debug().
					Int("bytes", len(message)).
					Int("clients", clientCount).
					Msg("Broadcast message to clients")
			}

		case <-h.ctx.Done():
			// Shutdown initiated by Stop() or parent context cancellation
			h.logger.Info().Msg("WebSocket hub context done, shutting down")
			return nil // Exit the run loop
		}
	}
}

// Stop signals the hub to shut down gracefully
func (h *WSHub) Stop() {
	h.logger.Info().Msg("Stopping WebSocket hub")
	h.cancel() // Cancel the hub's context

	// Allow some time for Run loop to exit and connections to close
	time.Sleep(100 * time.Millisecond)

	h.mutex.Lock()
	defer h.mutex.Unlock()

	// Close remaining client connections explicitly
	for client := range h.clients {
		select {
		case <-client.send:
			// Channel already closed
		default:
			close(client.send)
		}
		client.conn.Close() // Force close connection
		delete(h.clients, client)
	}

	h.logger.Info().Msg("WebSocket hub stop complete")
}

// isShuttingDown checks if the hub's context is cancelled
func (h *WSHub) isShuttingDown() bool {
	select {
	case <-h.ctx.Done():
		return true
	default:
		return false
	}
}

// readPump pumps messages from the WebSocket connection to the hub
func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadLimit(maxMessageSize)
	_ = c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		_ = c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	// We only read messages to handle pings and detect disconnection
	// We don't actually process messages from clients
	for {
		// Check if hub is shutting down
		if c.hub.isShuttingDown() {
			break
		}

		_, _, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err,
				websocket.CloseGoingAway,
				websocket.CloseAbnormalClosure) {
				c.hub.logger.Warn().
					Str("addr", c.addr).
					Err(err).
					Msg("WebSocket read error")
			}
			break
		}
	}
}

// writePump pumps messages from the hub to the WebSocket connection
func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			_ = c.conn.SetWriteDeadline(time.Now().Add(writeWait))

			if !ok {
				// The hub closed the channel
				_ = c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}

			_, _ = w.Write(message)

			// Add queued messages to the current WebSocket message
			n := len(c.send)
			for i := 0; i < n; i++ {
				_, _ = w.Write(<-c.send)
			}

			if err := w.Close(); err != nil {
				return
			}

		case <-ticker.C:
			_ = c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		// Also check hub context here to exit pump if hub is shutting down
		case <-c.hub.ctx.Done():
			return
		}
	}
}
