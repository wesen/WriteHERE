# Additional Events for Enhanced Graph Planning Visibility

## Overview

This document describes additional events to enhance visibility into the agent's execution, particularly focusing on run lifecycle, LLM interactions, graph planning, node execution, and memory management. For each event type, we detail:

1. The event schema
2. Where to emit the event
3. How to gather the required data
4. Implementation considerations

## 1. Run Lifecycle Events

### 1.1 `run_started` (Implemented)

**Purpose**: Signals the start of a new agent run with initial configuration.

**Schema**:

```json
{
  "event_type": "run_started",
  "payload": {
    "input_data": "...", // e.g., input filename
    "config": { // Simplified config based on args
      "model": "...",
      "engine_backend": "...",
      "start": null | int,
      "end": null | int,
      "today_date": "..."
    },
    "run_mode": "report|story|...",
    "timestamp_utc": "..." // ISO 8601 format
  },
  "run_id": "agent-run-uuid" // Added implicitly by event bus
}
```

**Implementation Points**:

- **Emission**: In `recursive/main.py`, after parsing `args` and generating/setting the `current_run_id`.
- **Data Sources**:
  - `input_data`: `args.filename`
  - `config`: Dictionary constructed from `args.model`, `args.engine_backend`, `args.start`, `args.end`, `args.today_date`.
  - `run_mode`: `args.mode`
  - `timestamp_utc`: `datetime.now(timezone.utc)`
  - `run_id`: `current_run_id` (passed explicitly to emitter, added to event by `_create_event`)

### 1.2 `run_finished`

**Purpose**: Signals successful completion of an agent run with summary statistics.

**Schema**:

```json
{
  "event_type": "run_finished",
  "payload": {
    "total_steps": 42,
    "duration_seconds": 123.45,
    "total_nodes": 15,
    "total_llm_calls": 30,
    "total_tool_calls": 10,
    "token_usage_summary": {
      "total_prompt_tokens": 5000,
      "total_completion_tokens": 2000
    },
    "node_statistics": {
      "total_created": 15,
      "total_completed": 15,
      "by_type": {
        "PLAN_NODE": 5,
        "EXECUTE_NODE": 10
      }
    }
  }
}
```

**Implementation Points**:

- **Emission**: In `recursive/engine.py`, at the end of the main execution loop
- **Data Sources**:
  - Engine's internal counters for steps
  - Start time stored from `run_started`
  - Accumulated token usage from LLM calls
  - Node statistics from graph state

### 1.3 `run_error`

**Purpose**: Signals an unrecoverable error during run execution.

**Schema**:

```json
{
  "event_type": "run_error",
  "payload": {
    "error_type": "LLMError|ToolError|GraphError",
    "error_message": "...",
    "stack_trace": "...",
    "node_id": "uuid", // if error occurred in node
    "step": 42, // if error occurred during step
    "context": {
      // Additional context about the error state
      "last_successful_step": 41,
      "active_nodes": ["uuid1", "uuid2"],
      "last_event_type": "llm_call_started"
    }
  }
}
```

**Implementation Points**:

- **Emission**:
  - Main try/catch block in `recursive/main.py`
  - Error handling in `recursive/engine.py`
  - Node execution error handlers
- **Data Sources**:
  - Exception information
  - Current execution context
  - Engine state at time of error

## 2. LLM Interaction Events

### 2.1 `prompt_template_rendered`

**Purpose**: Captures the inputs and output of prompt template rendering.

**Schema**:

```json
{
  "event_type": "prompt_template_rendered",
  "payload": {
    "template_name": "plan_node|execute_node|reflect",
    "template_vars": {
      "goal": "...",
      "context": "...",
      "history": "...",
      "parent_results": [...],
      "constraints": {...}
    },
    "rendered_prompt": "...",
    "node_id": "uuid",
    "template_version": "1.0"
  }
}
```

**Implementation Points**:

- **Emission**: In `recursive/agent/base.py`, before `call_llm()`
- **Data Sources**:
  - Template name from agent class
  - Variables from agent's prepare_prompt method
  - Node context from execution context

### 2.2 `llm_response_parsed`

**Purpose**: Captures the structured data extracted from LLM responses.

**Schema**:

```json
{
  "event_type": "llm_response_parsed",
  "payload": {
    "node_id": "uuid",
    "parser_type": "plan|execution|reflection",
    "raw_response": "...",
    "parsed_data": {
      // Structured data extracted from response
      "steps": [...],
      "reasoning": "...",
      "dependencies": [...]
    },
    "parsing_duration_ms": 123,
    "parsing_method": "regex|json|structured",
    "validation_results": {
      "is_valid": true,
      "errors": [],
      "warnings": []
    }
  }
}
```

**Implementation Points**:

- **Emission**: In agent classes after parsing LLM response
  - `PlanAgent.forward()` for plan parsing
  - `ExecuteAgent.forward()` for execution results
  - `ReflectAgent.forward()` for reflection analysis
- **Data Sources**:
  - Raw LLM response from `call_llm()`
  - Parser-specific validation results
  - Timing information from parsing process

## 3. Graph Planning Events

### 3.1 `plan_parsing_started`

**Purpose**: Signals the start of plan parsing from LLM response.

**Schema**:

```json
{
  "event_type": "plan_parsing_started",
  "payload": {
    "node_id": "uuid",
    "raw_plan": "...",
    "parent_node_ids": ["uuid1", "uuid2"],
    "parsing_config": {
      "allow_empty_dependencies": false,
      "max_depth": 5,
      "validation_rules": [...]
    }
  }
}
```

**Implementation Points**:

- **Emission**: Beginning of `AbstractNode.plan2graph()`
- **Data Sources**:
  - Raw plan from node's plan result
  - Parent nodes from current graph state
  - Configuration from node settings

### 3.2 `plan_validation_result`

**Purpose**: Records the results of validating a parsed plan.

**Schema**:

```json
{
  "event_type": "plan_validation_result",
  "payload": {
    "node_id": "uuid",
    "is_valid": true,
    "validation_errors": [],
    "warnings": [],
    "num_steps": 5,
    "detected_dependencies": ["1.1", "1.2"],
    "validation_details": {
      "circular_deps_check": "passed",
      "depth_limit_check": "passed",
      "dependency_format_check": "warning"
    }
  }
}
```

**Implementation Points**:

- **Emission**: After plan validation in `AbstractNode.plan2graph()`
- **Data Sources**:
  - Validation results from plan parser
  - Dependency analysis results
  - Plan structure analysis

### 3.3 `dependency_resolution`

**Purpose**: Records how node dependencies were resolved to actual node IDs.

**Schema**:

```json
{
  "event_type": "dependency_resolution",
  "payload": {
    "node_id": "uuid",
    "raw_dependencies": ["1.1", "1.2"],
    "resolved_node_ids": ["uuid1", "uuid2"],
    "unresolved_deps": [],
    "resolution_strategy": "exact|fuzzy|inferred",
    "resolution_details": {
      "1.1": {
        "matched_node": "uuid1",
        "match_confidence": 1.0,
        "alternative_matches": []
      }
    }
  }
}
```

**Implementation Points**:

- **Emission**: During dependency resolution in `Graph.add_node()`
- **Data Sources**:
  - Raw dependencies from plan
  - Node mapping from graph state
  - Resolution algorithm results

## 4. Node Execution Flow Events

### 4.1 `node_execution_started`

**Purpose**: Provides detailed information about node execution start.

**Schema**:

```json
{
  "event_type": "node_execution_started",
  "payload": {
    "node_id": "uuid",
    "node_type": "PLAN|EXECUTE",
    "task_goal": "...",
    "expected_actions": ["plan", "execute", "reflect"],
    "parent_results": {
      "uuid1": "summary1",
      "uuid2": "summary2"
    },
    "execution_context": {
      "available_tools": [...],
      "constraints": {...},
      "memory_snapshot": {...}
    }
  }
}
```

**Implementation Points**:

- **Emission**: Start of `AbstractNode.do_action()`
- **Data Sources**:
  - Node metadata
  - Parent node results
  - Current execution context

### 4.2 `node_execution_finished`

**Purpose**: Records comprehensive results of node execution.

**Schema**:

```json
{
  "event_type": "node_execution_finished",
  "payload": {
    "node_id": "uuid",
    "execution_path": ["plan", "execute", "reflect"],
    "total_duration_seconds": 45.6,
    "result_summary": "...",
    "token_usage": {
      "prompt_tokens": 1000,
      "completion_tokens": 500
    },
    "tool_usage": {
      "search": 2,
      "calculator": 1
    },
    "state_transitions": [
      {
        "from_state": "PLANNING",
        "to_state": "EXECUTING",
        "timestamp": "..."
      }
    ]
  }
}
```

**Implementation Points**:

- **Emission**: End of `AbstractNode.do_action()`
- **Data Sources**:
  - Accumulated execution data
  - Token usage from LLM calls
  - Tool usage from action executor
  - State transition history

## 5. Memory/Context Events

### 5.1 `context_snapshot`

**Purpose**: Provides periodic snapshots of execution context state.

**Schema**:

```json
{
  "event_type": "context_snapshot",
  "payload": {
    "step": 42,
    "active_nodes": ["uuid1", "uuid2"],
    "pending_nodes": ["uuid3"],
    "completed_nodes": ["uuid4"],
    "memory_usage": {
      "num_stored_results": 10,
      "total_tokens": 5000,
      "cached_embeddings": 100
    },
    "resource_usage": {
      "total_tokens_used": 50000,
      "total_api_calls": 100,
      "execution_time_seconds": 300
    }
  }
}
```

**Implementation Points**:

- **Emission**:
  - Periodically in `GraphRunEngine.forward_one_step_not_parallel()`
  - After significant state changes
  - On memory cleanup events
- **Data Sources**:
  - Engine state
  - Memory manager statistics
  - Resource usage counters

## Implementation Strategy

1. **Add Event Types**:

   - Add new event types to `EventType` enum
   - Create payload schemas for each event type
   - Update event validation logic

2. **Enhance Context Object**:

   - Add fields needed for new events
   - Ensure context propagation to all emission points

3. **Implement Emission Points**:

   - Add event emission calls at identified points
   - Ensure all required data is available
