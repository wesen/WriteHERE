# Research‑Agent Event Streaming Guide

Welcome! This document gives a new contributor everything they need to wire **Redis‑based event streaming** into the recursive‑agent code‑base, surface those events through a WebSocket server, and display them in a tiny browser UI.

---

## 0 Prerequisites

- Python ≥ 3.10
- Redis ≥ 6 (Streams enabled by default)
- Poetry or pip‑tools to manage the extra packages: `redis[p asyncio]`, `fastapi`, `uvicorn`, `pydantic`.

```bash
poetry add redis fastapi uvicorn pydantic
```

---

## 1 Problem & High‑Level Flow

```
Agents/Engine  ──► EventBus.publish(...) ──►  Redis Stream “events”
                                                  ▼
                                            WS Server (FastAPI)
                                                  ▼
                                            Browser UI (JavaScript)
```

- **Producers** (agents, engine, tools) are _synchronous_; they merely call `bus.publish(e)` and continue.
- **EventBus** pushes the JSON string into a Redis Stream (fire‑and‑forget, 1 RTT).
- **WS Server** runs in its own thread; it performs a non‑blocking `XREAD` loop and forwards each entry to every open WebSocket.
- **UI** listens on `/events` and appends rows to a table.

---

## 2 Relevant Source Files

| File                                 | Purpose                                     | Hooks you will edit                                                                  |
| ------------------------------------ | ------------------------------------------- | ------------------------------------------------------------------------------------ |
| `engine.py`                          | Task‑graph orchestration                    | `GraphRunEngine.forward_one_step_not_parallel` (emit _StepStarted_ / _StepFinished_) |
| `agent/base.py`                      | LLM wrapper + logging                       | `Agent.call_llm` (emit _LLMCallStarted_ / _LLMCallCompleted_)                        |
| `executor/action/action_executor.py` | Tool invocation                             | `ActionExecutor.__call__` (emit _ToolInvoked_ / _ToolReturned_)                      |
| `common/enums.py`                    | TaskStatus enum                             | status changes → emit _NodeStatusChanged_                                            |
| `your_new/event_bus.py`              | **New** – central EventBus/Types            |                                                                                      |
| `your_new/ws_server.py`              | **New** – internal FastAPI+WebSocket bridge |                                                                                      |
| `ui/index.html`                      | **New** – minimal frontend                  |                                                                                      |

> All of the existing files already import `loguru`; adding one more import (`from your_new.event_bus import bus`) will not disturb their public surface.

Layer | Critical hook | Typical event(s) | Suggested payload fields

GraphRunEngine ( engine.py ) | • start of forward_one_step_not_parallel • just after need_next_step_node.next_action_step returns | StepStarted  StepFinished | step #, root‑run id, selected node.id/hashkey, action_name, timestamp, duration, exception?

Node lifecycle (AbstractNode.do_exam & status enum) | whenever self.status mutates | NodeStatusChanged | node.id, old_status, new_status, layer, parents, timestamp

Agent action (Agent.call_llm) | • immediately before the OpenAI/Claude call • immediately after the response is parsed | LLMCallStarted LLMCallCompleted | node.id, agent_class, model, prompt_hash, cost_estimate, duration, token_usage, truncated_result

Action Executor (ActionExecutor.\_\_call\_\_) | at tool invocation boundaries | ToolInvoked ToolReturned | tool_name, api_name, args_hash, latency, success

Search / web phase (BingBrowser.full_pipeline_search, etc.) | after search round summarisation | SearchRoundCompleted | query_terms, page_count, selected_count, time_spent

## Event Types & Schemas

Create **`your_new/event_bus.py`**

```python
from __future__ import annotations
from enum import Enum
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict
from pydantic import BaseModel, Field
import redis, os

# 1 Redis client (single global)
r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), decode_responses=True)
STREAM = os.getenv("EVENT_STREAM", "agent_events")

class EventType(str, Enum):
    STEP_STARTED       = "step_started"
    STEP_FINISHED      = "step_finished"
    NODE_STATUS_CHANGE = "node_status_change"
    LLM_CALL_STARTED   = "llm_call_started"
    LLM_CALL_COMPLETED = "llm_call_completed"
    TOOL_INVOKED       = "tool_invoked"
    TOOL_RETURNED      = "tool_returned"

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=datetime.utcnow)
    type: EventType
    payload: Dict[str, Any]

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

class EventBus:
    def publish(self, ev: Event):
        r.xadd(STREAM, {"json": ev.json()}, maxlen=10000, approximate=True)

bus = EventBus()
```

Schema‑wise, everything is an **arbitrary payload** under a single `json` field, keeping Redis entries flat.

### Quick helpers

```python
from typing import Any

def step_started(step: int, node_id: str, root: str):
    bus.publish(Event(type=EventType.STEP_STARTED,
                      payload={"step": step, "node": node_id, "root": root}))
```

Feel free to add thin wrappers for each event kind so callers stay concise.

---

## 4 Instrumentation Walk‑Through

### 4.1 Engine Step Events  (`engine.py`)

```diff
 from loguru import logger
+from your_new.event_bus import step_started, bus, Event, EventType
@@
 def forward_one_step_not_parallel(...):
@@
-    logger.info("Step {}".format(step))
+    logger.info("Step {}".format(step))
+    step_started(step, need_next_step_node.hashkey, self.root_node.hashkey)
@@  # after the action completes
+    bus.publish(Event(type=EventType.STEP_FINISHED,
+                      payload={"step": step, "node": need_next_step_node.hashkey}))
```

### 4.2 LLM Calls  (`agent/base.py`)

```diff
 from recursive.llm.base import OpenAIApiProxy
@@
+from your_new.event_bus import Event, EventType, bus
@@
     logger.info(message[-1]["content"])
+    bus.publish(Event(type=EventType.LLM_CALL_STARTED,
+                      payload={"node": self.kwargs.get("nid", "?"),
+                               "agent": self.__class__.__name__,
+                               "model": model}))
@@  # just before returning result
+    bus.publish(Event(type=EventType.LLM_CALL_COMPLETED,
+                      payload={"node": self.kwargs.get("nid", "?"),
+                               "duration": "TODO"}))
```

### 4.3 Tool Invocations  (`action_executor.py`)

```diff
 from recursive.executor.schema import ActionReturn, ActionValidCode
+from your_new.event_bus import Event, EventType, bus
@@
-        if not self.is_valid(action_name):
+        if not self.is_valid(action_name):
             ...
         else:
-            action_return = self.actions[action_name](command, api_name)
+            bus.publish(Event(type=EventType.TOOL_INVOKED,
+                              payload={"tool": action_name, "api": api_name}))
+            action_return = self.actions[action_name](command, api_name)
+            bus.publish(Event(type=EventType.TOOL_RETURNED,
+                              payload={"tool": action_name, "state": action_return.state.name}))
```

### 4.4 Node Status Changes

In whatever method mutates `self.status` (usually inside `AbstractNode.do_exam`), insert:

```python
from your_new.event_bus import Event, EventType, bus
...
old, self.status = self.status, new_status
bus.publish(Event(type=EventType.NODE_STATUS_CHANGE,
                  payload={"node": self.hashkey,
                           "old": old.name, "new": self.status.name}))
```

---

## 5 Redis‑to‑WebSocket Bridge

Create **`your_new/ws_server.py`**

```python
import asyncio, threading, uvicorn, json, os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from .event_bus import STREAM   # reuse the same stream name

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost")
PORT      = int(os.getenv("WS_PORT", 9999))

def launch():
    app  = FastAPI()
    r    = Redis.from_url(REDIS_URL, decode_responses=True)
    peers = set()

    @app.websocket("/events")
    async def events(ws: WebSocket):
        await ws.accept()
        peers.add(ws)
        try:
            while True:
                await asyncio.sleep(3600)
        except WebSocketDisconnect:
            pass
        finally:
            peers.discard(ws)

    async def pump():
        last_id = "$"  # start from newest; change to "0" to replay history
        while True:
            res = await r.xread({STREAM: last_id}, block=0)  # block until new
            for _key, entries in res:
                for eid, kv in entries:
                    last_id = eid
                    msg = kv["json"]
                    for ws in list(peers):
                        await ws.send_text(msg)
    @app.on_event("startup")
    async def _startup():
        asyncio.create_task(pump())

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

# fire in separate thread so the main loop keeps running

def start_ws_thread():
    threading.Thread(target=launch, daemon=True).start()
```

Add one‑liner to your entry‑point before starting the agent loop:

```python
from your_new.ws_server import start_ws_thread
start_ws_thread()
```

---

## 6 Minimal Browser UI (`ui/index.html`)

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Agent Event Stream</title>
    <style>
      body {
        font-family: monospace;
        background: #111;
        color: #eee;
      }
      table {
        border-collapse: collapse;
        width: 100%;
      }
      td,
      th {
        border: 1px solid #444;
        padding: 4px;
      }
      tr:nth-child(even) {
        background: #222;
      }
    </style>
  </head>
  <body>
    <h2>Live Events</h2>
    <table id="t">
      <thead>
        <tr>
          <th>ts</th>
          <th>type</th>
          <th>payload</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <script>
      const tbody = document.querySelector("#t tbody");
      const ws = new WebSocket("ws://" + location.hostname + ":9999/events");
      ws.onmessage = (e) => {
        const ev = JSON.parse(e.data);
        const r = tbody.insertRow(0);
        r.insertCell().textContent = ev.ts;
        r.insertCell().textContent = ev.type;
        r.insertCell().textContent = JSON.stringify(ev.payload);
      };
    </script>
  </body>
</html>
```

Open `http://localhost:9999` through any static file server (or mount FastAPI’s `StaticFiles` if you prefer everything behind one port).

---

## 7 Running Everything

```bash
# 1.  Redis
redis-server &

# 2.  Your program (spawns WS server thread)
python run_agent.py   # whatever entry launches GraphRunEngine

# 3.  UI
python -m http.server -d ui 8080
```

Navigate to `http://localhost:8080` and watch events scroll in real time.

---

## 8 Checklist for the First PR

-

Happy streaming! 🎈

---

Below is a pragmatic carve‑out that lets you sprinkle **structured “progress” events** through the existing agent/engine code and fan them out through any broker you like.

---

## 1 . Where (and what) to emit

| Layer                                                             | Critical hook                                                                                              | Typical event(s)                    | Suggested payload fields                                                                         |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------ |
| **GraphRunEngine** ( `engine.py` )                                | • start of `forward_one_step_not_parallel` <br>• just after `need_next_step_node.next_action_step` returns | `StepStarted`  `StepFinished`       | step #, root‑run id, selected node.id/hashkey, action_name, timestamp, duration, exception?      |
| **Node lifecycle** (`AbstractNode.do_exam` & status enum)         | whenever `self.status` mutates                                                                             | `NodeStatusChanged`                 | node.id, old_status, new_status, layer, parents, timestamp                                       |
| **Agent action** (`Agent.call_llm`)                               | • immediately **before** the OpenAI/Claude call <br>• immediately **after** the response is parsed         | `LLMCallStarted` `LLMCallCompleted` | node.id, agent_class, model, prompt_hash, cost_estimate, duration, token_usage, truncated_result |
| **Action Executor** (`ActionExecutor.__call__`)                   | at tool invocation boundaries                                                                              | `ToolInvoked` `ToolReturned`        | tool_name, api_name, args_hash, latency, success                                                 |
| **Search / web phase** (`BingBrowser.full_pipeline_search`, etc.) | after search round summarisation                                                                           | `SearchRoundCompleted`              | query_terms, page_count, selected_count, time_spent                                              |

> You _don’t_ need to change control‑flow—just insert `publish(event)` at these seams. citeturn0file0

---

## 2 . Minimal event schema (type‑classes)

```python
from __future__ import annotations
from datetime import datetime
from uuid import uuid4
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _ts() -> datetime:
    return datetime.utcnow()

class EventType(str, Enum):
    STEP_STARTED       = "step_started"
    STEP_FINISHED      = "step_finished"
    NODE_STATUS_CHANGE = "node_status_change"
    LLM_CALL_STARTED   = "llm_call_started"
    LLM_CALL_COMPLETED = "llm_call_completed"
    TOOL_INVOKED       = "tool_invoked"
    TOOL_RETURNED      = "tool_returned"
    SEARCH_COMPLETED   = "search_completed"


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=_ts)
    type: EventType
    payload: Dict[str, Any]

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# — Concrete helpers ----------------------------------------------------------
class StepStarted(Event):
    type: EventType = EventType.STEP_STARTED
    payload: Dict[str, Any]  # {step:int, root_id:str, node_id:str, ...}

class NodeStatusChanged(Event):
    type: EventType = EventType.NODE_STATUS_CHANGE
    payload: Dict[str, Any]  # {node_id:str, old:str, new:str, layer:int}

class LLMCallStarted(Event):
    type: EventType = EventType.LLM_CALL_STARTED
    payload: Dict[str, Any]  # {node_id:str, model:str, prompt_sha:str}

class LLMCallCompleted(Event):
    type: EventType = EventType.LLM_CALL_COMPLETED
    payload: Dict[str, Any]  # {node_id:str, duration:float, tokens:int, extract:str}
```
