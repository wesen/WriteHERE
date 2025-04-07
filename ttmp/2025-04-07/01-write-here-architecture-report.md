# WriteHERE: Heterogeneous Recursive Planning Architecture Report

This document provides a detailed overview of the WriteHERE codebase architecture, explaining how the various components interact and the control flow through the system.

## 1. System Overview

WriteHERE is an AI-based writing framework that employs a hierarchical recursive planning approach for generating long-form content. The system stands out by implementing:

1. **Recursive Planning**: Breaking down complex writing tasks into manageable subtasks
2. **Heterogeneous Integration**: Combining different task types (retrieval, reasoning, composition)
3. **Dynamic Adaptation**: Adjusting the writing process in real-time

The codebase is organized into a modular structure with clear separation between the core engine, the backend API server, and the frontend visualization.

## 2. Repository Structure

```
.
├── backend/               # Flask server for API access to core engine
├── frontend/              # React-based visualization interface
├── recursive/             # Core engine implementation
│   ├── agent/             # Agent implementation and prompts
│   ├── executor/          # Task execution modules
│   ├── llm/               # Language model integrations
│   ├── utils/             # Utility functions and helpers
│   ├── cache.py           # Caching for improved efficiency
│   ├── engine.py          # Core planning and execution engine
│   ├── graph.py           # Task graph representation
│   ├── memory.py          # Memory management
├── test_data/             # Example data for testing
├── setup_env.sh           # Environment setup script
└── start.sh               # All-in-one startup script
```

## 3. Core Architecture Components

### 3.1 Task Graph System (`recursive/graph.py`)

The task graph is the central data structure that orchestrates the entire writing process. It represents tasks and their relationships in a hierarchical structure.

Key classes:
- `Graph`: Manages the relationship between task nodes
- `TaskStatus`: Enum representing different states of a task (NOT_READY, READY, DOING, FINISH, etc.)
- `NodeType`: Classification of nodes (PLAN_NODE, EXECUTE_NODE)
- `AbstractNode`: Base class for all task nodes
- `RegularDummyNode`: Concrete implementation of task nodes

The task graph enables:
- **Hierarchical Decomposition**: Tasks can contain sub-tasks, creating a tree-like structure
- **Dependency Management**: Tasks can depend on other tasks, creating a directed acyclic graph
- **Task State Management**: Tracks the execution status of each task

### 3.2 Execution Engine (`recursive/engine.py`)

The `GraphRunEngine` class is responsible for orchestrating the execution of the task graph. It manages:

- Finding nodes that are ready for execution
- Executing the next action for a given node
- Updating the status of nodes based on execution results
- Persisting the state of the execution (saving/loading)

Key methods:
- `find_need_next_step_nodes()`: Identifies nodes ready for execution
- `forward_one_step_not_parallel()`: Executes a single step in the task graph
- `forward_one_step_untill_done()`: Executes the entire graph until completion
- `forward_exam()`: Updates node statuses based on dependencies and execution results

The engine has two main execution modes:
1. **Story Writing**: Tailored for creative fiction generation
2. **Report Writing**: Specialized for technical report generation

### 3.3 Agent System (`recursive/agent/`)

Agents are the components that perform the actual task execution. The architecture follows a modular design:

- `Agent` (abstract base class): Defines the interface for all agents
- Specialized agents for different tasks:
  - `UpdateAtomPlanningAgent`: Handles task decomposition and updating
  - `SimpleExcutor`: Executes various task types (composition, retrieval, reasoning)
  - `FinalAggregateAgent`: Aggregates results into final outputs

The agent system works by:
1. Taking a node and memory context as input
2. Processing the task based on the node's type and status
3. Returning results that update the node's state and memory

### 3.4 Memory Management (`recursive/memory.py`)

The `Memory` class manages information flow between nodes and provides context for task execution. It:

- Stores the accumulated article text
- Maintains a representation of the task execution history
- Collects information about dependencies between tasks
- Provides utilities for updating and retrieving information

### 3.5 LLM Integration (`recursive/llm/`)

Language models are abstracted through proxy classes (e.g., `OpenAIApiProxy`), allowing the system to:

- Make calls to various LLM providers (OpenAI, Anthropic)
- Cache responses to improve efficiency
- Extract structured information from unstructured LLM outputs

### 3.6 Task Types

The system supports three primary task types:

1. **COMPOSITION**: Focused on writing text content
   - Plans how to structure text
   - Executes writing subtasks
   - Aggregates written content

2. **RETRIEVAL**: Information gathering tasks
   - Uses a search-based agent (`SearchAgent`)
   - Integrates with search engines via `SerpApiSearch`
   - Processes and summarizes search results

3. **REASONING**: Analytical tasks
   - Processes information from other tasks
   - Draws conclusions and makes decisions
   - Generates structured analysis

## 4. Control Flow

The system's execution follows this general flow:

1. **Initialization**:
   - Create a root node with the main writing task
   - Initialize memory and configuration
   - Set up the task graph

2. **Task Decomposition**:
   - The root node's `plan()` method is called
   - LLM-based planning decomposes the task into subtasks
   - New nodes are created for each subtask
   - Dependencies between nodes are established

3. **Task Execution Loop**:
   - `forward_one_step_not_parallel()` is called repeatedly
   - At each step:
     - Find a node ready for execution
     - Execute the appropriate action (plan, execute, update, reflect)
     - Update the node status
     - Update memory with new results

4. **Hierarchical Planning**:
   - As COMPOSITION nodes execute, they may further decompose into subtasks
   - This creates a nested structure of tasks and subtasks
   - Planning continues until atomic tasks are reached (determined by layer depth or agent decision)

5. **Final Aggregation**:
   - Once all subtasks are complete, results are aggregated upwards
   - Each level combines the results of its subtasks
   - The root node produces the final output

## 5. Backend Server (`backend/server.py`)

The backend server provides a REST API for interacting with the core engine, with endpoints for:

- Starting a new writing task
- Retrieving the status of ongoing tasks
- Getting the results of completed tasks
- Visualizing the task graph

It acts as a bridge between the core engine and the frontend visualization, managing task persistence and state.

## 6. Frontend Visualization (`frontend/`)

The React-based frontend provides:

- A visualization of the task graph execution
- Real-time monitoring of task status
- Interactive exploration of task details
- Visualization of the hierarchical task structure

Key components include:
- Task graph visualization
- Article view
- Task details panel
- Control interface for starting/stopping tasks

## 7. Architectural Patterns

Several architectural patterns are employed in the codebase:

### 7.1 Command Pattern

The execution of tasks follows the Command pattern, where each task node encapsulates a request as an object, allowing:
- Parameterization of tasks with different requests
- Queuing of tasks
- Support for undoable operations (through state management)

### 7.2 Proxy Pattern

The `AgentProxy` and LLM proxy classes implement the Proxy pattern, providing a surrogate for controlling access to the underlying services.

### 7.3 Factory Pattern

The agent and task node creation uses a factory-like approach through the `Register` class, which maintains a registry of available implementations.

### 7.4 Observer Pattern

The relationship between the graph and its execution follows an Observer-like pattern, where node status changes trigger updates throughout the system.

### 7.5 Strategy Pattern

Different agents implement different strategies for task execution, and can be swapped based on configuration.

## 8. Configuration System

The system is highly configurable through a hierarchical configuration structure specified at runtime:

- Global settings (language, model choices)
- Task-type-specific settings (prompts, parameters)
- Action-specific settings (execution strategies)

This allows for customization of the system behavior without code changes.

## 9. Caching System

The system implements multiple caching mechanisms:

- LLM response caching to avoid redundant API calls
- Search result caching to minimize external service usage
- Task state caching for persistence and recovery

## 10. Conclusion

WriteHERE's architecture embodies a sophisticated approach to AI writing through its hierarchical, recursive, and heterogeneous planning mechanisms. The clean separation of concerns between task representation (graph), execution logic (engine), and execution strategies (agents) enables a flexible system that can adapt to different writing tasks.

The core innovation lies in how the system:
1. Recursively decomposes complex writing tasks
2. Dynamically plans and adapts during execution
3. Seamlessly integrates different types of tasks (composition, retrieval, reasoning)
4. Provides visibility into the writing process through its visualization system

This architectural design enables the system to handle complex writing tasks that would be challenging for traditional, non-recursive approaches. 