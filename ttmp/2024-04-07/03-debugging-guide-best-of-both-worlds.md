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
# recursive/engine.py:report_writing (around line ~540)
# Breakpoint 1: Task initialization and configuration

# --> SET BREAKPOINT HERE <--
root_node = RegularDummyNode(
    config = config,
    nid = "",
    node_graph_info = {
        "outer_node": None,
        "root_node": None, # Will be set shortly after
        "parent_nodes": [],
        "layer": 0
    },
    task_info = {
        "goal": question,
        "task_type": "write", # Or specific type for the mode
        "length": "...",
        "dependency": []
    },
    node_type = NodeType.PLAN_NODE
)
root_node.node_graph_info["root_node"] = root_node # Important self-reference
engine = GraphRunEngine(root_node, "xml", config) # Or "xml" depending on mode
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
- `args`: Verify `--mode`, `--model`, input/output files
- `question`: The initial prompt for the entire writing task
- `root_node`: Check its initial `status` (should be `NOT_READY` initially, then set to `READY` before the loop starts)

**Why it matters:**
The configuration structure determines everything about how tasks will be decomposed and executed. Examining it helps you understand which agents will be used for different actions, what LLM parameters are being used, and how the system is configured for the specific writing task.

### 2.2 Main Execution Loop

```python
# recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel (around line ~150)
# Breakpoint 2: Main execution loop

# --> SET BREAKPOINT HERE <-- (Node Selection)
need_next_step_node = self.find_need_next_step_nodes(single=True)
if need_next_step_node is None:
    logger.info("All Done")
    # ... completion logic ...
    return "done"
logger.info("select node: {}".format(need_next_step_node.task_str()))

# --> SET BREAKPOINT HERE <-- (Memory Update)
self.memory.update_infos([need_next_step_node])

# --> SET BREAKPOINT HERE <-- (Action Execution)
action_name, action_result = need_next_step_node.next_action_step(self.memory, *action_args, **action_kwargs)

# --> SET BREAKPOINT HERE <-- (State Updates)
self.forward_exam(self.root_node, verbose) # After action
```

**What happens here:**
This is the heart of the execution engine. In each iteration:

1. The engine finds a node that's ready for action
2. Updates the memory with context relevant to that node
3. Executes the appropriate action on the node
4. Examines state transitions throughout the graph

**Values to examine:**

- **First Breakpoint (Node Selection)**:
  - Step _into_ `find_need_next_step_nodes` to observe how it traverses the graph looking for nodes in an `activate` status
  - `need_next_step_node` object: Check `.status`, `.task_str()`, `.node_type`, `.task_info`, and `.status_action_mapping`
  - `self.root_node.to_json()`: Visualize the current state of the entire graph hierarchy
- **Second Breakpoint (Memory Update)**:
  - Step _into_ `self.memory.update_infos` to see how context is prepared for the upcoming action
  - `self.memory.article`: Current state of the growing document
- **Third Breakpoint (Action Execution)**:
  - Step _into_ `need_next_step_node.next_action_step`
  - Inside `next_action_step` (in `graph.py`), examine `self.status_action_mapping[self.status]`
  - Step _into_ `self.do_action(action_name, memory, ...)` to reach the agent's `forward` method
- **Fourth Breakpoint (State Updates)**:
  - `action_name`, `action_result`: Examine what was returned by the agent
  - Step _into_ `self.forward_exam` to see how the engine updates node states
  - `self.root_node.to_json()`: Compare graph state after the step with the state before

**Why it matters:**
This is where you'll see the step-by-step execution of the task graph. By watching this point over multiple iterations, you can observe how the engine selects tasks, what actions it performs, and how the document grows. It's the best place to get a feel for the overall execution flow.

### 2.3 Node State Examination and Transitions

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

**What happens here:**
This method evaluates whether a node should transition to a new state. It checks the conditions in `status_exam_mapping` for the current state and makes a transition if a condition is met.

**Values to examine:**

- `self.status`: Current status
- `self.status_exam_mapping[self.status]`: List of (condition, next_status) pairs
- Step _into_ each `cond` lambda function to understand the exact transition logic
- `cond(self)`: The result of evaluating each condition function
- Parent node statuses: `[parent.status for parent in self.node_graph_info["parent_nodes"]]`
- Inner graph nodes (if any): `[node.status for node in self.topological_task_queue]`
- `next_status`: The target status if the condition is met
- Observe if `self.status` actually changes

**Why it matters:**
The state machine is the backbone of WriteHERE's execution logic. Understanding these transitions reveals how tasks progress from planning to execution to completion. Key transitions to watch:

- `NOT_READY → READY`: When dependencies are fulfilled
- `READY → PLAN_DONE`: After planning completes
- `PLAN_DONE → DOING`: After plan reflection
- `DOING → FINAL_TO_FINISH`: When all subtasks complete
- `FINAL_TO_FINISH → NEED_POST_REFLECT`: After aggregation
- `NEED_POST_REFLECT → FINISH`: After verification

### 2.4 Agent Selection (Action Dispatch)

```python
# recursive/agent/proxy.py:AgentProxy.proxy (around line ~20)
# Breakpoint 4: Dynamically selecting and initializing the agent

# --> SET BREAKPOINT HERE <--
def proxy(self, action_name):
    if action_name not in self.config["action_mapping"]:
        logger.warning("Action {} not in action_mapping".format(action_name))
        return getattr(self, action_name)

    agent_cls_name, agent_kwargs = self.config["action_mapping"][action_name]

    # --> SET BREAKPOINT HERE <-- (Before instantiation)
    module = importlib.import_module(self.agent_module)
    agent_cls = getattr(module, agent_cls_name)
    agent = agent_cls(self.config, **agent_kwargs)
    return agent
```

**What happens here:**
The `AgentProxy` acts as a factory, dynamically selecting and instantiating agents:

1. Looks up the agent name in the action mapping
2. Retrieves or creates the agent instance
3. Returns a bound method for the specified action

**Values to examine:**

- `action_name`: The action being requested (plan/execute/etc.)
- `self.config["action_mapping"][action_name]`: Agent class name and parameters
- `agent_cls_name`: The name of the agent class to be used (e.g., `"UpdateAtomPlanningAgent"`, `"SimpleExcutor"`)
- `agent_kwargs`: Any specific configuration passed to the agent's constructor
- `agent_cls`: The actual class object after dynamic import
- `agent`: The instantiated agent object

**Why it matters:**
The proxy pattern allows the system to dynamically wire different agents to different actions. By examining this process, you can understand how the system selects specialized agents for different tasks and how configuration controls the entire execution pipeline.

### 2.5 Task Planning and Decomposition

```python
# recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward (around line ~50)
# Breakpoint 5: Task planning and decomposition
import recursive.agent.helpers


# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
    # Entry point for planning

    # --> SET BREAKPOINT HERE <-- (After prompt construction)
    prompt_kwargs = self._build_input(node, memory, *args, **kwargs)

    # --> SET BREAKPOINT HERE <-- (After LLM call)
    llm_response = recursive.agent.helpers.get_llm_output(prompt_kwargs, self.llm_args)

    # --> SET BREAKPOINT HERE <-- (After parsing)
    result = self._parse_output(llm_response, node, memory, *args, **kwargs)
    return result
```

**What happens here:**
This is where the magic of task decomposition happens. The `UpdateAtomPlanningAgent`:

1. Builds a planning prompt with context from the node's goal and dependencies
2. Asks the LLM to create a structured plan of subtasks
3. Parses the response into a task plan

**Values to examine:**

- `node`: The `PLAN_NODE` being decomposed. Check its `task_info["goal"]`
- `prompt_kwargs`: The context being provided to the LLM
  - Step _into_ `_build_input` to see how it's constructed
  - Look for `"goal"`, `"previous_results"`, and any task-specific context
  - Verify the `prompt_version` used
- `llm_response.content`: The raw LLM response
- `result["result"]`: The parsed plan structure - this should be a list of dictionaries, each representing a subtask with keys like `id`, `goal`, `task_type`, `dependency`

**Why it matters:**
This is the critical point where the LLM translates a high-level goal into concrete subtasks. The quality of this decomposition largely determines the overall effectiveness of the system. By examining the prompt and response, you can understand how the system "teaches" the LLM to create good plans and how the LLM structures its thinking about the task.

### 2.6 Plan to Graph Conversion

```python
# recursive/graph.py:RegularDummyNode.plan (around line ~600)
# Breakpoint 6A: Processing the agent's plan to modify the graph

# --> SET BREAKPOINT HERE <-- (Start of method)
def plan(self, agent, memory, *args, **kwargs):
    # Agent's plan
    result = agent.forward(self, memory, *args, **kwargs)
    self.raw_plan = result["result"] # Store the raw plan

    # --> SET BREAKPOINT HERE <-- (Before plan2graph)
    self.plan2graph(self.raw_plan) # Step into this!
    return result
```

```python
# recursive/graph.py:AbstractNode.plan2graph (around line ~420)
# Breakpoint 6B: Converting a plan into a graph structure

# --> SET BREAKPOINT HERE <-- (Start of method)
def plan2graph(self, raw_plan):
    # Right after plan validation:
    if len(raw_plan) == 0:  # Atomic task
        # ... creates a single EXECUTE_NODE plan ...

    # --> SET BREAKPOINT HERE <-- (During node creation loop)
    nodes = []
    id2node = {}
    for task in raw_plan:
        # ... extract task_info, node_graph_info ...
        node = self.__class__(
            config = self.config,
            nid = task["id"],
            node_graph_info = node_graph_info,
            task_info = task_info,
            node_type = NodeType.PLAN_NODE if not task.get("atom") else NodeType.EXECUTE_NODE
        )
        nodes.append(node)
        id2node[task["id"]] = node

    # --> SET BREAKPOINT HERE <-- (Before building graph)
    # After dependency processing:
    self.inner_graph = Graph(self)
    self.inner_graph.build_graph(nodes)

    # --> SET BREAKPOINT HERE <-- (After graph is built)
    return
```

**What happens here:**
This method takes the raw plan from the planning agent and constructs an actual graph of Node objects:

1. Creates Node objects for each subtask in the plan
2. Sets up node_graph_info with parent-child relationships
3. Creates a Graph object and populates it with the nodes
4. Builds edges representing dependencies

**Values to examine:**

- **Breakpoint 6A**:

  - `result`: The dictionary returned by the planning agent
  - `self.raw_plan`: The list of subtask dictionaries
  - Step _into_ `plan2graph`

- **Breakpoint 6B**:
  - `raw_plan`: List of task dictionaries from the LLM
  - **During node creation loop**: For each `task`, watch how a new `node` object is created
    - Check `task["id"]`, `task_info`, `node_graph_info`
    - Note if the node is created as `PLAN_NODE` or `EXECUTE_NODE` based on `atom` flag
  - `nodes`: The created Node objects
  - `id2node`: Mapping from task IDs to Node objects
  - Watch the dependency processing logic for `REASONING` and implicit `COMPOSITION` tasks
  - **After graph building**:
    - `self.inner_graph.graph_edges`: Dictionary mapping node IDs to child nodes
    - `self.inner_graph.topological_task_queue`: Nodes sorted in execution order

**Why it matters:**
This is where the LLM's plan becomes an executable structure. Understanding this conversion helps you see how task dependencies are enforced and how execution order is determined. Pay particular attention to:

- How atomic tasks are handled differently
- How implicit dependencies between composition tasks are added
- How the topological sorting ensures dependencies are satisfied

### 2.7 Task Execution

```python
# recursive/agent/agents/regular.py:SimpleExcutor.forward (around line ~150)
# Breakpoint 7: Actual task execution
import recursive.agent.helpers


# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
    # Determine task type:
    task_type_tag = node.task_type_tag  # COMPOSITION, REASONING, or RETRIEVAL
    # --> SET BREAKPOINT HERE <-- (After task type determination)

    if task_type_tag in ("COMPOSITION", "REASONING"):
        # --> SET BREAKPOINT HERE <-- (Before LLM call for write/think)
        prompt_kwargs = self._build_input(node, memory, *args, **kwargs)
        llm_response = recursive.agent.helpers.get_llm_output(prompt_kwargs, self.llm_args)
        result = self._parse_output(llm_response, node, memory, *args, **kwargs)
    elif task_type_tag == "RETRIEVAL":
        if self.config["RETRIEVAL"]["execute"].get("react_agent", False):
            # --> SET BREAKPOINT HERE <-- (Before search agent)
            result = self.react_agent_run(node, memory, *args, **kwargs)
        else:
            # Simplified search
            pass
        if self.config["RETRIEVAL"]["execute"].get("llm_merge", False):
            # --> SET BREAKPOINT HERE <-- (Before merging search results)
            result = self.search_merge(node, memory, result["result"])
    else:
        raise NotImplementedError(...)

    # --> SET BREAKPOINT HERE <-- (After execution)
    return result
```

**What happens here:**
This is where atomic tasks are actually executed by the LLM:

- For writing tasks (`COMPOSITION`), the LLM generates text content
- For reasoning tasks (`REASONING`), the LLM performs analysis
- For search tasks (`RETRIEVAL`), the system may perform web searches

**Values to examine:**

- `node`: The `EXECUTE_NODE` being run
- `task_type_tag`: What kind of task is being executed
- **For `COMPOSITION`/`REASONING`**:
  - `prompt_kwargs`: Context provided to the LLM (step _into_ `_build_input`)
  - `llm_response.content`: Raw response from the LLM
  - `result["result"]`: Parsed and structured output
- **For `RETRIEVAL`**:
  - If `react_agent` is true: Step into `react_agent_run` to debug the search process
  - If `llm_merge` is true: Examine results before and after the merging process

**Why it matters:**
This is the "work" part of the system, where actual content is generated. Understanding this helps you see how the LLM receives context from parent tasks and dependencies, and how its output is structured for later use. The prompt construction is particularly important, as it shows how the system provides relevant context to the LLM.

### 2.8 Result Aggregation

```python
# recursive/agent/agents/regular.py:FinalAggregateAgent.forward (around line ~300)
# Breakpoint 8: Synthesizing results from subtasks
import recursive.agent.helpers


# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
    # --> SET BREAKPOINT HERE <-- (After gathering inner results)
    inner_results = memory.collect_inner_results(node)

    # --> SET BREAKPOINT HERE <-- (After building the aggregation prompt)
    prompt_kwargs = self._build_input(node, memory, inner_results=inner_results, *args, **kwargs)

    # --> SET BREAKPOINT HERE <-- (After LLM aggregation)
    llm_response = recursive.agent.helpers.get_llm_output(prompt_kwargs, self.llm_args)
    result = self._parse_output(llm_response, node, memory, *args, **kwargs)
    return result
```

**What happens here:**
When all subtasks of a plan node complete, this agent synthesizes their results:

1. Collects the results from all inner nodes
2. Constructs a prompt asking the LLM to synthesize them
3. Returns a coherent aggregated result

**Values to examine:**

- `node`: The `PLAN_NODE` that has finished all its children (status was `DOING`, now likely `FINAL_TO_FINISH`)
- `inner_results`: Dictionary mapping node IDs to their results
  - Step _into_ `memory.collect_inner_results` to see how child results are gathered
- `prompt_kwargs`: The synthesis prompt
  - Step _into_ `_build_input` to see how results are formatted for the LLM
- `llm_response.content`: Raw LLM response
- `result["result"]`: The final synthesized output

**Why it matters:**
This is how the system turns multiple partial results into a coherent whole. It reveals how the system "teaches" the LLM to integrate diverse pieces of content. The prompt construction is key, as it shows how the system structures subtask results for effective synthesis.

### 2.9 Memory Updates

```python
# recursive/memory.py:Memory.update_infos (around line ~100)
# Breakpoint 9A: Memory state management

# --> SET BREAKPOINT HERE <-- (Start of method)
def update_infos(self, nodes):
    # During info collection:
    for node in nodes:
        # --> SET BREAKPOINT HERE <-- (Inside loop, before collecting)
        self.collect_node_run_info(node)

    # --> SET BREAKPOINT HERE <-- (Before article update)
    self.article = self._compute_article()
```

```python
# recursive/memory.py:Memory.collect_node_run_info (around line ~120)
# Breakpoint 9B: Gathering specific node information

# --> SET BREAKPOINT HERE <-- (Start of method)
def collect_node_run_info(self, node):
    if node.hashkey in self.collected_info:
        # --> SET BREAKPOINT HERE <-- (Cache hit)
        return self.collected_info[node.hashkey]

    # --> SET BREAKPOINT HERE <-- (Before computing info)
    info = self._compute_node_info(node) # Step into this helper
    self.collected_info[node.hashkey] = info
    return info
```

**What happens here:**
The Memory system updates its state based on recent node activity:

1. Collects and caches information from specified nodes
2. Updates the article by recursively traversing the node graph

**Values to examine:**

- **Breakpoint 9A**:
  - `nodes`: The list containing the node(s) about to act
  - Step _into_ `collect_node_run_info` for each node
  - Step _into_ `_compute_article` to see how the final text is assembled
  - `self.article`: Current accumulated document before and after the update
- **Breakpoint 9B**:
  - `node`: The node for which information is being collected
  - Check if `node.hashkey` is in `self.collected_info` (cache hit)
  - If not cached, step _into_ `_compute_node_info`
  - `info`: The computed context information
  - `self.collected_info`: Cache of node information

**Why it matters:**
The Memory system maintains the growing document and provides context between task executions. Understanding it helps you see how information flows between nodes and how the final document is constructed piece by piece.

## 3. Debugging Workflow: A Progressive Approach

To effectively debug this complex system, follow this progressive workflow:

### 3.1 Understanding the Task and Configuration

1. Start at **Breakpoint 2.1** (Root Node Creation)
2. Examine `config` structure to understand:
   - Which agents are mapped to which actions (`action_mapping`)
   - LLM parameters for different task types
   - Prompt templates being used
3. Note the initial task in `task_info["goal"]`
4. Step through `RegularDummyNode` initialization to see how the state machine is set up

### 3.2 Observing the Planning Process

1. Continue to first iteration of **Breakpoint 2.2** (Main Loop)
   - Observe `find_need_next_step_nodes` - root node should be in `READY` state
   - Verify `action_name` is `"plan"`
2. Step into the action through **Breakpoint 2.4** (Agent Selection)
   - Verify the correct agent is selected (`UpdateAtomPlanningAgent`)
3. Continue to **Breakpoint 2.5** (Planning)
   - Step into `_build_input` to examine the planning prompt
   - Note how the LLM is instructed to create subtasks
   - Examine the raw LLM response and parsed plan in `result["result"]`
4. Continue to **Breakpoint 2.6** (Plan to Graph)
   - Step into `plan2graph` to watch the raw plan become a graph
   - Note the structure of subtasks created and their relationships
5. After planning, step through **Breakpoint 2.3** (State Transition)
   - Root node should transition to `PLAN_DONE` then `DOING`
   - Child nodes should be in `NOT_READY` initially

### 3.3 Following Task Execution

1. Return to **Breakpoint 2.2** (Main Loop) for subsequent iterations
2. Monitor which nodes are selected for execution
   - Nodes should be executed in dependency order
   - For each node, check the memory update via **Breakpoint 2.9** (Memory)
3. For atomic execution nodes:
   - Step into **Breakpoint 2.7** (Task Execution)
   - Follow the branch for the specific task type (writing, reasoning, or search)
   - Examine the execution prompt via `_build_input`
   - Note how context from dependencies is provided
   - Check the generated output in `result["result"]`
4. For complex tasks with nested plans:
   - Look for recursive planning via **Breakpoint 2.5**
   - Observe nested graph creation via **Breakpoint 2.6**

### 3.4 Observing Result Synthesis

1. When all subtasks of a plan node complete:
   - Node state should change to `FINAL_TO_FINISH` via **Breakpoint 2.3**
2. Step into **Breakpoint 2.8** (Result Aggregation)
   - Examine how subtask results are collected via `memory.collect_inner_results`
   - Note how the synthesis prompt is constructed in `_build_input`
   - Check the aggregated result in `result["result"]`
3. Watch parent nodes transition to `FINISH` via **Breakpoint 2.3**
4. Check the updated article via **Breakpoint 2.9** (Memory)

### 3.5 Completing the Process

1. Continue through iterations of **Breakpoint 2.2** (Main Loop)
2. Watch the progression of nodes through the graph
3. Observe the final article construction in `memory.article`
4. Check for completion when `find_need_next_step_nodes` returns `None`

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

### 4.5 Action Result Dictionary

```python
result = {
    'result': object,              # Main output (plan, text, search results)
    'time': float,                 # Execution time
    'agent': str,                  # Agent class name
    'prompt_kwargs': dict,         # (Optional) The input prompt context
    'response': object             # (Optional) Raw LLM response
}
```

## 5. Common Issues and Investigation Scenarios

### 5.1 Task Decomposition Problems

**Symptoms:**

- Illogical or too granular task breakdowns
- Missing critical tasks
- Circular dependencies

**Investigation approach:**

1. Break at **Breakpoint 2.5** (Planning)
2. Examine the planning prompt in `prompt_kwargs`
   - Check how the task goal is presented
   - Note any constraints or examples provided
3. Look at the raw LLM response in `llm_response.content`
   - Is the LLM following the requested format?
   - Are its task breakdowns logical?
4. Check `plan2graph` conversion at **Breakpoint 2.6** for any filtering or alterations
5. Verify dependency resolution in the graph creation

**Key questions:**

- Is the planning prompt clear about desired decomposition?
- Is the LLM temperature appropriate? (Lower for more predictable planning)
- Does the plan validation catch issues?
- Are circular dependencies being created or unresolvable plans?

### 5.2 Context Loss Between Tasks

**Symptoms:**

- Subtasks seem disconnected from parent tasks
- Information from dependencies isn't used effectively
- Content repetition or contradictions

**Investigation approach:**

1. Break at **Breakpoint 2.7** (Task Execution)
2. Examine `prompt_kwargs` for a subtask
   - Check what context from dependencies is included
   - Note how the parent task goal is presented
3. Step into `memory.collect_node_run_info` at **Breakpoint 2.9** to see how information is gathered
4. Check how dependency results are formatted in the execution prompt

**Key questions:**

- Are dependency results properly formatted in the prompt?
- Is relevant context being selected from memory?
- Is the prompt structure clear about how to use context?
- Are node hashkeys being properly cached and retrieved?

### 5.3 State Transition Issues

**Symptoms:**

- Tasks stuck in certain states
- Graph execution seems to halt
- Tasks executed in unexpected order

**Investigation approach:**

1. Break at **Breakpoint 2.3** (State Transitions)
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

### 5.4 Result Aggregation Problems

**Symptoms:**

- Final output lacks coherence
- Some subtask results missing from output
- Poor synthesis of diverse information

**Investigation approach:**

1. Break at **Breakpoint 2.8** (Result Aggregation)
2. Examine the `inner_results` collection
   - Check that all expected subtask results are present
   - Note the format of each result
3. Step into `_build_input` to review the aggregation prompt
   - How are results presented to the LLM?
   - What instructions are given for synthesis?
4. Check final output in `result["result"]`

**Key questions:**

- Are all subtasks completing successfully?
- Is the aggregation prompt structured effectively?
- Is the LLM given clear instructions for integration?
- Are there any format inconsistencies in the subtask results?

### 5.5 Memory Management Issues

**Symptoms:**

- Missing or incorrect context for task execution
- Article not updating properly
- Duplicate content in the final document

**Investigation approach:**

1. Break at **Breakpoint 2.9** (Memory Updates)
2. For memory.update_infos:
   - Check which nodes are being processed
   - Step into `_compute_article` to see how content is assembled
3. For memory.collect_node_run_info:
   - Check if cache hits are occurring (`node.hashkey in self.collected_info`)
   - Step into `_compute_node_info` to see how node context is gathered
   - Examine returned `info` dictionary

**Key questions:**

- Is the cache working correctly for node information?
- Is `_compute_article` correctly traversing the graph?
- Are there race conditions in memory updates?

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

### 6.4 Execution Trace

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

### 7.3 Performance Monitoring

Add timing instrumentation to identify bottlenecks:

```python
# Add to GraphRunEngine.forward_one_step_not_parallel
import time
start_time = time.time()
action_name, action_result = need_next_step_node.next_action_step(self.memory, *action_args, **action_kwargs)
elapsed = time.time() - start_time
if elapsed > 5.0:  # Slow operation
    logger.warning(f"Slow operation: {action_name} on {need_next_step_node.nid} took {elapsed:.2f}s")
```

### 7.4 Cache Inspection

Monitor cache performance and ensure it's working correctly:

```python
# Add to AgentBase.get_llm_output
cache_key = cache.get_key(prompt_kwargs, self.llm_args)
before = time.time()
response = cache.get(cache_key, lambda: self._call_llm(prompt_kwargs, self.llm_args))
after = time.time()
logger.debug(f"LLM call for {self.__class__.__name__}: cache_hit={after-before<0.1}, took {after-before:.3f}s")
```

## 8. Next Steps and Common Workflows

### 8.1 Start Simple, Then Expand

1. Begin by debugging a simple, single-sentence generation task

   - Focus on the basic flow through **Breakpoints 2.1, 2.2, 2.5, 2.6, 2.7**
   - Note the minimal planning structure

2. Progress to a multi-paragraph document

   - Observe hierarchical planning via recursive **Breakpoint 2.5** calls
   - Watch how higher-level tasks delegate to lower-level ones

3. Try a research-heavy task
   - Focus on search tasks via **Breakpoint 2.7**
   - Note how retrieval results feed into reasoning and writing tasks

### 8.2 Experiment with Configuration Changes

Try modifying `config` at **Breakpoint 2.1**:

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

### 8.4 Customization for Specific Task Types

For customizing behavior based on task type:

1. Create specialized agents in `recursive/agent/agents/`
2. Update config["action_mapping"] to use different agents for different actions
3. Modify prompt templates to better instruct the LLM for specific task types
4. Update `SimpleExcutor.forward` to handle new task types

## 9. Conclusion: The Power of Recursive Task Decomposition

As you debug the WriteHERE engine, you'll gain insights into how recursive task decomposition enables more coherent, well-structured content generation than traditional prompt engineering:

1. **Hierarchical thinking**: Breaking complex tasks into sub-problems mirrors human cognitive processes
2. **Contextual awareness**: Each subtask has clear access to relevant context
3. **Iterative refinement**: The state machine enables verification and reflection
4. **Structured cooperation**: Different agent types specialize in different cognitive tasks

This approach represents a significant evolution beyond simple prompt-based generation, enabling LLMs to tackle truly complex writing tasks with better organization, coherence, and depth.

Remember to check the engine logs in `project/qa/example_claude/test_output/` for detailed execution information. Good luck with your debugging journey!
