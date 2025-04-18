# Design: Finding and Displaying Related Events

## 1. Introduction

This document explores design ideas for implementing a feature in the event monitoring UI where selecting an event (e.g., in a table row) opens a modal displaying other events considered "related" to the selected one. The goal is to provide users with contextual information surrounding a specific event, aiding debugging and understanding the agent's execution flow.

We will examine different ways to define event "relatedness" based on the existing event schema (see `ttmp/2025-04-17/04-long-term-document--event-logging-system.md`) and propose logic for identifying and presenting these related events.

## 2. Defining Event "Relatedness"

Given the structure of the events and the agent's execution model, several criteria can be used to determine if two events are related. Here are some potential definitions:

**a) By Node ID (`node_id`)**

- **Rationale:** Events often pertain to the lifecycle or actions performed for a specific task node within the agent's execution graph. Grouping by `node_id` connects all activities associated with that single task.
- **Logic:** Given a selected event `E` with `payload.node_id`, find all other events `E'` where `E'.payload.node_id == E.payload.node_id`.
- **Scope:** Connects status changes, LLM calls, and tool usage for a specific task.
- **Applicability:** Applies to most event types (`step_started`, `step_finished`, `node_status_changed`, `llm_call_*`, `tool_*`).

**b) By Step Number (`step`)**

- **Rationale:** The agent engine executes in discrete steps. Events occurring within the same step number are temporally and logically grouped as part of a single engine cycle.
- **Logic:** Given a selected event `E` with `payload.step`, find all other events `E'` where `E'.payload.step == E.payload.step`.
- **Scope:** Connects the start/end of a step with any LLM or tool calls initiated _within_ that specific step number.
- **Applicability:** `step_started`, `step_finished`, `llm_call_started`, `llm_call_completed`.

**c) By Causal/Operational Pairs**

- **Rationale:** Certain operations inherently have start/end or invocation/return events. Linking these pairs directly shows the duration and outcome of specific operations.
- **Logic:**
  - `step_started` <-> `step_finished` (Match on `payload.step`).
  - `llm_call_started` <-> `llm_call_completed` (Match on `payload.node_id`, `payload.step`, `payload.agent_class`, `payload.model`. Requires careful logic if retries occur).
  - `tool_invoked` <-> `tool_returned` (Match on `payload.node_id`, `payload.tool_name`, `payload.api_name`. Step might also be relevant).
- **Scope:** Provides direct links for the duration and result of specific actions.
- **Applicability:** The paired event types.

**d) By Agent Class (`agent_class`)**

- **Rationale:** Useful for focusing on the activities of a specific type of agent component (e.g., how often `SimpleExecutor` was called, what it did).
- **Logic:** Given a selected LLM event `E`, find all other `llm_call_started` or `llm_call_completed` events `E'` where `E'.payload.agent_class == E.payload.agent_class`.
- **Scope:** Groups LLM interactions by the responsible agent.
- **Applicability:** `llm_call_started`, `llm_call_completed`.

**e) By Tool Name (`tool_name`)**

- **Rationale:** Useful for debugging a specific tool or understanding its usage patterns.
- **Logic:** Given a selected tool event `E`, find all other `tool_invoked` or `tool_returned` events `E'` where `E'.payload.tool_name == E.payload.tool_name`.
- **Scope:** Groups interactions with a specific tool.
- **Applicability:** `tool_invoked`, `tool_returned`.

**f) By Time Proximity (`timestamp`)**

- **Rationale:** Events occurring close together in time might be related, even if not linked by other identifiers, especially in potentially concurrent parts of the system (though the current engine seems largely sequential).
- **Logic:** Given a selected event `E`'s `timestamp`, find all events `E'` within `[E.timestamp - delta, E.timestamp + delta]`.
- **Scope:** Temporal locality.
- **Applicability:** All events.
- **Caveats:** Less precise, requires tuning `delta`, may include unrelated events.

**g) By Run ID (`run_id`)**

- **Rationale:** The most basic relationship – all events belong to the same overall agent execution run.
- **Logic:** Find all events `E'` where `E'.run_id == E.run_id`.
- **Scope:** The entire agent run.
- **Applicability:** All events.
- **Caveats:** Too broad for a focused "related events" view, but defines the maximum scope.

## 3. Proposed Logic for Finding Related Events

A practical approach would be to combine the most relevant criteria. When an event `E` is selected in the UI:

1.  **Identify Keys:** Extract primary identifiers from `E`: `node_id = E.payload.node_id`, `step = E.payload.step`, `event_type = E.event_type`.
2.  **Gather Base Sets:**
    - **Node Set:** If `node_id` exists, find all events `E_n` where `E_n.payload.node_id == node_id`.
    - **Step Set:** If `step` exists, find all events `E_s` where `E_s.payload.step == step`.
3.  **Find Causal Pairs:**
    - If `E` is `step_started`, find `step_finished` `E_f` where `E_f.payload.step == step`.
    - If `E` is `step_finished`, find `step_started` `E_st` where `E_st.payload.step == step`.
    - If `E` is `llm_call_started`, find `llm_call_completed` `E_lc` (matching `node_id`, `step`, `agent_class`). _Initial implementation might just match on node/step/agent._.
    - If `E` is `llm_call_completed`, find `llm_call_started` `E_ls` (matching `node_id`, `step`, `agent_class`).
    - If `E` is `tool_invoked`, find `tool_returned` `E_tr` (matching `node_id`, `tool_name`, `api_name`, maybe `step`).
    - If `E` is `tool_returned`, find `tool_invoked` `E_ti` (matching `node_id`, `tool_name`, `api_name`, maybe `step`).
4.  **Combine:** Create a final set by taking the union of the Node Set, Step Set, and any found Causal Pair events.
5.  **Filter:** Remove the original selected event `E` from the final set.
6.  **Sort:** Sort the remaining related events chronologically by `timestamp` (e.g., newest first or oldest first, depending on UI preference).

## 4. Alternative Display Options / Modal Design

Instead of a single flat, sorted list, the modal could offer more structure:

- **Tabbed View:**
  - Tab 1: "Node Context" (All events from Node Set, sorted chronologically).
  - Tab 2: "Step Context" (All events from Step Set, sorted chronologically).
  - Tab 3: "Direct Links" (Only the Causal Pair events, e.g., `llm_call_started` + `llm_call_completed`).
- **Grouped List:** A single list grouped by sections (e.g., "Within Same Step", "Within Same Node (Other Steps)", "Directly Linked Operation").
- **Timeline Snippet:** A small, focused timeline visualization showing only the related events.

Highlighting the originally selected event within the list/view is crucial for context.

## 5. Implementation Considerations

- **Data Source:** Can this logic run client-side on the events currently loaded in the UI state (e.g., held in Redux)? Or does it require a dedicated backend API endpoint?
  - **Client-Side:** Feasible if the number of events displayed/held in memory is manageable (e.g., < 1000s). Requires efficient JavaScript filtering/searching.
  - **Server-Side:** More scalable. An endpoint like `/api/events/{event_id}/related` could query the full event stream (e.g., Redis) using indexes on `node_id`, `step`, etc., and return the related set. This avoids loading all events into the browser.
- **Performance:** Client-side filtering needs to be performant. Memoized selectors (e.g., with `reselect` in Redux) can optimize recalculations.
- **Causal Pair Matching Robustness:** The initial matching logic for pairs (LLM, Tool) might need refinement. If an operation is retried within the same step/node context, simple identifier matching might find multiple pairs. Incorporating timestamps (finding the _closest_ match after the start event) or adding unique operation IDs to the events themselves in the future would make this more robust.
- **UI Complexity:** How much detail should be shown for each related event in the list? Just the type and timestamp, or key payload details? Clicking a related event in the modal could potentially highlight it in the main view or open _its_ related events modal (though this could lead to deep nesting).

## 6. Future Enhancements

- **Unique Operation IDs:** Add a unique ID shared between `llm_call_started`/`completed` and `tool_invoked`/`returned` events to make pairing unambiguous, especially across retries.
- **Graph Context:** If the full node graph structure is available client-side (or queryable), relatedness could extend to parent/child node events or events on sibling nodes within the graph.
- **User Configuration:** Allow users to configure which relatedness criteria are most important to them.
