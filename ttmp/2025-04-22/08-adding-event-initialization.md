# Server-Side Event Storage and Initialization

## Overview

The Recursive Agent Event Logging System currently streams events in real-time from the agent to the UI via WebSockets. However, when a user refreshes the page or connects midway through an agent run, all historical events are lost. Your task is to implement server-side event storage and an initialization endpoint that allows the UI to load historical events on startup.

## Current System Architecture

Before diving into implementation, it's important to understand the current event system:

1. **Event Bus**: Publishes events to Redis streams (`recursive/utils/event_bus.py`)
2. **WebSocket Server**: Relays events from Redis to web clients (`recursive/utils/ws_server.py`)
3. **React UI**: Consumes events and maintains state in Redux (`ui-react/src/features/events/eventsApi.ts`)

The system already has similar functionality for graph state as described in `ttmp/2025-04-21/05-reduce-graph-events-server-side.md`.

## Design Goals

Your implementation should:

1. Store a configurable number of recent events in memory on the server side
2. Provide a REST API to fetch historical events on client initialization
3. Support clearing events when a new run starts
4. Mirror the exact structure expected by the Redux store

## Technical Design

### Data Model

The event state structure should match what the React app expects:

```python
# Event state structure (for reference)
{
    "events": [
        {
            "event_id": "uuid-string",
            "timestamp": "2025-04-16T10:30:45.123Z",
            "event_type": "step_started|step_finished|...",
            "payload": { /* Event-specific data */ },
            "run_id": "agent-run-uuid"
        },
        # More events...
    ]
}
```

### Server-Side Event Manager

Create a class to manage events, similar to the `GraphStateManager`:

```python
class EventStateManager:
    def __init__(self, max_events=200):
        self.events = []  # List of events, newest first
        self.max_events = max_events
        self._lock = asyncio.Lock()

    async def add_event(self, event: dict):
        """Add a new event to the store."""
        pass

    async def clear_events(self):
        """Clear all events (called when a new run starts)."""
        pass

    async def get_events(self, limit=None):
        """Get events, with optional limit."""
        pass
```

### Event Processing

Implement event processing in the WebSocket server:

```python
async def process_event(event: dict):
    # Add event to the EventStateManager
    await event_manager.add_event(event)

    # Check for run_started event to clear events
    if event.get("event_type") == "run_started":
        await event_manager.clear_events()
        # Add the run_started event back after clearing
        await event_manager.add_event(event)
```

### REST API Endpoint

Add a FastAPI endpoint to fetch historical events:

```python
@app.get("/api/events")
async def get_events(limit: Optional[int] = None):
    """Return historical events."""
    events = await event_manager.get_events(limit)
    return {
        "status": "Connected",  # Default status for HTTP response
        "events": events
    }
```

## Implementation Steps

Follow these steps to complete the implementation:

1. **Create the EventStateManager Class**

   - Implement methods to add, clear, and retrieve events
   - Use async locks to ensure thread safety
   - Apply configurable limits on event storage

2. **Integrate with WebSocket Server**

   - Modify the Redis listener to store events
   - Implement special handling for run_started events
   - Connect the WebSocket server to the EventStateManager

3. **Add the REST API Endpoint**

   - Create a new FastAPI endpoint for event retrieval
   - Implement proper error handling and response formatting
   - Test with various query parameters

4. **Update Documentation**
   - Add your implementation details to the main event system documentation
   - Document configuration options and API usage

## Resources

- Current WebSocket server: `recursive/utils/ws_server.py`
- UI event handling: `ui-react/src/features/events/eventsApi.ts`
- Graph state implementation: `ttmp/2025-04-21/05-reduce-graph-events-server-side.md`
- Event documentation: `ttmp/2025-04-17/04-long-term-document--event-logging-system.md`
