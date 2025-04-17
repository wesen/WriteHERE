# Guide: Adding Redis Event Streaming to the Recursive Agent

## 1. Introduction

This document provides a step-by-step guide for integrating Redis-based event streaming into the `recursive` agent codebase. The goal is to emit events at key points during the agent's execution process (e.g., engine steps, node status changes, LLM calls, tool usage) and publish them to a Redis stream.

This enables real-time monitoring and visualization of the agent's progress, either through log analysis or via a simple web UI connected through a WebSocket server that relays events from Redis.

**Target Audience:** Developers familiar with the `recursive` agent codebase who need to implement or understand the event instrumentation.

**Scope:**

- Defining event types and schemas.
- Identifying locations in the code to emit events.
- Implementing a simple Redis-based event bus.
- Adding event emission calls to `engine.py`, `node/abstract.py`, `agent/base.py`, and `executor/action/action_executor.py`.
- Creating a FastAPI WebSocket server to bridge Redis events to web clients.
- Providing a minimal HTML/JavaScript UI for displaying events.

## 2. Requirements and Specifications

**Functional Requirements:**

- Events must be published to a configurable Redis stream.
- Key execution points must trigger specific event types.
- Event payloads should contain relevant context (timestamps, IDs, status, durations, etc.).
- A separate process (WebSocket server) should consume events from Redis and broadcast them.
- A basic web UI should connect to the WebSocket server and display incoming events.

**Technical Choices & Constraints:**

- **Event Broker:** Redis Streams (requires Redis >= 5.0)
- **Python Libraries:**
  - `redis` (for Redis interaction)
  - `pydantic` (for event schema definition)
  - `fastapi` (for WebSocket server)
  - `uvicorn` (to run FastAPI)
- **Event Format:** JSON serialization of Pydantic models.
- **Concurrency:** The WebSocket server should run in a separate thread to avoid blocking the main agent process.

**Dependencies Installation:**

```bash
# Using pip
pip install "redis[hiredis]" pydantic fastapi "uvicorn[standard]"

# Or using Poetry
poetry add redis pydantic fastapi uvicorn hiredis
```

_(Note: `hiredis` is optional but recommended for performance)_

## 3. Architecture Overview

The event streaming system follows this flow:

```mermaid
graph LR
    A[Agent Components (Engine, Node, Agent, Executor)] -- Publishes --> B(EventBus);
    B -- Pushes (XADD) --> C(Redis Stream 'agent_events');
    D[WebSocket Server (FastAPI)] -- Reads (XREAD) --> C;
    D -- Sends --> E(WebSocket Clients);
    F[Browser UI] -- Connects --> E;

    style C fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#ccf,stroke:#333,stroke-width:2px
```

- **Producers** (`Agent Components`): Synchronously call `event_bus.publish(Event(...))` at specific code locations.
- **EventBus:** A simple Python class that takes an `Event` object, serializes it to JSON, and pushes it to the configured Redis Stream (`agent_events` by default) using `XADD`. It's designed to be fire-and-forget.
- **WebSocket Server:** Runs in a background thread. It continuously reads new events from the Redis Stream using a blocking `XREAD` command and immediately forwards the JSON payload to all connected WebSocket clients.
- **Browser UI:** A simple HTML page with JavaScript that establishes a WebSocket connection to the server and appends incoming event data to a table.

## 4. Data Model (Event Schemas)

We'll define event types using Pydantic models for clear structure and serialization. Create a new file, e.g., `recursive/utils/event_bus.py`.

**`recursive/utils/event_bus.py`:**

```python
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import redis
from pydantic import BaseModel, Field

# --- Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
EVENT_STREAM_NAME = os.getenv("EVENT_STREAM", "agent_events")
EVENT_STREAM_MAXLEN = int(os.getenv("EVENT_STREAM_MAXLEN", 10000)) # Approx. max entries

# --- Redis Client ---
# Use decode_responses=True for easier handling in Python
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_timeout=5, # Add timeout
        health_check_interval=30 # Check connection periodically
    )
    # Test connection
    redis_client.ping()
    print(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis at {REDIS_HOST}:{REDIS_PORT}: {e}")
    print("Event publishing will be disabled.")
    redis_client = None
except Exception as e:
    print(f"An unexpected error occurred during Redis connection: {e}")
    redis_client = None


# --- Event Types Enum ---
class EventType(str, Enum):
    STEP_STARTED = "step_started"
    STEP_FINISHED = "step_finished"
    NODE_STATUS_CHANGED = "node_status_changed"
    LLM_CALL_STARTED = "llm_call_started"
    LLM_CALL_COMPLETED = "llm_call_completed"
    TOOL_INVOKED = "tool_invoked"
    TOOL_RETURNED = "tool_returned"
    # Add more specific events if needed, e.g., SEARCH_COMPLETED

# --- Base Event Model ---
class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    run_id: Optional[str] = None # Optional global run identifier

    class Config:
        # Ensure datetime objects are serialized to ISO 8601 format
        json_encoders = {datetime: lambda v: v.isoformat() + "Z"}


# --- Event Bus Class ---
class EventBus:
    def __init__(self, client: Optional[redis.Redis], stream_name: str, max_len: int):
        self._client = client
        self._stream_name = stream_name
        self._max_len = max_len
        self._enabled = client is not None

    def publish(self, event: Event):
        if not self._enabled:
            return # Silently ignore if Redis is not connected

        try:
            # Use Pydantic's json() method for serialization respecting json_encoders
            payload = {"json_payload": event.json()}
            self._client.xadd(
                self._stream_name,
                payload,
                maxlen=self._max_len,
                approximate=True # Use approximate trimming for performance
            )
        except redis.exceptions.ConnectionError as e:
            print(f"Redis connection error during publish: {e}. Disabling further publishes.")
            self._enabled = False # Disable on connection error
        except Exception as e:
            # Log other potential errors (e.g., serialization issues)
            print(f"Error publishing event to Redis: {e}")
            # Consider whether to disable or just log based on error type

# --- Global Event Bus Instance ---
# Initialize with the configured client and stream details
bus = EventBus(redis_client, EVENT_STREAM_NAME, EVENT_STREAM_MAXLEN)

# --- Helper Functions (Optional but Recommended) ---
# These make emitting specific events cleaner at the call site.

_current_run_id: Optional[str] = None # Module-level variable to hold the run ID

def set_run_id(run_id: str):
    """Sets a global run ID for all subsequent events in this process."""
    global _current_run_id
    _current_run_id = run_id

def _create_event(event_type: EventType, payload: Dict[str, Any]) -> Event:
    """Factory to create event with common fields."""
    return Event(event_type=event_type, payload=payload, run_id=_current_run_id)

def emit_step_started(step: int, node_id: str, node_goal: str, root_id: str):
    bus.publish(_create_event(EventType.STEP_STARTED, {
        "step": step, "node_id": node_id, "node_goal": node_goal, "root_id": root_id
    }))

def emit_step_finished(step: int, node_id: str, action_name: str, status_after: str, duration: float):
     bus.publish(_create_event(EventType.STEP_FINISHED, {
         "step": step, "node_id": node_id, "action_name": action_name,
         "status_after": status_after, "duration_seconds": duration
     }))

def emit_node_status_changed(node_id: str, node_goal: str, old_status: str, new_status: str):
    bus.publish(_create_event(EventType.NODE_STATUS_CHANGED, {
        "node_id": node_id, "node_goal": node_goal,
        "old_status": old_status, "new_status": new_status
    }))

def emit_llm_call_started(agent_class: str, model: str, prompt: str, node_id: Optional[str] = None):
     # Consider hashing or truncating the prompt for brevity/security
    payload = {"agent_class": agent_class, "model": model, "prompt_preview": prompt[:200] + "..."}
    if node_id: payload["node_id"] = node_id
    bus.publish(_create_event(EventType.LLM_CALL_STARTED, payload))


def emit_llm_call_completed(agent_class: str, model: str, duration: float, result_summary: str, error: Optional[str] = None, node_id: Optional[str] = None, token_usage: Optional[dict] = None):
    payload = {
        "agent_class": agent_class, "model": model, "duration_seconds": duration,
        "result_summary": result_summary[:500] + "..." # Truncate result
    }
    if error: payload["error"] = error
    if node_id: payload["node_id"] = node_id
    if token_usage: payload["token_usage"] = token_usage # e.g., {'prompt_tokens': 100, 'completion_tokens': 50}
    bus.publish(_create_event(EventType.LLM_CALL_COMPLETED, payload))


def emit_tool_invoked(tool_name: str, api_name: str, args_summary: str, node_id: Optional[str] = None):
    payload = {"tool_name": tool_name, "api_name": api_name, "args_summary": args_summary[:500] + "..."}
    if node_id: payload["node_id"] = node_id
    bus.publish(_create_event(EventType.TOOL_INVOKED, payload))


def emit_tool_returned(tool_name: str, api_name: str, state: str, duration: float, result_summary: str, error: Optional[str] = None, node_id: Optional[str] = None):
    payload = {
        "tool_name": tool_name, "api_name": api_name, "state": state,
        "duration_seconds": duration, "result_summary": result_summary[:500] + "..."
    }
    if error: payload["error"] = error
    if node_id: payload["node_id"] = node_id
    bus.publish(_create_event(EventType.TOOL_RETURNED, payload))

```

## 5. Implementation Plan (Instrumentation)

Modify the following files to import the event bus helpers and call them at the appropriate locations.

### 5.1 Engine Step Events (`recursive/engine.py`)

```diff
# ... existing imports ...
 from loguru import logger
 from recursive.common.log_typing import log_typing
+import time # For timing steps
+from recursive.utils.event_bus import emit_step_started, emit_step_finished

 class GraphRunEngine:
     # ... existing methods ...

+    # Add step counter to __init__ or manage it in forward_one_step_untill_done
+    # For simplicity, let's assume step is passed down or managed in the loop calling this
+
     @log_typing
     def forward_one_step_not_parallel(
         self,
+        step: int, # Add step number parameter
         full_step: bool = False,
         select_node_hashkey: Optional[str] = None,
         log_fn: Optional[str] = None,
@@ -197,6 +199,7 @@
                     )
                 )

+        step_start_time = time.monotonic()
         if need_next_step_node is None:
             logger.info("All Done")
             # display_graph(self.root_node.inner_graph, fn=log_fn)
@@ -209,6 +212,13 @@

             return "done"
         logger.info("select node: {}\".format(need_next_step_node.task_str()))
+
+        # --- Emit StepStarted ---
+        emit_step_started(step=step,
+                          node_id=need_next_step_node.hashkey,
+                          node_goal=need_next_step_node.task_info.get("goal", "?"),
+                          root_id=self.root_node.hashkey)
+
         # Execute the next step for this node
         # Update Memory
         self.memory.update_infos([need_next_step_node])
@@ -240,6 +250,13 @@
         # After the action ends, update the entire graph status. When in parallel, should wait for all parallel tasks to complete before executing uniformly
         self.forward_exam(self.root_node, verbose)

+        # --- Emit StepFinished ---
+        step_duration = time.monotonic() - step_start_time
+        emit_step_finished(step=step,
+                           node_id=need_next_step_node.hashkey,
+                           action_name=action_name,
+                           status_after=need_next_step_node.status.name,
+                           duration=step_duration)
         if verbose:
             display_plan(self.root_node.inner_graph)
         return None  # Explicitly return None if not done
@@ -273,10 +290,10 @@
         \"\"\"
         self.root_node.status = TaskStatus.READY
         step: int = 0
-        final_answer: str = \"\"
         for step in range(10000): # Use the loop variable 'step'
             logger.info(\"Step {}\".format(step))
             ret = self.forward_one_step_not_parallel(
+                step=step, # Pass step number down
                 full_step=False,  # Note: full_step arg passed from here seems ignored in the call above
                 log_fn=\"logs/temp/{}\".format(step),
                 nodes_json_file=nodes_json_file,  # Pass directly, internal method handles logic

```

_Modification in `forward_one_step_untill_done`: Ensure the `step` number is passed correctly to `forward_one_step_not_parallel`._
_You might also want to call `set_run_id()` at the beginning of your main script (`report_writing.py` or `story_writing.py`) with a unique ID for the overall run._

### 5.2 Node Status Changes (`recursive/node/abstract.py`)

```diff
 # ... existing imports ...
 from recursive.common.enums import TaskStatus, NodeType
 from recursive.graph import Graph
+from recursive.utils.event_bus import emit_node_status_changed


 class AbstractNode(ABC):
     # ... existing methods ...

     def do_exam(self, verbose):
         \"\"\"
+        Examine the node's status and update it based on defined conditions, emitting an event on change.
         # ... rest of docstring ...
         \"\"\"
         if not self.is_suspend:
@@ -466,12 +467,19 @@
                 )\n            )\n        for condition_func, next_status in self.status_exam_mapping[self.status]:\n            if condition_func(self):\n+                old_status = self.status\n+                # --- Emit NodeStatusChanged ---
+                if old_status != next_status:\n+                    emit_node_status_changed(\n+                        node_id=self.hashkey,\n+                        node_goal=self.task_info.get(\"goal\", \"?\"),\n+                        old_status=old_status.name,\n+                        new_status=next_status.name\n+                    )\n                 if verbose:\n                     logger.info(\n                         \"Do Exam, {}:{} make {} -> {}\".format(\n@@ -481,7 +489,7 @@
                             self.status,\n                             next_status\n                         )\n-                    )\n-                self.status = next_status\n+                    )\n+                self.status = next_status # Status change happens *after* event emission\n                 break\n \n     def task_str(self):\n@@ -746,7 +754,7 @@
         return\n \n     def do_action(self, action_name, memory, *args, **kwargs):\n-        \"\"\"\n+        \"\"\"\n         Execute an action on this node.\n \n         This method:\n@@ -763,7 +771,9 @@
         Returns:\n             The result of the action execution.\n         \"\"\"\n-        agent = self.agent_proxy.proxy(action_name)\n+        # Note: Action execution itself (LLM calls, Tool calls within agents)\n+        # should emit their own specific events.\n+        agent = self.agent_proxy.proxy(action_name)\n         result = getattr(self, action_name)(agent, memory, *args, **kwargs)\n         # Saving information\n         self.result[action_name] = {\n

```

### 5.3 LLM Calls (`recursive/agent/base.py`)

```diff
 # ... existing imports ...
 from loguru import logger
 from datetime import datetime
 import os
+import time # For timing
 import yaml
 from typing import Any
+import hashlib # For hashing prompt (optional)

 from recursive.node.abstract import AbstractNode
 from recursive.memory import Memory
+from recursive.utils.event_bus import emit_llm_call_started, emit_llm_call_completed

 class Agent(ABC):
     # ... existing methods ...

     def call_llm(
         self,
         system_message,
         prompt,
         parse_arg_dict,
         history_message=None,
+        node: Optional[AbstractNode] = None, # Pass node for context if possible
         **other_inner_args,
     ):\n         llm = OpenAIApiProxy()\n \n@@ -50,8 +53,10 @@
         logger.info(message[-1][\"content\"])\n \n         model = other_inner_args.pop(\"model\", \"gpt-4o\")\n-\n+\n+        llm_call_start_time = time.monotonic()
+        node_id = node.hashkey if node else None
         # Log the request before making the call
         timestamp = datetime.now().strftime(\"%Y-%m-%d--%H-%M-%S-%f\")\n         agent_name = self.__class__.__name__\n@@ -64,8 +69,16 @@
             \"messages\": message,\n             \"other_args\": other_inner_args,\n         }\n+\n+        # --- Emit LLMCallStarted ---
+        # Use a truncated prompt or a hash for the event payload
+        # prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
+        emit_llm_call_started(agent_class=agent_name, model=model, prompt=prompt, node_id=node_id)\n+\n+        error_msg = None
+        token_usage = None
+        result = {}\n \n         try:\n-            resp = llm.call(messages=message, model=model, **other_inner_args)[0]\n-            if \"r1\" in model:\n-                reason = resp[\"message\"][\"reasoning_content\"]\n-            else:\n-                reason = \"\"\n-            content = resp[\"message\"][\"content\"]\n-            logger.info(\"Get REASONING: {}\\n\\nResult: {}\".format(reason, content))\n+            resp = llm.call(messages=message, model=model, **other_inner_args)[0]\n+            reason = resp[\"message\"].get(\"reasoning_content\", \"\") if \"r1\" in model else \"\"\n+            content = resp[\"message\"].get(\"content\", \"\")\n+            logger.info(\"Get REASONING: {}\\n\\nResult: {}\".format(reason, content))\n+            token_usage = resp.get(\"usage\") # Assuming usage info is in the response\n+        except Exception as e:\n+            logger.error(f\"LLM call failed: {e}\")\n+            error_msg = str(e)\n+            content = \"\" # Ensure content is empty on error\n+            reason = \"\"\n+\n+        llm_call_duration = time.monotonic() - llm_call_start_time\n \n         # Update log data with response
+        log_data.update(\n@@ -75,6 +88,14 @@
         assert isinstance(parse_arg_dict, dict)\n         result = {\"original\": content, \"result\": content, \"reason\": reason}\n \n+        # --- Emit LLMCallCompleted ---
+        emit_llm_call_completed(agent_class=agent_name, model=model,\n+                                duration=llm_call_duration,\n+                                result_summary=content, # Summary is truncated in helper\n+                                error=error_msg,\n+                                node_id=node_id,\n+                                token_usage=token_usage)\n+\n         \"\"\"\n         The following code extracts structured information from an LLM\'s textual response by looking for content within specific XML-like tags. It works by:\n \n@@ -99,4 +120,6 @@
         with open(log_file, \"w\") as f:\n             yaml.safe_dump(log_data, f, default_flow_style=False, allow_unicode=True)\n \n-        return result\n+        # Add status based on error
+        result[\"status\"] = \"success\" if error_msg is None else \"error\"
+        return result
```

_Note: You'll need to adapt how `node` is passed into `call_llm` from its callers (like `get_llm_output` in `recursive/agent/helpers.py`). Add `node=node` to the `agent.call_llm` call within `get_llm_output`._

### 5.4 Tool Invocations (`recursive/executor/action/action_executor.py`)

```diff
 from typing import Dict, List, Union
+import time # For timing
+import json # For args summary

 from recursive.executor.schema import ActionReturn, ActionValidCode
 from .base import BaseAction
 from .builtin_actions import FinishAction, InvalidAction, NoAction
+from recursive.utils.event_bus import emit_tool_invoked, emit_tool_returned

 class ActionExecutor:
     # ... existing methods ...

     def __call__(self, name: str, command: str) -> ActionReturn:\n         action_name, api_name = name.split(\".\") if \".\" in name else (name, \"run\")\n+        node_id = None # TODO: Figure out how to get node context here if needed\n+        tool_start_time = time.monotonic()
+        action_return = None
+        error_msg = None
+
         if not self.is_valid(action_name):\n             if name == self.no_action.name:\n                 action_return = self.no_action(command)\n             elif name == self.finish_action.name:\n                 action_return = self.finish_action(command)\n             else:\n                 action_return = self.invalid_action(command)\n         else:\n-            action_return = self.actions[action_name](command, api_name)\n-            action_return.valid = ActionValidCode.OPEN\n-        return action_return\n+            # --- Emit ToolInvoked ---
+            try:\n+                # Attempt to parse command for better summary, fallback to raw string\n+                args_summary = json.dumps(json.loads(command))\n+            except:\n+                args_summary = str(command)\n+\n+            emit_tool_invoked(tool_name=action_name, api_name=api_name,\n+                              args_summary=args_summary, node_id=node_id)\n+\n+            try:\n+                action_return = self.actions[action_name](command, api_name)\n+                action_return.valid = ActionValidCode.OPEN\n+            except Exception as e:\n+                logger.error(f\"Tool execution failed for {action_name}.{api_name}: {e}\")\n+                error_msg = str(e)\n+                # Create a minimal ActionReturn on error
+                action_return = ActionReturn(args={}, type=action_name, errmsg=error_msg, state=ActionStatusCode.API_ERROR)\n+\n+        tool_duration = time.monotonic() - tool_start_time
+
+        # --- Emit ToolReturned ---
+        result_summary = str(action_return.result) if hasattr(action_return, 'result') else \"N/A\"
+        state_name = action_return.state.name if hasattr(action_return, 'state') else ActionStatusCode.UNKNOWN.name
+
+        emit_tool_returned(tool_name=action_name, api_name=api_name,\n+                           state=state_name,\n+                           duration=tool_duration,\n+                           result_summary=result_summary,\n+                           error=error_msg or action_return.errmsg, # Prioritize direct exception
+                           node_id=node_id)\n+\n+        return action_return

```

_Note: Getting the `node_id` context into the `ActionExecutor.__call__` might require passing it down through the agent layers that invoke it, which could be complex._

## 6. WebSocket Bridge Server

Create a new file, e.g., `recursive/utils/ws_server.py`, to house the FastAPI server.

**`recursive/utils/ws_server.py`:**

```python
import asyncio
import json
import os
import threading
from typing import Set

import redis.asyncio as aredis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse # For serving the UI directly
from fastapi.staticfiles import StaticFiles # Optional: For serving UI assets

# --- Configuration ---
# Reuse stream name from event_bus or define separately
EVENT_STREAM_NAME = os.getenv("EVENT_STREAM", "agent_events")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0") # Use URL format for async client
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", 9999))
UI_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "ui", "index.html") # Path to UI html

# Global set to keep track of active WebSocket connections
active_connections: Set[WebSocket] = set()

async def redis_listener(redis_client: aredis.Redis):
    """Listens to Redis stream and broadcasts messages to connected websockets."""
    last_id = "$" # Start reading new messages
    print(f"Starting Redis listener on stream '{EVENT_STREAM_NAME}'...")
    while True:
        try:
            # block=0 means wait indefinitely for new messages
            response = await redis_client.xread({EVENT_STREAM_NAME: last_id}, block=0)
            if response:
                for stream, messages in response:
                    for message_id, fields in messages:
                        last_id = message_id
                        # Assuming the event JSON is stored under 'json_payload' key
                        if "json_payload" in fields:
                            message_data = fields["json_payload"]
                            # Broadcast to all connected clients
                            # Create a list copy to avoid issues if set changes during iteration
                            disconnected_peers = set()
                            for connection in list(active_connections):
                                try:
                                    await connection.send_text(message_data)
                                except WebSocketDisconnect:
                                    disconnected_peers.add(connection)
                                    print("Client disconnected (during send)")
                                except Exception as e:
                                    print(f"Error sending to client: {e}")
                                    disconnected_peers.add(connection) # Assume problematic

                            # Clean up disconnected peers after broadcast
                            for peer in disconnected_peers:
                                active_connections.discard(peer)
                        else:
                            print(f"Warning: Received message {message_id} without 'json_payload' field.")

        except aredis.exceptions.ConnectionError as e:
            print(f"Redis connection error in listener: {e}. Attempting to reconnect...")
            await asyncio.sleep(5) # Wait before retrying
        except Exception as e:
            print(f"Unexpected error in Redis listener: {e}")
            await asyncio.sleep(1) # Prevent rapid looping on unknown errors

async def startup_event():
    """Creates Redis connection and starts the listener task."""
    print("WebSocket server starting up...")
    try:
        redis_client = aredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping() # Verify connection
        print(f"Async Redis connected successfully to {REDIS_URL}")
        # Start the Redis listener task in the background
        asyncio.create_task(redis_listener(redis_client))
    except aredis.exceptions.ConnectionError as e:
        print(f"FATAL: Could not connect to Redis at {REDIS_URL} on startup: {e}")
        # Optionally, exit or handle this critical failure
    except Exception as e:
        print(f"FATAL: Unexpected error during startup Redis connection: {e}")


app = FastAPI(on_startup=[startup_event])

# Optional: Mount static files directory if UI has separate CSS/JS
# ui_dir = os.path.join(os.path.dirname(__file__), "..", "..", "ui")
# if os.path.exists(ui_dir):
#     app.mount("/static", StaticFiles(directory=ui_dir), name="static")


# Serve the minimal HTML UI from the root path
@app.get("/")
async def get_ui():
    try:
        with open(UI_FILE_PATH, "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<html><body><h1>UI file not found</h1></body></html>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<html><body><h1>Error loading UI: {e}</h1></body></html>", status_code=500)


@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections."""
    await websocket.accept()
    print(f"Client connected: {websocket.client}")
    active_connections.add(websocket)
    try:
        # Keep the connection alive, listening for disconnect
        while True:
            # We don't expect messages from client in this simple broadcast setup
            # But keep receiving to detect disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"Client disconnected: {websocket.client}")
    except Exception as e:
        print(f"Error in WebSocket connection: {e}")
    finally:
        active_connections.discard(websocket)


def run_server():
    """Runs the Uvicorn server."""
    print(f"Starting Uvicorn server on {WS_HOST}:{WS_PORT}")
    uvicorn.run(app, host=WS_HOST, port=WS_PORT, log_level="info")

def start_ws_thread():
    """Starts the FastAPI server in a separate daemon thread."""
    print("Attempting to start WebSocket server thread...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("WebSocket server thread started.")
    return server_thread

# Example usage (if run directly)
if __name__ == "__main__":
    # This allows running the server standalone for testing
    print("Running WebSocket server directly...")
    run_server()

```

**Modify your main script (`recursive/main.py` or similar entry point):**

Add this near the beginning of your script execution:

```python
from recursive.utils.ws_server import start_ws_thread
from recursive.utils.event_bus import set_run_id
import uuid # For run ID

# Start the WebSocket server in a background thread
ws_thread = start_ws_thread()

# Generate a unique ID for this agent run
current_run_id = str(uuid.uuid4())
set_run_id(current_run_id)
print(f"Agent Run ID: {current_run_id}")

# --- Your existing main script logic follows ---
# Example:
# if __name__ == "__main__":
#     parser = define_args()
#     args = parser.parse_args()
#     # ... rest of your setup ...
#     if args.mode == "story":
#         story_writing(...)
#     else:
#         report_writing(...)

```

## 7. UI/UX Considerations (Minimal UI)

Create a directory `ui/` in your project root if it doesn't exist. Inside `ui/`, create `index.html`.

**`ui/index.html`:**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Recursive Agent - Live Events</title>
    <style>
      body {
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.6;
        margin: 0;
        padding: 20px;
        background-color: #f4f4f4;
        color: #333;
      }
      h1 {
        text-align: center;
        color: #2c3e50;
        margin-bottom: 20px;
      }
      #eventsTable {
        border-collapse: collapse;
        width: 100%;
        margin-top: 20px;
        background-color: #fff;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
      }
      #eventsTable th,
      #eventsTable td {
        border: 1px solid #ddd;
        padding: 10px 12px;
        text-align: left;
        font-size: 0.9em;
      }
      #eventsTable th {
        background-color: #3498db;
        color: white;
        position: sticky;
        top: 0;
        z-index: 1;
      }
      #eventsTable tr:nth-child(even) {
        background-color: #ecf0f1;
      }
      #eventsTable tr:hover {
        background-color: #d6eaf8;
      }
      #status {
        margin-top: 15px;
        padding: 10px;
        background-color: #eaf2f8;
        border: 1px solid #aed6f1;
        border-radius: 4px;
        text-align: center;
        font-weight: bold;
      }
      .status-connected {
        color: #27ae60;
      }
      .status-disconnected {
        color: #c0392b;
      }
      .payload-details {
        max-height: 100px;
        overflow-y: auto;
        display: block;
        white-space: pre-wrap;
        word-break: break-all;
        background-color: #fff;
        padding: 5px;
        border: 1px solid #eee;
        font-family: monospace;
        font-size: 0.85em;
        margin-top: 5px;
      }
      .event-type {
        font-weight: bold;
      }
      .event-step_started {
        color: #2980b9;
      }
      .event-step_finished {
        color: #16a085;
      }
      .event-node_status_changed {
        color: #8e44ad;
      }
      .event-llm_call_started {
        color: #f39c12;
      }
      .event-llm_call_completed {
        color: #d35400;
      }
      .event-tool_invoked {
        color: #2c3e50;
      }
      .event-tool_returned {
        color: #7f8c8d;
      }
      .error {
        color: #e74c3c;
        font-weight: bold;
      }
    </style>
  </head>
  <body>
    <h1>Recursive Agent - Live Event Stream</h1>
    <div id="status" class="status-disconnected">Connecting...</div>

    <table id="eventsTable">
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Type</th>
          <th>Run ID</th>
          <th>Payload / Details</th>
        </tr>
      </thead>
      <tbody>
        <!-- Events will be prepended here -->
      </tbody>
    </table>

    <script>
      const tableBody = document.querySelector("#eventsTable tbody");
      const statusDiv = document.getElementById("status");
      let ws;

      function connectWebSocket() {
        // Determine WebSocket protocol based on window location
        const wsProtocol =
          window.location.protocol === "https:" ? "wss:" : "ws:";
        // Construct WebSocket URL dynamically
        const wsUrl = `${wsProtocol}//${window.location.hostname}:${window.location.port}/ws/events`;
        console.log(`Attempting to connect to WebSocket: ${wsUrl}`);

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("WebSocket connection established");
          statusDiv.textContent = "Connected";
          statusDiv.className = "status-connected";
        };

        ws.onmessage = (event) => {
          try {
            const eventData = JSON.parse(event.data);
            console.log("Received event:", eventData);
            addEventToTable(eventData);
          } catch (e) {
            console.error("Failed to parse event data:", e);
            // Optionally display raw data or an error message in the table
            addRawEventToTable(event.data);
          }
        };

        ws.onerror = (error) => {
          console.error("WebSocket error:", error);
          statusDiv.textContent = "Connection Error";
          statusDiv.className = "status-disconnected";
        };

        ws.onclose = (event) => {
          console.log("WebSocket connection closed:", event.code, event.reason);
          statusDiv.textContent = "Disconnected. Attempting to reconnect...";
          statusDiv.className = "status-disconnected";
          // Simple exponential backoff reconnect
          setTimeout(
            connectWebSocket,
            Math.min(1000 * 2 ** Math.floor(Math.random() * 5), 30000)
          ); // Reconnect after 1-30 seconds
        };
      }

      function formatTimestamp(isoString) {
        try {
          const date = new Date(isoString);
          // Format to HH:MM:SS.sss
          return date.toLocaleTimeString("en-US", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            fractionalSecondDigits: 3,
          });
        } catch (e) {
          console.error("Error formatting timestamp:", isoString, e);
          return isoString; // Fallback to original string
        }
      }

      function addEventToTable(eventData) {
        const row = tableBody.insertRow(0); // Prepend new rows

        const cellTimestamp = row.insertCell();
        const cellType = row.insertCell();
        const cellRunId = row.insertCell();
        const cellPayload = row.insertCell();

        cellTimestamp.textContent = formatTimestamp(eventData.timestamp);
        cellType.innerHTML = `<span class="event-type event-${eventData.event_type.replace(
          /-/g,
          "_"
        )}">${eventData.event_type}</span>`;
        cellRunId.textContent = eventData.run_id || "N/A";

        // Pretty print payload
        const payloadPre = document.createElement("pre");
        payloadPre.className = "payload-details";
        try {
          // Check for specific error fields in payload for highlighting
          let payloadStr = JSON.stringify(eventData.payload, null, 2);
          if (eventData.payload && eventData.payload.error) {
            payloadStr = payloadStr.replace(
              /"error":\s*"(.*?)"/g,
              '"error": "<span class=\'error\'>$1</span>"'
            );
            // This simple replace might break JSON validity if error contains quotes.
            // A more robust approach would parse and reconstruct the HTML.
            payloadPre.innerHTML = payloadStr; // Use innerHTML for error highlighting
          } else {
            payloadPre.textContent = payloadStr;
          }
        } catch (e) {
          payloadPre.textContent = `Error formatting payload: ${e}`;
        }
        cellPayload.appendChild(payloadPre);

        // Limit table rows (optional)
        const maxRows = 200;
        if (tableBody.rows.length > maxRows) {
          tableBody.deleteRow(tableBody.rows.length - 1);
        }
      }

      function addRawEventToTable(rawData) {
        const row = tableBody.insertRow(0);
        const cellTimestamp = row.insertCell();
        const cellType = row.insertCell();
        const cellRunId = row.insertCell();
        const cellPayload = row.insertCell();

        cellTimestamp.textContent = formatTimestamp(new Date().toISOString()); // Use current time
        cellType.textContent = "RAW/ERROR";
        cellRunId.textContent = "N/A";
        cellPayload.innerHTML = `<pre class="payload-details error">Failed to parse: ${escapeHtml(
          rawData
        )}</pre>`;
      }

      function escapeHtml(unsafe) {
        return unsafe
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
      }

      // Initial connection attempt
      connectWebSocket();
    </script>
  </body>
</html>
```

## 8. Deployment Strategy / Running

1.  **Start Redis:** Ensure you have a Redis server running and accessible. You can use Docker:

    ```bash
    docker run -d -p 6379:6379 --name my-redis redis:latest
    ```

    _(If Redis requires a password or runs on a different host/port, set the `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` environment variables before running the Python application)._

2.  **Run the Agent:** Execute your main Python script (`recursive/main.py`, `report_writing.py`, etc.). This will automatically start the WebSocket server in a background thread and begin the agent process, which will publish events to Redis.

    ```bash
    # Example:
    python recursive/main.py --mode report --filename data/report_questions.jsonl --output-filename output/report_results.jsonl --model gpt-4o
    ```

3.  **Access the UI:** Open your web browser and navigate to the address where the FastAPI/Uvicorn server is running (by default: `http://localhost:9999`). The UI should load, connect to the WebSocket, and start displaying events as the agent runs.

## 9. Future Enhancements

- **Event Filtering/Search in UI:** Add controls to filter events by type, node ID, or keywords in the UI.
- **More Specific Events:** Emit more granular events, e.g., for specific search phases (`SearchRoundCompleted`), agent reflections (`ReflectionCompleted`), or memory updates.
- **Error Handling:** Improve error reporting in events and display errors more prominently in the UI.
- **Alternative Event Buses:** Abstract the `EventBus` further to support other backends like Kafka or RabbitMQ.
- **Persistence/Replay:** Implement functionality to replay historical events from Redis (by reading from stream ID `0` instead of `$`).
- **Authentication/Authorization:** Secure the WebSocket endpoint if exposing it beyond local development.

## 10. Conclusion

This guide outlines the steps to integrate a Redis-based event streaming system into the `recursive` agent. By publishing structured events at key execution points and providing a real-time web UI via WebSockets, this system significantly improves observability and debugging capabilities for complex agent runs. Remember to adjust Redis connection details and instrumentation points as needed for your specific environment and focus areas.
