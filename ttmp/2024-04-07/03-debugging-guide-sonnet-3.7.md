# WriteHERE Recursive Engine Debugging Guide

## Introduction: Understanding WriteHERE's Architecture

WriteHERE is a sophisticated recursive task planning and execution framework that uses large language models (LLMs) to decompose complex writing tasks into manageable subtasks. At its core, the system implements a hierarchical state machine where tasks are represented as nodes in a directed acyclic graph (DAG), with execution governed by state transitions and agent-based processing.

Unlike simpler LLM frameworks that use a single prompt for generation, WriteHERE employs a recursive decomposition strategy that mirrors how human writers plan and execute complex documents:

1. First breaking down a large writing task into logical sections
2. Then decomposing sections into specific research, reasoning, and writing tasks
3. Finally executing atomic tasks and synthesizing results upward

This guide is designed to help you understand this complex system by setting strategic breakpoints that reveal the internal mechanics during runtime. As you debug, you'll gain insights into how this recursive planning approach enables LLMs to produce more coherent, well-structured documents than simple prompt-based generation.

## The Big Picture: Tasks, Graphs, and Agents

Before diving into specific breakpoints, let's understand the core components:

1. **Node System**: Each writing task is represented as a `Node` in a graph structure. Nodes have:

   - A state (`TaskStatus`: NOT_READY, READY, DOING, etc.)
   - An action mapping (what function to call in each state)
   - A state transition mapping (when to change states)
   - Task information (goal, type, dependencies)
   - Potentially an inner graph of subtasks

2. **Agent System**: Agents are specialized modules that perform specific actions on nodes:

   - `UpdateAtomPlanningAgent`: Decomposes tasks into subtasks
   - `SimpleExecutor`: Actually performs the writing/thinking/searching
   - `FinalAggregateAgent`: Synthesizes results from subtasks
   - Reflection agents: Evaluate and potentially revise execution

3. **Memory System**: A shared state repository that:

   - Tracks the growing document
   - Caches node information
   - Provides context between executions

4. **Execution Flow**: The engine repeatedly:
   - Finds nodes ready for action
   - Performs the appropriate action via an agent
   - Updates states
   - Serializes progress

Now, let's explore how to debug this system effectively.

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

This configuration will launch the engine with a test question, using Claude as the LLM backend. The output will be saved to the specified directory, making it easy to inspect both the execution progress and final results.

## 2. Key Breakpoints for Understanding the System

### 2.1 Engine Initialization and Configuration

```python
# recursive/engine.py:report_writing (line ~540)
# Breakpoint 1: Task initialization and configuration
root_node = RegularDummyNode(
    config = config,
    nid = "",
    node_graph_info = {...},
    task_info = {...}
)
```

**What happens here:**
This is where the entire task execution begins. The system creates a root node representing the overall writing task. This root node will later contain an inner graph of subtasks.

**Values to examine:**

- `config`: A complex dictionary containing:
  - `action_mapping`: Maps state actions to agent implementations
  - `task_type2tag`: Defines writing/thinking/search task types
  - Task-specific configurations, including LLM parameters and prompts
- `task_info["goal"]`: The original writing prompt/question
- `node_type`: Should be `NodeType.PLAN_NODE` for the root

**Why it matters:**
The configuration structure determines everything about how tasks will be decomposed and executed. Examining it helps you understand which agents will be used for different actions, what LLM parameters are being used, and how the system is configured for the specific writing task.

### 2.2 Main Execution Loop

```python
# recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel (line ~150)
# Breakpoint 2: Main execution loop
need_next_step_node = self.find_need_next_step_nodes(single=True)

# After node identification, before execution:
self.memory.update_infos([need_next_step_node])

# Right before action execution:
action_name, action_result = need_next_step_node.next_action_step(self.memory, *action_args, **action_kwargs)
```

**What happens here:**
This is the heart of the execution engine. In each iteration:

1. The engine finds a node that's ready for action
2. Updates the memory with context relevant to that node
3. Executes the appropriate action on the node
4. Examines state transitions throughout the graph

**Values to examine:**

- `need_next_step_node` object:
  - `.status`: Current status (should be in `is_activate` list)
  - `.task_str()`: String representation of task
  - `.node_type`: Plan or execute node
  - `.task_info`: Task parameters
  - `.status_action_mapping`: What actions are valid
- `self.memory.article`: Current state of the article
- `action_name`: What action will be performed (plan/execute/update/etc.)

**Why it matters:**
This is where you'll see the step-by-step execution of the task graph. By watching this point over multiple iterations, you can observe how the engine selects tasks, what actions it performs, and how the document grows. It's the best place to get a feel for the overall execution flow.

### 2.3 Node State Examination and Transitions

```python
# recursive/graph.py:AbstractNode.do_exam (~line 350)
# Breakpoint 3: Node state transition logic
def do_exam(self, verbose):
    if self.status in self.status_exam_mapping:
        # Check if any exam condition is met
        for cond, next_status in self.status_exam_mapping[self.status]:
            if cond(self):
                if verbose:
                    logger.info("Node Status Change: {} -> {}".format(self.status, next_status))
                self.status = next_status
                break
```

**What happens here:**
This method evaluates whether a node should transition to a new state. It checks the conditions in `status_exam_mapping` for the current state and makes a transition if a condition is met.

**Values to examine:**

- `self.status`: Current status
- `self.status_exam_mapping[self.status]`: List of (condition, next_status) pairs
- The result of each condition function
- Parent node statuses: `[parent.status for parent in self.node_graph_info["parent_nodes"]]`
- Inner graph nodes (if any): `[node.status for node in self.topological_task_queue]`

**Why it matters:**
The state machine is the backbone of WriteHERE's execution logic. Understanding these transitions reveals how tasks progress from planning to execution to completion. Key transitions to watch:

- `NOT_READY → READY`: When dependencies are fulfilled
- `READY → PLAN_DONE`: After planning completes
- `PLAN_DONE → DOING`: After plan reflection
- `DOING → FINAL_TO_FINISH`: When all subtasks complete
- `FINAL_TO_FINISH → NEED_POST_REFLECT`: After aggregation
- `NEED_POST_REFLECT → FINISH`: After verification

### 2.4 Task Planning and Decomposition

```python
# recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward (line ~50)
# Breakpoint 4: Task planning and decomposition
def forward(self, node, memory, *args, **kwargs):
    # Entry point for planning

    # After prompt construction, before LLM call:
    prompt_kwargs = self._build_input(node, memory, *args, **kwargs)

    # After LLM call, before parsing:
    llm_response = self.get_llm_output(prompt_kwargs, llm_args)

    # After parsing the response:
    result = self._parse_output(llm_response, node, memory, *args, **kwargs)
```

**What happens here:**
This is where the magic of task decomposition happens. The `UpdateAtomPlanningAgent`:

1. Builds a planning prompt with context from the node's goal and dependencies
2. Asks the LLM to create a structured plan of subtasks
3. Parses the response into a task plan

**Values to examine:**

- `prompt_kwargs`: The context being provided to the LLM
  - Look for `"goal"`, `"previous_results"`, and any task-specific context
- `llm_response.content`: The raw LLM response
- `result["result"]`: The parsed plan structure

**Why it matters:**
This is the critical point where the LLM translates a high-level goal into concrete subtasks. The quality of this decomposition largely determines the overall effectiveness of the system. By examining the prompt and response, you can understand how the system "teaches" the LLM to create good plans and how the LLM structures its thinking about the task.

### 2.5 Plan to Graph Conversion

```python
# recursive/graph.py:AbstractNode.plan2graph (line ~420)
# Breakpoint 5: Converting a plan into a graph structure
def plan2graph(self, raw_plan):
    # Right after plan validation:
    if len(raw_plan) == 0:  # Atomic task
        # ...

    # During node creation loop:
    for task in raw_plan:
        # ...
        node = self.__class__(
            config = self.config,
            nid = task["id"],
            node_graph_info = node_graph_info,
            task_info = task_info,
            node_type = NodeType.PLAN_NODE if not task.get("atom") else NodeType.EXECUTE_NODE
        )
        nodes.append(node)
        id2node[task["id"]] = node

    # After dependency processing:
    self.inner_graph = Graph(self)
    self.inner_graph.build_graph(nodes)
```

**What happens here:**
This method takes the raw plan from the planning agent and constructs an actual graph of Node objects:

1. Creates Node objects for each subtask in the plan
2. Sets up node_graph_info with parent-child relationships
3. Creates a Graph object and populates it with the nodes
4. Builds edges representing dependencies

**Values to examine:**

- `raw_plan`: List of task dictionaries from the LLM
- `nodes`: The created Node objects
- `id2node`: Mapping from task IDs to Node objects
- `self.inner_graph`: The resulting Graph object
  - `.graph_edges`: Dictionary mapping node IDs to child nodes
  - `.topological_task_queue`: Nodes sorted in execution order

**Why it matters:**
This is where the LLM's plan becomes an executable structure. Understanding this conversion helps you see how task dependencies are enforced and how execution order is determined. Pay particular attention to:

- How atomic tasks are handled differently
- How implicit dependencies between composition tasks are added
- How the topological sorting ensures dependencies are satisfied

### 2.6 Task Execution

```python
# recursive/agent/agents/regular.py:SimpleExcutor.forward (line ~150)
# Breakpoint 6: Actual task execution
def forward(self, node, memory, *args, **kwargs):
    # Determine task type:
    task_type_tag = node.task_type_tag  # COMPOSITION, REASONING, or RETRIEVAL

    # For COMPOSITION or REASONING tasks (after prompt construction):
    prompt_kwargs = self._build_input(node, memory, *args, **kwargs)
    llm_response = self.get_llm_output(prompt_kwargs, llm_args)

    # For RETRIEVAL tasks (if configured to use react_agent):
    # [Complex search logic may occur here]

    # After execution and parsing:
    result = self._parse_output(llm_response, node, memory, *args, **kwargs)
```

**What happens here:**
This is where atomic tasks are actually executed by the LLM:

- For writing tasks (`COMPOSITION`), the LLM generates text content
- For reasoning tasks (`REASONING`), the LLM performs analysis
- For search tasks (`RETRIEVAL`), the system may perform web searches

**Values to examine:**

- `task_type_tag`: What kind of task is being executed
- `prompt_kwargs`: Context provided to the LLM
  - Look for task goal, constraints, and context from dependencies
- `llm_response.content`: Raw response from the LLM
- `result["result"]`: Parsed and structured output

**Why it matters:**
This is the "work" part of the system, where actual content is generated. Understanding this helps you see how the LLM receives context from parent tasks and dependencies, and how its output is structured for later use. The prompt construction is particularly important, as it shows how the system provides relevant context to the LLM.

### 2.7 Result Aggregation

```python
# recursive/agent/agents/regular.py:FinalAggregateAgent.forward (line ~300)
# Breakpoint 7: Synthesizing results from subtasks
def forward(self, node, memory, *args, **kwargs):
    # After retrieving results from inner nodes:
    inner_results = memory.collect_inner_results(node)

    # After building the aggregation prompt:
    prompt_kwargs = self._build_input(node, memory, inner_results=inner_results, *args, **kwargs)

    # After LLM aggregation:
    result = self._parse_output(llm_response, node, memory, *args, **kwargs)
```

**What happens here:**
When all subtasks of a plan node complete, this agent synthesizes their results:

1. Collects the results from all inner nodes
2. Constructs a prompt asking the LLM to synthesize them
3. Returns a coherent aggregated result

**Values to examine:**

- `inner_results`: Dictionary mapping node IDs to their results
- `prompt_kwargs`: The synthesis prompt
  - Look for how results are structured for the LLM
- `result["result"]`: The final synthesized output

**Why it matters:**
This is how the system turns multiple partial results into a coherent whole. It reveals how the system "teaches" the LLM to integrate diverse pieces of content. The prompt construction is key, as it shows how the system structures subtask results for effective synthesis.

### 2.8 Memory Updates

```python
# recursive/memory.py:Memory.update_infos (estimated line ~100)
# Breakpoint 8: Memory state management
def update_infos(self, nodes):
    # During info collection:
    for node in nodes:
        self.collect_node_run_info(node)

    # During article update:
    self.article = self._compute_article()
```

**What happens here:**
The Memory system updates its state based on recent node activity:

1. Collects and caches information from specified nodes
2. Updates the article by recursively traversing the node graph

**Values to examine:**

- `self.collected_info`: Cache of node information
- `self.article`: Current accumulated document
- Results of `_compute_article()`: How the article is assembled

**Why it matters:**
The Memory system maintains the growing document and provides context between task executions. Understanding it helps you see how information flows between nodes and how the final document is constructed piece by piece.

### 2.9 Agent Selection

```python
# recursive/agent/proxy.py:AgentProxy.proxy (line ~15)
# Breakpoint 9: Agent selection and instantiation
def proxy(self, action_name):
    if action_name not in self.config["action_mapping"]:
        logger.warning("Action {} not in action_mapping".format(action_name))
        return getattr(self, action_name)

    agent_name, agent_kwargs = self.config["action_mapping"][action_name]
    return getattr(self.agents[agent_name], action_name)
```

**What happens here:**
The `AgentProxy` acts as a factory, dynamically selecting and instantiating agents:

1. Looks up the agent name in the action mapping
2. Retrieves or creates the agent instance
3. Returns a bound method for the specified action

**Values to examine:**

- `action_name`: The action being requested (plan/execute/etc.)
- `self.config["action_mapping"][action_name]`: Agent class name and parameters
- `self.agents`: Dictionary of already instantiated agents

**Why it matters:**
The proxy pattern allows the system to dynamically wire different agents to different actions. By examining this process, you can understand how the system selects specialized agents for different tasks and how configuration controls the entire execution pipeline.

## 3. Debugging Workflow: A Progressive Approach

To effectively debug this complex system, follow this progressive workflow:

### 3.1 Understanding the Task and Configuration

1. Start at **Breakpoint 1** (Root Node Creation)
2. Examine `config` structure to understand:
   - Which agents are mapped to which actions
   - LLM parameters for different task types
   - Prompt templates being used
3. Note the initial task in `task_info["goal"]`
4. Step through `RegularDummyNode` initialization to see how the state machine is set up

### 3.2 Observing the Planning Process

1. Continue to first iteration of **Breakpoint 2** (Main Loop)
   - Root node should be in `READY` state
   - `action_name` should be `"plan"`
2. Step into the action to reach **Breakpoint 4** (Planning)
   - Examine the planning prompt
   - Note how the LLM is instructed to create subtasks
3. Continue to **Breakpoint 5** (Plan to Graph)
   - Watch how the raw plan becomes a graph
   - Note the structure of subtasks created
4. After planning, step through **Breakpoint 3** (State Transition)
   - Root node should transition to `PLAN_DONE` then `DOING`
   - Child nodes should be in `NOT_READY` initially

### 3.3 Following Task Execution

1. Return to **Breakpoint 2** (Main Loop) for subsequent iterations
2. Monitor which nodes are selected for execution
   - Nodes should be executed in dependency order
3. For writing/reasoning tasks, step into **Breakpoint 6** (Task Execution)
   - Examine the execution prompt
   - Note how context from dependencies is provided
4. For complex tasks with nested plans:
   - Look for recursive planning via **Breakpoint 4**
   - Observe nested graph creation via **Breakpoint 5**

### 3.4 Observing Result Synthesis

1. When subtasks complete, look for parent nodes entering `FINAL_TO_FINISH`
2. Step into **Breakpoint 7** (Result Aggregation)
   - Examine how subtask results are collected
   - Note how the synthesis prompt is constructed
3. Watch parent nodes transition to `FINISH` via **Breakpoint 3**
4. Check the updated article via **Breakpoint 8** (Memory)

## 4. Key Data Structures to Watch

### 4.1 Node Structure

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

### 4.2 Memory State

```python
memory = {
    'root_node': Node,             # Root task node
    'article': str,                # Generated content
    'collected_info': {            # Node info cache
        'hashkey1': {...},         # Cached information
        'hashkey2': {...}          # Indexed by node hashkey
    },
    'format': str,                 # Output format (xml/json)
    'config': dict                 # System configuration
}
```

### 4.3 Graph Structure

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

### 4.4 Agent Structure

```python
agent = {
    'config': dict,                # System configuration
    'prompt_version': str,         # Template identifier
    'prompt_kwargs': {             # Context for prompt
        'goal': str,               # Task objective
        'previous_results': {...}   # Dependency results
        # Other task-specific fields
    },
    'llm_args': {                  # LLM parameters
        'model': str,              # Model name
        'temperature': float,      # Creativity setting
        'max_tokens': int          # Output length
    }
}
```

## 5. Common Issues and Investigation Scenarios

### 5.1 Task Decomposition Problems

**Symptoms:**

- Illogical or too granular task breakdowns
- Missing critical tasks
- Circular dependencies

**Investigation approach:**

1. Break at **Breakpoint 4** (Planning)
2. Examine the planning prompt
   - Check how the task goal is presented
   - Note any constraints or examples provided
3. Look at the raw LLM response
   - Is the LLM following the requested format?
   - Are its task breakdowns logical?
4. Check `plan2graph` conversion for any filtering or alterations

**Key questions:**

- Is the planning prompt clear about desired decomposition?
- Is the LLM temperature appropriate? (Lower for more predictable planning)
- Does the plan validation catch issues?

### 5.2 Context Loss Between Tasks

**Symptoms:**

- Subtasks seem disconnected from parent tasks
- Information from dependencies isn't used effectively
- Content repetition or contradictions

**Investigation approach:**

1. Break at **Breakpoint 6** (Task Execution)
2. Examine `prompt_kwargs` for a subtask
   - Check what context from dependencies is included
   - Note how the parent task goal is presented
3. Check memory.collect_node_run_info for how information is gathered
4. Look at dependency result format in the execution prompt

**Key questions:**

- Are dependency results properly formatted in the prompt?
- Is relevant context being selected from memory?
- Is the prompt structure clear about how to use context?

### 5.3 State Transition Issues

**Symptoms:**

- Tasks stuck in certain states
- Graph execution seems to halt
- Tasks executed in unexpected order

**Investigation approach:**

1. Break at **Breakpoint 3** (State Transitions)
2. For stuck nodes, examine:
   - Current state
   - Available transitions in `status_exam_mapping`
   - Condition functions for transitions
   - State of dependencies and parent nodes
3. Check if nodes are in the expected state category (silence/suspend/activate)

**Key questions:**

- Are dependency tasks completing successfully?
- Are condition functions evaluating as expected?
- Is the node in the right category for the main loop?

### 5.4 Result Aggregation Problems

**Symptoms:**

- Final output lacks coherence
- Some subtask results missing from output
- Poor synthesis of diverse information

**Investigation approach:**

1. Break at **Breakpoint 7** (Result Aggregation)
2. Examine the inner_results collection
   - Check that all expected subtask results are present
   - Note the format of each result
3. Review the aggregation prompt
   - How are results presented to the LLM?
   - What instructions are given for synthesis?

**Key questions:**

- Are all subtasks completing successfully?
- Is the aggregation prompt structured effectively?
- Is the LLM given clear instructions for integration?

## 6. Visualization and Analysis Tools

### 6.1 Graph Visualization

During debugging, it can be helpful to visualize the task graph:

```python
# Add temporarily to engine.py:forward_one_step_not_parallel after state updates
from recursive.utils.display import display_graph
display_graph(self.root_node.inner_graph, fn="debug_graph_{}.png".format(step_count))
```

This will generate an image of the current graph state, showing:

- Nodes with their IDs and statuses
- Dependency edges between nodes
- Execution progress

### 6.2 State Logging

Add targeted logging for state transitions:

```python
# Add to AbstractNode.do_exam
if self.status != next_status:
    logger.debug(f"Node {self.nid} state: {self.status.name} -> {next_status.name}")
    logger.debug(f"   Trigger condition: {cond.__code__.co_filename}:{cond.__code__.co_firstlineno}")
```

### 6.3 Memory Inspection

Create a helper function to visualize memory state:

```python
def inspect_memory(memory, node_hashkey=None):
    """Print key memory information for debugging"""
    print(f"Current article length: {len(memory.article)} chars")
    print(f"Cached node count: {len(memory.collected_info)}")
    if node_hashkey and node_hashkey in memory.collected_info:
        print(f"Node info keys: {memory.collected_info[node_hashkey].keys()}")
```

## 7. Advanced Debugging Techniques

### 7.1 Conditional Breakpoints

Set conditional breakpoints to focus on specific scenarios:

```python
# Break only when planning a specific node type
# recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward
condition: 'REASONING' in str(node.task_info['task_type'])

# Break on unusual state transitions
# recursive/graph.py:AbstractNode.do_exam
condition: str(next_status) == 'TaskStatus.FAILED'

# Break when a specific node ID is processed
# recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel
condition: 'need_next_step_node and "1.2" in need_next_step_node.nid'
```

### 7.2 Watching for LLM Quality Issues

If you suspect LLM output quality problems:

```python
# Add to AgentBase.get_llm_output
if len(llm_response.content) < 50:  # Suspiciously short response
    logger.warning(f"Short LLM response from {self.__class__.__name__}: {llm_response.content}")
    # Consider setting a breakpoint here
```

### 7.3 Execution Trace Capture

Add a trace collector to capture detailed execution history:

```python
# Add to GraphRunEngine.__init__
self.execution_trace = []

# Add to forward_one_step_not_parallel before action execution
self.execution_trace.append({
    'step': len(self.execution_trace),
    'node_id': need_next_step_node.nid,
    'status': need_next_step_node.status.name,
    'action': action_name,
    'task_type': need_next_step_node.task_type_tag if hasattr(need_next_step_node, 'task_type_tag') else None,
    'timestamp': datetime.now().isoformat()
})
```

## 8. Next Steps and Common Workflows

### 8.1 Start Simple, Then Expand

1. Begin by debugging a simple, single-sentence generation task

   - Focus on the basic flow through **Breakpoints 1, 2, 4, 5, 6**
   - Note the minimal planning structure

2. Progress to a multi-paragraph document

   - Observe hierarchical planning via recursive **Breakpoint 4** calls
   - Watch how higher-level tasks delegate to lower-level ones

3. Try a research-heavy task
   - Focus on search tasks via **Breakpoint 6**
   - Note how retrieval results feed into reasoning and writing tasks

### 8.2 Experiment with Configuration Changes

Try modifying `config` at **Breakpoint 1**:

- Change LLM temperature to see effects on creativity vs. consistency
- Modify action_mapping to use different agent implementations
- Adjust prompt templates to see effects on planning quality

### 8.3 Common Extension Points

If you're planning to extend the system, focus on:

1. **Agent implementations**:

   - Start by studying existing agents in `recursive/agent/agents/regular.py`
   - Consider creating specialized agents for specific task types

2. **Prompt engineering**:

   - Locate prompt templates (likely in `recursive/agent/prompts/`)
   - Experiment with different instructions for planning and execution

3. **Execution flow**:
   - The state machine in `RegularDummyNode.define_status()` controls execution
   - Consider adding new states or transitions for more complex workflows

## 9. Conclusion: The Power of Recursive Task Decomposition

As you debug the WriteHERE engine, you'll gain insights into how recursive task decomposition enables more coherent, well-structured content generation than traditional prompt engineering:

1. **Hierarchical thinking**: Breaking complex tasks into sub-problems mirrors human cognitive processes
2. **Contextual awareness**: Each subtask has clear access to relevant context
3. **Iterative refinement**: The state machine enables verification and reflection
4. **Structured cooperation**: Different agent types specialize in different cognitive tasks

This approach represents a significant evolution beyond simple prompt-based generation, enabling LLMs to tackle truly complex writing tasks with better organization, coherence, and depth.

Remember to check the engine logs in `project/qa/example_claude/test_output/` for detailed execution information. Good luck with your debugging journey!
