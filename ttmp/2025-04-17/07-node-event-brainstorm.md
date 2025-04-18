# Brainstorm: Potential Node/Graph Event Types

Based on analysis of `recursive/node/abstract.py` and `recursive/graph.py`, here are potential new event types to provide more granular tracking of the task graph lifecycle beyond just `node_status_changed`.

## Potential New Event Types

### 1. `node_created`

- **Description**: Emitted when a new `AbstractNode` instance is initialized, typically within the `plan2graph` method of its outer node, or at the start for the root node.
- **Potential Emission Point**: End of `AbstractNode.__init__()`.
- **Purpose**: Track the creation of individual task nodes, capturing their initial configuration and position in the hierarchy.
- **Potential Payload**:
  ```json
  {
    "event_type": "node_created",
    "payload": {
      "node_id": "new-node-uuid-string", // The hashkey
      "node_nid": "1.2", // The human-readable NID
      "node_type": "PLAN_NODE" | "EXECUTE_NODE",
      "task_type": "COMPOSITION" | "REASONING" | "RETRIEVAL",
      "task_goal": "Goal description...",
      "layer": 2,
      "outer_node_id": "outer-node-uuid-string", // Hashkey of the node whose inner_graph this belongs to
      "root_node_id": "root-node-uuid-string",
      "initial_parent_nids": ["1.1", "0.3"] // NIDs from the raw plan
    }
  }
  ```

### 2. `plan_received`

- **Description**: Emitted when a node receives the raw plan (typically from an LLM planning agent) before it starts converting it into its inner graph structure.
- **Potential Emission Point**: Beginning of `AbstractNode.plan2graph()`.
- **Purpose**: Mark the availability of a raw plan and capture the planner's output before graph construction.
- **Potential Payload**:
  ```json
  {
    "event_type": "plan_received",
    "payload": {
      "node_id": "planning-node-uuid-string", // Node that received the plan
      "raw_plan": [
        /* List of task dicts from planner */
      ],
      "planner_agent_class": "PlannerAgentName" // If available
    }
  }
  ```

### 3. `inner_graph_built`

- **Description**: Emitted after a node has successfully processed a `raw_plan` and constructed its `inner_graph`.
- **Potential Emission Point**: End of `AbstractNode.plan2graph()`.
- **Purpose**: Signal that a node's sub-task structure and dependencies are defined and available.
- **Potential Payload**:
  ```json
  {
    "event_type": "inner_graph_built",
    "payload": {
      "node_id": "outer-node-uuid-string", // Node whose inner graph was built
      "inner_graph_nodes": [
        { "node_id": "inner-node-1-uuid", "nid": "1.1", "goal": "..." },
        { "node_id": "inner-node-2-uuid", "nid": "1.2", "goal": "..." }
      ],
      "inner_graph_edges": [
        { "parent_id": "inner-node-1-uuid", "child_id": "inner-node-2-uuid" }
      ]
    }
  }
  ```

### 4. `node_result_available`

- **Description**: Emitted when a node's final result is computed or becomes available, likely when it transitions to the `FINISH` state.
- **Potential Emission Point**: Potentially after the result is set in `do_action`, or tied to the transition to `FINISH` status.
- **Purpose**: Indicate that a node has completed its primary task and its output can be consumed.
- **Potential Payload**:
  ```json
  {
    "event_type": "node_result_available",
    "payload": {
      "node_id": "node-uuid-string",
      "action_name": "execute" | "final_aggregate" | ..., // Action that produced the final result
      "result_summary": "..." // Potentially truncated or summarized result
      // Maybe include full result if feasible?
    }
  }
  ```

## Considerations

- **Granularity**: Events like `node_added_to_graph` and `edge_added_to_graph` (emitted from `Graph.add_node`/`add_edge` within `plan2graph`) could offer finer detail but might be too noisy. `inner_graph_built` provides a summary after the structure stabilizes.
- **Payload Size**: Including full raw plans or graph structures could make events large. Summaries or references might be needed.
- **Context**: Ensure relevant context (like `run_id`, `step` if applicable) is included, similar to existing events.
