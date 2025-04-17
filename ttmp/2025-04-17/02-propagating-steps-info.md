# Enhancing LLM Event Logging: Step Number and Full Prompt/Response

## 1. Goal

This document details the investigation and proposed changes to enhance the LLM-related events (`llm_call_started`, `llm_call_completed`) emitted by the Recursive Agent system. The goals are:

1.  **Propagate Step Number:** Include the current execution `step` number in the LLM event payloads.
2.  **Include Full Details:** Add the complete `prompt` and `response` content to the corresponding event payloads, removing the current truncation.

Context for this investigation can be found in `ttmp/2025-04-17/04-event-logging-system.md`.

## 2. Investigation

### 2.1. Code Flow Analysis

The relevant code flow for LLM calls starts in the `GraphRunEngine` and proceeds to the `Agent`:

1.  **`recursive/engine.py:forward_one_step_not_parallel`**: This method orchestrates a single execution step. It has access to the current `step` number (passed as an argument). It identifies the `need_next_step_node`. **This is the source of the `step` number.**
2.  **`recursive/node/abstract.py:AbstractNode.next_action_step`**: The engine calls this method on the selected node. This method determines the appropriate action based on the node's status and calls `do_action`.
3.  **`recursive/node/abstract.py:AbstractNode.do_action`**: This method invokes the appropriate agent method (e.g., `plan`, `execute`) via the `AgentProxy`.
4.  **`recursive/agent/proxy.py:AgentProxy.call_agent`**: This proxy likely routes the call to the specific agent implementation's `forward` method.
5.  **Specific Agent (`recursive/agent/*.py`)**: The agent's `forward` method executes the core logic, eventually calling `call_llm`.
6.  **`recursive/agent/base.py:Agent.call_llm`**: This base method handles the actual LLM interaction (preparing messages, making the API call). **This is where `emit_llm_call_started` and `emit_llm_call_completed` are invoked.**

### 2.2. Data Availability

- **`step` Number:** The `step` number is available in `GraphRunEngine.forward_one_step_not_parallel` but is not currently passed down the call chain to `Agent.call_llm`.
- **Full `prompt`:** The full `prompt` (constructed from `system_message`, `history_message`, and `prompt` arguments) is available within `Agent.call_llm` in the `message` variable.
- **Full `response`:** The full LLM response content is available within `Agent.call_llm` in the `content` variable after the API call.

## 3. Propagating the Step Number

To get the `step` number from the engine to the `call_llm` method, several patterns are possible:

**Pattern 1: Pass Down the Call Stack (Recommended)**

- **Description:** Modify the signatures of intermediate methods (`next_action_step`, `do_action`, `AgentProxy.call_agent`, agent `forward` methods) to accept and pass the `step` number along.
- **Pros:** Explicit, clear data flow, follows existing patterns of passing `memory`.
- **Cons:** Requires modifying multiple function signatures.
- **Implementation Snippet:**

  ```python
  # recursive/engine.py
  def forward_one_step_not_parallel(self, step, ...):
      ...
      action_name, action_result = need_next_step_node.next_action_step(
          self.memory, step=step, *action_args, **action_kwargs # Pass step
      )
      ...

  # recursive/node/abstract.py
  def next_action_step(self, memory, step, *args, **kwargs): # Add step
      ...
      action_name, action_result = self.do_action(
          action_name, memory, step=step, *args, **kwargs # Pass step
      )
      ...

  def do_action(self, action_name, memory, step, *args, **kwargs): # Add step
      agent_func = self.agent_proxy.get_agent_func(action_name)
      result = agent_func(self, memory, step=step, *args, **kwargs) # Pass step
      ...

  # recursive/agent/proxy.py (Conceptual - needs checking AgentProxy impl.)
  def call_agent(self, agent_name, node, memory, step, *args, **kwargs): # Add step
      agent = self._get_agent(agent_name)
      return agent.forward(node, memory, step=step, *args, **kwargs) # Pass step

  # recursive/agent/*.py (Example: SimpleExecutor)
  def forward(self, node, memory, step, *args, **kwargs): # Add step
      ...
      result = self.call_llm(..., step=step, node=node, ...) # Pass step
      ...

  # recursive/agent/base.py
  def call_llm(self, ..., step: int, node: Optional[AbstractNode] = None, **other_inner_args): # Add step
      ...
      emit_llm_call_started(..., step=step, node_id=node_id)
      ...
      emit_llm_call_completed(..., step=step, node_id=node_id, ...)
      ...
  ```

**Pattern 2: Context Object**

- **Description:** Introduce a `Context` object (similar to how `Memory` is passed) that holds execution context like the `step` number. Pass this object down the call stack.
- **Pros:** Bundles related context information, potentially cleaner signatures if more context is needed later.
- **Cons:** Adds a new object to pass around, requires defining the `Context` class.

**Pattern 3: Thread-Local Storage or Global State (Not Recommended)**

- **Description:** Store the current `step` number in thread-local storage or a global variable accessible by the `EventBus` or `Agent`.
- **Pros:** Avoids modifying function signatures.
- **Cons:** Implicit dependency, harder to reason about, can cause issues in concurrent environments (though the current engine seems sequential), less testable.

**Recommendation:** Pattern 1 (Pass Down the Call Stack) is the most explicit and maintainable approach, aligning with how `Memory` is currently handled.

## 4. Including Full Prompt/Response

This is straightforward as the data is already available within `Agent.call_llm`.

1.  **Modify Event Emission Helpers:** Update `emit_llm_call_started` and `emit_llm_call_completed` in `recursive/utils/event_bus.py` to accept the full prompt/response and remove truncation.
2.  **Update `call_llm`:** Pass the full `message` list (or a formatted string representation) and the full `content` to the emission helpers.

## 5. Proposed Code Changes

### 5.1. Python Changes (`recursive/utils/event_bus.py`)

Update the emitter functions:

```python
# recursive/utils/event_bus.py

def emit_llm_call_started(
    agent_class: str,
    model: str,
    prompt_messages: list, # Changed from prompt: str
    step: Optional[int] = None, # Added step
    node_id: Optional[str] = None,
):
    payload = {
        "agent_class": agent_class,
        "model": model,
        "prompt": prompt_messages, # Pass full messages
        # Removed prompt_preview
    }
    if step is not None:
        payload["step"] = step # Add step
    if node_id:
        payload["node_id"] = node_id
    bus.publish(_create_event(EventType.LLM_CALL_STARTED, payload))

def emit_llm_call_completed(
    agent_class: str,
    model: str,
    duration: float,
    response_content: str, # Changed from result_summary: str
    error: Optional[str] = None,
    step: Optional[int] = None, # Added step
    node_id: Optional[str] = None,
    token_usage: Optional[dict] = None,
):
    payload = {
        "agent_class": agent_class,
        "model": model,
        "duration_seconds": duration,
        "response": response_content, # Pass full content
        # Removed result_summary
    }
    if error:
        payload["error"] = error
    if step is not None:
        payload["step"] = step # Add step
    if node_id:
        payload["node_id"] = node_id
    if token_usage:
        payload["token_usage"] = token_usage
    bus.publish(_create_event(EventType.LLM_CALL_COMPLETED, payload))
```

### 5.2. Python Changes (`recursive/agent/base.py`)

Update the `call_llm` method signature and the calls to the emitters (assuming Pattern 1 for step propagation):

```python
# recursive/agent/base.py

class Agent(ABC):
    # ... (other methods)

    def call_llm(
        self,
        system_message,
        prompt,
        parse_arg_dict,
        history_message=None,
        step: Optional[int] = None, # Added step argument
        node: Optional[AbstractNode] = None,
        **other_inner_args,
    ):
        # ... (message construction)
        message = [
            {"role": "system", "content": system_message},
            # ... (add history)
            {"role": "user", "content": prompt}
        ]
        # ... (other setup)
        agent_name = self.__class__.__name__
        node_id = node.hashkey if node else None

        # --- Emit LLMCallStarted ---
        emit_llm_call_started(
            agent_class=agent_name,
            model=model,
            prompt_messages=message, # Pass full message list
            step=step, # Pass step
            node_id=node_id,
        )

        error_msg = None
        token_usage = None
        resp_data = {} # Store raw response for logging
        content = "" # Initialize content

        try:
            resp = llm.call(messages=message, model=model, **other_inner_args)[0]
            resp_data = resp # Store raw response
            reason = (
                resp["message"].get("reasoning_content", "") if "r1" in model else ""
            )
            content = resp["message"].get("content", "")
            token_usage = resp.get("usage")
        except Exception as e:
            # ... (error handling)
            error_msg = str(e)
            content = "ERROR: " + error_msg # Include error in content for clarity
            reason = ""

        llm_call_duration = time.monotonic() - llm_call_start_time

        # ... (logging setup)
        log_data.update(
            {"response": {"content": content, "reason": reason, "raw_response": resp_data}}
        )

        result = {"original": content, "result": content, "reason": reason}

        # --- Emit LLMCallCompleted ---
        emit_llm_call_completed(
            agent_class=agent_name,
            model=model,
            duration=llm_call_duration,
            response_content=content, # Pass full content
            error=error_msg,
            step=step, # Pass step
            node_id=node_id,
            token_usage=token_usage,
        )

        # ... (rest of the method for parsing and logging)
        return result
```

- **Note:** The rest of the call stack needs to be updated as shown in Pattern 1 above to pass `step` down.

### 5.3. TypeScript Changes (`ui-react/src/features/events/eventsApi.ts`)

Update the payload interfaces:

```typescript
// ui-react/src/features/events/eventsApi.ts

// Define the structure for a single message in the prompt
export interface LlmMessage {
  role: "system" | "user" | "assistant" | string; // Allow other roles potentially
  content: string;
}

export interface LlmCallStartedPayload {
  agent_class: string;
  model: string;
  // Removed prompt_preview
  prompt: LlmMessage[]; // Changed to array of messages
  step?: number | null; // Added optional step
  node_id?: string | null;
}

export interface LlmCallCompletedPayload {
  agent_class: string;
  model: string;
  duration_seconds: number;
  // Removed result_summary
  response: string; // Changed to full response content
  error?: string | null;
  step?: number | null; // Added optional step
  node_id?: string | null;
  token_usage?: TokenUsage | null;
}

// Make sure the main AgentEvent discriminated union uses these updated payloads
export type AgentEvent =
  // ... (other event types)
  | {
      event_id: string;
      timestamp: string;
      event_type: "llm_call_started";
      run_id?: string | null;
      payload: LlmCallStartedPayload; // Use updated payload
    }
  | {
      event_id: string;
      timestamp: string;
      event_type: "llm_call_completed";
      run_id?: string | null;
      payload: LlmCallCompletedPayload; // Use updated payload
    };
// ... (rest of the union)

// ... (rest of the file: API definition, hooks, etc.)
```

## 6. Next Steps

1.  Implement the call stack modifications (Pattern 1) to pass the `step` number from `GraphRunEngine.forward_one_step_not_parallel` down to `Agent.call_llm`.
2.  Apply the changes to `recursive/utils/event_bus.py` and `recursive/agent/base.py` as outlined above.
3.  Update the TypeScript types in `ui-react/src/features/events/eventsApi.ts`.
4.  Update the React UI components (`ui-react/src/features/events/EventTable.tsx` or similar) to display the new `step`, `prompt`, and `response` fields correctly. Consider how to best display potentially long prompts/responses (e.g., expandable sections, modal popups).
5.  Test the changes thoroughly by running the agent and observing the events in the UI and/or tooltips). the UI). the UI or Redis stream and log files.
