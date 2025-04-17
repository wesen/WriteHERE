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
EVENT_STREAM_MAXLEN = int(
    os.getenv("EVENT_STREAM_MAXLEN", 10000)
)  # Approx. max entries

# --- Redis Client ---
# Use decode_responses=True for easier handling in Python
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_timeout=5,  # Add timeout
        health_check_interval=30,  # Check connection periodically
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
        if not self._enabled:
            return  # Silently ignore if Redis is not connected

        try:
            # Use Pydantic's json() method for serialization respecting json_encoders
            payload = {"json_payload": event.json()}
            self._client.xadd(
                self._stream_name,
                payload,
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


def _create_event(event_type: EventType, payload: Dict[str, Any]) -> Event:
    """Factory to create event with common fields."""
    return Event(event_type=event_type, payload=payload, run_id=_current_run_id)


def emit_step_started(step: int, node_id: str, node_goal: str, root_id: str):
    bus.publish(
        _create_event(
            EventType.STEP_STARTED,
            {
                "step": step,
                "node_id": node_id,
                "node_goal": node_goal,
                "root_id": root_id,
            },
        )
    )


def emit_step_finished(
    step: int, node_id: str, action_name: str, status_after: str, duration: float
):
    bus.publish(
        _create_event(
            EventType.STEP_FINISHED,
            {
                "step": step,
                "node_id": node_id,
                "action_name": action_name,
                "status_after": status_after,
                "duration_seconds": duration,
            },
        )
    )


def emit_node_status_changed(
    node_id: str, node_goal: str, old_status: str, new_status: str
):
    bus.publish(
        _create_event(
            EventType.NODE_STATUS_CHANGED,
            {
                "node_id": node_id,
                "node_goal": node_goal,
                "old_status": old_status,
                "new_status": new_status,
            },
        )
    )


def emit_llm_call_started(
    agent_class: str, model: str, prompt: str, node_id: Optional[str] = None
):
    # Consider hashing or truncating the prompt for brevity/security
    payload = {
        "agent_class": agent_class,
        "model": model,
        "prompt_preview": prompt[:200] + "...",
    }
    if node_id:
        payload["node_id"] = node_id
    bus.publish(_create_event(EventType.LLM_CALL_STARTED, payload))


def emit_llm_call_completed(
    agent_class: str,
    model: str,
    duration: float,
    result_summary: str,
    error: Optional[str] = None,
    node_id: Optional[str] = None,
    token_usage: Optional[dict] = None,
):
    payload = {
        "agent_class": agent_class,
        "model": model,
        "duration_seconds": duration,
        "result_summary": result_summary[:500] + "...",  # Truncate result
    }
    if error:
        payload["error"] = error
    if node_id:
        payload["node_id"] = node_id
    if token_usage:
        payload["token_usage"] = (
            token_usage  # e.g., {'prompt_tokens': 100, 'completion_tokens': 50}
        )
    bus.publish(_create_event(EventType.LLM_CALL_COMPLETED, payload))


def emit_tool_invoked(
    tool_name: str, api_name: str, args_summary: str, node_id: Optional[str] = None
):
    payload = {
        "tool_name": tool_name,
        "api_name": api_name,
        "args_summary": args_summary[:500] + "...",
    }
    if node_id:
        payload["node_id"] = node_id
    bus.publish(_create_event(EventType.TOOL_INVOKED, payload))


def emit_tool_returned(
    tool_name: str,
    api_name: str,
    state: str,
    duration: float,
    result_summary: str,
    error: Optional[str] = None,
    node_id: Optional[str] = None,
):
    payload = {
        "tool_name": tool_name,
        "api_name": api_name,
        "state": state,
        "duration_seconds": duration,
        "result_summary": result_summary[:500] + "...",
    }
    if error:
        payload["error"] = error
    if node_id:
        payload["node_id"] = node_id
    bus.publish(_create_event(EventType.TOOL_RETURNED, payload))
