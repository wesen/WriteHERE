# WriteHERE Result Aggregation

## Introduction to WriteHERE

WriteHERE is a recursive task planning and execution framework that uses large language models (LLMs) to break down complex writing tasks into manageable subtasks. After tasks are planned and executed, the system needs to synthesize the results of subtasks into coherent, unified outputs.

This guide focuses on the **Result Aggregation** process, which is responsible for combining the outputs of multiple subtasks into a cohesive whole that fulfills the parent task's goal.

## Result Aggregation Overview

Result aggregation in WriteHERE involves:

1. Collecting results from all completed subtasks in a node's inner graph
2. Providing these results, along with the parent task's goal, to the aggregation agent
3. Using an LLM to synthesize the results into a coherent output
4. Storing the synthesized result in the parent node

This process ensures that the outputs of atomic tasks are properly integrated into the overall document structure.

## Aggregation Process Flow

When all subtasks of a plan node are completed, the node transitions to the `FINAL_TO_FINISH` state, which triggers the aggregation process:

```python
self.status_action_mapping = {
    # ... other mappings ...
    TaskStatus.FINAL_TO_FINISH: ("final_aggregate", lambda node, *args, **kwargs: True)
}
```

The `final_aggregate` action is typically mapped to the `FinalAggregateAgent` in the configuration.

## FinalAggregateAgent

The aggregation process is handled by the `FinalAggregateAgent`, which is responsible for synthesizing results from subtasks:

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

**Values to examine:**

- `node`: The parent `PLAN_NODE` whose subtasks are being aggregated
- `inner_results`: Dictionary mapping subtask node IDs to their results
- `prompt_kwargs`: The context provided to the LLM for aggregation
- `llm_response`: The raw response from the LLM
- `result`: The structured final result after parsing

## Collecting Inner Results

The first step in aggregation is collecting results from all subtasks. This is done by the Memory system's `collect_inner_results` method:

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

1. Iterates through all child nodes in the node's inner graph
2. For each finished child, retrieves its final result
3. Returns a dictionary mapping node IDs to their results

## Aggregation Prompt Construction

The aggregation agent builds a prompt that instructs the LLM on how to synthesize the subtask results:

```python
def _build_input(self, node, memory, inner_results=None, *args, **kwargs):
    # Basic task information
    prompt_kwargs = {
        "goal": node.task_info["goal"],
        "task_type": node.task_info["task_type"],
    }

    # Format inner results for integration
    formatted_results = {}
    for child_id, child_result in inner_results.items():
        formatted_results[child_id] = {
            "goal": child_result.get("goal", ""),
            "content": child_result.get("content", ""),
            "task_type": child_result.get("task_type", "")
        }

    prompt_kwargs["inner_results"] = formatted_results

    # Add any constraints or special instructions
    if "length" in node.task_info:
        prompt_kwargs["length"] = node.task_info["length"]

    # Add document context if needed
    if memory.article:
        prompt_kwargs["article_context"] = truncate_article(memory.article, max_length=1000)

    return prompt_kwargs
```

The prompt typically includes:

- The parent task's goal
- All subtask results, with their goals and content
- Any constraints (like length limits)
- Instructions for synthesizing the results coherently

## Synthesis and Integration

The LLM uses the provided context to synthesize the subtask results into a coherent whole. The aggregation prompt is crucial for guiding this synthesis process.

### Example Aggregation Prompt

```
Your task is to synthesize the following results into a coherent section that fulfills the goal:

GOAL: Write a comprehensive overview of renewable energy sources

SUBTASK RESULTS:
1. [ID: 1]
   Goal: Describe solar energy technologies and applications
   Content: Solar energy harnesses the power of the sun through photovoltaic cells and solar thermal systems. Photovoltaic (PV) technology directly converts sunlight into electricity using semiconductor materials that exhibit the photovoltaic effect...

2. [ID: 2]
   Goal: Explain wind energy generation and its advantages
   Content: Wind energy converts the kinetic energy of moving air into electricity through wind turbines. Modern wind turbines typically consist of three blades mounted on a tall tower, connected to a generator...

3. [ID: 3]
   Goal: Outline hydroelectric power and its environmental considerations
   Content: Hydroelectric power generates electricity by harnessing the energy of flowing water. Typically, dams are constructed on rivers to create reservoirs, allowing controlled water flow through turbines...

INSTRUCTIONS:
- Synthesize these results into a unified, coherent section
- Ensure smooth transitions between different energy sources
- Maintain a consistent tone and style throughout
- Focus on fulfilling the overall goal while preserving key information
```

### Output Parsing and Storage

After the LLM generates the synthesized content, the agent parses it and returns a structured result:

```python
def _parse_output(self, response, node, memory, *args, **kwargs):
    # For final aggregation, the result typically contains the synthesized content
    return {
        "result": {
            "content": response.content.strip(),
            "goal": node.task_info["goal"],
            "task_type": "AGGREGATION"
        }
    }
```

This result is then stored in the node's `result` dictionary under the `"final_aggregate"` key.

## Recursive Aggregation

One of the powerful aspects of WriteHERE's architecture is that aggregation happens recursively at each level of the task hierarchy:

1. Atomic task results are aggregated by their immediate parent
2. These aggregated results are then aggregated by their parent
3. This continues up the hierarchy until reaching the root node

This recursive aggregation ensures that coherence is maintained at all levels of the document structure.

## Handling Different Task Types

The aggregation process may vary depending on the types of tasks being aggregated:

### 1. Aggregating Writing Tasks

When aggregating multiple writing tasks (COMPOSITION), the focus is on:

- Creating smooth transitions between sections
- Ensuring stylistic consistency
- Maintaining a logical flow

### 2. Aggregating Analysis Tasks

When aggregating reasoning or analysis tasks (REASONING), the focus is on:

- Synthesizing potentially diverse perspectives
- Resolving conflicting analyses
- Creating a coherent analytical framework

### 3. Aggregating Search Tasks

When aggregating search results (RETRIEVAL), the focus is on:

- Consolidating information from multiple sources
- Eliminating redundancies
- Highlighting the most relevant findings

## Debugging Aggregation

### Aggregation Breakpoint

```python
# recursive/agent/agents/regular.py:FinalAggregateAgent.forward (around line ~300)
# Breakpoint 8: Synthesizing results from subtasks

# --> SET BREAKPOINT HERE <-- (Start of forward)
def forward(self, node, memory, *args, **kwargs):
```

**Values to examine:**

- `node`: The node whose subtasks are being aggregated
  - Check its `task_info`, `node_type`, and `status`
  - Verify that its inner graph contains completed subtasks
- `memory`: The memory object providing context

### Inner Results Collection

Set a breakpoint after collecting inner results:

```python
# --> SET BREAKPOINT HERE <-- (After gathering inner results)
inner_results = memory.collect_inner_results(node)
```

**Values to examine:**

- `inner_results`: Dictionary mapping subtask IDs to their results
  - Check that all expected subtasks are present
  - Verify that each result contains the expected content
  - Look for any missing or unusually formatted results

### Aggregation Prompt Construction

Set a breakpoint after building the aggregation prompt:

```python
# --> SET BREAKPOINT HERE <-- (After building the aggregation prompt)
prompt_kwargs = self._build_input(node, memory, inner_results=inner_results, *args, **kwargs)
```

**Values to examine:**

- `prompt_kwargs`: The context provided to the LLM
  - Check the parent task's goal
  - Verify that all subtask results are included
  - Check how the results are formatted for the LLM
  - Look for any aggregation instructions or constraints

## Common Aggregation Issues

### Incomplete Synthesis

**Symptoms:**

- Some subtask content is missing from the aggregated result
- The aggregated result seems biased toward certain subtasks
- Important details are lost during aggregation

**Investigation approach:**

1. Break at the aggregation breakpoint
2. Examine the inner results to ensure all subtasks are included
3. Check how results are formatted in the aggregation prompt
4. Verify that the LLM is given clear instructions for synthesis

**Key questions:**

- Are all subtask results being collected and provided to the LLM?
- Is the prompt structure prioritizing certain results over others?
- Are there clear instructions for comprehensive synthesis?

### Incoherent Integration

**Symptoms:**

- Abrupt transitions between sections in the aggregated result
- Inconsistent style or tone across the document
- Repetition of information from different subtasks

**Investigation approach:**

1. Break after the LLM call for aggregation
2. Examine the raw LLM response
3. Check the aggregation prompt for instructions on coherence
4. Compare the subtask results to see if they have consistent formats

**Key questions:**

- Does the aggregation prompt emphasize coherence and integration?
- Are the subtask results themselves consistent in format and style?
- Would additional context help the LLM create smoother transitions?

### Context Overload in Aggregation

**Symptoms:**

- Aggregation fails or produces poor results for complex tasks
- The LLM seems to ignore parts of the context
- Aggregation is slow or times out

**Investigation approach:**

1. Break before the LLM call
2. Check the total size of the aggregation prompt
3. Examine how subtask results are structured and prioritized
4. Consider if summarization or filtering should be applied to subtask results

**Key questions:**

- Is the aggregation prompt exceeding the LLM's context window?
- Could subtask results be summarized before aggregation?
- Should certain types of results be prioritized over others?

## Advanced Debugging Techniques

### Aggregation Visualization

To visualize how subtasks contribute to the aggregated result:

```python
def visualize_aggregation(node_result, inner_results):
    """Generate a visualization of how subtasks contribute to the aggregated result."""
    aggregated_content = node_result.get("content", "")

    # Track content from each subtask
    content_mapping = {}
    for child_id, child_result in inner_results.items():
        content = child_result.get("content", "")
        for sentence in split_into_sentences(content):
            sentence = sentence.strip()
            if sentence and len(sentence) > 20:  # Ignore very short sentences
                # Find this content in the aggregated result
                if sentence in aggregated_content:
                    content_mapping[sentence] = child_id

    # Generate visualization
    annotated_content = aggregated_content
    for sentence, child_id in content_mapping.items():
        annotated_content = annotated_content.replace(
            sentence,
            f"<span style='color: {get_color_for_id(child_id)};'>{sentence}</span>"
        )

    return f"<html><body>{annotated_content}</body></html>"
```

### Aggregation Metrics

To evaluate aggregation quality:

```python
def evaluate_aggregation(node_result, inner_results):
    """Calculate metrics to evaluate aggregation quality."""
    aggregated_content = node_result.get("content", "")

    # Calculate coverage (what percentage of subtask content is included)
    coverage_scores = {}
    total_content = ""
    for child_id, child_result in inner_results.items():
        content = child_result.get("content", "")
        total_content += content
        coverage = calculate_content_coverage(content, aggregated_content)
        coverage_scores[child_id] = coverage

    # Calculate coherence score
    coherence_score = estimate_text_coherence(aggregated_content)

    # Calculate content density (ratio of aggregated size to sum of parts)
    density = len(aggregated_content) / (len(total_content) + 1)  # +1 to avoid division by zero

    return {
        "per_subtask_coverage": coverage_scores,
        "avg_coverage": sum(coverage_scores.values()) / len(coverage_scores),
        "coherence": coherence_score,
        "density": density
    }
```

## Extending Aggregation

To customize the aggregation process:

1. Create a specialized aggregation agent:

   ```python
   class CustomAggregationAgent(AgentBase):
       def _build_input(self, node, memory, inner_results=None, *args, **kwargs):
           # Custom prompt construction for specific task types

       def _parse_output(self, response, node, memory, *args, **kwargs):
           # Custom parsing of aggregated results
   ```

2. Update the action mapping in the configuration:

   ```python
   config["action_mapping"]["final_aggregate"] = ("CustomAggregationAgent", {"prompt_version": "custom_aggregation"})
   ```

3. Create specialized prompts for different task types or document structures

## Next Steps

- Review the [Task Execution](06-task-execution.md) process to understand how the results being aggregated are generated
- Explore the [Node System and State Machine](02-node-system.md) to understand how aggregation fits into the overall execution flow
- Study the [Memory and Context Management](04-memory-system.md) to understand how context is provided during aggregation
- Complete your exploration with the [Debugging Workflow](08-debugging-workflow.md) for a comprehensive approach to debugging
