package websocket

import (
	"context"
	"encoding/json"
	"net/http"
	"sync"
	"time"

	"writehere-go/internal/models"
	"writehere-go/pkg/log"

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
	maxMessageSize = 512
)

// Client is a middleman between the websocket connection and the hub.
type Client struct {
	hub *Hub
	// The websocket connection.
	conn *websocket.Conn
	// Buffered channel of outbound messages.
	send chan []byte
	// Set of task IDs this client is subscribed to.
	subscriptions map[string]bool
	mu            sync.RWMutex
}

// Message defines the structure for messages sent over WebSocket.
type Message struct {
	Type    string      `json:"type"`
	Payload interface{} `json:"payload"`
}

// SubscriptionRequest is the payload for a 'subscribe' message.
type SubscriptionRequest struct {
	TaskID string `json:"taskId"`
}

// readPump pumps messages from the websocket connection to the hub.
func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
		log.Log.Info().Msg("WebSocket client disconnected and unregistered")
	}()
	c.conn.SetReadLimit(maxMessageSize)
	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})
	for {
		_, messageBytes, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Log.Error().Err(err).Msg("WebSocket unexpected close error")
			} else {
				log.Log.Info().Err(err).Msg("WebSocket closed")
			}
			break
		}

		var msg Message
		if err := json.Unmarshal(messageBytes, &msg); err != nil {
			log.Log.Error().Err(err).Bytes("message", messageBytes).Msg("Failed to unmarshal WebSocket message")
			continue
		}

		log.Log.Debug().Str("type", msg.Type).Interface("payload", msg.Payload).Msg("Received WebSocket message")

		switch msg.Type {
		case "subscribe":
			// Re-marshal payload to get SubscriptionRequest struct
			payloadBytes, _ := json.Marshal(msg.Payload)
			var subReq SubscriptionRequest
			if err := json.Unmarshal(payloadBytes, &subReq); err != nil {
				log.Log.Error().Err(err).Msg("Failed to unmarshal subscribe payload")
				// TODO: Send error message back to client?
				continue
			}
			if subReq.TaskID != "" {
				c.Subscribe(subReq.TaskID)
				// Send confirmation back
				confirmMsg := Message{
					Type: "subscription_status",
					Payload: map[string]interface{}{
						"taskId": subReq.TaskID,
						"status": "subscribed",
					},
				}
				confirmBytes, _ := json.Marshal(confirmMsg)
				c.send <- confirmBytes
				log.Log.Info().Str("clientId", c.conn.RemoteAddr().String()).Str("taskId", subReq.TaskID).Msg("Client subscribed to task")
				// Trigger sending initial data if available (or let the manager handle it)
				c.hub.TaskManager.SendInitialData(c.hub.ctx, subReq.TaskID, c)
			} else {
				log.Log.Warn().Msg("Received subscribe message with empty taskId")
			}
		// Add other message types here (e.g., unsubscribe)
		default:
			log.Log.Warn().Str("type", msg.Type).Msg("Received unknown WebSocket message type")
		}
	}
}

// writePump pumps messages from the hub to the websocket connection.
func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()
	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				// The hub closed the channel.
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				log.Log.Info().Msg("Hub closed client send channel")
				return
			}

			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				log.Log.Error().Err(err).Msg("Failed to get next writer")
				return
			}
			_, err = w.Write(message)
			if err != nil {
				log.Log.Error().Err(err).Msg("Failed to write message to WebSocket")
				// Attempt to close the writer even if write failed
				if closeErr := w.Close(); closeErr != nil {
					log.Log.Error().Err(closeErr).Msg("Failed to close writer after write error")
				}
				return // Exit writePump on write error
			}

			// Log the sent message (optional, can be verbose)
			// log.Log.Debug().Bytes("message", message).Msg("Sent WebSocket message")

			// Add queued chat messages to the current websocket message.
			n := len(c.send)
			for i := 0; i < n; i++ {
				_, err = w.Write(<-c.send)
				if err != nil {
					log.Log.Error().Err(err).Msg("Failed to write queued message to WebSocket")
					// Attempt to close the writer even if write failed
					if closeErr := w.Close(); closeErr != nil {
						log.Log.Error().Err(closeErr).Msg("Failed to close writer after queued write error")
					}
					return // Exit writePump on write error
				}
			}

			if err := w.Close(); err != nil {
				log.Log.Error().Err(err).Msg("Failed to close WebSocket writer")
				return
			}
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				log.Log.Error().Err(err).Msg("Failed to write ping message")
				return
			}
		case <-c.hub.ctx.Done(): // Check for hub shutdown
			log.Log.Info().Msg("Hub context done, closing client write pump")
			return
		}
	}
}

// Subscribe adds a task ID to the client's subscriptions.
func (c *Client) Subscribe(taskID string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.subscriptions == nil {
		c.subscriptions = make(map[string]bool)
	}
	c.subscriptions[taskID] = true
}

// Unsubscribe removes a task ID from the client's subscriptions.
func (c *Client) Unsubscribe(taskID string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.subscriptions != nil {
		delete(c.subscriptions, taskID)
	}
}

// IsSubscribed checks if the client is subscribed to a specific task ID.
func (c *Client) IsSubscribed(taskID string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.subscriptions == nil {
		return false
	}
	_, exists := c.subscriptions[taskID]
	return exists
}

// SendMessage sends a marshalled message to the client's send channel.
func (c *Client) SendMessage(messageType string, payload interface{}) {
	msg := Message{
		Type:    messageType,
		Payload: payload,
	}
	bytes, err := json.Marshal(msg)
	if err != nil {
		log.Log.Error().Err(err).Str("type", messageType).Msg("Failed to marshal message for client")
		return
	}

	// Use a select with a timeout to avoid blocking indefinitely if the send channel is full
	// (which might happen if the client is slow or disconnected)
	// Also check if the hub is shutting down.
	select {
	case c.send <- bytes:
	case <-time.After(1 * time.Second):
		log.Log.Warn().Str("clientId", c.conn.RemoteAddr().String()).Msg("Failed to send message to client: send channel full or blocked")
	case <-c.hub.ctx.Done():
		log.Log.Info().Str("clientId", c.conn.RemoteAddr().String()).Msg("Hub context done, aborting SendMessage")
	}
}

// SendInitialConnectionTest sends the connection test message.
func (c *Client) SendInitialConnectionTest() {
	c.SendMessage("connection_test", map[string]string{"message": "Server connected"})
}

// SendTaskUpdate sends a task update message to the client.
func (c *Client) SendTaskUpdate(task *models.Task) {
	if task == nil {
		return
	}
	payload := map[string]interface{}{
		"taskId":    task.ID,
		"status":    task.Status,
		"taskGraph": task.MockGraph,
		"error":     task.Error,
		// Add other relevant fields like progress if needed
	}
	c.SendMessage("task_update", payload)
}

// Hub maintains the set of active clients and broadcasts messages.
type Hub struct {
	// Registered clients.
	clients map[*Client]bool
	// Inbound messages from the clients.
	// broadcast chan []byte // We broadcast based on subscription now
	// Register requests from the clients.
	register chan *Client
	// Unregister requests from clients.
	unregister chan *Client
	// Task manager for accessing task data.
	TaskManager TaskManager // Use interface
	// Logger
	log zerolog.Logger
	// Context for managing the Hub's lifecycle.
	ctx context.Context

	mu sync.RWMutex
}

// TaskManager defines the interface for managing tasks (mock or real).
type TaskManager interface {
	GetTask(id string) (*models.Task, bool)
	SendInitialData(ctx context.Context, taskID string, client *Client)
}

func NewHub(ctx context.Context, taskManager TaskManager) *Hub {
	if ctx == nil {
		ctx = context.Background() // Fallback to background context
	}
	return &Hub{
		register:    make(chan *Client),
		unregister:  make(chan *Client),
		clients:     make(map[*Client]bool),
		TaskManager: taskManager,
		log:         log.Log.With().Str("component", "WebSocketHub").Logger(),
		ctx:         ctx,
	}
}

func (h *Hub) Run() error {
	h.log.Info().Msg("WebSocket Hub started")
	defer h.log.Info().Msg("WebSocket Hub stopped")
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			h.log.Info().Str("remoteAddr", client.conn.RemoteAddr().String()).Msg("Client registered")
			// Send initial connection test message
			client.SendInitialConnectionTest()
		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
				h.log.Info().Str("remoteAddr", client.conn.RemoteAddr().String()).Msg("Client unregistered")
			}
			h.mu.Unlock()
		case <-h.ctx.Done():
			h.log.Info().Msg("Hub context cancelled, shutting down WebSocket Hub")
			// Close all client connections gracefully?
			h.mu.Lock()
			for client := range h.clients {
				close(client.send) // Signal writePump to close connection
				delete(h.clients, client)
			}
			h.mu.Unlock()
			return h.ctx.Err() // Return the context error (e.g., context.Canceled)
		}
	}
}

// BroadcastTaskUpdate sends a task update message to all subscribed clients.
func (h *Hub) BroadcastTaskUpdate(task *models.Task) {
	if task == nil {
		return
	}
	h.log.Debug().Str("taskId", task.ID).Str("status", string(task.Status)).Msg("Broadcasting task update")
	payload := map[string]interface{}{
		"taskId":    task.ID,
		"status":    task.Status,
		"taskGraph": task.MockGraph,
		"error":     task.Error,
		// Add other relevant fields like progress, elapsedTime?
	}
	msg := Message{
		Type:    "task_update",
		Payload: payload,
	}
	messageBytes, err := json.Marshal(msg)
	if err != nil {
		h.log.Error().Err(err).Str("taskId", task.ID).Msg("Failed to marshal task update message")
		return
	}

	h.mu.RLock()
	defer h.mu.RUnlock()

	// Check if hub is shutting down before iterating
	if h.ctx.Err() != nil {
		h.log.Warn().Str("taskId", task.ID).Msg("Hub shutting down, skipping BroadcastTaskUpdate")
		return
	}

	for client := range h.clients {
		if client.IsSubscribed(task.ID) {
			select {
			case client.send <- messageBytes:
				h.log.Debug().Str("taskId", task.ID).Str("client", client.conn.RemoteAddr().String()).Msg("Sent task update to subscribed client")
			default:
				// Assume client is slow/gone, let the read/write pumps handle cleanup
				h.log.Warn().Str("taskId", task.ID).Str("client", client.conn.RemoteAddr().String()).Msg("Failed to send task update to client: channel full")
			}
		}
	}
}

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	// Allow all origins for now - adjust in production!
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

// ServeWs handles websocket requests from the peer.
func ServeWs(hub *Hub, w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Log.Error().Err(err).Msg("Failed to upgrade WebSocket connection")
		return
	}
	log.Log.Info().Str("remoteAddr", conn.RemoteAddr().String()).Msg("WebSocket connection established")
	client := &Client{
		hub:           hub,
		conn:          conn,
		send:          make(chan []byte, 256),
		subscriptions: make(map[string]bool),
	}
	client.hub.register <- client

	// Allow collection of memory referenced by the caller by doing all work in
	// new goroutines.
	go client.writePump()
	go client.readPump()
}
