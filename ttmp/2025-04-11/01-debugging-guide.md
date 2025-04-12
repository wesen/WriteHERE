# Debugging Guide: WriteHERE Recursive Engine

## 1. Introduction: The Bigger Picture

**What is WriteHERE?**

WriteHERE is a framework designed for complex, multi-step writing tasks like generating detailed reports or stories. It aims to automate the process by breaking down a high-level goal (e.g., "Write a report on AI advancements in 2024") into smaller, manageable sub-tasks.

**What is the `recursive` Engine?**

The `recursive` directory contains the core logic engine of WriteHERE. Its primary responsibility is to:

1.  **Plan:** Take an initial writing goal and decompose it into a hierarchical task graph. Nodes in this graph represent specific actions like planning further, writing a section, searching for information, or reasoning about content.
2.  **Execute:** Traverse this task graph according to dependencies and node statuses. For each node, it selects and invokes the appropriate "Agent" (specialized LLM prompts or other tools like web search).
3.  **Manage State:** Keep track of the status of each task (e.g., `READY`, `DOING`, `FINISH`).
4.  **Maintain Context:** Use a `Memory` system to provide relevant information (like previously written text or results from dependencies) to each agent during execution.
5.  **Aggregate Results:** Combine the outputs of individual tasks to produce the final written document.

Essentially, the `recursive` engine orchestrates the complex workflow of generating long-form content by managing a dynamic graph of tasks and leveraging LLMs and other tools via specialized agents. The `backend` directory provides an API layer on top of this engine, but the core execution logic resides here.

## 2. Why Debug the `recursive` Engine?

Debugging the `recursive` engine allows you to:

- **Understand the Flow:** See exactly how a high-level goal is broken down into sub-tasks and how those tasks are executed in order.
- **Trace State Transitions:** Observe how nodes move between statuses (`READY`, `DOING`, `FINISH`, etc.) based on dependency completion and agent results.
- **Inspect Data Flow:** See what information (context, dependencies, previous results) is passed to each agent via the `Memory` object.
- **Analyze Agent Behavior:** Step into specific agent calls (`plan`, `execute`, `search`) to see the exact prompts sent to LLMs and the raw responses received.
- **Diagnose Issues:** Pinpoint errors, infinite loops, incorrect state changes, or unexpected agent outputs.
- **Verify Configuration:** Ensure the settings in the `config` dictionary (e.g., model names, prompt versions, agent mappings) are being applied correctly.
- **Visualize Progress:** Correlate the debugger state with the `nodes.json` output to see the graph evolve over time.

This is invaluable for understanding _how_ WriteHERE achieves its results and for modifying or extending its capabilities.

## 3. Prerequisites

1.  Python environment set up with dependencies from `backend/requirements.txt` (ensure all dependencies needed by the `recursive` module are also installed, though they might not be explicitly listed there).
2.  VS Code with the Python extension installed.
3.  Input data (e.g., a `.jsonl` file for report or story writing) and necessary API keys (likely configured via environment variables or an `api_key.env` file based on `recursive/api_key.env.example`).

## 4. VS Code Debugger Configuration (`launch.json`)

Create or update a `.vscode/launch.json` file in your workspace root (`/home/manuel/code/others/llms/WriteHERE`) with the following configuration. **Remember to replace placeholders** like `"path/to/your/input.jsonl"` and `"your-model-name"`.

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Debug WriteHERE Engine",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/recursive/engine.py", // Path to the engine script
      "console": "integratedTerminal",
      "args": [
        "--mode",
        "report", // Or "story"
        "--filename",
        "path/to/your/input.jsonl", // *** REPLACE: Path to your input file ***
        "--output-filename",
        "ttmp/debug_output.jsonl", // Temporary output for the run
        "--model",
        "your-model-name", // *** REPLACE: Specify the LLM you want to use ***
        "--engine-backend",
        "google", // Or "bing", required for report mode search
        "--start",
        "0", // Index of the first item in input file to process
        "--end",
        "1", // Process only one item for focused debugging
        "--nodes-json-file",
        "ttmp/debug_nodes.json" // For intermediate graph state visualization
      ],
      // Point to your .env file if you store API keys there
      // Create one from recursive/api_key.env.example if needed
      "envFile": "${workspaceFolder}/recursive/api_key.env",
      "justMyCode": false // Set to false to allow stepping into library/dependency code
    }
  ]
}
```

**Note:** You might need to adjust the `program` path if your entry point differs, and ensure the `envFile` path is correct for your API key setup.

## 5. Debugging Walkthrough & Key Breakpoints

Set breakpoints at the following locations to trace the execution flow.

**a) Initialization & Setup (`recursive/engine.py`)**

- **Breakpoint:** `engine.py:610` (Inside `if __name__ == "__main__":`)
  - **Purpose:** Understand how command-line arguments are parsed and which mode (`story` or `report`) is triggered.
  - **Inspect:** `args` (verify parsed arguments).
- **Breakpoint:** `engine.py:377` (Inside `report_writing`) or `engine.py:177` (Inside `story_writing`)
  - **Purpose:** See the initial configuration (`config`) being set up for the run. This defines agents, prompts, and task types.
  - **Inspect:** `config` dictionary (check model names, prompts, agent mappings).
- **Breakpoint:** `engine.py:530` (`report_writing`) or `engine.py:335` (`story_writing`) - After `RegularDummyNode` creation.
  - **Purpose:** Examine the initial state of the root node (representing the overall goal) before execution begins.
  - **Inspect:** `root_node` object, especially `root_node.task_info`, `root_node.status`, `root_node.node_graph_info`.
- **Breakpoint:** `engine.py:545` (`report_writing`) or `engine.py:340` (`story_writing`) - After `GraphRunEngine` creation.
  - **Purpose:** See the engine and memory system initialized with the root node and config.
  - **Inspect:** `engine` object, `engine.memory` object (especially `engine.memory.format`, `engine.memory.config`).

**b) The Main Execution Loop (`recursive/engine.py`)**

- **Breakpoint:** `engine.py:141` (Start of the `for` loop in `forward_one_step_untill_done`)
  - **Purpose:** Track the overall progress, step by step. Each iteration represents one unit of work in the graph.
  - **Inspect:** `step` counter, `self.root_node` (observe changes across steps, especially node statuses).
- **Breakpoint:** `engine.py:144` (Call to `forward_one_step_not_parallel`)
  - **Purpose:** Step into the core logic that finds and executes a single task node.

**c) Selecting the Next Node (`recursive/engine.py`)**

- **Breakpoint:** `engine.py:26` (Start of `find_need_next_step_nodes`)
  - **Purpose:** Understand how the engine traverses the graph (breadth-first) to find the next node ready for execution based on its status (`is_activate`).
  - **Inspect:** `self.root_node` (visualize the graph structure), `queue`, `node.is_activate`.
- **Breakpoint:** `engine.py:33` (When `node.is_activate`)
  - **Purpose:** See which nodes are currently considered active and candidates for execution.
  - **Inspect:** `node` (properties like `nid`, `status`, `task_info`).
- **Breakpoint:** `engine.py:41` (Return statement of `find_need_next_step_nodes`)
  - **Purpose:** Identify the specific node selected for the current step (usually the first active one found).
  - **Inspect:** The returned `nodes` or single node.

**d) Executing a Single Step (`recursive/engine.py`)**

- **Breakpoint:** `engine.py:90` (Inside `forward_one_step_not_parallel`, after node selection)
  - **Purpose:** Confirm the specific `need_next_step_node` chosen for this step.
  - **Inspect:** `need_next_step_node`.
- **Breakpoint:** `engine.py:98` (After `self.memory.update_infos`)
  - **Purpose:** Observe how the shared `Memory` object is updated with information derived _from_ the selected node _before_ its action runs. This provides context for the upcoming action.
  - **Inspect:** `self.memory.collected_info`, `self.memory.article`. Step into `update_infos` (`memory.py:158`) for details on context collection.
- **Breakpoint:** `engine.py:107` (Before `need_next_step_node.next_action_step`)
  - **Purpose:** Prepare to step into the node's action execution logic. The action taken depends on the node's current `status`.
  - **Inspect:** `need_next_step_node.status` (determines the action), `self.memory` (context passed to the action).
- **Breakpoint:** `engine.py:110` (After `need_next_step_node.next_action_step`)
  - **Purpose:** See the immediate result and the action performed by the node (`plan`, `execute`, `update`, etc.). Observe how the node's `result` and `status` might change.
  - **Inspect:** `action_name`, `action_result`, `need_next_step_node.result`, `need_next_step_node.status`.
- **Breakpoint:** `engine.py:116` (Before `self.forward_exam`)
  - **Purpose:** Prepare to step into the graph state update logic, which propagates status changes based on the completed action.

**e) Node Actions & Agent Calls (`recursive/graph.py` & `recursive/agent/`)**

- **Breakpoint:** `graph.py:491` (Start of `RegularDummyNode.next_action_step`)
  - **Purpose:** Understand how a node determines _which_ action (`plan`, `execute`, `update`, etc.) to perform based on its `status`. It maps status to an action name and looks up the corresponding agent in the config.
  - **Inspect:** `self.status`, `self.task_info`, `action_name`.
- **Breakpoint:** `graph.py:503` (Before `agent.run`)
  - **Purpose:** See which specific Agent class (e.g., `UpdateAtomPlanningAgent`, `SimpleExecutor`, `SearchAgent`) is being invoked and what context (`memory`, `kwargs`) it receives.
  - **Inspect:** `agent` (type of agent), `memory` (context), `kwargs` (specific inputs like dependencies).
  - **Action:** Step Into (`F11`) this call to debug the specific agent's logic.
- **Agent Logic (Example: `recursive/agent/agents/regular.py:UpdateAtomPlanningAgent.run`)**
  - **Breakpoint:** Within the `run` method of the specific agent class you want to inspect (find the class based on `config["action_mapping"]` and `config[task_type]`).
  - **Purpose:** Understand the agent's internal logic: how it uses the provided context (`memory`, `node`, `kwargs`) to construct prompts, call LLMs (or other tools like search), and parse the results.
  - **Inspect:** `node`, `memory`, `kwargs` (inputs). Look for prompt construction logic.
  - **Breakpoint:** Before the call to `get_llm_output` or similar LLM/tool interaction functions (e.g., search calls in `SimpleExecutor`).
  - **Inspect:** The fully constructed prompt string/object being sent to the external service.
  - **Breakpoint:** After the external call.
  - **Inspect:** The raw response, parsed results (`plan_think`, `result`, `search_querys`, etc.).

**f) State Updates (`recursive/engine.py` & `recursive/graph.py`)**

- **Breakpoint:** `engine.py:65` (Start of `forward_exam`)
  - **Purpose:** See how the engine recursively checks (`do_exam`) and updates node statuses throughout the entire graph after an action completes. This ensures nodes become `READY` when dependencies finish, or `FINISH` when sub-tasks are done.
  - **Inspect:** `node` being examined.
- **Breakpoint:** `engine.py:70` (Before `node.do_exam`)
  - **Purpose:** Prepare to step into the individual node's state transition logic.
- **Breakpoint:** `graph.py:408` (Start of `RegularDummyNode.do_exam`)
  - **Purpose:** Understand the specific conditions under which a node changes its status (e.g., from `READY` to `DOING`, `DOING` to `FINAL_TO_FINISH`, `FINAL_TO_FINISH` to `FINISH`). This often involves checking the status of its dependencies (`dep.status`) or its inner graph nodes.
  - **Inspect:** `self.status`, dependency statuses (`dep.status`), inner graph node statuses (if applicable, `inner_node.status`).
  - **Breakpoint:** Around lines `graph.py:430-475` (Specific status transition checks like `_exam_ready_to_doing`, `_exam_doing_to_final`).
  - **Inspect:** The boolean conditions being evaluated.

**g) Memory & Caching (`recursive/memory.py` & `recursive/cache.py`)**

- **Breakpoint:** `memory.py:106` (Start of `collect_node_run_info`)
  - **Purpose:** See how information (like results from finished dependencies) is gathered for a node when its context is needed (usually before an agent runs).
  - **Inspect:** `node`, `self.collected_info` (check for cache hits within memory).
- **Breakpoint:** `memory.py:116` (After `self._compute_node_info`)
  - **Purpose:** Examine the computed information (e.g., formatted dependency results, global plan) before it's cached in the `Memory` object.
  - **Inspect:** `info`.
- **Breakpoint:** `cache.py:166` (`Cache.get`)
  - **Purpose:** Observe external cache lookups (filesystem-based) for potentially expensive operations like LLM calls or search results.
  - **Inspect:** `key` (often the prompt or search query), `key_hash`, `self.cache_dir`.
- **Breakpoint:** `cache.py:175` (`Cache.set`)
  - **Purpose:** See what data is being stored in the external cache.
  - **Inspect:** `key`, `value` (the result being cached, usually pickled).

**h) Persistence (`recursive/engine.py`)**

- **Breakpoint:** `engine.py:149` (Call to `self.save`)
  - **Purpose:** Observe the state (graph nodes, memory) being saved to disk periodically during the `forward_one_step_untill_done` loop. Step into `save` (`engine.py:46`) to see the `pickle` and `json` serialization process.
  - **Inspect:** `self.root_node`, `self.memory`.

## 6. Key Variables to Watch

- `node.nid`: Unique ID within the _original_ plan structure (can be hierarchical like "1.2.3").
- `node.hashkey`: Unique ID for the _runtime instance_ of the node (UUID). Used for memory caching.
- `node.status` (`TaskStatus` enum): Crucial for understanding the node's lifecycle stage.
- `node.task_info`: The definition of the task (goal, type, dependencies, length).
- `node.result`: The output produced by the node's action (e.g., a plan, written text, search summary).
- `engine.memory.article`: The accumulated text output, updated incrementally.
- `engine.memory.collected_info`: Dictionary mapping node hashkeys to their gathered context/results.
- `agent` (within `next_action_step`): The specific agent class instance being used.
- `prompt` (within agents): The input being sent to the LLM.
- `response` / `result` (within agents): The output from the LLM or other action (search, etc.).
- `cache key` / `cache value`: Monitor external cache interactions.
- `action_name` (in `forward_one_step_not_parallel` and `next_action_step`): The specific action being performed (e.g., "plan", "execute").

## 7. Tips for Effective Debugging

- **Start Small:** Use the `start`/`end` arguments in `launch.json` to process only _one_ input item initially. This keeps the graph manageable.
- **Focus Scope:** Decide if you want to understand the high-level orchestration (`engine.py`) or the details of a specific agent (`agent/`). Set breakpoints accordingly. Avoid stepping into _everything_ initially.
- **Use Conditional Breakpoints:** If the loop runs many times or the graph is large, set conditions on breakpoints (e.g., break when `node.nid == '1.2'` or when `node.status == TaskStatus.DOING`). Right-click the breakpoint margin in VS Code to add conditions.
- **Inspect the Graph:** Use the `nodes.json` file (specified in `launch.json`) with a JSON viewer or analyze the `engine.root_node.to_json()` output in the debugger's variable inspector to understand the graph structure and node states visually.
- **Step In/Out Wisely:** Use "Step Into" (`F11`) to dive into function calls (like agent runs or memory updates) and "Step Out" (`Shift+F11`) to return quickly. "Step Over" (`F10`) executes a line without diving into its functions.
- **Read Logs:** Concurrently check the log file created in the `records/{qstr}/engine.log` directory (where `qstr` is the task ID) for high-level event logging that complements the debugger view.
- **LLM Calls:** Be aware that stepping through LLM calls will execute them, potentially incurring costs and time delays. Use caching (`recursive/cache.py`) effectively during development/debugging. Break _before_ and _after_ LLM calls to inspect inputs and outputs without waiting for the call itself every time.

This guide should provide a solid foundation for exploring the runtime behavior of the WriteHERE recursive engine. Happy debugging!
