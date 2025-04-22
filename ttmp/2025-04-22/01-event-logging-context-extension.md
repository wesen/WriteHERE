# Event Logging Context Extension

## Overview

This document outlines the attributes that can be added to the `ExecutionContext` to enhance the event logging system. These attributes will help in passing down accumulated data to subevents emitted, such as the current node ID, task type, and other relevant metadata.

## Attributes to Add to `ExecutionContext`

1. **Node ID (`node_id`)**:

   - **Purpose**: To uniquely identify the node associated with the current execution context.
   - **Scope**: Should be included in all contexts where node-specific events are emitted.
   - **Call Sites**:
     - `emit_step_started` and `emit_step_finished` in `GraphRunEngine.forward_one_step_not_parallel`.
     - `emit_node_status_changed`, `emit_node_created`, `emit_node_result_available` in `AbstractNode` methods.
     - `emit_llm_call_started` and `emit_llm_call_completed` in `Agent.call_llm`.
     - `emit_tool_invoked` and `emit_tool_returned` in `ActionExecutor.__call__`.

2. **Task Type (`task_type`)**:

   - **Purpose**: To provide context about the type of task being executed (e.g., COMPOSITION, REASONING, RETRIEVAL).
   - **Scope**: Useful for understanding the nature of the task at various stages of execution.
   - **Call Sites**:
     - `emit_node_created` and `emit_node_result_available` in `AbstractNode` methods.
     - `emit_llm_call_started` and `emit_llm_call_completed` in `Agent.call_llm`.

3. **Task Goal (`task_goal`)**:

   - **Purpose**: To log the objective of the task, providing insight into the purpose of the node's actions.
   - **Scope**: Should be included in contexts where task-specific events are emitted.
   - **Call Sites**:
     - `emit_step_started` in `GraphRunEngine.forward_one_step_not_parallel`.
     - `emit_node_created` in `AbstractNode.__init__`.

4. **Parent Node IDs (`parent_node_ids`)**:

   - **Purpose**: To track dependencies and relationships between nodes.
   - **Scope**: Useful for events related to graph construction and node addition.
   - **Call Sites**:
     - `emit_node_added` and `emit_edge_added` in `Graph` methods.

5. **Execution Step (`step`)**:

   - **Purpose**: To track the current step in the execution process.
   - **Scope**: Essential for all events to understand the sequence of operations.
   - **Call Sites**:
     - Already included in most emit functions via `ctx`.

6. **Agent Class (`agent_class`)**:

   - **Purpose**: To identify the agent responsible for executing a task or making an LLM call.
   - **Scope**: Relevant for LLM-related events.
   - **Call Sites**:
     - `emit_llm_call_started` and `emit_llm_call_completed` in `Agent.call_llm`.


## Context Expansion and Contraction

- **Expansion**: When entering a new scope (e.g., a new node or task), the context should be expanded to include additional attributes relevant to that scope.
- **Contraction**: Upon exiting the scope, the context should be contracted to remove attributes that are no longer relevant, ensuring that only pertinent data is passed to subsequent events.
