import asyncio
import json
import os
import threading
from typing import Set

import redis.asyncio as aredis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse  # For serving the UI directly
from fastapi.staticfiles import StaticFiles  # Optional: For serving UI assets

# --- Configuration ---
# Reuse stream name from event_bus or define separately
EVENT_STREAM_NAME = os.getenv("EVENT_STREAM", "agent_events")
REDIS_URL = os.getenv(
    "REDIS_URL", "redis://localhost:6379/0"
)  # Use URL format for async client
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", 9999))
# Construct the path relative to this file's location
UI_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui", "index.html"
)  # Path to UI html

# Global set to keep track of active WebSocket connections
active_connections: Set[WebSocket] = set()


async def redis_listener(redis_client: aredis.Redis):
    """Listens to Redis stream and broadcasts messages to connected websockets."""
    last_id = "$"  # Start reading new messages
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
                                    disconnected_peers.add(
                                        connection
                                    )  # Assume problematic

                            # Clean up disconnected peers after broadcast
                            for peer in disconnected_peers:
                                active_connections.discard(peer)
                        else:
                            print(
                                f"Warning: Received message {message_id} without 'json_payload' field."
                            )

        except aredis.exceptions.ConnectionError as e:
            print(
                f"Redis connection error in listener: {e}. Attempting to reconnect..."
            )
            await asyncio.sleep(5)  # Wait before retrying
        except Exception as e:
            print(f"Unexpected error in Redis listener: {e}")
            await asyncio.sleep(1)  # Prevent rapid looping on unknown errors


async def startup_event():
    """Creates Redis connection and starts the listener task."""
    print("WebSocket server starting up...")
    try:
        redis_client = aredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()  # Verify connection
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
        # Check if the file exists before opening
        if not os.path.exists(UI_FILE_PATH):
            print(f"UI file not found at expected path: {UI_FILE_PATH}")
            return HTMLResponse(
                content="<html><body><h1>UI file not found</h1><p>Expected at: {}</p></body></html>".format(
                    UI_FILE_PATH
                ),
                status_code=404,
            )

        with open(UI_FILE_PATH, "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        # This might be redundant due to the exists check, but good practice
        print(f"Error: UI file not found at {UI_FILE_PATH} (FileNotFoundError)")
        return HTMLResponse(
            content="<html><body><h1>UI file not found</h1></body></html>",
            status_code=404,
        )
    except Exception as e:
        print(f"Error loading UI from {UI_FILE_PATH}: {e}")
        return HTMLResponse(
            content=f"<html><body><h1>Error loading UI: {e}</h1></body></html>",
            status_code=500,
        )


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
