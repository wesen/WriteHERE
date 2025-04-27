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
    - Configures the Redis Stream PubSub subscriber.
    - Registers independent handlers for different components (DB persist, state update, WS broadcast).
    - Provides exactly-once message delivery with acknowledgement/retry capabilities.
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
2.  **Event Bus (Python):** The Python `EventBus` publishes the event (as JSON) to the configured Redis stream (`agent_events`).
3.  **Watermill Router (Go):** 
    - The Redis Stream PubSub subscribes to the stream and receives new messages.
    - The message router delivers the message to all registered handlers in parallel.
4.  **Handler Execution:**
    - **Database Handler:** Decodes the message, persists event to SQLite, and acknowledges the message.
    - **State Update Handler:** Decodes the message, updates in-memory state managers, and acknowledges the message.
    - **WebSocket Broadcast Handler:** Gets the raw payload, sends it to the WebSocket hub for broadcasting, and acknowledges the message.
5.  **WebSocket Hub:** Takes the raw JSON from the broadcast handler and sends it to all connected clients.
6.  **UI:** The React UI receives the JSON string, parses it, and updates its Redux store.

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

## 11. Logging

- Use `github.com/rs/zerolog` for structured JSON logging.
- Initialize the logger in the main application based on the `log_level` config.
- Pass logger instances down to components or use a package-level logger.
- Include contextual fields in logs (e.g., `component`, `run_id`, `event_id`, `client_addr`).
- Configure Watermill to use structured logging adapter for zerolog.

## 12. Dependencies

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

## 13. Lifecycle Management

- The main application entry point (`cmd/server/main.go`) will create a root `context`.
- Signal handling (SIGINT, SIGTERM) will be used to cancel this root context.
- The Watermill router will be configured to respect this context via `router.Run(ctx)`.
- Components (Router, Hub, HTTP server shutdown) will listen for context cancellation (`<-ctx.Done()`) to initiate graceful shutdown procedures.
- Watermill will handle draining in-flight messages and proper acknowledgement during shutdown.

## 14. Package Layout

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