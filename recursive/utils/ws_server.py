import asyncio
import json
import os
import threading
from typing import Set
from pathlib import Path  # Added for path manipulation

import redis.asyncio as aredis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse  # Added FileResponse
from fastapi.staticfiles import StaticFiles

# --- Configuration ---
# Reuse stream name from event_bus or define separately
EVENT_STREAM_NAME = os.getenv("EVENT_STREAM", "agent_events")
REDIS_URL = os.getenv(
    "REDIS_URL", "redis://localhost:6379/0"
)  # Use URL format for async client
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", 9999))

# Calculate path to the React build directory relative to this file
# ws_server.py -> utils -> recursive -> ROOT -> ui-react/dist
REACT_BUILD_DIR = Path(__file__).parent.parent.parent / "ui-react" / "dist"
REACT_INDEX_FILE = REACT_BUILD_DIR / "index.html"

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

        except redis.exceptions.ConnectionError as e:
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

# --- Serve React App Static Files ---
# Mount the 'assets' directory first if it exists (Vite specific)
assets_dir = REACT_BUILD_DIR / "assets"
if assets_dir.exists() and assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    print(f"Serving static assets from: {assets_dir}")


@app.get("/api/events")
async def get_events():
    """Dummy endpoint for initial event fetch."""
    return {"events": [], "status": "connected"}


# Serve the main index.html for the root path and any other unhandled paths
# This allows React Router (if used) to handle client-side routing.
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    print(f"Request for path: {full_path}")
    # Check if the requested path corresponds to a file in the build directory
    potential_file = REACT_BUILD_DIR / full_path
    if potential_file.exists() and potential_file.is_file():
        print(f"Serving specific file: {potential_file}")
        return FileResponse(potential_file)

    # If it's not a specific file or doesn't exist, serve index.html
    if REACT_INDEX_FILE.exists():
        print(f"Serving index.html: {REACT_INDEX_FILE}")
        return FileResponse(REACT_INDEX_FILE)
    else:
        print(f"Error: React index.html not found at {REACT_INDEX_FILE}")
        return HTMLResponse(
            content=f"<html><body><h1>React App Not Found</h1><p>Build directory not found or index.html missing at {REACT_INDEX_FILE}. Run 'npm run build' in ui-react.</p></body></html>",
            status_code=404,
        )


# --- End Serve React App ---


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
    print(f"React UI build directory expected at: {REACT_BUILD_DIR}")
    if not REACT_INDEX_FILE.exists():
        print("\nWARNING: React index.html not found!")
        print(f"Expected path: {REACT_INDEX_FILE}")
        print("Please build the React app first by running:")
        print("  cd ui-react && npm install && npm run build")
        print("Server will start, but UI will show an error.\n")
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
