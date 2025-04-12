# WriteHERE Debugging Workflow

## Introduction to WriteHERE

WriteHERE is a recursive task planning and execution framework that uses large language models (LLMs) to break down complex writing tasks into manageable subtasks. With its sophisticated architecture involving nodes, agents, memory, and state machines, debugging the system requires a systematic approach.

This guide provides a comprehensive debugging workflow that integrates all the key components of the WriteHERE system into a coherent debugging strategy.

## Setting Up the Debugging Environment

### Launch Configuration

First, add this configuration to your `.vscode/launch.json`:

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

### Debugging Tools Setup

To enhance debugging capabilities, add these utility functions to your debugging toolkit:

```python
# debugging_utils.py

import logging
import time
from datetime import datetime
import json
from pprint import pformat
import os

logger = logging.getLogger(__name__)

def log_node_state(node, prefix=""):
    """Log the current state of a node and its inner graph."""
    logger.info(f"{prefix}Node {node.nid} ({node.node_type.name}) - Status: {node.status.name}")
    if hasattr(node, "inner_graph") and node.inner_graph:
        logger.info(f"  Inner graph has {len(node.inner_graph.node_list)} nodes:")
        for child in node.inner_graph.topological_task_queue:
            logger.info(f"    - {child.nid}: {child.status.name} - {child.task_info['goal'][:50]}...")

def inspect_memory(memory, node_hashkey=None):
    """Print key memory information for debugging."""
    logger.info(f"Current article length: {len(memory.article)} chars")
    logger.info(f"Cached node count: {len(memory.collected_info)}")
    if node_hashkey and node_hashkey in memory.collected_info:
        logger.info(f"Node info keys: {memory.collected_info[node_hashkey].keys()}")
        for key, value in memory.collected_info[node_hashkey].items():
            logger.info(f"  {key}: {type(value)} of size {len(str(value))}")

def save_execution_trace(trace, filename="execution_trace.json"):
    """Save execution trace to a file."""
    with open(filename, 'w') as f:
        json.dump(trace, f, indent=2)
    logger.info(f"Execution trace saved to {filename}")
```

## Progressive Debugging Workflow

The most effective way to debug WriteHERE is to follow a progressive approach, starting with the system configuration and gradually moving through the execution flow:

### 1. Understanding the Task and Configuration

**Breakpoint 1**: Engine initialization in `recursive/engine.py:report_writing`

```python
# --> SET BREAKPOINT HERE <--
root_node = RegularDummyNode(
    config = config,
    nid = "",
    node_graph_info = {...},
    task_info = {...}
)
```

**Investigation steps**:

1. Examine `config` structure:
   - Check `action_mapping` to see which agents handle which actions
   - Verify LLM parameters for different task types
   - Note prompt templates being used
2. Examine input parameters and the initial task goal
3. Step through `RegularDummyNode` initialization to understand state machine setup
4. Set up the execution trace collection (if needed):
   ```python
   # Add to GraphRunEngine.__init__
   self.execution_trace = []
   ```

### 2. Understanding the Main Execution Loop

**Breakpoint 2**: Main execution loop in `recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel`

```python
# --> SET BREAKPOINT HERE <-- (Node Selection)
need_next_step_node = self.find_need_next_step_nodes(single=True)
```

**Investigation steps**:

1. Step _into_ `find_need_next_step_nodes` to see how it traverses the graph
2. Watch which nodes are selected based on their status and type
3. Add trace collection if needed:
   ```python
   # Add before action execution
   self.execution_trace.append({
       'step': len(self.execution_trace),
       'node_id': need_next_step_node.nid,
       'status': need_next_step_node.status.name,
       'action': action_name,
       'task_type': need_next_step_node.task_type_tag if hasattr(need_next_step_node, 'task_type_tag') else None,
       'timestamp': datetime.now().isoformat()
   })
   ```

### 3. Following the Task Planning Process

**Breakpoint 3**: Agent selection in `recursive/agent/proxy.py:AgentProxy.proxy`

```python
# --> SET BREAKPOINT HERE <--
def proxy(self, action_name):
    agent_cls_name, agent_kwargs = self.config["action_mapping"][action_name]
```

**Breakpoint 4**: Planning agent in `recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward`

```python
# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
```

**Investigation steps**:

1. Verify the correct agent is selected for the "plan" action
2. Step through the planning agent's execution:
   - Step _into_ `_build_input` to see how the planning prompt is constructed
   - Examine the prompt sent to the LLM
   - Check the raw LLM response
   - Step _into_ `_parse_output` to see how the plan is parsed
3. Examine the resulting plan structure in `result["result"]`

### 4. Understanding Plan to Graph Conversion

**Breakpoint 5**: Plan to graph conversion in `recursive/graph.py:AbstractNode.plan2graph`

```python
# --> SET BREAKPOINT HERE <-- (Start of method)
def plan2graph(self, raw_plan):
```

**Investigation steps**:

1. Step through the node creation loop
2. Watch how dependencies are established between nodes
3. Examine the resulting graph structure:
   - `self.inner_graph.graph_edges`: Dependency relationships
   - `self.inner_graph.topological_task_queue`: Execution order

### 5. Tracing State Transitions

**Breakpoint 6**: State transitions in `recursive/graph.py:AbstractNode.do_exam`

```python
# --> SET BREAKPOINT HERE <--
def do_exam(self, verbose):
```

**Investigation steps**:

1. Watch state transitions after planning, execution, and aggregation
2. Step _into_ condition functions to understand transition logic
3. Add state change logging if needed:
   ```python
   # Add to AbstractNode.do_exam
   if self.status != next_status:
       logger.debug(f"Node {self.nid} state: {self.status.name} -> {next_status.name}")
       logger.debug(f"   Trigger condition: {cond.__code__.co_filename}:{cond.__code__.co_firstlineno}")
   ```

### 6. Examining Task Execution

**Breakpoint 7**: Execution agent in `recursive/agent/agents/regular.py:SimpleExcutor.forward`

```python
# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
```

**Investigation steps**:

1. Determine the task type (`task_type_tag`)
2. Follow the appropriate branch for the task type:
   - For `COMPOSITION`/`REASONING`: Check prompt construction, LLM call, and result parsing
   - For `RETRIEVAL`: Step _into_ search functions if applicable
3. Examine the execution result in `result["result"]`

### 7. Understanding Memory and Context

**Breakpoint 8**: Memory updates in `recursive/memory.py:Memory.update_infos`

```python
# --> SET BREAKPOINT HERE <-- (Start of method)
def update_infos(self, nodes):
```

**Breakpoint 9**: Node info collection in `recursive/memory.py:Memory.collect_node_run_info`

```python
# --> SET BREAKPOINT HERE <-- (Start of method)
def collect_node_run_info(self, node):
```

**Investigation steps**:

1. Watch how context is collected for each node
2. Examine the cached information in `self.collected_info`
3. Check article updates in `_compute_article`
4. Use the `inspect_memory` utility to analyze memory state

### 8. Observing Result Aggregation

**Breakpoint 10**: Aggregation agent in `recursive/agent/agents/regular.py:FinalAggregateAgent.forward`

```python
# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
```

**Investigation steps**:

1. Examine how subtask results are collected and formatted
2. Check the aggregation prompt sent to the LLM
3. Analyze the aggregated result
4. Watch the node transition to `FINISH` state after aggregation

## Targeted Debugging Scenarios

### 1. Debugging Task Decomposition Issues

**Symptoms**:

- Illogical or too granular task breakdowns
- Missing critical tasks
- Circular dependencies

**Investigation strategy**:

1. Set breakpoints in `UpdateAtomPlanningAgent._build_input` and `_parse_output`
2. Examine the planning prompt:
   - Are instructions clear?
   - Are constraints well-defined?
3. Check the LLM's plan response:
   - Is it following the expected format?
   - Are task dependencies logical?
4. Verify the plan2graph conversion:
   - Are all tasks included?
   - Are dependencies properly established?

**Potential solutions**:

- Adjust planning prompt to give clearer instructions
- Modify LLM parameters (reduce temperature for more predictable plans)
- Add validation to catch circular dependencies or other issues

### 2. Debugging Context Loss Between Tasks

**Symptoms**:

- Subtasks seem disconnected from parent tasks
- Information from dependencies isn't used effectively
- Content repetition or contradictions

**Investigation strategy**:

1. Set breakpoints in `Memory.collect_node_run_info` and `SimpleExcutor._build_input`
2. Check what context is being collected:
   - Are dependency results included?
   - Is parent context available?
3. Examine the prompt construction:
   - Is collected context being formatted properly for the LLM?
   - Is there a clear structure for using the context?

**Potential solutions**:

- Enhance context collection in memory methods
- Improve prompt templates to better utilize context
- Adjust context size limits if too much is being truncated

### 3. Debugging State Machine Issues

**Symptoms**:

- Tasks stuck in certain states
- Graph execution seems to halt
- Tasks executed in unexpected order

**Investigation strategy**:

1. Set breakpoints in `AbstractNode.do_exam` and `GraphRunEngine.forward_one_step_not_parallel`
2. For stuck nodes, check:
   - Current status and available transitions
   - Status of dependencies (parent nodes)
   - Status of subtasks (inner graph nodes)
3. Examine condition functions for state transitions

**Potential solutions**:

- Fix condition functions for state transitions
- Add additional logging to track state changes
- Check for tasks in error states

### 4. Debugging Aggregation Problems

**Symptoms**:

- Final output lacks coherence
- Some subtask results missing from output
- Poor synthesis of diverse information

**Investigation strategy**:

1. Set breakpoints in `FinalAggregateAgent.forward` and `memory.collect_inner_results`
2. Check inner result collection:
   - Are all subtask results being collected?
   - Are the results properly formatted?
3. Examine the aggregation prompt:
   - Are clear synthesis instructions provided?
   - Is enough context available for coherent integration?

**Potential solutions**:

- Improve the aggregation prompt template
- Enhance collection of subtask results
- Add post-aggregation validation

## Advanced Debugging Techniques

### 1. Graph Visualization

To visualize the task graph during debugging:

```python
# Add temporarily to engine.py:forward_one_step_not_parallel after state updates
from recursive.utils.display import display_graph
display_graph(self.root_node.inner_graph, fn=f"debug_graph_{step_count}.png")
```

### 2. Execution Tracing

To collect a detailed execution trace:

```python
# Add to GraphRunEngine.forward_one_step_not_parallel
if not hasattr(self, "execution_trace"):
    self.execution_trace = []

before_action = time.time()
action_name, action_result = need_next_step_node.next_action_step(self.memory, *action_args, **action_kwargs)
after_action = time.time()

self.execution_trace.append({
    "step": len(self.execution_trace),
    "timestamp": datetime.now().isoformat(),
    "node_id": need_next_step_node.nid,
    "node_type": need_next_step_node.node_type.name,
    "status_before": need_next_step_node.status.name,
    "action": action_name,
    "duration_s": after_action - before_action,
    "result_keys": list(action_result.keys()) if action_result else None
})

# At the end of execution, save the trace
if need_next_step_node is None:  # All done
    save_execution_trace(self.execution_trace, "execution_trace.json")
```

### 3. Conditional Breakpoints

Set conditional breakpoints to focus on specific scenarios:

```python
# Break only when planning a task with a specific keyword
# recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward
condition: '"introduction" in str(node.task_info["goal"]).lower()'

# Break on unusual state transitions
# recursive/graph.py:AbstractNode.do_exam
condition: str(next_status) == 'TaskStatus.FAILED'

# Break when a specific node ID is processed
# recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel
condition: 'need_next_step_node and "1.2" in need_next_step_node.nid'
```

### 4. Performance Monitoring

To monitor performance and detect bottlenecks:

```python
# Add to AgentBase.get_llm_output
before = time.time()
response = self._call_llm(prompt_kwargs, llm_args)
after = time.time()
if after - before > 5.0:  # Slow LLM call
    logger.warning(f"Slow LLM call in {self.__class__.__name__}: {after-before:.2f}s")
```

## Progressive Debugging Strategy

For most effective debugging, follow this progressive approach:

### 1. Start Simple, Then Expand

1. Begin with a simple, single-sentence generation task

   - Focus on the basic flow through the key breakpoints
   - Note the minimal planning structure

2. Progress to a multi-paragraph document

   - Observe hierarchical planning via recursive planning calls
   - Watch how higher-level tasks delegate to lower-level ones

3. Try a research-heavy task
   - Focus on search tasks and their integration
   - Note how retrieval results feed into reasoning and writing tasks

### 2. Isolate Components

When debugging specific issues:

1. Isolate the problematic component (planning, execution, aggregation)
2. Set targeted breakpoints around that component
3. Add temporary logging or visualization to collect more data
4. Create minimal reproduction cases when possible

### 3. Experiment with Configuration Changes

Try modifying `config` parameters to isolate issues:

- Change LLM temperature to see effects on creativity vs. consistency
- Modify action_mapping to use different agent implementations
- Adjust prompt templates to see effects on planning quality or execution

## Debugging Reference: Key Breakpoints

For quick reference, here are the key breakpoints ordered by typical execution flow:

1. **Engine Initialization**: `recursive/engine.py:report_writing` - Root node creation
2. **Main Loop**: `recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel` - Node selection and action execution
3. **Agent Selection**: `recursive/agent/proxy.py:AgentProxy.proxy` - Dynamic agent selection
4. **Planning Agent**: `recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward` - Task decomposition
5. **Plan to Graph**: `recursive/graph.py:AbstractNode.plan2graph` - Converting plans to graph structure
6. **State Transitions**: `recursive/graph.py:AbstractNode.do_exam` - Node state transitions
7. **Execution Agent**: `recursive/agent/agents/regular.py:SimpleExcutor.forward` - Task execution
8. **Memory Updates**: `recursive/memory.py:Memory.update_infos` - Context management
9. **Aggregation Agent**: `recursive/agent/agents/regular.py:FinalAggregateAgent.forward` - Result synthesis

## Conclusion: Tackling Complexity Through Structure

Debugging WriteHERE effectively requires understanding its structured, hierarchical approach:

1. **System Architecture**: The node system, agents, memory, and state machine
2. **Component Interactions**: How agents operate on nodes, how memory provides context
3. **Execution Flow**: The sequence of planning, execution, and aggregation

By following the debugging workflow outlined in this guide, you can navigate the complexity of the WriteHERE system and effectively troubleshoot issues at all levels of the architecture.

Don't forget to check the execution logs in `project/qa/example_claude/test_output/` for additional insights. Good luck with your debugging journey!
