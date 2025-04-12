# WriteHERE Recursive Engine Debugging Guide

This guide provides a detailed walkthrough for debugging the WriteHERE recursive engine, focusing on key components, execution flow, agents, and task decomposition.

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

## 2. Key Breakpoints and Detailed Analysis

### 2.1 Task Initialization (Engine Setup)

```python
# recursive/engine.py:report_writing (around line ~450) or story_writing (around line ~300)
# Breakpoint 1: Root node creation and engine initialization

# --> SET BREAKPOINT HERE <--
root_node = RegularDummyNode(
    config=config,
    nid="",
    node_graph_info={
        "outer_node": None,
        "root_node": None, # Will be set shortly after
        "parent_nodes": [],
        "layer": 0
    },
    task_info={
        "goal": question,
        "task_type": "write", # Or specific type for the mode
        "length": "...",
        "dependency": []
    },
    node_type=NodeType.PLAN_NODE
)
root_node.node_graph_info["root_node"] = root_node # Important self-reference
engine = GraphRunEngine(root_node, "xml", config) # Or "xml" depending on mode
```

**Purpose**: Understand how the overall writing task is configured and how the main `GraphRunEngine` is initialized. This is the starting point for any task.

**What to Examine**:

- `args`: The command-line arguments passed to the script. Verify `--mode`, `--model`, input/output files.
- `config`: This dictionary is _crucial_. It holds all settings:
  - `action_mapping`: Which agent class handles which action (`plan`, `execute`, etc.).
  - `llm_args`: Default LLM parameters (model, temperature).
  - Task-specific sections (`COMPOSITION`, `RETRIEVAL`, `REASONING`): Contain prompt names (`prompt_version`), specific LLM args, parsing instructions (`parse_arg_dict`), and agent behavior flags (e.g., `react_agent`, `llm_merge`, `update_diff`). Deeply inspect the section relevant to the current task mode (`report` or `story`).
  - `tag2task_type`: Mapping between human-readable tags ("write", "think", "search") and internal types (`COMPOSITION`, `REASONING`, `RETRIEVAL`).
- `question`: The initial prompt or goal for the entire writing task.
- `root_node`: The top-level node representing the overall task. Check its `nid`, `task_info`, `node_type` (should be `PLAN_NODE`), and initial `status` (should be `NOT_READY` initially, then set to `READY` before the loop starts in `forward_one_step_untill_done`).
- `engine`: The main orchestrator. Inspect its `memory` object (which should be initialized with the `root_node`).

### 2.2 Main Execution Loop (Step Progression)

```python
# recursive/engine.py:GraphRunEngine.forward_one_step_not_parallel (around line ~150)
# Breakpoint 2: Selecting the next node to process

# --> SET BREAKPOINT HERE <--
need_next_step_node = self.find_need_next_step_nodes(single=True)
if need_next_step_node is None:
    logger.info("All Done")
    # ... completion logic ...
    return "done"
logger.info("select node: {}".format(need_next_step_node.task_str()))

# --> SET BREAKPOINT HERE <-- (After node selection)
self.memory.update_infos([need_next_step_node]) # Before action

# --> SET BREAKPOINT HERE <-- (Before executing the action)
action_name, action_result = need_next_step_node.next_action_step(self.memory,
                                                            *action_args,
                                                            **action_kwargs)

# --> SET BREAKPOINT HERE <-- (After executing the action, before status exam)
self.forward_exam(self.root_node, verbose) # After action
```

**Purpose**: Observe the core execution cycle: how the engine picks the next active node, executes its corresponding action, and updates the graph state.

**What to Examine**:

- **First Breakpoint (Node Selection)**:
  - Step _into_ `find_need_next_step_nodes`. Observe how it traverses the graph (likely BFS or DFS) looking for nodes in an `activate` status (see `AbstractNode.is_activate`). Understand why a particular node is chosen (it should be the first one found in the traversal that's ready for action).
  - `need_next_step_node`: The selected node. Examine its `nid`, `task_info`, `status`, `node_type`.
  - `self.root_node.to_json()`: Visualize the current state of the entire graph hierarchy before the step.
- **Second Breakpoint (Memory Update)**:
  - Step _into_ `self.memory.update_infos`. See how context is prepared for the upcoming action (Breakpoint 5 provides more detail).
- **Third Breakpoint (Action Execution)**:
  - Step _into_ `need_next_step_node.next_action_step`. This leads to the node's state machine logic.
  - Inside `next_action_step` (in `graph.py`), examine `self.status_action_mapping[self.status]`. See which conditions are checked (`condition_func`) and which `action_name` is selected (e.g., "plan", "execute").
  - Step _into_ `self.do_action(action_name, memory, ...)`. This will call the specific agent's `forward` method (e.g., `RegularDummyNode.plan`, `RegularDummyNode.execute`). **This is the entry point to agent logic.** (See Breakpoints 2.6, 2.7, 2.8).
- **Fourth Breakpoint (Status Examination)**:
  - `action_name`, `action_result`: The result returned by the agent. Inspect `action_result` carefully (e.g., for plans, generated text, search results).
  - Step _into_ `self.forward_exam`. Observe how the engine traverses the graph bottom-up (`inner_node` recursion) and calls `node.do_exam()` for suspended nodes to update their statuses based on the completed action. (See Breakpoint 2.3).
  - `self.root_node.to_json()`: Visualize the graph state _after_ the step and status updates. Compare with the state before the step.

### 2.3 Node State Transitions (Readiness Check)

```python
# recursive/graph.py:AbstractNode.do_exam (around line ~350)
# Breakpoint 3: Checking conditions for state changes in suspended nodes

# --> SET BREAKPOINT HERE <--
def do_exam(self, verbose):
    # Check if the node is actually suspended (should be)
    if not self.is_suspend:
        # This shouldn't happen if called from forward_exam correctly
        raise NotImplementedError(...)

    # --> SET BREAKPOINT HERE <-- (Inside the loop)
    for condition_func, next_status in self.status_exam_mapping[self.status]:
        if condition_func(self): # Evaluate the condition
            if verbose:
                logger.info(...)
            self.status = next_status # State transition happens here
            break # Only one transition per exam
```

**Purpose**: Understand how nodes waiting for dependencies (`NOT_READY`) or for subtasks to finish (`DOING`) check if they can transition to an active state.

**What to Examine**:

- `self`: The node being examined. Check its `nid`, `task_info`, current `status` (should be `NOT_READY` or `DOING`).
- `self.status_exam_mapping[self.status]`: The list of potential transitions for the current status.
- **Inside the loop**:
  - `condition_func`: The function being evaluated. Step _into_ the lambda function (e.g., `lambda node, *args, **kwargs: node.node_graph_info["outer_node"].status == TaskStatus.DOING and ...`) to understand the exact logic.
  - Check the status of `parent_nodes` (for `NOT_READY` transitions) or `inner_graph.topological_task_queue` nodes (for `DOING` transitions). Are all dependencies `FINISH`? Are all children `FINISH`?
  - `next_status`: The target status if the condition is met.
  - Observe if `self.status` actually changes.

### 2.4 Agent Selection (Action Dispatch)

```python
# recursive/agent/proxy.py:AgentProxy.proxy (around line ~20)
# Breakpoint 4: Dynamically selecting and initializing the agent for an action

# --> SET BREAKPOINT HERE <--
def proxy(self, action_name):
    agent_cls_name, agent_kwargs = self.config["action_mapping"][action_name]

    # --> SET BREAKPOINT HERE <-- (Before instantiation)
    module = importlib.import_module(self.agent_module)
    agent_cls = getattr(module, agent_cls_name)
    agent = agent_cls(self.config, **agent_kwargs)
    return agent
```

**Purpose**: See exactly which agent class is chosen for a given action (`plan`, `execute`, etc.) based on the configuration.

**What to Examine**:

- `action_name`: The action requested by the node (e.g., "plan", "execute", "final_aggregate").
- `self.config["action_mapping"]`: Verify the mapping for the given `action_name`.
- `agent_cls_name`: The name of the agent class to be used (e.g., `"UpdateAtomPlanningAgent"`, `"SimpleExcutor"`).
- `agent_kwargs`: Any specific configuration passed to the agent's constructor.
- `agent_cls`: The actual class object after dynamic import.
- `agent`: The instantiated agent object. Inspect its attributes, especially any specific configurations set via `agent_kwargs`.

### 2.5 Agent Execution (Core Logic Entry Point)

```python
# recursive/agent/agent_base.py:AgentBase.forward (around line ~30)
# Breakpoint 5: The main entry point for any agent's execution

# --> SET BREAKPOINT HERE <--
def forward(self, node, memory, *args, **kwargs):
    # 1. Build Input
    # --> SET BREAKPOINT HERE <-- (Before building input)
    prompt_kwargs = self._build_input(node, memory, *args, **kwargs)

    # 2. Get LLM Output (potentially cached)
    # --> SET BREAKPOINT HERE <-- (Before calling LLM/cache)
    response = self.get_llm_output(prompt_kwargs, self.llm_args) # Step into this

    # 3. Parse Output
    # --> SET BREAKPOINT HERE <-- (Before parsing output)
    result = self._parse_output(response, node, memory, *args, **kwargs)

    return result
```

**Purpose**: Observe the three main stages of any agent's operation: input preparation, LLM interaction (or cache hit), and output parsing.

**What to Examine**:

- `self`: The specific agent instance (e.g., `UpdateAtomPlanningAgent`, `SimpleExcutor`). Verify its type and configuration.
- `node`: The node the agent is acting upon.
- `memory`: The shared memory state.
- **Before Building Input**: Inspect the raw `node` and `memory` state.
- **After Building Input**:
  - `prompt_kwargs`: This dictionary is _critical_. It contains all the information formatted to be injected into the prompt template. Examine its keys and values carefully. This shows exactly what information the LLM will receive. Step _into_ `_build_input` for the specific agent (e.g., `UpdateAtomPlanningAgent._build_input`) to see how it's constructed.
- **After LLM Call**:
  - Step _into_ `get_llm_output`. Observe if it hits the cache (`recursive/cache.py:Cache.get`). If not, see the final `prompt` sent to the LLM and the raw `response`.
  - `response`: The raw output from the LLM or cache.
- **After Parsing Output**:
  - Step _into_ `_parse_output` for the specific agent. See how the raw `response` (often XML or JSON) is processed.
  - `result`: The structured dictionary returned by the agent. This is what the `GraphRunEngine` receives. Check its contents (e.g., `result["result"]` might contain the plan, generated text, etc.).

### 2.6 Task Planning (Agent Side)

```python
# recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward (around line ~150)
# Breakpoint 6: Inside the planning agent's execution

# --> SET BREAKPOINT HERE <-- (Start of forward)
class UpdateAtomPlanningAgent(AgentBase):
    @overrides
    def forward(self, node, memory, *args, **kwargs):
        # ... standard agent flow starts ...
        # --> SET BREAKPOINT HERE <-- (After _build_input)
        prompt_kwargs = self._build_input(node, memory, *args, **kwargs)
        # --> SET BREAKPOINT HERE <-- (After get_llm_output)
        response = self.get_llm_output(prompt_kwargs, self.llm_args)
        # --> SET BREAKPOINT HERE <-- (After _parse_output)
        result = self._parse_output(response, node, memory, *args, **kwargs) # Contains the raw plan
        return result # This result['result'] is the plan
```

**Purpose**: Specifically trace the process of decomposing a task (`PLAN_NODE`) into subtasks using the LLM.

**What to Examine**:

- `node`: The `PLAN_NODE` being decomposed. Check its `task_info["goal"]`.
- `prompt_kwargs`: (After `_build_input`) Examine the input to the LLM. Does it include parent goals, dependency results, the overall plan outline (`get_all_previous_writing_plan`)? Verify the `prompt_version` used.
- `response`: (After `get_llm_output`) The raw LLM response containing the proposed plan (likely structured, e.g., in XML or JSON within the response).
- `result`: (After `_parse_output`) The parsed plan. Examine `result["result"]`. It should be a list of dictionaries, each representing a subtask with keys like `id`, `goal`, `task_type`, `dependency`, potentially `length` or `atom`.

### 2.7 Graph Creation from Plan (Node Side)

```python
# recursive/graph.py:RegularDummyNode.plan (around line ~600)
# Breakpoint 7: Processing the agent's plan to modify the graph

# --> SET BREAKPOINT HERE <-- (Start of the method)
def plan(self, agent, memory, *args, **kwargs):
    # Agent's plan (calls agent.forward, which we traced in Breakpoint 2.6)
    # --> SET BREAKPOINT HERE <-- (After agent returns)
    result = agent.forward(self, memory, *args, **kwargs)
    self.raw_plan = result["result"] # Store the raw plan

    # Parse the plan generated by the agent and build the inner graph
    # --> SET BREAKPOINT HERE <-- (Before plan2graph)
    self.plan2graph(self.raw_plan) # Step into this!
    return result
```

```python
# recursive/graph.py:AbstractNode.plan2graph (around line ~450)
# Breakpoint 8: Inside the graph construction logic

# --> SET BREAKPOINT HERE <-- (Start of the method)
def plan2graph(self, raw_plan):
    # Handle atomic tasks edge case
    if len(raw_plan) == 0:
       # ... creates a single EXECUTE_NODE plan ...

    nodes = []
    id2node = {}
    # --> SET BREAKPOINT HERE <-- (Inside the loop creating nodes)
    for task in raw_plan:
        # ... extract task_info, node_graph_info ...
        node = self.__class__( # Creates the new Node object
            config=self.config,
            nid=task["id"],
            node_graph_info=node_graph_info,
            task_info=task_info,
            node_type=NodeType.PLAN_NODE if not task.get("atom") else NodeType.EXECUTE_NODE
        )
        nodes.append(node)
        id2node[task["id"]] = node

    # ... (dependency processing logic for REASONING and COMPOSITION) ...

    # Build Graph
    self.inner_graph.clear()
    # --> SET BREAKPOINT HERE <-- (Before adding nodes/edges to inner_graph)
    for node in nodes:
        self.inner_graph.add_node(node)
    for node in nodes:
        for parent_node in node.node_graph_info["parent_nodes"]:
            # Ensure parent_node is the actual node object, not just ID here
            self.inner_graph.add_edge(parent_node, node) # Add dependency edge
    self.inner_graph.topological_sort()
    # --> SET BREAKPOINT HERE <-- (After graph is built)
    return
```

**Purpose**: Understand precisely how the plan generated by the `UpdateAtomPlanningAgent` is translated into actual `Node` objects and edges within the `inner_graph` of the parent `PLAN_NODE`. **This is the moment new tasks become part of the executable structure.**

**What to Examine**:

- **Breakpoint 7**:
  - `result`: The dictionary returned by the planning agent. Verify `result["result"]` contains the expected plan structure.
  - `self.raw_plan`: Confirm the plan is stored.
  - Step _into_ `plan2graph`.
- **Breakpoint 8**:
  - `raw_plan`: The list of subtask dictionaries.
  - **Inside the loop**: For each `task` dictionary from the plan, watch how a new `node` object (`RegularDummyNode`) is created. Examine its `nid`, `task_info` (copied from the plan), `node_graph_info` (linking it to the outer node and setting the layer), and `node_type` (`PLAN_NODE` or `EXECUTE_NODE` based on `atom` flag).
  - `nodes`: The list of newly created node objects.
  - `id2node`: The mapping used to resolve dependencies.
  - **Dependency Processing**: Step through the logic that adjusts dependencies for `REASONING` and implicit `COMPOSITION` tasks. See how `node.node_graph_info["parent_nodes"]` is modified.
  - **Graph Building**: Watch `self.inner_graph.add_node` and `self.inner_graph.add_edge` being called. Inspect `self.inner_graph.graph_edges` to see the dependency structure being built.
  - **After `topological_sort`**: Examine `self.inner_graph.topological_task_queue`. Does the order respect the dependencies defined in the plan and adjusted by the logic?

### 2.8 Task Execution (Agent Side)

```python
# recursive/agent/agents/regular.py:SimpleExcutor.forward (around line ~250)
# Breakpoint 9: Inside the execution agent for atomic tasks

# --> SET BREAKPOINT HERE <-- (Start of forward)
class SimpleExcutor(AgentBase):
    @overrides
    def forward(self, node, memory, *args, **kwargs):
        task_type_tag = node.task_type_tag
        # --> SET BREAKPOINT HERE <-- (After determining task type)

        if task_type_tag in ("COMPOSITION", "REASONING"):
            # ... build prompt_kwargs ...
            # --> SET BREAKPOINT HERE <-- (Before LLM call for write/think)
            response = self.get_llm_output(prompt_kwargs, self.llm_args)
            result = self._parse_output(response, node, memory, *args, **kwargs)
        elif task_type_tag == "RETRIEVAL":
            if self.config["RETRIEVAL"]["execute"].get("react_agent", False):
                # --> SET BREAKPOINT HERE <-- (Before starting search agent)
                result = self.react_agent_run(node, memory, *args, **kwargs) # Step into this complex part if needed
            else:
                 # Simplified search (might not be used in report mode)
                 pass
            if self.config["RETRIEVAL"]["execute"].get("llm_merge", False):
                 # --> SET BREAKPOINT HERE <-- (Before merging search results)
                 result = self.search_merge(node, memory, result["result"])
        else:
            raise NotImplementedError(...)
        return result
```

**Purpose**: Trace the execution of atomic tasks (writing, thinking, searching) handled by the `SimpleExcutor`.

**What to Examine**:

- `node`: The `EXECUTE_NODE` being run. Check its `task_info["goal"]` and `task_type_tag`.
- `task_type_tag`: Verify the determined type (`COMPOSITION`, `REASONING`, `RETRIEVAL`).
- **For `COMPOSITION`/`REASONING`**:
  - Examine `prompt_kwargs` before the LLM call. What context is provided?
  - Examine `response` and the parsed `result`. Does `result["result"]` contain the expected generated text or reasoning?
- **For `RETRIEVAL`**:
  - If `react_agent` is true: This often involves multiple steps (planning query, searching, summarizing). Consider stepping _into_ `react_agent_run` (or related search functions) if you need to debug the search process itself. Breakpoints within the search loop (e.g., before calling the search API, before summarizing results) would be beneficial.
  - If `llm_merge` is true: Examine the input `result` before merging and the `result` after the merge LLM call. How are the search results synthesized?

### 2.9 Task Aggregation (Agent Side)

```python
# recursive/agent/agents/regular.py:FinalAggregateAgent.forward (around line ~450)
# Breakpoint 10: Inside the agent responsible for combining subtask results

# --> SET BREAKPOINT HERE <-- (Start of forward)
class FinalAggregateAgent(AgentBase):
    @overrides
    def forward(self, node, memory, *args, **kwargs):
        # --> SET BREAKPOINT HERE <-- (After building input)
        prompt_kwargs = self._build_input(node, memory, *args, **kwargs) # Step into _build_input
        # --> SET BREAKPOINT HERE <-- (After LLM call)
        response = self.get_llm_output(prompt_kwargs, self.llm_args)
        # --> SET BREAKPOINT HERE <-- (After parsing output)
        result = self._parse_output(response, node, memory, *args, **kwargs)
        return result
```

**Purpose**: See how the results of completed subtasks within a `PLAN_NODE` are gathered and synthesized into a final result for that node.

**What to Examine**:

- `node`: The `PLAN_NODE` that has finished all its children (`status` was `DOING`, now likely `FINAL_TO_FINISH`).
- Step _into_ `_build_input`. Observe how it iterates through `node.topological_task_queue` (the completed children) and calls `child.get_node_final_result()` to gather their outputs. See how these results are formatted for the aggregation prompt.
- `prompt_kwargs`: Examine the input to the LLM. Does it contain all the necessary child results?
- `response`: The raw LLM response containing the aggregated result.
- `result`: The parsed aggregated result. Examine `result["result"]`. This becomes the final output of the `PLAN_NODE`.

### 2.10 Memory Updates (Context Accumulation)

```python
# recursive/memory.py:Memory.update_infos (around line ~100, estimate)
# Breakpoint 11: How memory is updated before a node acts

# --> SET BREAKPOINT HERE <-- (Start of method)
def update_infos(self, nodes):
    for node in nodes:
        # --> SET BREAKPOINT HERE <-- (Inside loop, before collecting)
        info = self.collect_node_run_info(node) # Step into this
        # Optionally update article or other shared state
        # --> SET BREAKPOINT HERE <-- (After potential updates)
    self.article = self._compute_article() # Step into this if needed

# recursive/memory.py:Memory.collect_node_run_info (around line ~120, estimate)
# Breakpoint 12: Gathering specific information for a node from memory/dependencies

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

**Purpose**: Understand how the shared `Memory` object gathers context (like results from dependencies) for the node that is about to execute an action, and how the overall article/state might be updated.

**What to Examine**:

- **Breakpoint 11**:
  - `nodes`: The list containing the node(s) about to act (usually just one in non-parallel mode).
  - Step _into_ `collect_node_run_info`.
  - Step _into_ `_compute_article` if you want to see how the final text is assembled (often involves traversing the finished parts of the graph). Examine `self.article` before and after.
- **Breakpoint 12**:
  - `node`: The node for which information is being collected.
  - Check if `node.hashkey` is in `self.collected_info` (cache hit).
  - If not cached, step _into_ the relevant `_compute_node_info` helper function. This is where logic resides to find parent results, sibling results, or other relevant context needed by the node's upcoming action. Examine the `info` dictionary that is computed and cached.

## 3. Debugging Workflow (Revised)

1.  **Setup (Breakpoint 2.1)**: Verify config, initial prompt, and root node creation.
2.  **Main Loop (Breakpoint 2.2)**:
    - Observe node selection (`find_need_next_step_nodes`).
    - Step into `next_action_step` -> `do_action`.
3.  **Agent Selection (Breakpoint 2.4)**: See which agent class is chosen (`AgentProxy.proxy`).
4.  **Agent Execution (Breakpoint 2.5)**: Follow the `forward` method in `AgentBase`:
    - Step into `_build_input` for the specific agent. Examine `prompt_kwargs`.
    - Step into `get_llm_output`. Check cache/LLM interaction. Examine `response`.
    - Step into `_parse_output`. Examine the final `result`.
5.  **Planning Focus**:
    - If `action_name` is "plan", set Breakpoints 2.6, 2.7, 2.8.
    - Trace `UpdateAtomPlanningAgent.forward` (2.6) to see the plan generation (`result["result"]`).
    - Trace `RegularDummyNode.plan` (2.7) calling `plan2graph`.
    - Trace `AbstractNode.plan2graph` (2.8) to see the `inner_graph` being built with new nodes and edges.
6.  **Execution Focus**:
    - If `action_name` is "execute", set Breakpoint 2.8 (`SimpleExcutor.forward`).
    - Follow the logic based on `task_type_tag`. Examine prompts, results, and step into search/merge functions if needed.
7.  **Aggregation Focus**:
    - If `action_name` is "final_aggregate", set Breakpoint 2.9 (`FinalAggregateAgent.forward`).
    - Step into its `_build_input` to see how child results are gathered. Examine the aggregation prompt and result.
8.  **State Update (Breakpoint 2.2 - after action)**: Step into `forward_exam`.
9.  **Readiness Check (Breakpoint 2.3)**: Step into `do_exam` for suspended nodes. See how `status_exam_mapping` conditions are evaluated based on the results of the previous step.
10. **Memory (Breakpoints 2.11, 2.12)**: Set these to understand context gathering (`collect_node_run_info`) before an agent acts and article assembly (`_compute_article`).
11. **Repeat**: Continue stepping through the main loop (Breakpoint 2.2) to observe subsequent steps.

## 4. Key Data Structures to Watch

(Keep the existing list, but emphasize inspecting `config` and agent-specific `result` dictionaries).

### 4.1 Node Structure

```python
node = {
    'nid': str,                    # Node ID (e.g., "1", "1.2")
    'hashkey': str,                # Unique instance ID
    'status': TaskStatus,          # Current state (READY, DOING, FINISH, etc.)
    'node_type': NodeType,         # PLAN_NODE or EXECUTE_NODE
    'task_info': dict,             # {'goal': str, 'task_type': str, 'length': str, 'dependency': list[int]}
    'node_graph_info': dict,       # {'outer_node': Node, 'root_node': Node, 'parent_nodes': list[Node], 'layer': int}
    'inner_graph': Graph,          # Subtask graph (if PLAN_NODE and planned)
    'result': dict,                # Results stored by action name {'plan': {...}, 'execute': {...}, 'final_aggregate': {...}}
    'raw_plan': list[dict] | None  # Raw plan from LLM for PLAN_NODE
}
```

### 4.2 Memory State

```python
memory = {
    'root_node': Node,             # Reference to the top-level node
    'article': str,                # Accumulated generated content (updated periodically)
    'collected_info': dict,        # Cache for node context {node.hashkey: info_dict}
    'format': str,                 # Output format ('xml', 'markdown', etc.)
    'config': dict                 # Reference to the main engine config
}
```

### 4.3 Graph Structure (`node.inner_graph` or `engine.root_node.inner_graph`)

```python
graph = {
    'graph_edges': dict,           # {parent_nid: [child_node1, child_node2]}
    'nid_list': list[str],         # All node IDs in this graph layer
    'node_list': list[Node],       # All node objects in this layer
    'topological_task_queue': list[Node], # Nodes sorted by dependency
    'outer_node': Node             # Reference to the node containing this graph
}
```

### 4.4 Agent Result Dictionary (`node.result[action_name]` or `action_result` variable)

- Structure varies greatly depending on the agent and action.
- **Planning**: `result['result']` often contains the list of subtask dictionaries.
- **Execution (Write/Think)**: `result['result']` often contains the generated text/reasoning.
- **Execution (Search)**: `result['result']` might contain summarized search findings or raw results.
- **Aggregation**: `result['result']` contains the synthesized content.
- Often includes metadata like `time`, `agent` info, sometimes `prompt_kwargs` or raw `response`.

## 5. Common Issues to Watch For

(Keep the existing list, add agent-specific issues)

1.  **State Transition Errors**:
    - Check `status_exam_mapping` conditions (Breakpoint 2.3).
    - Verify parent/child node statuses match expectations for the transition.
2.  **Memory Management**:
    - Incorrect context gathered in `collect_node_run_info` (Breakpoint 2.12).
    - Article not updating correctly in `_compute_article`.
3.  **Task Decomposition (Planning)**:
    - Agent generates invalid plan structure (missing keys, incorrect types) (Breakpoint 2.6 - check `response` and `result`).
    - `plan2graph` fails to parse the plan or creates incorrect dependencies (Breakpoint 2.8).
    - Dependency cycles created by the plan.
4.  **LLM Integration**:
    - Incorrect `prompt_kwargs` built by `_build_input` (Breakpoint 2.5).
    - LLM response parsing errors in `_parse_output` (Breakpoint 2.5).
    - Cache issues (stale data, incorrect keys).
5.  **Agent Configuration**:
    - Wrong agent mapped to an action in `config["action_mapping"]` (Breakpoint 2.4).
    - Incorrect prompt version or LLM args specified in `config` for the agent/task type.
6.  **Task Execution**:
    - `SimpleExcutor` fails for a specific task type (Breakpoint 2.8). Search agent (`react_agent_run`) errors. Merge failures.
7.  **Task Aggregation**:
    - `FinalAggregateAgent` fails to gather child results correctly in `_build_input` (Breakpoint 2.10).
    - Aggregation prompt leads to poor synthesis by LLM.

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
