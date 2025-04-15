# WriteHERE: OpenTelemetry Instrumentation Design for Task Planning & Execution

## 1. Introduction: The Need for Tracing in a Recursive System

WriteHERE employs a sophisticated **hierarchical recursive planning** approach to generate complex content (as detailed in `ttmp/2025-04-07/01-write-here-architecture-report.md`). Unlike simpler frameworks, it decomposes large tasks into a dynamic graph (`recursive/graph.py`) of smaller, potentially heterogeneous sub-tasks (**COMPOSITION**, **REASONING**, **RETRIEVAL**). Each task (`AbstractNode`) progresses through a defined state machine (`TaskStatus`), managed by the `GraphRunEngine` (`recursive/engine.py`).


Crucially, the system dynamically selects specific **agents** and **prompt templates** based on the task's type, its current state (e.g., readiness, need for update), and the specific action being performed (e.g., `plan`, `execute`, `atom` check) as defined in the configuration and outlined in `ttmp/2025-04-14/02-tasks-mapping-planning-report.md`. This involves complex logic within agents like `UpdateAtomPlanningAgent` deciding whether to further decompose a task (recursive planning) or treat it as atomic, and within `get_llm_output` to select and construct the precise prompt for the LLM.

This inherent complexity—recursive decomposition, state-driven execution, dynamic agent/prompt selection, and heterogeneous task handling—makes it challenging to follow the flow of execution simply by reading logs. **Distributed tracing with OpenTelemetry becomes essential** to:

- Visualize the dynamic task graph creation and execution flow.
- Understand the decision-making process for task decomposition (planning vs. atomicity).
- Track task scheduling and state transitions based on dependencies.
- Pinpoint how specific prompts are selected and constructed based on context.
- Monitor the interactions with LLMs, including parsing of results.
- Debug issues related to unexpected task states, incorrect prompt usage, or performance bottlenecks.

This document outlines a detailed instrumentation strategy using OpenTelemetry (OTel) focused on providing this visibility into the core components: `recursive/engine.py`, `recursive/graph.py`, and `recursive/agent/agents/regular.py`.

## 2. Goals of Instrumentation (Refined Focus)

- **Track Task Lifecycle & Scheduling:** Follow a task (Node) from creation through its state transitions (`TaskStatus`), observing how the `GraphRunEngine` finds ready nodes (`find_need_next_step_nodes`) and updates states based on dependencies (`forward_exam`, `do_exam`).
- **Visualize Planning & Task Splitting:** Understand how `UpdateAtomPlanningAgent` decides if a task is atomic or requires recursive planning (`plan` action). Trace the conversion of LLM planning output into the graph structure via `plan2graph`.
- **Analyze Prompt Selection & Atomicity:** Trace the logic within `get_llm_output` determining the specific `prompt_version` based on `agent_type`, `task_type`, configuration (e.g., `update_diff`), and node state. Explicitly capture the result of atomicity checks (`UpdateAtomPlanningAgent`).
- **Observe Prompt Construction:** See how context (memory, dependencies, task info, plans) is gathered and formatted into the final LLM prompt within `get_llm_output`.
- **Monitor LLM Interaction & Parsing:** Track calls to LLMs, including the request details (model, prompt hash/summary) and the response. Observe how the response is parsed back into structured data (e.g., within agent `forward` methods or `plan2graph`).
- **Differentiate Agent Actions:** Clearly distinguish agent strategies (`plan`, `execute`, `final_aggregate`, etc.) and their inputs/outputs.
- **Identify Bottlenecks & Errors:** Easily spot issues in any of the above areas.

## 3. Key Concepts & Objects to Trace

- **Task Execution Run:** The entire process for a single input prompt, orchestrated by `GraphRunEngine.forward_one_step_untill_done`.
- **Engine Step:** A single iteration of the `GraphRunEngine`'s main loop (`forward_one_step_not_parallel`).
- **Node (`AbstractNode`/`RegularDummyNode`):** Represents a single task unit. Trace its creation, state transitions, actions performed, and relationship to parent/child nodes.
- **Graph (`Graph`):** The container for nodes and edges. Trace modifications (node/edge additions) and key operations like topological sorting.
- **Agent Action:** The execution of a specific agent's `forward` method.
- **LLM Interaction:** The end-to-end process within `get_llm_output`.
- **Prompt Selection & Construction:** The logic determining which prompt template to use and how it's filled.
- **State Transition:** Explicit changes in a Node's `TaskStatus`.

## 4. Instrumentation Plan: Spans, Attributes, and Events (Enhanced)

Below is the detailed plan, organized by file and function, with enhancements focusing on the refined goals. We assume `tracer = trace.get_tracer(__name__)` is obtained in each file.

### 4.1 `recursive/engine.py`

- **`GraphRunEngine.forward_one_step_untill_done(self, ...)`**

  - **Span Name:** `Engine.Run` (Root Span for a single input)
  - **Attributes:**
    - `engine.input.filename`: Input data source.
    - `engine.output.filename`: Output destination.
    - `engine.llm.model`: `global_use_model`.
    - `engine.backend`: `engine_backend`.
    - `engine.mode`: `report` or `story`.
    - `task.root.goal`: `self.root_node.task_info['goal']`.
    - `date.today`: `config.today_date`.
  - **Events:**
    - `Engine loop started`.
    - `Saving state` (Attributes: `folder`).
    - `Engine loop finished` (Attributes: `status`="done" | "max_steps_reached").
    - `Final result generated`.

- **`GraphRunEngine.forward_one_step_not_parallel(self, ...)`**

  - **Span Name:** `Engine.Step`
  - **Parent:** `Engine.Run`
  - **Attributes:**
    - `engine.step.number`: Current loop iteration (passed or tracked).
    - `engine.step.selected_node_hashkey` (optional): `select_node_hashkey`.
  - **Events:**
    - `Step started`.
    - `Finding next node`.
    - `Executing node action` (Attributes: `node.nid`, `node.task_info.goal`).
    - `Examining graph state`.
    - `Saving intermediate nodes.json` (Attributes: `nodes_json_file`).
    - `Step finished`.

- **`GraphRunEngine.find_need_next_step_nodes(self, single=False)`**

  - **Span Name:** `Engine.FindNextNode`
  - **Parent:** `Engine.Step`
  - **Attributes:**
    - `engine.find.single_mode`: `single`.
  - **Events:**
    - `Scan started`.
    - `Checking node` (Attributes: `node.nid`, `node.status`, `node.is_activate`).
    - `Node eligible for execution` (Attributes: `node.nid`, `node.status`).
    - `Scan finished` (Attributes: `found_node.nid`=[list or single NID] | `None`).

- **`GraphRunEngine.forward_exam(self, node, verbose)`**
  - **Span Name:** `Engine.ExamGraphState` (Potentially Recursive)
  - **Parent:** `Engine.Step` or `Engine.ExamGraphState` (for recursive calls)
  - **Attributes:**
    - `node.nid`: `node.nid`.
    - `node.status.before`: `node.status.name`.
    - `engine.exam.verbose`: `verbose`.
  - **Events:**
    - `Examining node`.
    - `Recursively examining children` (if `node.is_suspend` and has children).
    - `Calling node.do_exam`.
    - `Exam finished` (Attributes: `node.status.after`=`node.status.name`).

### 4.2 `recursive/graph.py`

- **`AbstractNode.__init__(self, ...)`**

  - **Span Name:** `Node.Create` (Consider if too noisy, maybe an Event in `plan2graph` is better)
  - **Parent:** `Graph.plan2graph`
  - **Attributes:**
    - `node.nid`: `nid`.
    - `node.type`: `node_type.name`.
    - `node.task.type`: `task_info['task_type']`.
    - `node.task.goal`: `task_info['goal']`.
    - `node.layer`: `node_graph_info['layer']`.
    - `node.parent_count`: `len(node_graph_info['parent_nodes'])`.

- **`AbstractNode.next_action_step(self, memory, ...)`**

  - **Span Name:** `Node.SelectAction`
  - **Parent:** `Engine.Step` (via `forward_one_step_not_parallel`)
  - **Attributes:**
    - `node.nid`: `self.nid`.
    - `node.task.type`: `self.task_type_tag`.
    - `node.task.goal`: `self.task_info['goal']`.
    - `node.status.before`: `self.status.name`.
  - **Events:**
    - `Action determination started`.
    - `Checking condition` (Attributes: `condition`=representation of `condition_func`, `result`=`condition_func(...)`).
    - `Action selected` (Attributes: `action.name`=`action_name`, `node.status.next`=`next_status.name`).
    - `Calling do_action`.
    - `Action finished, status updated` (Attributes: `node.status.after`=`self.status.name`).
    - `No condition matched` (If loop finishes without break).

- **`AbstractNode.do_action(self, action_name, memory, ...)`**

  - **Span Name:** `Node.ExecuteAction`
  - **Parent:** `Node.SelectAction`
  - **Attributes:**
    - `node.nid`: `self.nid`.
    - `action.name`: `action_name`.
    - `agent.class`: `self.agent_proxy.proxy(action_name).__class__.__name__`.
    - `agent.config.llm`: `self.config['action_mapping'][action_name]`.
  - **Events:**
    - `Agent proxy obtained`.
    - `Calling agent.forward`.
    - `Agent forward finished` (Attributes: `result.summary`=short summary/type of result).
    - `Storing action result`.
    - `Action completed`.

- **`AbstractNode.do_exam(self, verbose)`**

  - **Span Name:** `Node.EvaluateState`
  - **Parent:** `Engine.ExamGraphState`
  - **Attributes:**
    - `node.nid`: `self.nid`.
    - `node.status.before`: `self.status.name`.
    - `node.exam.verbose`: `verbose`.
  - **Events:**
    - `Exam started`.
    - `Checking condition` (Attributes: `condition`=representation of `condition_func`, `result`=`condition_func(self)`).
    - `Status transition triggered` (Attributes: `node.status.next`=`next_status.name`).
    - `Exam finished` (Attributes: `node.status.after`=`self.status.name`).

- **`AbstractNode.plan2graph(self, raw_plan)`**

  - **Span Name:** `Node.PlanToGraph`
  - **Parent:** `Agent.Forward` (e.g., `UpdateAtomPlanningAgent.forward`)
  - **Attributes:**
    - `node.nid`: `self.nid` (The node _being_ planned).
    - `plan.raw.length`: `len(raw_plan)`.
    - `plan.raw.summary`: JSON summary or hash of `raw_plan`.
  - **Events:**
    - `Raw plan received`.
    - `Handling atomic task case` (if `len(raw_plan) == 0`).
    - `Processing task from plan` (Attributes: `task.id`, `task.goal`, `task.type`).
    - `Node created` (Attributes: `inner_node.nid`, `inner_node.task.type`, `inner_node.node_type`, `inner_node.task.goal`).
    - `Adding edge` (Attributes: `parent.nid`, `child.nid`).
    - `Applying implicit COMPOSITION dependency`.
    - `Calling graph.topological_sort`.
    - `Graph construction complete` (Attributes: `graph.nodes.count`=`len(self.inner_graph.node_list)`, `graph.edges.count`=calculated edge count).

- **`Graph.add_node`, `Graph.add_edge`, `Graph.topological_sort`**:
  - **Strategy:** Primarily use _Events_ within `Node.PlanToGraph` to avoid excessive span noise.
  - **Example Events (within `Node.PlanToGraph`):**
    - `Graph updated: add_node` (Attributes: `node.nid`).
    - `Graph updated: add_edge` (Attributes: `parent.nid`, `child.nid`).
    - `Graph updated: topological_sort` (Attributes: `result.queue.length`=`len(self.topological_task_queue)`).

### 4.3 `recursive/agent/agents/regular.py`

- **Agent `forward` methods (General)** (e.g., `UpdateAtomPlanningAgent.forward`, `SimpleExcutor.forward`, `FinalAggregateAgent.forward`)

  - **Span Name:** `Agent.Forward` (Prefix with agent name, e.g., `Agent.Forward.UpdateAtomPlanning`)
  - **Parent:** `Node.ExecuteAction`
  - **Attributes:**
    - `agent.class`: `self.__class__.__name__`.
    - `node.nid`: `node.nid`.
    - `node.task.type`: `node.task_type_tag`.
    - `node.task.goal`: `node.task_info['goal']`.
  - **Events:**
    - `Agent execution started`.
    - _Specific events for each agent's logic (see below)._
    - `Agent execution finished`.

- **`UpdateAtomPlanningAgent.forward` (Specific Focus: Task Splitting, Atomicity)**

  - **Events:**
    - `Atom/Plan logic started`.
    - `Checking config: all_atom` (Attributes: `result`).
    - `Checking config: use_candidate_plan` (Attributes: `result`, `candidate_plan_valid`).
    - `Checking config: force_atom_layer` (Attributes: `node.layer`, `config.force_atom_layer`, `result`).
    - `Calling get_llm_output for atom check` (Attributes: `retry_count`). (Leads to `Agent.LLMInteraction` span)
    - `Atom check LLM result received` (Attributes: `atom_result`, `atom_think`, `update_result`=(goal if changed)). **(Focus: Atomicity Result)**
    - `Planning decision` (Attributes: `decision`="atomic" | "recursive" | "candidate_plan" | "force_atom" | "all_atom"). **(Focus: Task Splitting Decision)**
    - `Calling get_llm_output for planning` (Attributes: `retry_count`, `skipped`=(True if decision != recursive)). (Leads to `Agent.LLMInteraction` span)
    - `Parsing planning result` (Attributes: `parse_successful`, `raw_response_summary`). **(Focus: LLM Parsing)**
    - `Planning result parsed` (Attributes: `plan_result.summary`).

- **`SimpleExcutor.forward` (Specific Focus: Execution, RETRIEVAL Handling)**

  - **Events:**
    - `Executor logic started`.
    - `Checking for RETRIEVAL React Agent`.
    - `Initializing React Agent` (Attributes: `prompt_version`, `model`, `max_turn`).
    - `Calling React Agent chat` (Attributes: `message`).
    - `Processing React Agent results` (Attributes: `num_pages`, `num_turns`).
    - `Calling LLM Merge (search_merge)` (if `llm_merge`). (Leads to `Agent.SearchMerge` span)
    - `Calling get_llm_output for standard execution` (Attributes: `retry_count`). (Leads to `Agent.LLMInteraction` span)
    - `Execution LLM result` (Attributes: `result.summary`). **(Focus: LLM Result)**
    - `Updating memory.article` (for COMPOSITION).

- **`get_llm_output(node, agent, memory, agent_type, ...)`** (Focus: Prompt Selection/Construction, LLM Interaction)

  - **Span Name:** `Agent.LLMInteraction`
  - **Parent:** `Agent.Forward.*` or `Agent.SearchMerge`
  - **Attributes:**
    - `llm.agent_type`: `agent_type`.
    - `node.nid`: `node.nid`.
    - `node.task.type`: `node.task_type_tag`.
    - `llm.prompt.version.determined`: The final `prompt_version`. **(Focus: Prompt Selection Result)**
    - `llm.model`: `inner_kwargs['llm_args']['model']`.
    - `llm.temperature`: `inner_kwargs['llm_args'].get('temperature')`.
    - `llm.overwrite_cache`: `overwrite_cache`.
  - **Events:**
    - `Collecting memory info` (Attributes: `keys`=list(memory_info.keys())). **(Focus: Prompt Construction Info)**
    - `Determining prompt version` (Attributes: `logic_path`="planning_depth" | "atom_update" | "standard", `determined_version`). **(Focus: Prompt Selection Logic)**
    - `Constructing system message`.
    - `Preparing prompt arguments` (Attributes: `keys`=list(prompt_args.keys())). **(Focus: Prompt Construction Args)**
    - `Prompt constructed` (Attributes: `prompt.hash`, `prompt.length`). **(Focus: Prompt Construction Result)**
    - `Calling LLM`. **(Focus: LLM Interaction)**
    - `LLM response received` (Attributes: `response.hash`, `response.length`). **(Focus: LLM Interaction)**
    - `Parsing LLM result` (Attributes: `parse_args`=list(inner_kwargs['parse_arg_dict'].keys())). **(Focus: LLM Parsing Start)**
    - `LLM interaction finished` (Attributes: `parsed_result.keys`).

- **`SimpleExcutor.search_merge(self, ...)`**
  - **Span Name:** `Agent.SearchMerge`
  - **Parent:** `Agent.Forward.SimpleExecutor`
  - **Attributes:**
    - `node.nid`: `node.nid`.
    - `llm.prompt.version`: `prompt_version`.
    - `llm.model`: `inner_kwargs['llm_args']['model']`.
    - `search_results.length`: `len(search_results)`.
  - **Events:** Similar structure to `get_llm_output`, emphasizing the merge context.

## 5. Interleaving Spans and Events (Refined Explanation)

- **Spans:** Represent logical units of work or operations with potential latency. The nesting directly reflects the call hierarchy, making it easy to see how an `Engine.Step` leads to a `Node.SelectAction`, then `Node.ExecuteAction`, which invokes an `Agent.Forward.*` span, potentially containing `Agent.LLMInteraction` or `Node.PlanToGraph`. This structure is key to understanding the **task splitting** and **scheduling** flow.
- **Events:** Mark critical point-in-time occurrences _within_ these spans. They are crucial for capturing:
  - **Prompt Selection Logic:** Events in `get_llm_output` show _why_ a prompt was chosen.
  - **Atomicity Checks:** An event in `UpdateAtomPlanningAgent.forward` records the outcome.
  - **Prompt Construction Details:** Events log the context gathered and the final prompt hash.
  - **LLM Interaction Milestones:** Events mark the call and response.
  - **Parsing Steps:** Events indicate when parsing starts and what the result looks like.
  - **State Transitions:** Events in `Node.EvaluateState` record status changes vital for **scheduling**.
    Using events for these details keeps the trace view cleaner than creating excessive tiny spans.

## 6. Conclusion

This refined instrumentation plan, grounded in the WriteHERE architecture, provides comprehensive tracing coverage focused on the critical aspects of its recursive planning and execution. By carefully placing spans and events, particularly around agent decisions (`UpdateAtomPlanningAgent`), state management (`GraphRunEngine`, `AbstractNode.do_exam`), and LLM interactions (`get_llm_output`), the resulting traces will offer invaluable insights into task decomposition, scheduling, prompt engineering, and overall system behavior. Remember to add necessary imports (`from opentelemetry import trace`) and obtain a tracer instance (`tracer = trace.get_tracer(__name__)`) in each modified Python file.
