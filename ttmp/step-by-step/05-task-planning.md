# WriteHERE Task Planning and Decomposition

## Introduction to WriteHERE

WriteHERE is a recursive task planning and execution framework that uses large language models (LLMs) to break down complex writing tasks into manageable subtasks. One of the most critical components of this system is the **Task Planning and Decomposition** process, which is responsible for transforming high-level writing goals into a structured hierarchy of executable tasks.

This guide focuses on how the planning process works, how plans are created by LLMs, and how they are converted into executable graph structures.

## Task Planning Overview

Task planning in WriteHERE involves:

1. Using an LLM to decompose a task into logical subtasks
2. Converting that plan into a graph of node objects
3. Establishing dependencies between tasks
4. Preparing the nodes for execution

This process happens recursively, allowing complex tasks to be broken down into increasingly specific subtasks until atomic execution nodes are reached.

## Planning Agent

The planning process begins with the `UpdateAtomPlanningAgent`, which is responsible for asking the LLM to create a plan:

```python
# recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward (around line ~50)
# Breakpoint 5: Task planning and decomposition

# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
    # Entry point for planning

    # --> SET BREAKPOINT HERE <-- (After prompt construction)
    prompt_kwargs = self._build_input(node, memory, *args, **kwargs)

    # --> SET BREAKPOINT HERE <-- (After LLM call)
    llm_response = self.get_llm_output(prompt_kwargs, self.llm_args)

    # --> SET BREAKPOINT HERE <-- (After parsing)
    result = self._parse_output(llm_response, node, memory, *args, **kwargs)
    return result
```

**Values to examine:**

- `node`: The `PLAN_NODE` being decomposed. Check its `task_info["goal"]`
- `prompt_kwargs`: The context being provided to the LLM
  - Step _into_ `_build_input` to see how it's constructed
  - Look for `"goal"`, `"previous_results"`, and any task-specific context
  - Verify the `prompt_version` used
- `llm_response.content`: The raw LLM response
- `result["result"]`: The parsed plan structure - a list of task dictionaries

### Planning Prompt Construction

The planning agent constructs a prompt that instructs the LLM on how to decompose the task. The prompt typically includes:

1. The task goal from `node.task_info["goal"]`
2. Instructions for how to structure the response
3. Guidelines on task granularity and types
4. Examples of good decompositions (in some cases)

The exact content of the prompt is determined by the `prompt_version` specified in the agent's configuration.

### LLM Plan Generation

The LLM responds to the planning prompt with a structured plan, usually in a format like:

```xml
<plan>
  <task>
    <id>1</id>
    <goal>Research background information on the topic</goal>
    <task_type>search</task_type>
    <dependency></dependency>
    <atom>true</atom>
  </task>
  <task>
    <id>2</id>
    <goal>Define key concepts and terminology</goal>
    <task_type>write</task_type>
    <dependency>1</dependency>
    <atom>true</atom>
  </task>
  <!-- Additional tasks... -->
</plan>
```

The plan specifies:

- Unique IDs for each task
- Clear goals for each subtask
- Task types (write, think, search)
- Dependencies between tasks
- Whether tasks are atomic or need further decomposition

### Plan Parsing

The `_parse_output` method of the planning agent is responsible for parsing the LLM's structured response into a list of task dictionaries:

```python
def _parse_output(self, response, node, memory, *args, **kwargs):
    # Extract the plan XML or JSON from the LLM response
    plan_data = extract_structured_data(response.content)

    # Parse into a list of task dictionaries
    tasks = []
    for task_element in plan_data.find_all("task"):
        task = {
            "id": task_element.find("id").text,
            "goal": task_element.find("goal").text,
            "task_type": task_element.find("task_type").text,
            "dependency": [dep.strip() for dep in task_element.find("dependency").text.split(",") if dep.strip()],
            "atom": task_element.find("atom").text.lower() == "true" if task_element.find("atom") else False
        }
        tasks.append(task)

    return {"result": tasks}
```

The result is a list of dictionaries, each representing a subtask in the plan.

## Plan to Graph Conversion

Once the planning agent has created a plan, the node system needs to convert it into an executable graph structure:

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

The `plan` method does two things:

1. Calls the planning agent to get a plan
2. Converts that plan into a graph using `plan2graph`

### Graph Creation

The `plan2graph` method is responsible for creating actual node objects from the plan:

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

This method:

1. Creates a `Node` object for each task in the plan
2. Determines if each node is a `PLAN_NODE` (needs further decomposition) or `EXECUTE_NODE` (atomic task)
3. Sets up parent-child relationships based on dependencies
4. Creates a `Graph` object to hold these nodes
5. Builds the graph structure with edges representing dependencies

### Node Type Determination

Each task in the plan is converted to either a `PLAN_NODE` or an `EXECUTE_NODE`:

- `PLAN_NODE`: A non-atomic task that will be further decomposed into subtasks
- `EXECUTE_NODE`: An atomic task that will be directly executed

The determination is made based on the `atom` flag in the task dictionary:

```python
node_type = NodeType.PLAN_NODE if not task.get("atom") else NodeType.EXECUTE_NODE
```

### Dependency Processing

The system processes dependencies to establish the correct execution order:

```python
# For each node, set up parent-child relationships
for node in nodes:
    dependencies = node.task_info.get("dependency", [])
    for dep_id in dependencies:
        if dep_id in id2node:
            parent_node = id2node[dep_id]
            node.node_graph_info["parent_nodes"].append(parent_node)
```

Additional dependency processing may occur for specific task types:

- `REASONING` tasks often depend on multiple sources
- `COMPOSITION` tasks may have implicit dependencies on previous sections

### Graph Building

After nodes are created and dependencies are processed, the system builds a `Graph` object:

```python
# Create the graph
self.inner_graph = Graph(self)

# Add nodes to the graph
for node in nodes:
    self.inner_graph.add_node(node)

# Add edges based on dependencies
for node in nodes:
    for parent_node in node.node_graph_info["parent_nodes"]:
        self.inner_graph.add_edge(parent_node, node)

# Sort nodes topologically
self.inner_graph.topological_sort()
```

The resulting graph is stored in the parent node's `inner_graph` attribute, and its `topological_task_queue` contains the nodes sorted in dependency order.

## Task Types and Specialization

Tasks in WriteHERE are categorized into three main types:

1. **COMPOSITION**: Writing tasks that generate content
2. **REASONING**: Analytical tasks that involve thinking or analyzing
3. **RETRIEVAL**: Search tasks that gather information

These types are defined in the configuration and mapped to human-readable tags:

```python
config["tag2task_type"] = {
    "write": "COMPOSITION",
    "think": "REASONING",
    "search": "RETRIEVAL"
}
```

The task type influences:

- Which agent is used for execution
- How context is provided
- How results are formatted
- How dependencies are processed

## Recursive Planning

The power of WriteHERE comes from its recursive planning approach:

1. The root task is decomposed into subtasks
2. Non-atomic subtasks (PLAN_NODEs) are further decomposed
3. This continues until all paths end in atomic tasks (EXECUTE_NODEs)

This creates a hierarchical task structure that mirrors how humans break down complex writing tasks.

## Common Task Planning Issues

### Task Decomposition Problems

**Symptoms:**

- Illogical or too granular task breakdowns
- Missing critical tasks
- Circular dependencies

**Investigation approach:**

1. Break at **Breakpoint 5** (Planning)
2. Examine the planning prompt in `prompt_kwargs`
   - Check how the task goal is presented
   - Note any constraints or examples provided
3. Look at the raw LLM response in `llm_response.content`
   - Is the LLM following the requested format?
   - Are its task breakdowns logical?
4. Check `plan2graph` conversion at **Breakpoint 6** for any filtering or alterations
5. Verify dependency resolution in the graph creation

**Key questions:**

- Is the planning prompt clear about desired decomposition?
- Is the LLM temperature appropriate? (Lower for more predictable planning)
- Does the plan validation catch issues?
- Are circular dependencies being created or unresolvable plans?

## Advanced Debugging Techniques

### Visualizing the Task Graph

To visualize the task hierarchy after planning:

```python
# Add temporarily after plan2graph completes
from recursive.utils.display import display_graph
display_graph(self.inner_graph, fn=f"plan_graph_{self.nid}.png")
```

This creates an image showing:

- Nodes with their IDs and types
- Dependency relationships between nodes
- The hierarchical structure of the plan

### Analyzing Plan Quality

To evaluate plan quality, you can add logging that tracks metrics like:

```python
def analyze_plan(raw_plan):
    task_types = Counter(task.get("task_type") for task in raw_plan)
    dependency_counts = Counter(len(task.get("dependency", [])) for task in raw_plan)
    has_cycles = check_dependency_cycles(raw_plan)

    logger.info(f"Plan analysis: {len(raw_plan)} tasks")
    logger.info(f"Task types: {dict(task_types)}")
    logger.info(f"Dependency counts: {dict(dependency_counts)}")
    logger.info(f"Has cycles: {has_cycles}")
```

### Conditional Breakpoints for Planning

```python
# Break only when planning a task with a specific keyword
# recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.forward
condition: '"introduction" in str(node.task_info["goal"]).lower()'

# Break when creating a plan with many tasks
# recursive/graph.py:AbstractNode.plan2graph
condition: 'len(raw_plan) > 10'
```

## Next Steps

- Explore [Task Execution](06-task-execution.md) to understand how the planned tasks are carried out
- Learn about [Result Aggregation](07-result-aggregation.md) to see how results are synthesized
- Review the [Node System and State Machine](02-node-system.md) for deeper understanding of the node structure
- Study the [Agent System](03-agent-system.md) to learn more about the planning agent's implementation
