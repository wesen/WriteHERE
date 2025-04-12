# WriteHERE Node System and State Machine

## Introduction to WriteHERE

WriteHERE is a recursive task planning and execution framework that enables LLMs to generate well-structured documents. The system breaks down complex writing tasks into manageable subtasks using a hierarchical approach similar to how human writers work.

This guide focuses on the **Node System** and its **State Machine**, which form the backbone of the WriteHERE architecture.

## Node System Overview

In WriteHERE, each writing task is represented as a `Node` in a graph structure. Nodes can be nested hierarchically, with parent nodes delegating work to child nodes in their "inner graph." This allows the system to decompose complex tasks into simpler ones.

There are two main types of nodes:

1. **PLAN_NODE**: Nodes that will be further decomposed into subtasks
2. **EXECUTE_NODE**: Atomic nodes that perform a single action (writing, reasoning, or retrieval)

## Node Data Structure

A node contains multiple important fields:

```python
node = {
    'nid': str,                    # Node ID (e.g., "1.2.3")
    'hashkey': str,                # UUID for unique identification
    'status': TaskStatus,          # Current execution state
    'node_type': NodeType,         # PLAN_NODE or EXECUTE_NODE
    'node_graph_info': {           # Graph context
        'outer_node': Node,        # Parent in hierarchy
        'root_node': Node,         # Top-level node
        'parent_nodes': [Node],    # Dependencies
        'layer': int               # Hierarchical depth
    },
    'task_info': {                 # Task details
        'goal': str,               # What to accomplish
        'task_type': str,          # write/think/search
        'length': str,             # For composition tasks
        'dependency': [str]        # IDs of dependencies
    },
    'inner_graph': Graph,          # Subtask graph
    'result': {                    # Execution results
        'plan': {...},             # From planning
        'execute': {...},          # From execution
        'final_aggregate': {...}   # From aggregation
    },
    'status_list': {               # State categories
        'silence': [TaskStatus],   # Inactive states
        'suspend': [TaskStatus],   # Paused states
        'activate': [TaskStatus]   # Active states
    }
}
```

## State Machine

The node system implements a state machine that controls the execution flow. Each node has a current `status` that determines what actions it can perform and when it can transition to another state.

### Task Status States

The key states a node can be in include:

- `NOT_READY`: Dependencies are not yet fulfilled
- `READY`: Ready to be processed
- `PLAN_DONE`: Planning phase is complete
- `DOING`: Executing subtasks
- `FINAL_TO_FINISH`: All subtasks completed, ready for aggregation
- `NEED_POST_REFLECT`: Needs reflection/verification
- `FINISH`: Task completed
- `FAILED`: Error occurred

### State Categories

States are grouped into categories that determine how the execution engine treats them:

- `silence`: Inactive states (not considered for execution)
- `suspend`: Paused states (checked for possible transitions)
- `activate`: Active states (ready for execution)

### State Transition Mappings

For each state, there's a mapping to potential next states and the conditions for transitioning:

```python
self.status_exam_mapping = {
    TaskStatus.NOT_READY: [
        (lambda node, *args, **kwargs: all(parent.status == TaskStatus.FINISH
            for parent in node.node_graph_info["parent_nodes"]), TaskStatus.READY)
    ],
    TaskStatus.PLAN_DONE: [
        (lambda node, *args, **kwargs: True, TaskStatus.DOING)
    ],
    TaskStatus.DOING: [
        (lambda node, *args, **kwargs: all(n.status == TaskStatus.FINISH
            for n in node.inner_graph.topological_task_queue), TaskStatus.FINAL_TO_FINISH)
    ],
    # ... other state transitions ...
}
```

### Action Mappings

For each active state, there's a mapping to the action that should be performed:

```python
self.status_action_mapping = {
    TaskStatus.READY: ("plan", lambda node, *args, **kwargs: True),
    TaskStatus.FINAL_TO_FINISH: ("final_aggregate", lambda node, *args, **kwargs: True),
    # ... other action mappings ...
}
```

## Debugging Node States

### Breakpoint 3: State Transitions

One of the most critical breakpoints for understanding the node system is in the state transition logic:

```python
# recursive/graph.py:AbstractNode.do_exam (around line ~350)
# Breakpoint 3: Node state transition logic

# --> SET BREAKPOINT HERE <--
def do_exam(self, verbose):
    # Check if the node is actually suspended
    if not self.is_suspend:
        raise NotImplementedError(...)

    if self.status in self.status_exam_mapping:
        # --> SET BREAKPOINT HERE <-- (Inside exam loop)
        for cond, next_status in self.status_exam_mapping[self.status]:
            if cond(self):  # Condition is met
                if verbose:
                    logger.info("Node Status Change: {} -> {}".format(self.status, next_status))
                self.status = next_status
                break
```

**Values to examine:**

- `self.status`: Current status
- `self.status_exam_mapping[self.status]`: List of (condition, next_status) pairs
- Step _into_ each `cond` lambda function to understand the exact transition logic
- `cond(self)`: The result of evaluating each condition function
- Parent node statuses: `[parent.status for parent in self.node_graph_info["parent_nodes"]]`
- Inner graph nodes (if any): `[node.status for node in self.topological_task_queue]`

### Key State Transitions to Watch

- `NOT_READY → READY`: When dependencies are fulfilled
- `READY → PLAN_DONE`: After planning completes
- `PLAN_DONE → DOING`: After plan reflection
- `DOING → FINAL_TO_FINISH`: When all subtasks complete
- `FINAL_TO_FINISH → NEED_POST_REFLECT`: After aggregation
- `NEED_POST_REFLECT → FINISH`: After verification

## Graph Structure

When a node has subtasks, they're organized in an inner graph:

```python
graph = {
    'graph_edges': {               # Node dependencies
        'nid1': [Node, Node],      # Child nodes by parent ID
        'nid2': [Node]             # ...
    },
    'nid_list': [str],             # List of all node IDs
    'node_list': [Node],           # List of all nodes
    'topological_task_queue': [Node], # Execution order
    'outer_node': Node             # Container node
}
```

The graph maintains a topological sorting of nodes to ensure dependencies are satisfied during execution.

## Common Node System Issues

### State Transition Issues

**Symptoms:**

- Tasks stuck in certain states
- Graph execution seems to halt
- Tasks executed in unexpected order

**Investigation approach:**

1. Break at the state transition breakpoint
2. For stuck nodes, examine:
   - Current state in `self.status`
   - Available transitions in `status_exam_mapping[self.status]`
   - Step into condition functions to see why they evaluate to False
   - State of dependencies and parent nodes
3. Check if nodes are in the expected state category:
   - `is_activate`: Ready for processing
   - `is_suspend`: Waiting for a condition
   - `is_silence`: Inactive

**Key questions:**

- Are dependency tasks completing successfully?
- Are condition functions evaluating as expected?
- Is the node in the right category for the main loop to find it?
- Are there tasks in error states?

## Visualization Tools

### Graph Visualization

```python
# Add temporarily to engine.py:forward_one_step_not_parallel after state updates
from recursive.utils.display import display_graph
display_graph(self.root_node.inner_graph, fn="debug_graph_{}.png".format(step_count))
```

### State Logging

```python
# Add to AbstractNode.do_exam
if self.status != next_status:
    logger.debug(f"Node {self.nid} state: {self.status.name} -> {next_status.name}")
    logger.debug(f"   Trigger condition: {cond.__code__.co_filename}:{cond.__code__.co_firstlineno}")
```

## Advanced Techniques

### Conditional Breakpoints

```python
# Break on unusual state transitions
# recursive/graph.py:AbstractNode.do_exam
condition: str(next_status) == 'TaskStatus.FAILED'

# Break when a specific node ID is processed
# recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel
condition: 'need_next_step_node and "1.2" in need_next_step_node.nid'
```

## Next Steps

- Review [Agent System](03-agent-system.md) to understand how actions are performed on nodes
- See [Memory and Context Management](04-memory-system.md) to learn how nodes share information
- Explore [Task Planning and Decomposition](05-task-planning.md) to understand how nodes are created
