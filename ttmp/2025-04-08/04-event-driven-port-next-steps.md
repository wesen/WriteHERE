# WriteHERE Go Event-Driven Port: Status and Next Steps

## 1. Purpose and Scope

This document outlines the progress made in porting the core WriteHERE engine from its original Python implementation to a new event-driven architecture written in Go. The goal of this port is to leverage Go's concurrency, performance, and strong typing to create a more scalable, resilient, and maintainable system based on the principles outlined in `ttmp/2025-04-08/03-event-driven-architecture.md`.

This document serves as a handover guide for developers joining the project, explaining what has been built, the key architectural decisions made, and the immediate next steps required to continue development.

## 2. Accomplishments So Far (Phase 1, 2 & 3 Started)

We have implemented the foundational infrastructure (Phase 1) and begun work on the Scheduler Framework (Phase 2) and Action System (Phase 3):

- **Project Setup & Core Packages (Phase 1):**
  - Go module (`github.com/go-go-golems/writehere-go`), directory structure.
  - `pkg/events`: Event definitions (`TaskSubmitted`, `TaskReady`, `TaskAssigned`, `TaskStarted`, `TaskCompleted`, `TaskFailed`, `SubtasksPlanned`), `EventBus` (Watermill/GoChannel).
  - `pkg/state`: `Task` model (with `RUNNING` status), `Store` interface, `InMemoryStore`, `StateService` (handles `TaskSubmitted`, `TaskCompleted`, `TaskFailed`, `TaskStarted`, `SubtasksPlanned`).
  - `cmd/engine-api`: API gateway (`POST /tasks`, `GET /tasks/{id}`, `GET /tasks/root/{root_id}`).
- **Scheduler Framework (Phase 2):**
  - `pkg/scheduler`: `Service` subscribes to `TaskReady`, determines worker type, publishes `TaskAssigned`.
  - `pkg/workers/planning`: Stubbed `Service` subscribes to `TaskAssigned`, filters for `planning-worker`, publishes `TaskStarted`, generates _dummy_ subtasks, publishes `SubtasksPlanned`, then publishes `TaskCompleted`.
  - `pkg/workers/execution`: Stubbed `Service` subscribes to `TaskAssigned`, filters for `execution-worker`, publishes `TaskStarted`, logs processing (includes stubbed `ActionExecutor` call for `COMPOSITION` type), publishes `TaskCompleted` or `TaskFailed`.
  - Integration: All services (`StateService`, `Scheduler`, `PlanningWorker`, `ExecutionWorker`) are initialized and run via `errgroup` in `cmd/engine-api/main.go`.
- **Action System (Phase 3):**
  - `pkg/actions`: Defined `Action` interface, `ActionResult`, `ActionStatus`, registry (`RegisterAction`, `GetAction`), and `ActionExecutor`.
  - `pkg/actions/echo.go`: Implemented a sample `EchoAction`.
  - Integration: `ActionExecutor` is initialized in `ExecutionWorker` and used in its stubbed logic.
- **Dependencies & Tooling:** Zerolog, `pkg/errors`, Cobra, `errgroup`.

## 3. Key Architectural Decisions

- **Event-Driven Core:** Communication via events.
- **Watermill:** Using `gochannel` for now.
- **Explicit Scheduler:** `Scheduler` handles `TaskReady` -> `TaskAssigned`.
- **State Service as Truth Source:** Manages state updates based on events.
- **Refined State Flow:** Introduced `TaskStarted` event and `RUNNING` status. Workers publish `TaskStarted` upon receiving `TaskAssigned`.
- **In-Memory Store (Initial):** To be replaced later.

## 4. Current System Setup & Flow (Updated)

1.  Run `go run cmd/engine-api/main.go`.
2.  Send a `POST` request to `http://localhost:8080/api/tasks` with JSON body like `{"goal": "Outline a blog post about Go", "task_type": "PLANNING"}`.
3.  **API Gateway** -> `stateService.CreateRootTask`.
4.  **State Service** publishes `TaskSubmitted`.
5.  **State Service** consumes `TaskSubmitted`, creates `Task` (status `READY`), publishes `TaskReady`.
6.  **Scheduler** consumes `TaskReady`, determines worker (`planning-worker`), publishes `TaskAssigned`.
7.  **Planning Worker** consumes `TaskAssigned` (matches type), publishes `TaskStarted`.
8.  **State Service** consumes `TaskStarted`, updates task status to `RUNNING`.
9.  **Planning Worker** generates dummy subtasks (e.g., two `EXECUTION` tasks), publishes `SubtasksPlanned`.
10. **State Service** consumes `SubtasksPlanned`, creates new subtask records (e.g., subtask1 `READY`, subtask2 `PENDING_DEPS`), publishes `TaskReady` for subtask1.
11. **Planning Worker** publishes `TaskCompleted` (for the original planning task).
12. **State Service** consumes `TaskCompleted`, updates original planning task status to `COMPLETED`.
13. **Scheduler** consumes `TaskReady` (for subtask1), determines worker (`execution-worker`), publishes `TaskAssigned`.
14. **Execution Worker** consumes `TaskAssigned`, publishes `TaskStarted`.
15. **State Service** consumes `TaskStarted`, updates subtask1 status to `RUNNING`.
16. **Execution Worker** runs stubbed logic (maybe calls `echo` action), publishes `TaskCompleted`.
17. **State Service** consumes `TaskCompleted` (for subtask1), updates subtask1 status to `COMPLETED`. Checks dependents (subtask2), sees its dependencies (subtask1) are now complete, updates subtask2 status to `READY`, publishes `TaskReady` (for subtask2).
18. Flow continues similarly for subtask2...
19. You can query `GET /api/tasks/{task_id}` or `GET /api/tasks/root/{root_task_id}` to observe the state changes.

## 5. Next Steps (Updated)

With the foundational LLM client and basic Action system (interface, registry, built-ins, executor) in place, the next priorities involve implementing the core agent logic and porting key actions:

1.  **Implement Real Planning Logic (`pkg/workers/planning`)**: **[DONE]**

    - [x] Replace dummy subtask generation with actual LLM calls (`llms.Client`).
    - [x] Define a prompt structure (`systemPrompt`, `userPrompt`) for task decomposition requesting JSON output.
    - [x] Integrate the `llms.Client` (`go-openai` implementation).
    - [x] Parse the LLM response (`llmPlanResponse`) into `events.Subtask` structures, handling dependency mapping.
    - [x] Handle potential LLM/parsing errors gracefully (publish `TaskFailed`).

2.  **Implement Basic ReAct Agent Logic (`pkg/workers/execution`)**: **[NEXT]**

    - [ ] **Inject Dependencies:** Modify `execution.NewService` to accept `llms.Client` and initialize an `actions.ActionExecutor`.
    - [ ] **Core ReAct Loop:** Inside `handleTaskAssigned`:
      - [ ] Fetch task details and context (dependency results).
      - [ ] Get available action schemas using `actionExecutor.GetActionSchemas()`.
      - [ ] Implement the core loop (max turns, history management):
        - [ ] Construct the prompt using goal, history, context, action schemas (inspired by `claude_fc_react.py`).
        - [ ] Call `llmClient.ChatCompletion`.
        - [ ] **Parse LLM Output:** Extract thought and action invocation (e.g., using regex or structured output if the LLM supports it). Handle cases where no action is returned (`NoAction`) or the action is invalid (`InvalidAction`).
        - [ ] **Execute Action:** If an action is requested, call `actionExecutor.ExecuteAction(actionName, args)`.
        - [ ] **Handle Finish:** If `FinishAction` is executed, extract the final answer from `ActionResult.Data` and break the loop.
        - [ ] **Update History:** Append thought, action request, and observation (from `ActionResult.Result`) to the loop's history.
        - [ ] Handle action execution errors.
    - [ ] **Publish Result:** After the loop terminates (finish, max turns, error), publish `TaskCompleted` with the final answer or `TaskFailed`.
    - [ ] **Prompts:** Define system/user prompts suitable for a generic ReAct agent, instructing it to use the provided actions to achieve the goal.

3.  **Expand Action Library (`pkg/actions`)**: **[NEXT, Parallel]**

    - [ ] **Port `BingBrowser` (`bing_browser.py`) -> `SearchAction` (`pkg/actions/search.go`):**
      - [ ] Define `SearchAction` struct implementing `actions.Action`.
      - [ ] Implement `ParameterSchema` (e.g., for `query` argument).
      - [ ] Implement `Execute`: This will require integrating a Go web search library (e.g., calling a search API like SerpApi, Google Search API, or a browser automation tool) and potentially logic for selecting/summarizing results (maybe simple for now, or requires further LLM calls via `llms.Client`). Mimic the core functionality of `BingBrowser.run`.
      - [ ] Register the `SearchAction` in `search.go`'s `init()`.
    - [ ] **(Optional) Port File I/O Actions:** Consider simple `ReadFileAction` and `WriteFileAction` if needed early on.
    - [ ] **Ensure Built-in Actions are Registered:** Verify `FinishAction`, `InvalidAction`, `NoAction` from `builtin.go` are correctly registered via `init()`. [DONE]

4.  **Configuration Management**: **[Later]**

    - [ ] Introduce Viper or similar.
    - [ ] Make LLM API keys, model names, worker types, prompts configurable.
    - [ ] Pass config to `NewService` functions.

5.  **Testing**: **[Later]**
    - [ ] Unit tests for `PlanningWorker` LLM logic (mock `llms.Client`).
    - [ ] Unit tests for `ExecutionWorker` ReAct loop (mock `llms.Client`, `actions.ActionExecutor`).
    - [ ] Unit tests for individual `Actions` (mock external calls).
    - [ ] Integration tests for full Submit -> Plan -> Execute flow.

## 6. What to Pay Attention To

- **Configuration:** As services (Scheduler, Workers) are added, establish a clear way to configure them (e.g., worker type strings, Pub/Sub connection details if moving off GoChannel, LLM API keys/endpoints). Viper/Cobra flags can be used.
- **Error Handling:** Ensure errors are handled appropriately within each service and propagated correctly (e.g., when a worker handler fails, should it Nack the message for retry, or publish `TaskFailed`?).
- **State Store Concurrency:** The `InMemoryStore` uses `sync.RWMutex`. If replacing with a persistent DB, ensure transactionality and proper locking/atomicity for state updates, especially around task assignment.
- **Idempotency:** Design event handlers to be idempotent where possible, meaning processing the same event multiple times doesn't cause incorrect side effects. Watermill's retry middleware makes this important.
- **Testing:** Develop unit tests for individual components (State Service logic, Scheduler logic, Worker filtering) and integration tests for event flows.
- **Observability:** Maintain clear logging. Consider adding distributed tracing (e.g., OpenTelemetry) later as more services are added to track requests across the system.
- **Graceful Shutdown:** Ensure all services (API Gateway, State Service, Scheduler, Workers) handle OS signals correctly (like SIGTERM) to shut down cleanly, finishing in-progress work within a timeout and closing event bus connections. The current API gateway has a good example using `context` and `errgroup`.

By following these next steps, focusing on the ReAct loop implementation in the `ExecutionWorker` and porting the `SearchAction`, we can achieve end-to-end execution capabilities for basic research-and-write tasks.
