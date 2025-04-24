# Understanding the Task Graph System in Recursive

## Overview

The task graph system in Recursive is a hierarchical structure that represents the decomposition of complex tasks into smaller, manageable subtasks. It's designed to track dependencies between tasks, manage their execution order, and maintain the state of task completion. This document explains how the graph works, what different components exist, and how they interact.

## Core Components

### 1. Nodes

Nodes are the fundamental building blocks of the task graph. Each node represents a task and has several key properties:

- `nid`: A hierarchical identifier (e.g., "1.2.3") that shows the node's position in the task hierarchy
- `hashkey`: A unique UUID for the node
- `task_info`: Contains task-specific information like:
  - `goal`: What the task aims to achieve
  - `task_type`: Type of task (COMPOSITION, REASONING, RETRIEVAL)
  - Other task-specific settings
- `node_type`: Either PLAN_NODE (can have children) or EXECUTE_NODE (leaf node)
- `status`: Current execution status (NOT_READY, READY, PLANNING, etc.)
- `inner_graph`: A Graph instance containing this node's subtasks

### 2. Graph Structure

The `Graph` class (`recursive/graph.py`) manages relationships between nodes:

```python
class Graph:
    def __init__(self, outer_node):
        self.graph_edges = {}  # parent.nid -> [child1, child2, ...]
        self.nid_list = []     # List of all node IDs
        self.node_list = []    # List of all nodes
        self.topological_task_queue = []  # Sorted execution order
        self.outer_node = outer_node  # Node that owns this graph
```

## Node Relationships

There are several types of relationships between nodes:

1. **Parent-Child (Dependencies)**

   - Represented by edges in the graph
   - A child node can only execute after all its parents complete
   - Example:

   ```python
   # Adding a dependency
   graph.add_edge(parent_node, child_node)
   ```

2. **Outer-Inner (Hierarchical)**

   - Each PLAN_NODE has an `inner_graph` containing its subtasks
   - The `outer_node` reference points back to the parent node
   - Creates a tree-like structure:

   ```
   Root Node
   ├── Inner Node 1 (Plan)
   │   ├── Subtask 1.1 (Execute)
   │   └── Subtask 1.2 (Execute)
   └── Inner Node 2 (Plan)
       └── Subtask 2.1 (Execute)
   ```

3. **Root-Node Path**
   - Every node maintains a path to the root node
   - Used for context and memory management
   - Example structure:
   ```python
   node.node_graph_info = {
       "outer_node": parent_node,
       "root_node": root_node,
       "layer": current_depth,
       "parent_nodes": [dependency1, dependency2]
   }
   ```

## Graph Building Process

The graph is built through a planning process:

1. **Plan Creation**

```python
def plan(self, agent, memory, ctx):
    # Agent generates a plan
    result = agent.forward(self, memory, ctx)
    self.raw_plan = result["result"]
    # Convert plan to graph structure
    self.plan2graph(raw_plan=self.raw_plan, ctx=ctx)
```

2. **Plan to Graph Conversion**

```python
def plan2graph(self, raw_plan, ctx):
    # Emit event that plan was received
    emit_plan_received(node_id=self.hashkey, raw_plan=raw_plan, ctx=ctx)

    # Create nodes for each task in plan
    for task in raw_plan:
        node = create_node(task)
        self.inner_graph.add_node(node)

    # Add dependencies between nodes
    for node in nodes:
        for parent_id in node.parent_nodes:
            self.inner_graph.add_edge(parent_node, node)

    # Sort nodes for execution
    self.inner_graph.topological_sort()
```

## Node States and Transitions

Nodes go through various states during execution:

1. **Initial States**

   - `NOT_READY`: Dependencies not met
   - `READY`: Ready for execution

2. **Planning States**

   - `PLANNING`: Creating subtasks
   - `PLANNING_POST_REFLECT`: Reviewing plan

3. **Execution States**
   - `DOING`: Currently executing
   - `FINAL_TO_FINISH`: Gathering results
   - `FINISH`: Task completed

Example state transition:

```python
# In RegularDummyNode
self.status_list = {
    TaskStatus.READY: [
        (lambda node, *args, **kwargs: True, TaskStatus.PLANNING)
    ],
    TaskStatus.DOING: [
        (
            lambda node, *args, **kwargs: all(
                inner_node.status == TaskStatus.FINISH
                for inner_node in node.topological_task_queue
            ),
            TaskStatus.FINAL_TO_FINISH,
        )
    ]
}
```

## Memory and Context

The graph system maintains context through:

1. **Memory Management**

   - Each node can access results from its dependencies
   - Memory is organized hierarchically:

   ```python
   memory.collect_node_run_info(node) -> {
       "same_graph_precedents": [...],  # Results from same level
       "upper_graph_precedents": [...]  # Results from higher levels
   }
   ```

2. **Execution Context**
   - Tracks current execution state
   - Passed down through the node hierarchy
   - Contains:
     - Current step number
     - Node IDs
     - Task types
     - Parent relationships

## Event System

The graph system emits events at key points:

1. **Node Events**

   - `node_created`: New node instantiated
   - `node_status_changed`: Node state transitions
   - `node_result_available`: Task completion

2. **Graph Events**

   - `node_added`: Node added to graph
   - `edge_added`: Dependency created
   - `inner_graph_built`: Subgraph construction complete

3. **Planning Events**
   - `plan_received`: Raw plan from agent
   - `step_started`/`step_finished`: Execution progress

## Best Practices

When working with the task graph:

1. **Node Creation**

   - Always set proper node types (PLAN vs EXECUTE)
   - Initialize with correct task_info and node_graph_info
   - Use unique nids within each graph level

2. **Dependencies**

   - Add all necessary dependencies before execution
   - Ensure no circular dependencies
   - Consider implicit dependencies (e.g., sequential COMPOSITION tasks)

3. **State Management**

   - Monitor node states through events
   - Handle state transitions appropriately
   - Use memory system for sharing results

4. **Error Handling**
   - Check for graph cycles
   - Validate node types and relationships
   - Monitor for stuck states

## Resources

Key files to review:

- `recursive/graph.py`: Core graph structure
- `recursive/node/abstract.py`: Base node implementation
- `recursive/engine.py`: Execution engine
- `recursive/memory.py`: Memory management
- `recursive/utils/event_bus.py`: Event system
