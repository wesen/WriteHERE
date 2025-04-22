# Event Logging Context Extension

## Overview

This document outlines potential attributes for the `ExecutionContext` object, designed to enhance the event logging system by passing down relevant data through the execution flow. The goal is to provide richer context for events emitted at various stages.

The `ExecutionContext` is immutable. The `with_` method creates _new_ context instances with updated information, allowing for scoped context augmentation without modifying the original context passed down the call stack.

## Attributes for `ExecutionContext` (Implemented & Potential)

This section lists attributes considered for the `ExecutionContext`. Attributes marked with (\*) were implemented in the context object itself.

1.  **`step` (\*)**: `Optional[int]`

    - **Purpose**: Tracks the current global execution step number.
    - **Scope**: Global for a run step.
    - **Propagation**: Set initially in `GraphRunEngine.forward_one_step_not_parallel`. Passed down the call stack.
    - **Event Enrichment**: Added to payloads by `_create_event` if not already present. Essential for sequencing.

2.  **`node_id` (\*)**: `Optional[str]`

    - **Purpose**: Uniquely identifies the primary node associated with the current execution context.
    - **Scope**: Node-specific.
    - **Propagation**: Set initially in `GraphRunEngine.forward_one_step_not_parallel`. Added/updated using `ctx.with_` in `AbstractNode.do_action`, `AbstractNode.do_exam`, `AbstractNode.plan2graph`.
    - **Event Enrichment**: Added by `_create_event`. Crucial for associating events like LLM calls or tool usage back to the responsible node.

3.  **`task_type` (\*)**: `Optional[str]`

    - **Purpose**: Provides context about the type of task the current node represents (e.g., "COMPOSITION", "REASONING", "RETRIEVAL").
    - **Scope**: Node-specific.
    - **Propagation**: Set initially in `GraphRunEngine.forward_one_step_not_parallel`. Added/updated using `ctx.with_` alongside `node_id`.
    - **Event Enrichment**: Added by `_create_event`. Useful for filtering/analyzing events based on the kind of work being done.

4.  **`action_name` (\*)**: `Optional[str]`

    - **Purpose**: Identifies the specific action being performed within a node's execution step (e.g., "plan", "execute", "prior_reflect").
    - **Scope**: Action-specific within a node's step.
    - **Propagation**: Added using `ctx.with_` in `AbstractNode.next_action_step` before calling `do_action`.
    - **Event Enrichment**: Added by `_create_event`. Relevant for `node_result_available` and associating LLM/Tool events with the specific node action that triggered them.

5.  **`node_status` (\*)**: `Optional[str]`

    - **Purpose**: Logs the status of the node _before_ the current action starts.
    - **Scope**: Action-specific within a node's step.
    - **Propagation**: Added using `ctx.with_` in `AbstractNode.next_action_step`.
    - **Event Enrichment**: Added by `_create_event`. Provides context for why an action is running (e.g., action 'plan' runs when status is 'PLANNING').

6.  **`node_next_status` (\*)**: `Optional[str]`

    - **Purpose**: Logs the status the node is expected to transition to _after_ the current action completes successfully.
    - **Scope**: Action-specific within a node's step.
    - **Propagation**: Added using `ctx.with_` in `AbstractNode.next_action_step`.
    - **Event Enrichment**: Added by `_create_event`. Helps understand the intended outcome or transition of an action.

7.  **`task_goal` (\*)**: `Optional[str]`

    - **Purpose**: Logs the objective of the task associated with the current node.
    - **Scope**: Node-specific.
    - **Propagation**: Set initially in `GraphRunEngine.forward_one_step_not_parallel`. Passed down implicitly through `ctx` to subsequent calls.
    - **Event Enrichment**: Added by `_create_event`. Provides direct insight into the purpose of the node's activity in relevant events.

8.  **`agent_class` (\*)**: `Optional[str]`

    - **Purpose**: Identifies the agent class responsible for an LLM call or a specific action involving an agent.
    - **Scope**: Agent/Action-specific.
    - **Propagation**: Added using `ctx.with_` in agent methods like `Agent.call_llm` and potentially within agent `forward` methods before invoking tools/actions. Passed down to event emitters.
    - **Event Enrichment**: Added by `_create_event`. Useful for analyzing the behavior or performance of different agent implementations, especially for LLM and Tool events.

9.  **`parent_node_ids`**: `Optional[List[str]]` (Not Implemented in Context)
    - **Purpose**: Tracks the hashkeys of the parent nodes for dependency analysis.
    - **Scope**: Graph structure specific.
    - **Propagation (Potential)**: This information is specific to individual nodes rather than the broader execution context. Adding it to the context object could be complex and redundant.
    - **Event Enrichment**: Relevant parent ID information is already included directly in the payloads of specific events like `node_created` (as `initial_parent_nids`) and `edge_added` (as `parent_node_id`). Therefore, adding it to the general `ExecutionContext` was deemed unnecessary for now.

## Context Propagation Summary (Based on Implemented Fields)

- **`GraphRunEngine.forward_one_step_not_parallel`**: Creates initial `ctx` with `step`, `node_id`, `task_type`, `task_goal`. Passes it to `next_action_step` and `forward_exam`.
- **`AbstractNode.next_action_step`**: Receives `ctx`. Creates enriched `action_step_ctx` with `action_name`, `node_status`, `node_next_status` (using `ctx.with_`). Passes `action_step_ctx` to `do_action`.
- **`AbstractNode.do_action`**: Receives `action_step_ctx`. Passes it to the agent's `forward` method and `emit_node_result_available`.
- **`AbstractNode.plan2graph`**: Receives `ctx`. Creates enriched `graph_ctx` (using `ctx.with_` adding current `node_id`, `task_type`). Passes `graph_ctx` down when creating child nodes and calling graph methods/events. (_Note: task_goal is passed implicitly if present in received ctx_).
- **`AbstractNode.do_exam`**: Receives `ctx`. Creates enriched `event_ctx` (using `ctx.with_` adding current `node_id`, `task_type`). Passes `event_ctx` to `emit_node_status_changed`. (_Note: task_goal is passed implicitly if present in received ctx_).
- **`Agent.forward` methods (e.g., `SimpleExecutor.forward`)**: Receives `ctx`. Passes it down to `call_llm`, helper methods (like `search_merge`), or other agent calls (e.g., `SearchAgent.chat`).
- **`Agent.call_llm`**: Receives `ctx`. Creates enriched `agent_ctx` (using `ctx.with_` adding `agent_class`). Passes `agent_ctx` to `emit_llm_call_started` and `emit_llm_call_completed`.
- **`SearchAgent.chat` (Example)**: Receives `ctx`. Should create enriched context adding `agent_class` before passing it to `ActionExecutor.__call__`. (_Implementation detail depends on SearchAgent structure_).
- **`ActionExecutor.__call__`**: Receives `ctx` (expected to include `agent_class` from caller). Passes it to `emit_tool_invoked` and `emit_tool_returned`.
- **`Graph.add_node`/`add_edge`**: Receives `ctx` (likely `graph_ctx`). Passes it to `emit_node_added`/`emit_edge_added`.
- **`event_bus._create_event`**: Receives `ctx`. Enriches event payload with fields from `ctx` (`step`, `node_id`, `task_type`, `action_name`, `node_status`, `node_next_status`, `task_goal`, `agent_class`) if not already present in the payload.

## Context Expansion and Contraction

- **Expansion**: Achieved using `ctx.with_(...)` when entering a more specific scope (e.g., node action, agent call, graph building). This creates a new, richer context object without altering the caller's context.
- **Contraction**: Happens implicitly when returning from a function call. The caller retains its original, less specific context object. This ensures context relevance is maintained throughout the call stack.
