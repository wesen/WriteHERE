# Go WebSocket Server Architecture PRD

## 1. Introduction

This document outlines the proposed architecture for the Go implementation of the Recursive Agent Event Logging WebSocket server. The goal is to create a high-performance, robust, and maintainable server that acts as a complete drop-in replacement for the existing Python implementation, adhering to the specifications defined in `01-ws-server-in-depth.md`.

## 2. Goals

- **Performance:** Leverage Go's concurrency model for efficient handling of Redis streams, WebSocket connections, and database operations.
- **Reliability:** Implement robust error handling, automatic reconnection (for Redis), and graceful shutdown.
- **Maintainability:** Utilize clear package structure, idiomatic Go practices, and structured logging.
- **Compatibility:** Ensure 100% compatibility with the existing database schema, API endpoints, WebSocket communication protocol, and configuration methods.
- **Observability:** Integrate structured logging (zerolog) for easier monitoring and debugging.
- **Decoupling:** Use Watermill as a message router to decouple event processing components.

## 3. Overall Architecture

The Go server will be a standalone application consisting of several key concurrent components managed via `context` and `errgroup`, utilizing Watermill for message routing:

```mermaid
graph TD
    subgraph Go WebSocket Server Process
        A[HTTP Server (net/http)] -- Serves --> F[Static UI Files]
        A -- Handles --> G[API Requests (/api/*)]
        A -- Upgrades --> B(WebSocket Hub)
        B -- Manages --> C(Client Connections)
        W[Watermill Router] -- Subscribes To --> E(Redis Stream: agent_events)
        W -- Routes Via Handler 1 --> H(Database Manager)
        W -- Routes Via Handler 2 --> I(State Managers)
        W -- Routes Via Handler 3 --> B
        H -- Writes/Reads --> J[(SQLite DB: events.db)]
        I -- Provides Data --> G
        I -- Provides Initial Data --> C
        B -- Broadcasts Events --> C
    end

    F <-- Served By --- A
    E <-- PubSub Subscriber --- W
    J <-- Accessed By --- H
```

**Key Components:**

- **Main Application (`cmd/server/main.go`):** Parses configuration (using Cobra/Viper), initializes components, sets up `context` and `errgroup` for lifecycle management, starts the Watermill router and HTTP server.
- **HTTP Server (`internal/server/http.go`):** Uses the standard `net/http` library. Handles:
    - Serving static React UI files.
    - Routing HTTP API requests (`/api/*`) to handlers.
    - Upgrading `/ws/events` connections to WebSocket using `gorilla/websocket`.
- **WebSocket Hub (`internal/ws/hub.go`):** Manages active WebSocket client connections. Responsible for:
    - Registering/unregistering clients.
    - Broadcasting events received from the Watermill handler to connected clients.
    - Handling client-specific logic (like sending historical data upon connection).
- **Watermill Message Router (`internal/redis/router.go`):** Manages the event flow:
    - Configures the Redis Stream PubSub subscriber, utilizing a custom unmarshaller to handle the specific JSON payload format sent by the Python publisher.
    - Registers independent handlers for different components (DB persist, state update, WS broadcast).
    - Provides message delivery guarantees (e.g., at-least-once) with acknowledgement/retry capabilities.
    - Handles graceful shutdown of message processing.
- **Database Manager (`internal/db/manager.go`):** Handles all interactions with the SQLite database. Responsible for:
    - Establishing and managing the DB connection.
    - Ensuring the schema exists on startup.
    - Storing incoming events through a Watermill handler that processes and acknowledges messages.
    - Providing methods to query historical data (e.g., latest run events, latest graph state).
    - Uses Go's `database/sql` package with a suitable SQLite driver (e.g., `mattn/go-sqlite3`).
- **State Managers (`internal/state/event_manager.go`, `internal/state/graph_manager.go`):** Maintain in-memory state mirroring the Python implementation. Responsible for:
    - Storing recent events (`EventManager`) and the current graph structure (`GraphManager`).
    - Providing thread-safe methods (using `sync.Mutex` or `sync.RWMutex`) to add/update/query state.
    - Loading initial state from the Database Manager if `reload_session` is enabled.
- **API Handlers (`internal/api/handlers.go`):** Implement the logic for the HTTP API endpoints, interacting with the State Managers.
- **Configuration (`pkg/config/config.go`):** Defines the `ServerConfig` struct and handles loading configuration from environment variables and potentially CLI flags (via Cobra/Viper).
- **Logging (`pkg/log/log.go`):** Centralized setup for structured logging using `zerolog`.

## 4. Data Flow (Event Processing with Watermill)

1.  **Agent:** An event occurs in the external agent process.
2.  **Event Bus (Python):** The Python `EventBus` publishes the **entire event object serialized as a JSON string** under the key **`json_payload`** within the Redis stream message.
3.  **Watermill Router (Go):** 
    - The Redis Stream PubSub subscribes to the stream and receives new messages.
    - **A custom Watermill unmarshaller** reads the `json_payload` field from the Redis message, extracts the JSON string, and constructs a Watermill message with this string as its payload.
    - The message router delivers the message to all registered handlers in parallel.
4.  **Handler Execution:**
    - **Database Handler:** Decodes the JSON payload (which represents the full event), persists the event to SQLite, and acknowledges the message.
    - **State Update Handler:** Decodes the JSON payload, updates in-memory state managers based on the event type/data, and acknowledges the message.
    - **WebSocket Broadcast Handler:** Gets the raw JSON payload, sends it to the WebSocket hub for broadcasting, and acknowledges the message.
5.  **WebSocket Hub:** Takes the raw JSON string from the broadcast handler and sends it to all connected clients.
6.  **UI:** The React UI receives the event JSON string, parses it, and updates its Redux store.

The key advantage is that each handler operates independently on the same original message, with its own acknowledgement control, eliminating the need for custom fan-out channels.

## 5. API Design

The Go server will implement the exact same API endpoints as the Python server:

- **WebSocket:**
    - `GET /ws/events`: Handles WebSocket connection upgrades. Sends historical data if `reload_session=true`, then streams live events.
- **HTTP:**
    - `GET /api/events`: Returns JSON `{ "status": "Connected", "events": [...] }` from `EventManager`.
    - `GET /api/graph`: Returns JSON `{ "graph": { "nodes": ..., "edges": ... } }` from `GraphManager`.
    - `GET /api/graph/nodes`: Returns JSON `{ "nodes": { "node_id": {...}, ...} }` from `GraphManager`.
    - `GET /api/graph/nodes/{id}`: Returns JSON node object or 404 from `GraphManager`.
    - `GET /api/graph/edges`: Returns JSON `{ "edges": { "edge_id": {...}, ...} }` from `GraphManager`.
    - `GET /api/graph/edges/{id}`: Returns JSON edge object or 404 from `GraphManager`.
    - `GET /{full_path:path}`: Serves static files from the configured React build directory. If a file isn't found, serves `index.html`.

## 6. Database Interaction

- The `DatabaseManager` will encapsulate all SQLite operations.
- It will use the `database/sql` package and `mattn/go-sqlite3` (or similar CGO-enabled driver).
- Connection management: A single connection pool managed by the `DatabaseManager`.
- Schema Initialization: On startup, `_ensure_db` logic will be replicated to create tables and indexes if they don't exist.
- Event Storage: The `StoreEvent` logic will be used in the Watermill handler function, handling the conditional logic based on `event_type` to update related tables.
- Data Retrieval: Methods like `GetLatestRunEvents` and `GetLatestRunGraph` will be implemented to fetch data for state reloading.
- Transactions: Use transactions where appropriate, especially when multiple tables are updated.
- Error Handling: Database errors will trigger message NACK in the Watermill handler, allowing built-in retry mechanisms to handle temporary failures.

## 7. Configuration Handling

- A `config.Config` struct will hold all configuration parameters.
- Configuration will be loaded primarily from environment variables (matching Python's `ServerConfig.from_env`).
- Additional Watermill-specific configuration will be added for Redis Stream consumer group, consumer name, etc.
- [Optional but Recommended] Use Cobra for defining CLI flags that can override environment variables.
- [Optional but Recommended] Use Viper to manage configuration loading from environment variables and flags.

## 8. State Management

- `EventManager` and `GraphManager` structs will reside in the `internal/state` package.
- They will hold the application's in-memory state (event list, nodes/edges maps).
- Data structures will mirror the Python implementation (e.g., using maps for `entities` and slices for `ids`).
- **Concurrency:** All methods that modify or read the internal state must be protected by `sync.Mutex` or `sync.RWMutex` to prevent race conditions, as they will be accessed concurrently by the Watermill handler (writes) and API Handlers (reads).
- State Reloading: On startup (if `reload_session=true`), the main application will call methods on the `DatabaseManager` to get historical data and then pass this data to `LoadStateFromDB` methods on the state managers.

## 9. Concurrency Model

- **`errgroup`:** The main application will use `golang.org/x/sync/errgroup` to manage the lifecycle of the primary goroutines (HTTP Server, Watermill Router, WebSocket Hub).
- **Goroutines:**
    - HTTP Server listener (`srv.ListenAndServe`)
    - HTTP Server graceful shutdown handler
    - Watermill Router (`router.Run`) - manages its own goroutines for handlers
    - WebSocket Hub (`hub.Run`)
    - WebSocket client read/write pumps (one pair per client)
- **Watermill Router:** Eliminates the need for many custom channels by:
    - Managing its own handler goroutines
    - Providing built-in acknowledgement, retry, and backpressure mechanisms
    - Allowing different components to independently process the same message
- **`sync.Mutex` / `sync.RWMutex`:** Used within state managers and WebSocket Hub to protect shared data structures.
- **`context.Context`:** Passed down from the main application to manage cancellation and timeouts, ensuring graceful shutdown of all components including the Watermill router.

## 10. Error Handling

- **Structured Logging:** All errors will be logged using `zerolog` with relevant context (component, function, error details).
- **Watermill Error Handling:**
    - Handlers return errors to indicate message handling status (nil for success, error for failure).
    - Failed messages can be retried with customizable policies.
    - Dead-letter queues can be configured for messages that repeatedly fail.
- **`errgroup`:** Errors returned by the main component goroutines will cause the `errgroup`'s context to be canceled, initiating a graceful shutdown.
- **Component-Level:**
    - **Database Handler:** Return error for NACK, leading to retry. Use transactions and commit/rollback appropriately.
    - **WebSocket Hub:** Handle client connection errors by unregistering the client. Log broadcast errors.
    - **HTTP Server:** Standard HTTP error responses (e.g., 404, 500) with logged details.
- **Error Wrapping:** Use `fmt.Errorf` with `%w` or `github.com/pkg/errors` for wrapping errors to preserve context.

## 11. Event Message Format and Processing

### Redis Stream Message Format

The Redis Stream messages published by the Python `EventBus` have a specific format that requires special handling in the Go service. Based on examination of actual messages, the Python publisher uses the following pattern:

```
XADD agent_events * json_payload "{ complete JSON serialized event object }"
```

The key aspects of this format are:

- **Single Field:** Unlike Watermill's default publisher which uses multiple fields for message metadata (`_watermill_message_uuid`, `_watermill_payload`), the Python implementation uses a single field `json_payload`.
- **Complete Event Object:** The value of `json_payload` is a JSON string representing the entire event object, including `event_id`, `timestamp`, `event_type`, `payload`, and `run_id`.
- **No Watermill Metadata:** The messages do not contain any Watermill-specific metadata that the default unmarshaller expects.

Example payload structure:
```json
{
  "event_id": "9ec55edc-1f96-4541-8eb7-9382e00a4d7c",
  "timestamp": "2025-04-26T02:56:10.937611Z",
  "event_type": "tool_invoked",
  "payload": {
    "tool_call_id": "8f6a60d4-77a7-48c6-8b60-b71648849794",
    "tool_name": "BingBrowser",
    // other tool-specific fields...
  },
  "run_id": "b3a7ae44-23c4-4082-8ad5-ce1f898a8d27"
}
```

### Custom Unmarshaller Implementation

To handle this Redis message format, a custom unmarshaller needs to be implemented:

```go
// CustomEventUnmarshaller handles the specific format of messages published 
// by the Python EventBus, where the entire event is a JSON string under the "json_payload" key
type CustomEventUnmarshaller struct{}

func (u CustomEventUnmarshaller) Unmarshal(values map[string]interface{}) (*message.Message, error) {
    // Get the raw payload value
    payload, ok := values["json_payload"]
    if !ok {
        // Fallback to the default Watermill field, just in case
        payload, ok = values["_watermill_payload"]
        if !ok {
            return nil, fmt.Errorf("message does not contain payload under key 'json_payload' or '_watermill_payload'")
        }
    }

    // Handle different payload types
    var payloadStr string
    switch v := payload.(type) {
    case string:
        payloadStr = v
    default:
        // Marshal any non-string payload to JSON
        b, err := json.Marshal(v)
        if err != nil {
            return nil, fmt.Errorf("failed to marshal payload to JSON string: %w", err)
        }
        payloadStr = string(b)
    }

    // Create a new Watermill message with the payload
    msgUUID := watermill.NewUUID()
    msg := message.NewMessage(msgUUID, []byte(payloadStr))
    return msg, nil
}

func (u CustomEventUnmarshaller) Marshal(topic string, msg *message.Message) (*redis.XAddArgs, error) {
    // Marshal implementation is not needed for subscriber-only code
    // But could be implemented if we want to publish back to Redis with the same format
    panic("CustomEventUnmarshaller.Marshal not implemented")
}
```

This custom unmarshaller is used when configuring the Redis Stream subscriber:

```go
subscriber, err := redisstream.NewSubscriber(
    redisstream.SubscriberConfig{
        Client:          redisClient,
        Unmarshaller:    CustomEventUnmarshaller{},
        ConsumerGroup:   "go_server_group",
        NackResendSleep: time.Second * 5,
        MaxIdleTime:     time.Minute * 2,
    },
    watermillLogger,
)
```

### Event Processing Pipeline

The complete event processing pipeline follows these steps:

1. **Message Reception:** The Watermill Redis Stream subscriber consumes messages from the Redis stream and monitors them for acknowledgement (via XACK).

2. **Message Unmarshalling:** The custom unmarshaller converts the Redis stream item into a Watermill message:
   - Extracts the JSON string from the `json_payload` field
   - Creates a new Watermill message with a generated UUID
   - Sets the full event JSON as the message payload

3. **Router Handling:** The Watermill router delivers the message to all registered handlers:
   - **Database Handler:**
     - Parses the JSON payload back into a Go struct representing the event
     - Determines the event type (`event_type` field) and executes specific logic based on it
     - Updates the appropriate database tables using transactions where necessary
   
   - **State Manager Handler:**
     - Parses the JSON payload into an event object
     - Updates the corresponding state manager (`EventManager` or `GraphManager`) based on event type
     - For graph-relevant events (e.g., `node_created`, `edge_added`), updates the graph structure
     - For event log events, appends to the in-memory event list

   - **WebSocket Broadcast Handler:**
     - Takes the raw message payload (which is already the full JSON event string)
     - Passes it directly to the WebSocket hub
     - The hub forwards it to all connected clients without modification

4. **Message Acknowledgement:** Each handler acknowledges the message upon successful processing using `msg.Ack()` or returns an error which causes Watermill to NACK the message.

### Event Structs and Type Handling

To parse the JSON payloads into Go objects, a set of structs will be defined in the `pkg/model` package:

```go
// Base Event struct matching the Python implementation
type Event struct {
    EventID   string          `json:"event_id"`
    Timestamp string          `json:"timestamp"`
    EventType string          `json:"event_type"`
    Payload   json.RawMessage `json:"payload"` // Use RawMessage for flexible payload types
    RunID     string          `json:"run_id"`
}

// EventPayload interface for type-specific payloads
type EventPayload interface {
    GetType() string
}

// Concrete payload types for each event type
type RunStartedPayload struct {
    InputData  json.RawMessage `json:"input_data"`
    Config     json.RawMessage `json:"config"`
    RunMode    string          `json:"run_mode"`
    TimestampUTC string        `json:"timestamp_utc"`
}

type NodeCreatedPayload struct {
    NodeID      string   `json:"node_id"`
    NodeNID     string   `json:"node_nid"`
    NodeType    string   `json:"node_type"`
    TaskType    string   `json:"task_type"`
    TaskGoal    string   `json:"task_goal"`
    Layer       int      `json:"layer"`
    OuterNodeID *string  `json:"outer_node_id"`
    RootNodeID  string   `json:"root_node_id"`
    InitialParentNIDs []string `json:"initial_parent_nids"`
    Step        *int    `json:"step,omitempty"`
}

// Additional payload structs for other event types...
```

The `StateManager` implementations will use these structs to process events and update the in-memory state.

## 12. Logging

- Use `github.com/rs/zerolog` for structured JSON logging.
- Initialize the logger in the main application based on the `log_level` config.
- Pass logger instances down to components or use a package-level logger.
- Include contextual fields in logs (e.g., `component`, `run_id`, `event_id`, `client_addr`).
- Configure Watermill to use structured logging adapter for zerolog.

## 13. Dependencies

- **`net/http`:** Standard library for HTTP server.
- **`database/sql`:** Standard library for DB interaction.
- **`github.com/ThreeDotsLabs/watermill`:** Message routing framework.
- **`github.com/ThreeDotsLabs/watermill/message/infrastructure/redisstream`:** Redis stream connector for Watermill.
- **`github.com/mattn/go-sqlite3`:** CGO driver for SQLite.
- **`github.com/gorilla/websocket`:** WebSocket protocol implementation.
- **`github.com/rs/zerolog`:** Structured logging.
- **`golang.org/x/sync/errgroup`:** Goroutine lifecycle management.
- **`github.com/spf13/cobra`:** [Recommended] CLI framework.
- **`github.com/spf13/viper`:** [Recommended] Configuration management.
- **`github.com/pkg/errors`:** Error wrapping.

## 14. Lifecycle Management

- The main application entry point (`cmd/server/main.go`) will create a root `context`.
- Signal handling (SIGINT, SIGTERM) will be used to cancel this root context.
- The Watermill router will be configured to respect this context via `router.Run(ctx)`.
- Components (Router, Hub, HTTP server shutdown) will listen for context cancellation (`<-ctx.Done()`) to initiate graceful shutdown procedures.
- Watermill will handle draining in-flight messages and proper acknowledgement during shutdown.

## 15. Package Layout

```
cmd/
  server/
    main.go             ← wiring, config, shutdown
internal/
  api/
    handlers.go         ← HTTP/REST endpoints
  ws/
    hub.go              ← gorilla/websocket hub
  redis/
    router.go           ← Watermill router + handlers
  db/
    manager.go          ← SQLite storage (port of Python logic)
  state/
    event_manager.go
    graph_manager.go
pkg/
  model/
    event.go            ← Go version of Event struct
  config/
    config.go           ← mirrors ServerConfig
``` 