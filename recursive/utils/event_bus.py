from __future__ import annotations

import os
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, List

import redis
from pydantic import BaseModel, Field

from recursive.common.context import ExecutionContext

# --- Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
EVENT_STREAM_NAME = os.getenv("EVENT_STREAM", "agent_events")
EVENT_STREAM_MAXLEN = int(
    os.getenv("EVENT_STREAM_MAXLEN", 10000)
)  # Approx. max entries

# --- Redis Client ---
# Use decode_responses=True for easier handling in Python
try:
    redis_client: Optional[redis.Redis] = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_timeout=5,  # Add timeout
        health_check_interval=30,  # Check connection periodically
    )
    # Test connection
    redis_client.ping()  # type: ignore
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

    # --- New Types ---
    NODE_CREATED = "node_created"
    PLAN_RECEIVED = "plan_received"
    NODE_ADDED = "node_added"
    EDGE_ADDED = "edge_added"
    INNER_GRAPH_BUILT = "inner_graph_built"
    NODE_RESULT_AVAILABLE = "node_result_available"


# --- Base Event Model ---
class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    run_id: Optional[str] = None  # Optional global run identifier

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
        if not self._enabled or self._client is None:
            return  # Silently ignore if Redis is not connected or client is None

        try:
            # Use Pydantic's json() method for serialization respecting json_encoders
            payload = {"json_payload": event.json()}
            # Use non-None assertion since we've already checked above
            self._client.xadd(
                self._stream_name,
                payload,  # type: ignore
                maxlen=self._max_len,
                approximate=True,  # Use approximate trimming for performance
            )
        except redis.exceptions.ConnectionError as e:
            print(
                f"Redis connection error during publish: {e}. Disabling further publishes."
            )
            self._enabled = False  # Disable on connection error
        except Exception as e:
            # Log other potential errors (e.g., serialization issues)
            print(f"Error publishing event to Redis: {e}")
            # Consider whether to disable or just log based on error type


# --- Global Event Bus Instance ---
# Initialize with the configured client and stream details
bus = EventBus(redis_client, EVENT_STREAM_NAME, EVENT_STREAM_MAXLEN)

# --- Helper Functions (Optional but Recommended) ---
# These make emitting specific events cleaner at the call site.

_current_run_id: Optional[str] = None  # Module-level variable to hold the run ID


def set_run_id(run_id: str):
    """Sets a global run ID for all subsequent events in this process."""
    global _current_run_id
    _current_run_id = run_id


def _create_event(
    event_type: EventType, payload: Dict[str, Any], ctx: Optional[ExecutionContext]
) -> Event:
    """Factory to create event with common fields and context enrichment."""
    # Start with the provided payload
    final_payload = payload.copy()

    # Enrich payload with context data if ctx is provided
    if ctx:
        # Define the fields to potentially add from context
        context_fields = [
            "step",
            "node_id",
            "task_type",
            "action_name",
            "node_status",
            "node_next_status",
            "task_goal",
            "agent_class",
        ]
        for field_name in context_fields:
            field_value = getattr(ctx, field_name, None)
            if field_value is not None and field_name not in final_payload:
                final_payload[field_name] = field_value

    return Event(event_type=event_type, payload=final_payload, run_id=_current_run_id)


def emit_step_started(
    step: int,
    node_id: str,
    node_goal: str,
    root_id: str,
    ctx: Optional[ExecutionContext] = None,
):
    bus.publish(
        _create_event(
            EventType.STEP_STARTED,
            {
                # Keep explicit args for clarity, context may enrich further
                "step": step,
                "node_id": node_id,
                "node_goal": node_goal,
                "root_id": root_id,
            },
            ctx=ctx,
        )
    )


def emit_step_finished(
    step: int,
    node_id: str,
    action_name: str,
    status_after: str,
    duration: float,
    ctx: Optional[ExecutionContext] = None,
):
    bus.publish(
        _create_event(
            EventType.STEP_FINISHED,
            {
                # Keep explicit args
                "step": step,
                "node_id": node_id,
                "action_name": action_name,
                "status_after": status_after,
                "duration_seconds": duration,
            },
            ctx=ctx,
        )
    )


def emit_node_status_changed(
    node_id: str,
    node_goal: str,
    old_status: str,
    new_status: str,
    ctx: Optional[ExecutionContext] = None,
):
    payload: Dict[str, Any] = {
        "node_id": node_id,  # Explicit node_id remains
        "node_goal": node_goal,
        "old_status": old_status,
        "new_status": new_status,
    }
    # Context will add step, task_type etc. if available and not already present
    bus.publish(_create_event(EventType.NODE_STATUS_CHANGED, payload, ctx=ctx))


def emit_llm_call_started(
    agent_class: str,
    model: str,
    prompt_messages: List[Dict[str, str]],
    prompt_preview: str,
    ctx: Optional[ExecutionContext] = None,
    # node_id is now primarily expected via ctx
):
    payload: Dict[str, Any] = {
        "agent_class": agent_class,
        "model": model,
        "prompt": prompt_messages,
        "prompt_preview": prompt_preview,
    }
    # Context will add step, node_id, task_type if available
    bus.publish(_create_event(EventType.LLM_CALL_STARTED, payload, ctx=ctx))


def emit_llm_call_completed(
    agent_class: str,
    model: str,
    duration: float,
    response_content: str,
    error: Optional[str] = None,
    ctx: Optional[ExecutionContext] = None,
    # node_id is now primarily expected via ctx
    token_usage: Optional[dict] = None,
):
    payload: Dict[str, Any] = {
        "agent_class": agent_class,
        "model": model,
        "duration_seconds": duration,
        "response": response_content,
        "result_summary": response_content[:500] + "...",
    }
    if error:
        payload["error"] = error
    if token_usage:
        payload["token_usage"] = token_usage

    # Context will add step, node_id, task_type if available
    bus.publish(_create_event(EventType.LLM_CALL_COMPLETED, payload, ctx=ctx))


def emit_tool_invoked(
    tool_name: str,
    api_name: str,
    args_summary: str,
    ctx: Optional[ExecutionContext] = None,
    # node_id is now primarily expected via ctx
):
    payload: Dict[str, Any] = {
        "tool_name": tool_name,
        "api_name": api_name,
        "args_summary": args_summary[:500] + "...",
    }
    # Context will add step, node_id, task_type if available
    bus.publish(_create_event(EventType.TOOL_INVOKED, payload, ctx=ctx))


def emit_tool_returned(
    tool_name: str,
    api_name: str,
    state: str,
    duration: float,
    result_summary: str,
    error: Optional[str] = None,
    ctx: Optional[ExecutionContext] = None,
    # node_id is now primarily expected via ctx
):
    payload: Dict[str, Any] = {
        "tool_name": tool_name,
        "api_name": api_name,
        "state": state,
        "duration_seconds": duration,
        "result_summary": result_summary[:500] + "...",
    }
    if error:
        payload["error"] = error
    # Context will add step, node_id, task_type if available
    bus.publish(_create_event(EventType.TOOL_RETURNED, payload, ctx=ctx))


# --- NEW EMITTERS ---


def emit_node_created(
    node_id: str,  # Keep explicit node_id as it's the primary identifier here
    node_nid: str,
    node_type: str,
    task_type: str,  # Keep explicit task_type
    task_goal: str,
    layer: int,
    outer_node_id: Optional[str],
    root_node_id: str,
    initial_parent_nids: List[str],
    ctx: Optional[ExecutionContext] = None,
):
    payload: Dict[str, Any] = {
        "node_id": node_id,
        "node_nid": node_nid,
        "node_type": node_type,
        "task_type": task_type,
        "task_goal": task_goal,
        "layer": layer,
        "outer_node_id": outer_node_id,
        "root_node_id": root_node_id,
        "initial_parent_nids": initial_parent_nids,
    }
    # Context will add step if available
    bus.publish(_create_event(EventType.NODE_CREATED, payload, ctx=ctx))


def emit_plan_received(
    node_id: str,  # Keep explicit node_id
    raw_plan: List[Dict],
    ctx: Optional[ExecutionContext] = None,
):
    payload: Dict[str, Any] = {
        "node_id": node_id,  # Explicit node_id remains
        "raw_plan": raw_plan,
    }
    # Context will add step, task_type etc. if available
    bus.publish(_create_event(EventType.PLAN_RECEIVED, payload, ctx=ctx))


def emit_node_added(
    graph_owner_node_id: str,
    added_node_id: str,
    added_node_nid: str,
    ctx: Optional[ExecutionContext] = None,
):
    payload: Dict[str, Any] = {
        "graph_owner_node_id": graph_owner_node_id,
        "added_node_id": added_node_id,
        "added_node_nid": added_node_nid,
    }
    # Context will add step, potentially owner's node_id/task_type if needed
    bus.publish(_create_event(EventType.NODE_ADDED, payload, ctx=ctx))


def emit_edge_added(
    graph_owner_node_id: str,
    parent_node_id: str,
    child_node_id: str,
    parent_node_nid: str,
    child_node_nid: str,
    ctx: Optional[ExecutionContext] = None,
):
    payload: Dict[str, Any] = {
        "graph_owner_node_id": graph_owner_node_id,
        "parent_node_id": parent_node_id,
        "child_node_id": child_node_id,
        "parent_node_nid": parent_node_nid,
        "child_node_nid": child_node_nid,
    }
    # Context will add step, potentially owner's node_id/task_type
    bus.publish(_create_event(EventType.EDGE_ADDED, payload, ctx=ctx))


def emit_inner_graph_built(
    node_id: str,  # Keep explicit node_id
    node_count: int,
    edge_count: int,
    node_ids: List[str],
    ctx: Optional[ExecutionContext] = None,
):
    payload: Dict[str, Any] = {
        "node_id": node_id,  # Explicit node_id remains
        "node_count": node_count,
        "edge_count": edge_count,
        "node_ids": node_ids,
    }
    # Context will add step, task_type etc. if available
    bus.publish(_create_event(EventType.INNER_GRAPH_BUILT, payload, ctx=ctx))


def emit_node_result_available(
    node_id: str,  # Keep explicit node_id
    action_name: str,
    result_summary: str,
    ctx: Optional[ExecutionContext] = None,
):
    payload: Dict[str, Any] = {
        "node_id": node_id,  # Explicit node_id remains
        "action_name": action_name,
        "result_summary": result_summary[:500] + "...",
    }
    # Context will add step, task_type etc. if available
    bus.publish(_create_event(EventType.NODE_RESULT_AVAILABLE, payload, ctx=ctx))
