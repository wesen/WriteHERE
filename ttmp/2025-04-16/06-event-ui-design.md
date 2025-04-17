# Designing Custom UIs for the WriteHERE Recursive Planning Agent: Event Visualization Guide

## 1. System Context and Purpose

The WriteHERE system is a sophisticated AI-based writing framework that employs hierarchical recursive planning to generate long-form content. This document expands on our existing React UI framework to address the specific visualization needs for monitoring and understanding WriteHERE's internal processes.

### Key System Characteristics

- **Recursive Planning Architecture**: The system decomposes complex writing tasks into nested subtasks organized in a hierarchical task graph
- **Heterogeneous Task Types**: Different nodes in the graph perform specialized functions (composition, retrieval, reasoning)
- **Dynamic Execution Flow**: Tasks execute based on dependencies and status changes, creating a complex execution pattern
- **Multi-Stage Processing**: Each task goes through multiple states (planning, execution, reflection, aggregation)

### Visualization Challenges

- **Complex State Transitions**: Tasks move through multiple states that should be intuitively visualized
- **Hierarchical Relationships**: The nested structure of tasks requires clear representation of parent-child relationships
- **Temporal Patterns**: Understanding when and how long specific operations take is critical for performance analysis
- **Event Volume**: The system generates many events that must be filtered and prioritized for effective monitoring

## 2. Event System Architecture

The event system is built on a Redis-based event bus with WebSocket delivery to the UI:

```
Agents/Engine  ──► EventBus.publish(...) ──►  Redis Stream "events"
                                                  ▼
                                            WS Server (FastAPI)
                                                  ▼
                                            Browser UI (React)
```

### Key Components

- **Event Producers**: Core system components that generate events (engine, agents, tools)
- **Redis Event Bus**: Central message broker that stores events in a time-ordered stream
- **WebSocket Server**: Forwards events from Redis to connected browser clients
- **React UI Components**: Consumes and visualizes the event stream

### Event Flow

1. System components emit typed events with structured payloads during execution
2. Events are published to Redis streams (fire-and-forget)
3. WebSocket server subscribes to the Redis stream and forwards events to clients
4. UI components consume events based on type and render appropriate visualizations

## 3. Primary UI Objectives

The custom UI should enable users to:

- **Monitor Task Progress**: Track the overall writing process and identify bottlenecks
- **Understand Task Relationships**: Visualize the hierarchical structure of tasks and dependencies
- **Analyze LLM Usage**: Monitor language model calls, costs, and performance metrics
- **Track Tool Interactions**: See when and how external tools (search, retrieval) are used
- **Debug Writing Process**: Identify issues in the writing flow and task execution
- **Observe Final Composition**: View how the final document comes together from component parts

## 4. Key Visualization Requirements

### 4.1 Task Graph Visualization

- **Real-time Task Status**: Display the current status of each task node using clear visual indicators
- **Hierarchical Relationships**: Show parent-child relationships between tasks
- **Dependency Visualization**: Highlight task dependencies to understand execution flow
- **Layer-based Organization**: Organize nodes by their layer/depth in the task hierarchy
- **Status Change Animation**: Animate transitions between task states
- **Node Details On-demand**: Provide detailed information when interacting with specific nodes

### 4.2 Event Timeline

- **Chronological View**: Display events on a horizontal timeline
- **Event Type Filtering**: Allow filtering by event type (LLM calls, tool usage, status changes)
- **Event Grouping**: Group related events (e.g., all events for a specific node)
- **Time Scaling**: Allow zooming in/out to see different time ranges
- **Marker Integration**: Show important milestones in the writing process
- **Event Details**: Show full event payload on selection/hover

### 4.3 LLM Monitoring Dashboard

- **Call Frequency Visualization**: Show the rate of LLM calls over time
- **Model Distribution**: Display proportion of calls to different LLM models
- **Token Usage Metrics**: Visualize token consumption and associated costs
- **Response Time Analysis**: Show response latency distribution
- **Prompt-Response Inspection**: Allow viewing of actual prompts and responses
- **Cost Tracking**: Calculate and display cumulative API costs

### 4.4 State Transition Flow

- **Sankey Diagram**: Visualize how tasks flow between different states
- **State Duration Analysis**: Show how long tasks spend in each state
- **Critical Path Highlighting**: Identify the sequence of tasks on the critical path
- **Bottleneck Identification**: Highlight states where tasks are getting stuck
- **Transition Metrics**: Show counts and rates of different state transitions

### 4.5 Document Composition View

- **Incremental Text Assembly**: Show how the final document is built up over time
- **Section Contribution**: Visualize which tasks contribute to which document sections
- **Content Origin Tracing**: Trace portions of text back to their generating tasks
- **Version Timeline**: Show document evolution through successive revisions
- **Content Type Analysis**: Distinguish between different types of content (retrieved vs. generated)

## 5. Event Types and Their Visualization Implications

### 5.1 Engine Step Events

**Key Events**: `step_started`, `step_finished`

**Visualization Opportunities**:

- Step counter and progress indicator
- Step execution duration metrics
- Error tracking for failed steps
- Active node highlighting in the task graph

**Typical Payload Fields**:

- `step`: Step number in execution sequence
- `node`: The node ID being processed
- `root`: Root node ID for this execution
- `duration`: Time taken (for step_finished)
- `exception`: Error information if step failed

### 5.2 Node Status Change Events

**Key Events**: `node_status_change`

**Visualization Opportunities**:

- Node status color coding in graph view
- Status transition animations
- State duration tracking
- Flow diagrams showing transition patterns

**Typical Payload Fields**:

- `node_id`: The node experiencing the status change
- `old`: Previous status value
- `new`: New status value
- `layer`: Hierarchical depth of the node
- `parents`: IDs of parent/dependency nodes

### 5.3 LLM Interaction Events

**Key Events**: `llm_call_started`, `llm_call_completed`

**Visualization Opportunities**:

- LLM usage dashboard
- Token and cost tracking
- Model performance comparison
- Response time analysis

**Typical Payload Fields**:

- `node_id`: The node making the LLM call
- `agent_class`: Type of agent making the call
- `model`: The specific LLM model used
- `prompt_hash`: Hash of the prompt for deduplication/tracking
- `duration`: Time the call took to complete
- `token_usage`: Token consumption metrics
- `cost_estimate`: Estimated API cost
- `truncated_result`: Sample of the response

### 5.4 Tool Usage Events

**Key Events**: `tool_invoked`, `tool_returned`

**Visualization Opportunities**:

- Tool usage frequency charts
- Tool performance metrics
- Success/failure rate tracking
- Tool dependency mapping

**Typical Payload Fields**:

- `tool_name`: The tool being used
- `api_name`: Specific API endpoint/method
- `args_hash`: Hash of the arguments
- `latency`: Response time
- `success`: Whether the tool completed successfully
- `state`: Return status code

### 5.5 Information Retrieval Events

**Key Events**: `search_completed`

**Visualization Opportunities**:

- Search query visualization
- Source attribution tracking
- Information quality metrics
- Search efficiency analysis

**Typical Payload Fields**:

- `query_terms`: Search terms used
- `page_count`: Number of pages retrieved
- `selected_count`: Number of results used
- `time_spent`: Duration of search operation

## 6. UI Design Considerations

### 6.1 Layout and Organization

- **Split View Design**: Separate panels for different visualization types
- **Collapsible Sections**: Allow users to focus on relevant information
- **Responsive Adaptation**: Scale appropriately for different screen sizes
- **Consistent Navigation**: Clear mechanism to switch between views
- **State Persistence**: Remember user preferences for filters and views

### 6.2 Visual Language

- **Status Color Coding**: Consistent colors for different task states

  - NOT_READY: Gray
  - READY: Blue
  - DOING: Yellow
  - FINISH: Green
  - FAILED: Red

- **Event Type Icons**: Distinct icons for different event types
- **Hierarchy Indicators**: Clear visual cues for parent-child relationships
- **Time Representation**: Consistent approach to showing temporal information
- **Alert Indicators**: Distinctive visual elements for errors or important events

### 6.3 Interactive Elements

- **Filtering Controls**: Allow filtering by event type, time range, node ID
- **Zoom and Pan**: Provide navigation within large graphs or timelines
- **Selection and Details**: Click/hover interactions to reveal detailed information
- **Search Functionality**: Find specific nodes or events by text search
- **Export Options**: Allow exporting visualizations or data for further analysis

## 7. Event Schema Reference

Below are the key event schemas that the UI will need to visualize:

```
Event (base type)
├── id: string (UUID)
├── ts: ISO8601 timestamp
├── type: EventType enum
└── payload: object (event-specific data)

EventType Enum:
├── STEP_STARTED
├── STEP_FINISHED
├── NODE_STATUS_CHANGE
├── LLM_CALL_STARTED
├── LLM_CALL_COMPLETED
├── TOOL_INVOKED
├── TOOL_RETURNED
└── SEARCH_COMPLETED

TaskStatus Enum (for node status):
├── NOT_READY
├── READY
├── NEED_UPDATE
├── FINAL_TO_FINISH
├── NEED_POST_REFLECT
├── FINISH
├── PLAN_DONE
├── DOING
└── FAILED
```

## 9. Conclusion and Next Steps

The WriteHERE event visualization UI represents a critical tool for understanding and improving the complex recursive planning process. By effectively visualizing the event stream, we can:

- Gain insights into the writing process that would be invisible otherwise
- Understand the relationship between system components
- Debug issues in the recursive planning logic
