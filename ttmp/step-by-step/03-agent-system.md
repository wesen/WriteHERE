# WriteHERE Agent System

## Introduction to WriteHERE

WriteHERE is a recursive task planning and execution framework that uses large language models (LLMs) to break down complex writing tasks into manageable subtasks. One of the core components of this system is the **Agent System**, which provides specialized modules that perform specific actions on nodes.

This guide focuses on how the Agent System works, its key components, and how to debug it effectively.

## Agent System Overview

In WriteHERE, agents are specialized classes responsible for performing specific actions on nodes in the task graph. The agent system uses a proxy pattern to dynamically select and instantiate the appropriate agent for each action required by a node.

The main agent types include:

1. **Planning Agent** (`UpdateAtomPlanningAgent`): Decomposes tasks into subtasks
2. **Execution Agent** (`SimpleExcutor`): Performs writing, reasoning, or search tasks
3. **Aggregation Agent** (`FinalAggregateAgent`): Synthesizes results from subtasks
4. **Reflection Agents**: Evaluate and potentially revise execution

## Agent Proxy Pattern

Agents are not directly instantiated by nodes. Instead, a proxy system is used to dynamically select and initialize the appropriate agent based on the required action:

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

**Values to examine:**

- `action_name`: The action being requested (plan/execute/etc.)
- `self.config["action_mapping"][action_name]`: Agent class name and parameters
- `agent_cls_name`: The name of the agent class to be used (e.g., `"UpdateAtomPlanningAgent"`, `"SimpleExcutor"`)
- `agent_kwargs`: Any specific configuration passed to the agent's constructor
- `agent`: The instantiated agent object

This proxy pattern allows for flexible configuration of which agent implements which action. The mapping is defined in the `config` dictionary under `"action_mapping"`.

## Agent Base Class

All agent classes inherit from a common `AgentBase` class, which defines the general execution flow:

```python
# recursive/agent/agent_base.py:AgentBase.forward (around line ~30)
# Breakpoint 5: The main entry point for any agent's execution
import recursive.agent.helpers


# --> SET BREAKPOINT HERE <--
def forward(self, node, memory, *args, **kwargs):
    # 1. Build Input
    # --> SET BREAKPOINT HERE <-- (Before building input)
    prompt_kwargs = self._build_input(node, memory, *args, **kwargs)

    # 2. Get LLM Output (potentially cached)
    # --> SET BREAKPOINT HERE <-- (Before calling LLM/cache)
    response = recursive.agent.helpers.get_llm_output(prompt_kwargs, self.llm_args)  # Step into this

    # 3. Parse Output
    # --> SET BREAKPOINT HERE <-- (Before parsing output)
    result = self._parse_output(response, node, memory, *args, **kwargs)

    return result
```

```result

```

The core agent execution flow consists of three main stages:

1. **Input preparation** (`_build_input`): Constructs the context for the LLM
2. **LLM interaction** (`get_llm_output`): Gets output from the LLM or cache
3. **Output parsing** (`_parse_output`): Processes the LLM response into a structured format

Each specific agent type overrides these methods to implement its specialized behavior.

## Agent Configuration

Agents receive their configuration from the system's main `config` dictionary. The typical agent structure includes:

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

The configuration controls:

- Which prompt template to use
- LLM parameters like temperature and max tokens
- Task-specific behavior flags

## Key Agent Types

### 1. Planning Agent (UpdateAtomPlanningAgent)

Responsible for decomposing a task into subtasks:

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

This agent:

- Builds a planning prompt based on the node's goal
- Asks the LLM to create a structured plan of subtasks
- Parses the response into a list of task dictionaries
- Returns this plan to be converted into a node graph

### 2. Execution Agent (SimpleExcutor)

Handles the actual execution of tasks:

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

This agent:

- Determines the task type (composition, reasoning, or retrieval)
- For writing/reasoning tasks: Builds a prompt, calls the LLM, and parses the response
- For search tasks: Can use a multi-step search process and optionally merge results
- Returns the task output (generated text, analysis, or search results)

### 3. Aggregation Agent (FinalAggregateAgent)

Combines results from subtasks:

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

This agent:

- Collects results from all completed subtasks
- Builds an aggregation prompt that includes these results
- Asks the LLM to synthesize the results into a coherent whole
- Returns the synthesized output

## Agent Interface with the LLM

Agents interact with LLMs through standardized methods:

### 1. `get_llm_output` Method

```python
def get_llm_output(self, prompt_kwargs, llm_args):
    # Check cache first
    cache_key = cache.get_key(prompt_kwargs, llm_args)
    response = cache.get(cache_key, lambda: self._call_llm(prompt_kwargs, llm_args))
    return response
```

This method:

- Tries to find the result in cache first
- If not found, calls the LLM via `_call_llm`
- Returns the response

### 2. `_call_llm` Method

```python
def _call_llm(self, prompt_kwargs, llm_args):
    # Construct prompt from template
    prompt = get_prompt_template(self.prompt_version).format(**prompt_kwargs)

    # Call LLM with appropriate backend
    response = self.backend.call_llm(prompt, **llm_args)
    return response
```

This method:

- Retrieves the prompt template for the agent's `prompt_version`
- Formats it with the `prompt_kwargs`
- Calls the LLM backend with the formatted prompt and LLM arguments
- Returns the response

## Debugging Agent Issues

### Agent Selection Problems

**Symptoms:**

- Wrong agent being used for an action
- Missing agent implementation

**Investigation approach:**

1. Break at [Breakpoint 4](#agent-proxy-pattern) (Agent Proxy)
2. Verify that `action_name` is mapped correctly in `config["action_mapping"]`
3. Check that the specified agent class exists and is imported correctly

### LLM Interaction Issues

**Symptoms:**

- Poor-quality LLM outputs
- LLM not following the prompt instructions

**Investigation approach:**

1. Break inside `get_llm_output` before the LLM call
2. Examine the full prompt being sent to the LLM
3. Check the LLM parameters (temperature, max_tokens, etc.)
4. Examine the raw response from the LLM

### Parsing Problems

**Symptoms:**

- Agent failures with parsing errors
- Missing or malformed data in results

**Investigation approach:**

1. Break at `_parse_output` in the relevant agent
2. Check the raw LLM response content
3. Examine the parsing logic to ensure it matches the expected format
4. Verify the structure of the returned `result` dictionary

## Advanced Debugging Techniques

### Watching for LLM Quality Issues

```python
# Add to AgentBase.get_llm_output
if len(llm_response.content) < 50:  # Suspiciously short response
    logger.warning(f"Short LLM response from {self.__class__.__name__}: {llm_response.content}")
    # Consider setting a breakpoint here
```

### Cache Inspection

```python
# Add to AgentBase.get_llm_output
cache_key = cache.get_key(prompt_kwargs, self.llm_args)
before = time.time()
response = cache.get(cache_key, lambda: self._call_llm(prompt_kwargs, self.llm_args))
after = time.time()
logger.debug(f"LLM call for {self.__class__.__name__}: cache_hit={after-before<0.1}, took {after-before:.3f}s")
```

## Extending the Agent System

To add a new agent type:

1. Create a new class in `recursive/agent/agents/` that inherits from `AgentBase`
2. Implement the `_build_input`, `_parse_output`, and any specialized methods
3. Update the `config["action_mapping"]` to use your new agent for the desired action

## Next Steps

- Examine [Node System and State Machine](02-node-system.md) to understand what nodes the agents operate on
- Explore [Memory and Context Management](04-memory-system.md) to see how agents share information
- Learn about [Task Planning and Decomposition](05-task-planning.md) for deeper insights into the planning agent
- Study [Task Execution](06-task-execution.md) to understand the execution agent in more detail
