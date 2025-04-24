---
document_type: guide
longevity: long
---

# Redis Streams for Event Logging: A Developer's Guide

## Introduction

This document provides an overview of how Redis Streams are used within the Recursive Agent project for handling real-time event logging and monitoring. It's intended for developers new to Redis Streams or this specific eventing mechanism.

We use Redis Streams as the backbone of our event bus, allowing different parts of the agent to publish events (like "step started", "LLM call completed") and enabling consumers (like our WebSocket server) to listen and react to these events in real-time.

## What are Redis Streams?

At its core, a Redis Stream is an **append-only log** data structure. Think of it like a log file, but managed within Redis, offering persistence and efficient querying capabilities.

Key characteristics:

1.  **Append-Only:** New entries (events, in our case) are always added to the end.
2.  **Persistence:** Unlike basic Redis Pub/Sub, streams store messages in memory (up to configurable limits), so consumers can potentially read past events even if they were offline when the events were published.
3.  **Unique IDs:** Each entry in a stream gets a unique ID. By default, Redis generates IDs based on the milliseconds timestamp plus a sequence number (e.g., `1713988523000-0`). This ensures ordering and uniqueness.
4.  **Field-Value Pairs:** Each entry consists of one or more field-value pairs, similar to Redis Hashes. This allows storing structured data within each event.
5.  **Consumer Groups (Advanced):** Streams support consumer groups, allowing multiple consumers to read from the same stream in a coordinated way, ensuring each message is processed by only one consumer within the group. (Note: Our current `ws_server` implementation reads directly, not using a formal consumer group).

## Key Commands Used in Our System

We primarily use two Redis commands for our event streaming:

### 1. `XADD` (Publishing Events)

This command adds a new entry (event) to a specified stream.

**Syntax:** `XADD <key> <ID> <field1> <value1> [field2 value2 ...]`

**How We Use It (`recursive/utils/event_bus.py`):**

- `<key>`: The name of our event stream, configured as `agent_events`.
- `<ID>`: We use `*`, telling Redis to automatically generate the timestamp-based ID.
- `<field1> <value1> ...`: We store the entire serialized event (as a JSON string) under a single field named `json_payload`.
  - Example: `XADD agent_events * json_payload "{...event data as json...}"`

When an agent component calls `EventBus.publish()`, it ultimately results in an `XADD` command being sent to Redis.

### 2. `XREAD` (Consuming Events)

This command reads entries from one or more streams, starting _after_ a specified ID.

**Syntax:** `XREAD [BLOCK milliseconds] STREAMS <key1> <key2> ... <ID1> <ID2> ...`

**How We Use It (`recursive/utils/ws_server.py:redis_listener`):**

- `BLOCK milliseconds`: We use `BLOCK 0`. This tells Redis to wait indefinitely (`0` milliseconds) until at least one new message is available in one of the specified streams after the given ID. This avoids busy-polling.
- `STREAMS <key1> ... <ID1> ...`:
  - `<key1>`: We specify our stream name, `agent_events`.
  - `<ID1>`: This is the crucial part for continuous listening.
    - On the first call, we use `$`. This special ID means "start reading only messages that arrive _after_ this connection starts listening".
    - After receiving messages, we update our local `last_id` variable to the ID of the _last message received_ in that batch.
    - On subsequent calls within the loop, we use this updated `last_id`. `XREAD` will then return only messages added to the stream _after_ that specific ID, effectively giving us a continuous stream of new events.

**Response Format:** `XREAD` returns a nested list structure. For a single stream query, it looks like: `[[stream_name, [[message_id1, [field1, value1, ...]], [message_id2, [field2, value2, ...]]]]]`. Our code parses this structure to get the individual message IDs and the `json_payload` field.

## Our Implementation (`recursive/` project)

- **Publisher (`EventBus`):** Located in `recursive/utils/event_bus.py`. It provides helper methods (`emit_step_started`, etc.) that construct event dictionaries, serialize them to JSON, and use `XADD` via a Redis client to add them to the `agent_events` stream.
- **Consumer (`ws_server.py`):** Located in `recursive/utils/ws_server.py`. The `redis_listener` function runs as an asyncio background task. It uses a `while True` loop containing an `await redis_client.xread(..., block=0)` call. This blocks until new events arrive. When events are received, it parses the `json_payload`, updates internal state managers, and broadcasts the raw JSON event data to connected WebSocket clients. It carefully manages the `last_id` passed to `XREAD` to ensure it only gets new messages on each iteration.

## Why Use Streams Here?

- **Decoupling:** Publishers (agent components) don't need to know about consumers (WebSocket server). They just fire events into Redis.
- **Persistence:** If the `ws_server` restarts, Redis still holds the events in the stream (up to limits). When the server reconnects and starts reading with `XREAD ... $`, it will get any _new_ events published while it was down. (Note: It won't automatically get events published _before_ it restarted unless we modified the logic to start reading from an older ID).
- **Real-time Broadcasting:** The `XREAD BLOCK 0` mechanism provides an efficient way for the `ws_server` to wait for new events without constantly polling Redis.
- **Potential for Scalability:** While we currently have one main consumer (`ws_server`), Streams inherently support multiple independent readers or coordinated consumer groups if needed in the future.

## Further Reading

- [Redis Streams Introduction (Official Docs)](https://redis.io/docs/data-types/streams/)
- [Redis `XADD` Command](https://redis.io/commands/xadd/)
- [Redis `XREAD` Command](https://redis.io/commands/xread/)
