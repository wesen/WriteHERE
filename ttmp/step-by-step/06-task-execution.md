# WriteHERE Task Execution

## Introduction to WriteHERE

WriteHERE is a recursive task planning and execution framework that uses large language models (LLMs) to break down complex writing tasks into manageable subtasks. After tasks are planned and organized into a graph structure, the system needs to execute the atomic tasks at the leaves of the task hierarchy.

This guide focuses on the **Task Execution** process, which is responsible for performing the actual writing, reasoning, and search operations that produce the content of the final document.

## Task Execution Overview

Task execution in WriteHERE involves:

1. Processing `EXECUTE_NODE` instances that represent atomic tasks
2. Determining the task type (COMPOSITION, REASONING, or RETRIEVAL)
3. Providing appropriate context from memory and dependencies
4. Calling the LLM with a specialized prompt or performing search operations
5. Processing the results and storing them in the node

The execution engine handles one node at a time, ensuring that all dependencies are completed before a node is executed.

## Execution Agent (SimpleExcutor)

The execution process is handled by the `SimpleExcutor` agent, which is responsible for executing atomic tasks:

```python
# recursive/agent/agents/regular.py:SimpleExcutor.forward (around line ~150)
# Breakpoint 7: Actual task execution

# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
    # Determine task type:
    task_type_tag = node.task_type_tag  # COMPOSITION, REASONING, or RETRIEVAL
    # --> SET BREAKPOINT HERE <-- (After task type determination)

    if task_type_tag in ("COMPOSITION", "REASONING"):
        # --> SET BREAKPOINT HERE <-- (Before LLM call for write/think)
        prompt_kwargs = self._build_input(node, memory, *args, **kwargs)
        llm_response = self.get_llm_output(prompt_kwargs, self.llm_args)
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

**Values to examine:**

- `node`: The `EXECUTE_NODE` being executed
- `task_type_tag`: Indicates whether this is a COMPOSITION (writing), REASONING (thinking), or RETRIEVAL (search) task
- `prompt_kwargs`: For writing and reasoning tasks, the context provided to the LLM
- `llm_response`: The raw response from the LLM
- `result`: The structured result after parsing

## Task Types and Execution Paths

The execution path varies based on the task type:

### 1. COMPOSITION Tasks (Writing)

For writing tasks, the execution process:

1. Builds a prompt that includes the goal and relevant context
2. Calls the LLM to generate text content
3. Parses the result and returns it in a structured format

Example prompt construction:

```python
def _build_input(self, node, memory, *args, **kwargs):
    # Basic task information
    prompt_kwargs = {
        "goal": node.task_info["goal"],
        "task_type": node.task_info["task_type"],
    }

    # Add dependency results
    dependency_results = memory.get_node_info(node).get("dependency_results", {})
    if dependency_results:
        prompt_kwargs["previous_results"] = format_dependency_results(dependency_results)

    # Add length constraint if specified
    if "length" in node.task_info:
        prompt_kwargs["length"] = node.task_info["length"]

    # Add parent context
    if node.node_graph_info["outer_node"]:
        prompt_kwargs["parent_goal"] = node.node_graph_info["outer_node"].task_info["goal"]

    # Add article context
    if memory.article:
        prompt_kwargs["article_so_far"] = truncate_article(memory.article, max_length=2000)

    return prompt_kwargs
```

The generated content is then processed:

```python
def _parse_output(self, response, node, memory, *args, **kwargs):
    # For composition tasks, the result is typically just the generated text
    return {
        "result": {
            "content": response.content.strip(),
            "task_type": node.task_type_tag,
            "goal": node.task_info["goal"]
        }
    }
```

### 2. REASONING Tasks (Thinking)

For reasoning tasks, the execution is similar to writing tasks but with a different prompt structure:

1. Builds a prompt that emphasizes analytical thinking
2. Calls the LLM to perform reasoning or analysis
3. Parses the structured analysis result

The prompt typically encourages the LLM to:

- Break down the problem
- Consider multiple perspectives
- Support conclusions with evidence
- Provide structured analysis

The result is usually more structured than simple writing, often including explicit sections for analysis, evidence, and conclusions.

### 3. RETRIEVAL Tasks (Searching)

For search tasks, the execution can follow two main paths:

#### Simple Search:

For basic searches, the system might:

1. Extract search queries from the task goal
2. Perform web searches using an API
3. Return and format the search results

#### Multi-step ReAct Agent:

For more complex searches, the system may use a ReAct (Reasoning + Acting) approach:

```python
def react_agent_run(self, node, memory, *args, **kwargs):
    # Initial plan for search
    search_plan = self._create_search_plan(node, memory)

    # Execute multi-step search process
    results = []
    for step in search_plan:
        # Perform search
        search_results = self._execute_search(step["query"])

        # Analyze results
        analysis = self._analyze_search_results(search_results, step["goal"])

        results.append({
            "query": step["query"],
            "results": search_results,
            "analysis": analysis
        })

    # Synthesize all search results
    if self.config["RETRIEVAL"]["execute"].get("llm_merge", False):
        return self.search_merge(node, memory, results)
    else:
        return {"result": results}
```

After search tasks, results may be merged (synthesized) using the LLM to create a coherent summary:

```python
def search_merge(self, node, memory, search_results):
    # Create merge prompt
    prompt_kwargs = {
        "goal": node.task_info["goal"],
        "search_results": format_search_results(search_results)
    }

    # Ask LLM to synthesize search results
    llm_response = self.get_llm_output(prompt_kwargs, self.llm_args)

    # Parse and return
    return {
        "result": {
            "content": llm_response.content.strip(),
            "raw_search_results": search_results,
            "task_type": node.task_type_tag
        }
    }
```

## Execution Context

One of the key aspects of task execution is providing the right context to the LLM. The context typically includes:

### 1. Task-Specific Information

- The task goal (`node.task_info["goal"]`)
- Task type and any constraints (e.g., length)
- Any specific instructions for the task

### 2. Dependency Results

- Results from parent nodes that this task depends on
- These provide necessary information for the current task

### 3. Hierarchical Context

- The parent task's goal and context
- The broader section or document structure

### 4. Document Context

- The current state of the generated document
- Neighboring sections for coherence

The `Memory` system (covered in [Memory and Context Management](04-memory-system.md)) is responsible for gathering this context before execution.

## Task Execution and the State Machine

Execution is triggered by the state machine when a node's state transitions to an active state that maps to the "execute" action:

```python
self.status_action_mapping = {
    # ... other mappings ...
    TaskStatus.READY: ("execute", lambda node, *args, **kwargs: node.node_type == NodeType.EXECUTE_NODE)
}
```

After execution completes:

1. The result is stored in the node
2. The node's state transitions to `FINISH`
3. This may trigger parent nodes to transition to `FINAL_TO_FINISH` if all their subtasks are complete

## Debugging Task Execution

### Execution Breakpoint

```python
# recursive/agent/agents/regular.py:SimpleExcutor.forward (around line ~150)
# Breakpoint 7: Actual task execution

# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
    # Determine task type:
    task_type_tag = node.task_type_tag  # COMPOSITION, REASONING, or RETRIEVAL
```

**Values to examine:**

- `node`: The node being executed. Check its `task_info`, `node_type`, and `status`
- `memory`: The memory object providing context
- `task_type_tag`: The type of task (COMPOSITION, REASONING, or RETRIEVAL)

### Writing/Reasoning Execution

For composition and reasoning tasks, set a breakpoint before the LLM call:

```python
# --> SET BREAKPOINT HERE <-- (Before LLM call for write/think)
prompt_kwargs = self._build_input(node, memory, *args, **kwargs)
```

**Values to examine:**

- `prompt_kwargs`: The full context provided to the LLM
  - Step _into_ `_build_input` to see how context is gathered
  - Check for `"goal"`, `"previous_results"`, and other context
- `self.llm_args`: LLM parameters (model, temperature, etc.)

### Search Execution

For retrieval tasks with ReAct agent, set a breakpoint before starting the search:

```python
# --> SET BREAKPOINT HERE <-- (Before search agent)
result = self.react_agent_run(node, memory, *args, **kwargs)
```

**Values to examine:**

- Step _into_ `react_agent_run` to follow the search process
- Check search queries, results, and analysis

## Common Task Execution Issues

### Low-Quality Outputs

**Symptoms:**

- Generated content is irrelevant or low quality
- Content contradicts itself or the task goal
- Writing style is inconsistent with the rest of the document

**Investigation approach:**

1. Break at the execution breakpoint
2. Examine the prompt being sent to the LLM
   - Is the task goal clear?
   - Is sufficient context provided?
   - Are there conflicting instructions?
3. Check the LLM parameters
   - Is temperature appropriate for the task?
   - Is max_tokens sufficient?
4. Verify that dependency results are correctly included

**Key questions:**

- Is the prompt structured effectively for the task type?
- Are the LLM parameters appropriate for the task?
- Is important context from dependencies being included?

### Context Overload

**Symptoms:**

- LLM responses ignore relevant context
- Content generation is slow or fails
- Results focus on only part of the provided context

**Investigation approach:**

1. Break before the LLM call
2. Check the total size of the prompt
3. Examine how context is prioritized and truncated
4. Consider reducing context or improving its structure

**Key questions:**

- Is the prompt too large for the LLM's context window?
- Is the most important context prioritized?
- Could summarization help reduce context size?

### Search Failures

**Symptoms:**

- Search tasks return irrelevant results
- Search queries are poorly formulated
- Results aren't properly analyzed or synthesized

**Investigation approach:**

1. Break before the search agent
2. Step through the search planning process
3. Examine the generated queries
4. Check how results are processed and analyzed

**Key questions:**

- Are search queries well-formed?
- Is the search API working correctly?
- Is the analysis of search results effective?

## Advanced Debugging Techniques

### Execution Tracing

Add logging to track execution details:

```python
def forward(self, node, memory, *args, **kwargs):
    task_type_tag = node.task_type_tag

    logger.info(f"Executing {task_type_tag} task: {node.nid} - {node.task_info['goal'][:50]}...")
    start_time = time.time()

    # ... normal execution ...

    elapsed = time.time() - start_time
    logger.info(f"Completed {task_type_tag} task in {elapsed:.2f}s: {node.nid}")
    return result
```

### Prompt Inspection

To debug prompt issues:

```python
# Add to SimpleExcutor before LLM call
prompt = get_prompt_template(self.prompt_version).format(**prompt_kwargs)
prompt_tokens = len(prompt.split())
logger.debug(f"Prompt for {node.nid} ({prompt_tokens} tokens):\n{'-'*40}\n{prompt[:500]}...\n{'-'*40}")
```

### Result Analysis

To evaluate the quality of generated content:

```python
def analyze_result(result, goal):
    """Analyze the quality of a task result."""
    content = result.get("content", "")

    metrics = {
        "length": len(content),
        "goal_terms_count": count_goal_terms(content, goal),
        "readability_score": calculate_readability(content),
        "coherence_score": estimate_coherence(content)
    }

    logger.info(f"Result analysis: {metrics}")
    return metrics
```

## Extending Task Execution

To add support for a new task type:

1. Update the task type mapping in the configuration:

   ```python
   config["tag2task_type"]["new_type"] = "NEW_TASK_TYPE"
   ```

2. Add a new branch in the `SimpleExcutor.forward` method:

   ```python
   elif task_type_tag == "NEW_TASK_TYPE":
       # Implementation for the new task type
   ```

3. Implement specialized prompt construction and result parsing for the new task type

## Next Steps

- Learn about [Result Aggregation](07-result-aggregation.md) to understand how subtask results are synthesized
- Review the [Memory and Context Management](04-memory-system.md) to understand how context is provided
- Study the [Task Planning and Decomposition](05-task-planning.md) to understand how tasks are created
- Explore the [Debugging Workflow](08-debugging-workflow.md) for a comprehensive approach to debugging
