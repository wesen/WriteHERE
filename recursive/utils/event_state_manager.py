"""
Manages server-side event state that mirrors the Redux store structure in the UI.
Stores recent events and provides methods to query them.
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ConnectionStatus(str, Enum):
    """Connection status values matching the UI's expectations."""

    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"


@dataclass
class EventState:
    """Represents the event state structure expected by the UI."""

    events: List[dict] = field(default_factory=list)  # List of events, newest first


class EventStateManager:
    """
    Manages server-side event state that mirrors the Redux store structure in the UI.
    Stores recent events and provides methods to query them.
    """

    def __init__(self, max_events: int = 200):
        """Initialize the event state manager.

        Args:
            max_events: Maximum number of events to store (default: 200)
        """
        self.state = EventState()
        self.max_events = max_events
        self._lock = asyncio.Lock()

    async def add_event(self, event: dict):
        """Add a new event to the store.

        Args:
            event: The event to add
        """
        async with self._lock:
            # Insert at the beginning to maintain newest-first order
            self.state.events.insert(0, event)

            # Trim to max_events if needed
            if len(self.state.events) > self.max_events:
                self.state.events = self.state.events[: self.max_events]

    async def clear_events(self):
        """Clear all events (called when a new run starts)."""
        async with self._lock:
            self.state.events.clear()

    async def get_events(self, limit: Optional[int] = None) -> List[dict]:
        """Get events, with optional limit.

        Args:
            limit: Maximum number of events to return (None for all)

        Returns:
            List of events, newest first
        """
        async with self._lock:
            if limit is not None:
                return self.state.events[:limit]
            return self.state.events

    def get_state(self) -> dict:
        """Get the complete state object matching the UI's expected format.

        Returns:
            Dict containing events list and connection status
        """
        return {
            "status": ConnectionStatus.CONNECTED,  # Default to connected for HTTP
            "events": self.state.events,
        }
