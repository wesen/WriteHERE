# WriteHERE Go Event-Driven Port: Status and Next Steps

## 1. Purpose and Scope

This document outlines the progress made in porting the core WriteHERE engine from its original Python implementation to a new event-driven architecture written in Go. The goal of this port is to leverage Go's concurrency, performance, and strong typing to create a more scalable, resilient, and maintainable system based on the principles outlined in `ttmp/2025-04-08/03-event-driven-architecture.md`.

This document serves as a handover guide for developers joining the project, explaining what has been built, the key architectural decisions made, and the immediate next steps required to continue development.

## 2. Accomplishments So Far (Phase 1 Complete)

We have successfully implemented the foundational infrastructure (Phase 1) of the event-driven architecture:

- **Project Setup:** Initialized the Go module (`github.com/go-go-golems/writehere-go`) and established the basic directory structure.
- **Core Packages:**
  - `pkg/events`: Defines event structures (`Event`, `EventType`, specific payloads like `TaskSubmittedPayload`), serialization logic, and the `EventBus` implementation using Watermill.
  - `pkg/state`: Defines the core `Task` model, `TaskStatus` enum, `TaskType` enum, an `InMemoryStore` for task persistence, and the `StateService`.
- **Event Bus (`pkg/events/bus.go`):** Implemented using Watermill with an in-memory `gochannel` Pub/Sub. It includes middleware for recovery, correlation IDs, and retries. Provides `Publish` and `Subscribe` methods.
- **State Management (`pkg/state/`):**
  - `task.go`: Defines the `Task` struct reflecting the design document, including fields for dependencies, status, results, etc.
  - `store.go`: Provides an `InMemoryStore` implementation satisfying the `Store` interface for basic CRUD operations, dependency management, and querying tasks (e.g., `GetReadyTasks`).
  - `service.go`: The `StateService` acts as the central manager of task state. It subscribes to `TaskSubmitted`, `TaskCompleted`, `TaskFailed`, and `SubtasksPlanned` events. It updates the `Store` accordingly and is responsible for checking task dependencies and publishing `TaskReady` events when a task's prerequisites are met.
- **API Gateway (`cmd/engine-api/main.go`):** A basic HTTP server built using Go's standard `net/http` library and Cobra for command-line argument parsing. It provides:
  - `POST /api/tasks`: Endpoint to submit a new root task (goal, type, metadata). This triggers the `StateService`'s `CreateRootTask` method, which publishes a `TaskSubmitted` event.
  - `GET /api/tasks/{task_id}`: Retrieves the current state of a specific task.
  - `GET /api/tasks/root/{root_task_id}`: Retrieves all tasks associated with a given root task ID.
- **Dependencies & Tooling:** Integrated Zerolog for logging, `github.com/pkg/errors` for error handling, Cobra for CLI, and `golang.org/x/sync/errgroup` for managing concurrent operations.

## 3. Key Architectural Decisions

- **Event-Driven Core:** Communication between major components (API Gateway, State Service, Scheduler, Workers) happens primarily via events published to and consumed from the event bus.
- **Watermill:** Chosen as the Go library for handling Pub/Sub interactions, providing abstractions over different brokers and useful middleware. Currently uses the simple `gochannel` implementation, but can be swapped later (e.g., to Kafka, Google Cloud Pub/Sub).
- **Explicit Scheduler (Phase 2):** We explicitly decided _against_ having workers subscribe directly to `TaskReady` events. Instead, a dedicated `Scheduler` service will subscribe to `TaskReady`, determine the appropriate worker type, and publish a `TaskAssigned` event. This approach was chosen for:
  - **Efficiency:** Avoids having every worker fetch task details just to check the type.
  - **Race Condition Mitigation:** Simplifies avoiding multiple workers picking up the same task compared to distributed locking/CAS on `TaskReady`.
  - **Centralized Control:** Provides a natural place for future prioritization, load balancing, and capability-based routing logic.
  - **Clearer State Flow:** Introduces a distinct `ASSIGNED` state.
- **State Service as Truth Source:** The `StateService` is responsible for consuming events that signify state changes and is the only component designed to modify task state in the `Store`. It also determines when tasks become `READY`.
- **In-Memory Store (Initial):** Started with `InMemoryStore` for simplicity. This will likely need to be replaced with a persistent database (e.g., PostgreSQL, MongoDB) for production use.

## 4. Current System Setup & Flow

1.  Run `go run cmd/engine-api/main.go`.
2.  Send a `POST` request to `http://localhost:8080/api/tasks` with JSON body like `{"goal": "Write a story about a dragon", "task_type": "COMPOSITION"}`.
3.  The **API Gateway** receives the request.
4.  The **API Gateway** calls `stateService.CreateRootTask`.
5.  The **State Service** publishes a `TaskSubmitted` event to the `events.TaskTopic`.
6.  The **State Service** (also subscribed) consumes the `TaskSubmitted` event.
7.  The `handleTaskSubmitted` function creates the `Task` object in the `InMemoryStore`.
8.  Since it's a root task with no dependencies, the task status is set to `READY`.
9.  The `handleTaskSubmitted` function publishes a `TaskReady` event to the `events.TaskTopic`.
10. **Currently, no service consumes `TaskReady`, so the process stops here.**
11. You can query `GET /api/tasks/{task_id}` to see the task in the `READY` state.

## 5. Next Steps (Phase 2 & 3 Implementation)

The immediate focus is on implementing the Scheduler and the basic structure for Worker services.

1.  **Implement the Scheduler Service (`pkg/scheduler`)**:

    - Create `scheduler.Service`.
    - Subscribe to `TaskReady` events on `events.TaskTopic`.
    - In the handler (`handleTaskReady`):
      - Fetch the full `Task` details from the `state.Store` using the `TaskID` from the event payload.
      - Determine the target `WorkerType` string based on `task.TaskType` (e.g., map `state.TaskTypePlanning` to `"planning-worker"`).
      - Publish a `TaskAssigned` event to `events.TaskTopic` containing the `TaskID`, `RootTaskID`, and the determined `WorkerType`.
    - Integrate the `Scheduler` into `cmd/engine-api/main.go` (or a separate command) so it runs alongside the `StateService`.

2.  **Implement a Basic Planning Worker Service (`pkg/workers/planning`)**:

    - Create `planning.Service`. Define its `workerType` as `"planning-worker"`.
    - Subscribe to `TaskAssigned` events on `events.TaskTopic`.
    - In the handler (`handleTaskAssigned`):
      - Decode the event payload (`events.TaskAssignedPayload`).
      - **Filter:** Check if `payload.WorkerType` matches this worker's type (`"planning-worker"`). If not, return `nil` immediately (ACK message).
      - Fetch the full `Task` details from the `state.Store`.
      - **(Stub Logic):** Initially, log that the planning task is being "processed".
      - **(Stub Output):** Publish a `TaskCompleted` event for the planning task itself (use `events.NewEvent` and `eventBus.Publish`).
      - **(Future):** This is where the actual planning logic (calling LLMs, generating subtasks) will go, eventually publishing `SubtasksPlanned` first, then `TaskCompleted`.
    - Integrate the `PlanningWorker` into `cmd/engine-api/main.go` (or a separate command).

3.  **Implement a Basic Execution Worker Service (`pkg/workers/execution`)**:

    - Follow the same pattern as the Planning Worker, but with `workerType` as `"execution-worker"` (or similar).
    - The stub logic should just log execution and publish `TaskCompleted`.
    - **(Future):** This worker will eventually contain the agent logic (like ReAct), action execution, and LLM calls for content generation/reasoning/retrieval.

4.  **Refine State Transitions:** Ensure the `StateService` correctly handles the `ASSIGNED` status once the `Scheduler` publishes `TaskAssigned` events (this might require adding a handler for `TaskAssigned` in the `StateService` or having workers update the status upon starting). _Self-correction: It's cleaner for the worker receiving `TaskAssigned` to potentially update the state to `RUNNING` via an event or direct store update if necessary, rather than adding that complexity to the StateService._

5.  **Implement Action System (`pkg/actions`)**:
    - Define the `Action` interface (`Name`, `Description`, `ParameterSchema`, `Execute`).
    - Create a registration mechanism for actions.
    - Port a simple `BaseAction` from Python (e.g., a simple calculator or echo tool).
    - Implement a basic `ActionExecutor` within the `ExecutionWorker` to load and run registered actions.

## 6. What to Pay Attention To

- **Configuration:** As services (Scheduler, Workers) are added, establish a clear way to configure them (e.g., worker type strings, Pub/Sub connection details if moving off GoChannel, LLM API keys/endpoints). Viper/Cobra flags can be used.
- **Error Handling:** Ensure errors are handled appropriately within each service and propagated correctly (e.g., when a worker handler fails, should it Nack the message for retry, or publish `TaskFailed`?).
- **State Store Concurrency:** The `InMemoryStore` uses `sync.RWMutex`. If replacing with a persistent DB, ensure transactionality and proper locking/atomicity for state updates, especially around task assignment.
- **Idempotency:** Design event handlers to be idempotent where possible, meaning processing the same event multiple times doesn't cause incorrect side effects. Watermill's retry middleware makes this important.
- **Testing:** Develop unit tests for individual components (State Service logic, Scheduler logic, Worker filtering) and integration tests for event flows.
- **Observability:** Maintain clear logging. Consider adding distributed tracing (e.g., OpenTelemetry) later as more services are added to track requests across the system.
- **Graceful Shutdown:** Ensure all services (API Gateway, State Service, Scheduler, Workers) handle OS signals correctly (like SIGTERM) to shut down cleanly, finishing in-progress work within a timeout and closing event bus connections. The current API gateway has a good example using `context` and `errgroup`.

By following these next steps, we can incrementally build out the core functionality of the event-driven WriteHERE engine in Go.
