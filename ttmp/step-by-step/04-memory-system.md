# WriteHERE Memory System and Context Management

## Introduction to WriteHERE

WriteHERE is a recursive task planning and execution framework that enables LLMs to generate well-structured documents. The system decomposes complex writing tasks into a hierarchy of subtasks represented as nodes in a directed acyclic graph (DAG).

This guide focuses on the **Memory System**, which is responsible for managing context, caching node information, and maintaining the growing document as tasks are executed.

## Memory System Overview

The Memory system serves as a shared state repository that:

1. Tracks the growing document
2. Caches node information
3. Provides context between executions
4. Facilitates information sharing between nodes

The Memory system is crucial for maintaining coherence across the generated content and ensuring that subtasks have access to relevant context from other parts of the document.

## Memory Data Structure

The Memory object contains these key components:

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

## Memory Updates

During execution, the Memory system is updated before each node's action is performed:

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

This method:

1. Collects and caches information for each specified node
2. Updates the article by computing it from the node graph

## Node Information Collection

The system collects context information for nodes to use during their execution:

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

This method:

1. Checks if the node's information is already cached
2. If not, computes the information using `_compute_node_info`
3. Caches the information for future use
4. Returns the information

## Context Information Computation

The exact information collected depends on the node type and task, but typically includes:

- The node's goal and task type
- Results from dependency nodes
- Parent task context
- Relevant sections of the growing document
- Any constraints or special instructions

The `_compute_node_info` method is responsible for gathering this information:

```python
def _compute_node_info(self, node):
    info = {}

    # Basic node info
    info["goal"] = node.task_info["goal"]
    info["task_type"] = node.task_info["task_type"]

    # Dependency results
    info["dependency_results"] = {}
    for parent in node.node_graph_info["parent_nodes"]:
        if parent.status == TaskStatus.FINISH:
            # Get results from finished dependencies
            info["dependency_results"][parent.nid] = parent.get_node_final_result()

    # Parent context
    if node.node_graph_info["outer_node"]:
        parent = node.node_graph_info["outer_node"]
        info["parent_goal"] = parent.task_info["goal"]

    # Other context information...

    return info
```

## Article Computation

The `_compute_article` method assembles the current state of the document by traversing the node graph and collecting completed content:

```python
def _compute_article(self):
    article = ""

    # Start from the root node
    root = self.root_node

    # Helper function for recursive traversal
    def collect_content(node):
        nonlocal article

        # If node is finished, add its content
        if node.status == TaskStatus.FINISH:
            result = node.get_node_final_result()
            if result:
                article += result.get("content", "")

        # If node has inner graph, traverse it
        if hasattr(node, "inner_graph") and node.inner_graph:
            for child in node.inner_graph.topological_task_queue:
                collect_content(child)

    # Start traversal
    collect_content(root)
    return article
```

This method ensures that the `article` field in memory contains the most up-to-date version of the generated content, which can then be used to provide context for subsequent tasks.

## Result Collection for Aggregation

When aggregating results from subtasks, the Memory system provides a specialized method:

```python
def collect_inner_results(self, node):
    results = {}

    if hasattr(node, "inner_graph") and node.inner_graph:
        for child in node.inner_graph.topological_task_queue:
            if child.status == TaskStatus.FINISH:
                results[child.nid] = child.get_node_final_result()

    return results
```

This method:

1. Gathers results from all finished subtasks in a node's inner graph
2. Returns them as a dictionary mapped by node ID
3. Is used by the `FinalAggregateAgent` during result synthesis

## The Flow of Context Through the System

To understand how context flows through the system:

1. **Node Initialization**: Nodes are created with basic task information
2. **Before Execution**: The Memory system collects context for the node
3. **During Execution**: Agents use this context in their prompts to the LLM
4. **After Execution**: Results are stored in the node
5. **During Aggregation**: Results from subtasks are collected and synthesized
6. **Article Update**: The growing document is updated with new content

This flow ensures that each task has access to all relevant information from dependencies and the overall document structure.

## Debugging the Memory System

### Memory Update Breakpoint

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

**Values to examine:**

- `nodes`: The list containing the node(s) about to act
- Step _into_ `collect_node_run_info` for each node
- Step _into_ `_compute_article` to see how the final text is assembled
- `self.article`: Current accumulated document before and after the update

### Node Information Collection Breakpoint

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

**Values to examine:**

- `node`: The node for which information is being collected
- Check if `node.hashkey` is in `self.collected_info` (cache hit)
- If not cached, step _into_ `_compute_node_info`
- `info`: The computed context information
- `self.collected_info`: Cache of node information

## Common Memory System Issues

### Memory Management Issues

**Symptoms:**

- Missing or incorrect context for task execution
- Article not updating properly
- Duplicate content in the final document

**Investigation approach:**

1. Break at Memory Updates breakpoint
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

### Context Loss Between Tasks

**Symptoms:**

- Subtasks seem disconnected from parent tasks
- Information from dependencies isn't used effectively
- Content repetition or contradictions

**Investigation approach:**

1. Break at the Memory Update breakpoint
2. Examine the context information collected for the node
3. Step into `_compute_node_info` to see how dependency results and parent context are gathered
4. Check agent prompts to verify that context is being included

**Key questions:**

- Are dependency results properly collected and formatted?
- Is relevant context from the parent task being included?
- Is the context being properly used in agent prompts?

## Advanced Debugging Tools

### Memory Inspection Helper

```python
def inspect_memory(memory, node_hashkey=None):
    """Print key memory information for debugging"""
    print(f"Current article length: {len(memory.article)} chars")
    print(f"Cached node count: {len(memory.collected_info)}")
    if node_hashkey and node_hashkey in memory.collected_info:
        print(f"Node info keys: {memory.collected_info[node_hashkey].keys()}")
        for key, value in memory.collected_info[node_hashkey].items():
            print(f"  {key}: {type(value)} of size {len(str(value))}")
```

### Cache Performance Monitoring

```python
# Add to Memory.collect_node_run_info at the start
hits = getattr(self, '_cache_hits', 0)
misses = getattr(self, '_cache_misses', 0)

if node.hashkey in self.collected_info:
    self._cache_hits = hits + 1
    logger.debug(f"Cache hit for node {node.nid} ({hits+1}/{hits+misses+1} hits)")
    return self.collected_info[node.hashkey]
else:
    self._cache_misses = misses + 1
    logger.debug(f"Cache miss for node {node.nid} ({hits}/{hits+misses+1} hits)")
```

## Next Steps

- Explore the [Node System and State Machine](02-node-system.md) to understand the nodes that memory manages
- Learn about the [Agent System](03-agent-system.md) to see how agents use the context provided by memory
- Dive into [Task Planning and Decomposition](05-task-planning.md) to understand how the task hierarchy is created
- Study [Task Execution](06-task-execution.md) to see how context is used during task execution
