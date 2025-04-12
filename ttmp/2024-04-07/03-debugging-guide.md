# WriteHERE Recursive Engine Debugging Guide

This guide provides a detailed walkthrough for debugging the WriteHERE recursive engine, focusing on key components and execution flow.

## 1. Launch Configuration

Add this configuration to your `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug WriteHERE Engine",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/recursive/engine.py",
      "args": [
        "--filename",
        "../test_data/qa_test.jsonl",
        "--output-filename",
        "project/qa/example_claude/test_output/result.jsonl",
        "--done-flag-file",
        "project/qa/example_claude/test_output/done.txt",
        "--model",
        "claude-3-5-sonnet-20241022",
        "--engine-backend",
        "google",
        "--mode",
        "report"
      ],
      "console": "integratedTerminal",
      "justMyCode": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

## 2. Key Breakpoints

### 2.1 Task Initialization

```python
# recursive/engine.py:report_writing (line ~450)
# Breakpoint 1: Task initialization and configuration
root_node = RegularDummyNode(
    config = config,
    nid = "",
    node_graph_info = {...},
    task_info = {...}
)

# Values to examine:
- config: Task configuration including LLM settings and prompts
- task_info: Initial task goal and parameters
```

### 2.2 Graph Execution Flow

```python
# recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel (line ~150)
# Breakpoint 2: Main execution loop
need_next_step_node = self.find_need_next_step_nodes(single=True)

# Values to examine:
- need_next_step_node.status: Current node status
- need_next_step_node.task_str(): Task description
- self.memory.article: Current accumulated article
```

### 2.3 Node State Transitions

```python
# recursive/graph.py:AbstractNode.do_exam (line ~350)
# Breakpoint 3: Node state transition logic
def do_exam(self, verbose):
    if not self.is_suspend:
        raise NotImplementedError()

# Values to examine:
- self.status: Current status
- self.status_exam_mapping: Available transitions
- self.node_graph_info: Node context
```

### 2.4 Task Planning

```python
# recursive/graph.py:RegularDummyNode.plan (line ~600)
# Breakpoint 4: Task planning and decomposition
def plan(self, agent, memory, *args, **kwargs):
    result = agent.forward(self, memory, *args, **kwargs)

# Values to examine:
- self.raw_plan: Generated plan structure
- self.inner_graph: Task decomposition graph
```

### 2.5 Memory Updates

```python
# recursive/memory.py (estimated line ~100)
# Breakpoint 5: Memory state management
def update_infos(self, nodes):
    # Update internal state
    self.article = self._compute_article()

# Values to examine:
- self.collected_info: Cached node information
- self.article: Current article state
```

## 3. Debugging Workflow

### 3.1 Task Graph Construction

1. Start at Breakpoint 1
2. Examine `config` structure for task settings
3. Step through `RegularDummyNode` initialization
4. Watch `node_graph_info` construction

### 3.2 Execution Flow

1. Set Breakpoint 2
2. Monitor node selection in `find_need_next_step_nodes`
3. Track state transitions through `forward_exam`
4. Observe memory updates

### 3.3 Node State Machine

1. Use Breakpoint 3
2. Watch state transitions:
   - NOT_READY → READY
   - READY → PLAN_DONE
   - DOING → FINAL_TO_FINISH
   - FINAL_TO_FINISH → FINISH

### 3.4 Task Planning and Decomposition

1. Break at Breakpoint 4
2. Examine plan generation
3. Watch graph construction in `plan2graph`
4. Monitor task dependencies

## 4. Key Data Structures to Watch

### 4.1 Node Structure

```python
node = {
    'nid': str,                    # Node ID
    'hashkey': str,                # UUID
    'status': TaskStatus,          # Current state
    'node_type': NodeType,         # PLAN_NODE or EXECUTE_NODE
    'task_info': dict,             # Task parameters
    'inner_graph': Graph,          # Subtask graph
    'result': dict                 # Execution results
}
```

### 4.2 Memory State

```python
memory = {
    'root_node': Node,             # Root task node
    'article': str,                # Generated content
    'collected_info': dict,        # Node cache
    'format': str,                 # Output format
}
```

### 4.3 Graph Structure

```python
graph = {
    'graph_edges': dict,           # Node dependencies
    'nid_list': list,             # Node IDs
    'node_list': list,            # Node objects
    'topological_task_queue': list # Execution order
}
```

## 5. Common Issues to Watch For

1. **State Transition Errors**

   - Check `status_exam_mapping` conditions
   - Verify parent node completion
   - Monitor dependency resolution

2. **Memory Management**

   - Watch for memory leaks in cache
   - Monitor article concatenation
   - Check info collection efficiency

3. **Task Decomposition**

   - Validate plan structure
   - Check dependency cycles
   - Monitor task atomicity

4. **LLM Integration**
   - Verify prompt construction
   - Check response parsing
   - Monitor cache hits/misses

## 6. Logging Tips

Enable detailed logging by adding:

```python
from loguru import logger
logger.add("debug.log", format="{time} {level} {message}", level="DEBUG")
```

Key log points:

- Node state transitions
- Task execution steps
- Memory updates
- Graph modifications

## 7. Performance Monitoring

Watch for:

1. Cache efficiency in `recursive/cache.py`
2. Memory growth in long-running tasks
3. Graph traversal performance
4. LLM response times

## 8. Next Steps

1. Start with a simple task to understand the basic flow
2. Progress to more complex tasks with multiple subtasks
3. Experiment with different task types (write/think/search)
4. Test error handling and recovery mechanisms

Remember to check the engine logs in `project/qa/example_claude/test_output/` for execution details.
