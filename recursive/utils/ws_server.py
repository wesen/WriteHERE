import asyncio
import json
import os
import threading
import logging  # Import logging
import traceback  # Import traceback
from typing import Set, Optional, List, Dict
from pathlib import Path  # Added for path manipulation

import redis
import redis.asyncio as aredis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    JSONResponse,
)  # Added JSONResponse
from fastapi.staticfiles import StaticFiles

# Import the new GraphStateManager
from recursive.utils.graph_state_manager import GraphStateManager

# Import the new EventStateManager
from recursive.utils.event_state_manager import EventStateManager

# Import the new DatabaseManager
from recursive.utils.db_manager import DatabaseManager

# Import the new ServerConfig
from recursive.utils.config import ServerConfig

# --- Configuration ---
# Calculate path to the React build directory relative to this file
# ws_server.py -> utils -> recursive -> ROOT -> ui-react/dist
REACT_BUILD_DIR = Path(__file__).parent.parent.parent / "ui-react" / "dist"
REACT_INDEX_FILE = REACT_BUILD_DIR / "index.html"

# Global set to keep track of active WebSocket connections
active_connections: Set[WebSocket] = set()

# Initialize the global graph state manager
graph_manager = GraphStateManager()

# Initialize the global event state manager
event_manager = EventStateManager()

# --- Setup Logging ---
# Define the format including caller info
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d - %(funcName)s()] - %(message)s"

# Get a logger instance specific to this module
logger = logging.getLogger(__name__)


# --- FastAPI App State --- (Moved initialization here)
class AppState:
    def __init__(self):
        self.db_manager: Optional[DatabaseManager] = None
        self.redis_listener_task: Optional[asyncio.Task] = None
        self.latest_events_for_broadcast: List[Dict] = (
            []
        )  # Only for sending history to new clients
        self.config: ServerConfig = ServerConfig.from_env()


app_state = AppState()


async def redis_listener(redis_client: aredis.Redis):
    """Listens to Redis stream, stores events in DB, updates state managers, and broadcasts."""
    last_id = "$"  # Start reading new messages
    logger.info(
        f"Starting Redis listener on stream '{app_state.config.event_stream}'..."
    )
    try:  # Outer try to catch errors during the loop itself
        while True:
            inner_loop_completed_normally = False
            try:
                logger.info(
                    f"Redis listener: Waiting for messages from ID '{last_id}'..."
                )
                # block=0 means wait indefinitely for new messages
                response = await redis_client.xread(
                    {app_state.config.event_stream: last_id}, block=0
                )
                logger.info(
                    f"Redis listener: xread returned (response type: {type(response)})"
                )

                if response:
                    logger.info(f"Received {len(response)} stream(s) with messages.")
                    for stream, messages in response:
                        logger.info(
                            f"Processing stream '{stream}' with {len(messages)} message(s)."
                        )
                        # print(f"Received messages: {messages}") # Redundant with logger
                        for message_id, fields in messages:
                            last_id = message_id
                            logger.info(f"Processing message ID: {message_id}")
                            # Assuming the event JSON is stored under 'json_payload' key
                            # Important: The event structure here must match what's expected by state managers and DB
                            # It should contain event_id, run_id, event_type, timestamp, payload
                            if "json_payload" in fields:
                                message_data_str = fields["json_payload"]
                                logger.info(
                                    f"Message payload found (length: {len(message_data_str)})"
                                )

                                # Process the event for state management and DB storage
                                try:
                                    event = json.loads(message_data_str)
                                    event_type = event.get("event_type", "UNKNOWN")
                                    logger.info(f"Processing event: {event_type}")

                                    # --- Store Event in Database --- (Do this first)
                                    if app_state.db_manager:
                                        app_state.db_manager.store_event(event)
                                    # --------------------------------

                                    # --- Update State Managers --- (Process the event)
                                    # Handle run_started event specially for clearing state
                                    if event_type == "run_started":
                                        logger.info(
                                            "Event is 'run_started', clearing events history."
                                        )
                                        await event_manager.clear_events()
                                        # Optionally clear graph manager too? Depends on desired behavior.
                                        # await graph_manager.clear_state() # Maybe needed if runs aren't isolated

                                    # Add event to EventStateManager
                                    logger.info(
                                        f"Adding event to EventStateManager: {event_type}"
                                    )
                                    await event_manager.add_event(event)

                                    # Process for graph state
                                    logger.info(
                                        f"Processing event for GraphStateManager: {event_type}"
                                    )
                                    await graph_manager.process_event(event)
                                    logger.info(
                                        f"Finished processing event for state managers: {event_type}"
                                    )
                                    # -----------------------------

                                except Exception as e:
                                    logger.error(
                                        f"Error processing event for state/DB: {e}",
                                        exc_info=True,
                                    )
                                    # traceback.print_exc() # Use logger's exc_info instead

                                # --- Broadcast to WebSocket Clients --- (Send original string)
                                logger.info(
                                    f"Broadcasting message to {len(active_connections)} active connection(s)..."
                                )
                                # Create a list copy to avoid issues if set changes during iteration
                                disconnected_peers = set()
                                for connection in list(active_connections):
                                    try:
                                        # Send the original JSON string received from Redis
                                        await connection.send_text(message_data_str)
                                    except WebSocketDisconnect:
                                        disconnected_peers.add(connection)
                                        logger.warning(
                                            f"Client disconnected during send: {connection.client}"
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Error sending to client {connection.client}: {e}",
                                            exc_info=True,
                                        )
                                        disconnected_peers.add(
                                            connection
                                        )  # Assume problematic

                                # Clean up disconnected peers after broadcast
                                if disconnected_peers:
                                    logger.info(
                                        f"Removing {len(disconnected_peers)} disconnected peer(s)."
                                    )
                                    for peer in disconnected_peers:
                                        active_connections.discard(peer)
                                # ---------------------------------------
                            else:
                                logger.warning(
                                    f"Received message {message_id} without 'json_payload' field."
                                )
                    logger.info("Finished processing batch of messages.")
                else:
                    # This might happen if xread times out (if block > 0) or connection issue
                    logger.debug("Redis listener: xread returned empty response.")

                inner_loop_completed_normally = (
                    True  # Mark normal completion for this iteration
                )

            # Specific exception handlers first
            except redis.exceptions.ConnectionError as e:
                logger.error(
                    f"Redis connection error in listener loop: {e}. Attempting to reconnect in 5 seconds..."
                )
                await asyncio.sleep(5)  # Wait before retrying
            except asyncio.CancelledError:
                logger.warning("Redis listener task explicitly cancelled.")
                raise  # Re-raise CancelledError to ensure the task actually stops
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to decode JSON payload from Redis: {e}", exc_info=True
                )
                # Skip this message and continue
                await asyncio.sleep(0.1)  # Prevent tight loop on continuous bad data
            except BaseException as e:  # Catch BaseException last
                # Log the full traceback for unexpected errors
                logger.error(
                    f"Unexpected BaseException in Redis listener loop: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                # traceback.print_exc() # Use logger's exc_info instead
                logger.info("Waiting 1 second before retrying after unexpected error.")
                await asyncio.sleep(1)  # Prevent rapid looping on unknown errors
            finally:
                # This will run even if the task is cancelled during the 'await xread'
                logger.debug(
                    f"Redis listener inner loop finally block reached. Completed normally: {inner_loop_completed_normally}"
                )

    except asyncio.CancelledError:
        logger.warning("Redis listener task cancelled (caught in outer block).")
        # Task cancellation is usually expected during shutdown, but log it
    except BaseException as e:
        # This catches errors in the while condition or outside the inner try/finally
        logger.critical(
            f"CRITICAL error in Redis listener outer scope: {type(e).__name__}: {e}",
            exc_info=True,
        )
    finally:
        logger.info("Redis listener task is terminating.")


async def startup_event():
    """Initializes DB, Redis connection, loads history (optional), starts listener."""
    logger.info("WebSocket server starting up...")
    try:
        # --- Initialize Database Manager ---
        logger.info(f"Initializing database at {app_state.config.db_path}")
        app_state.db_manager = DatabaseManager(app_state.config.db_path)
        logger.info("Database initialized successfully.")
        # ---------------------------------

        # --- Reload State from DB (Optional) ---
        if app_state.config.reload_session:
            logger.info(
                "RELOAD_LATEST_SESSION is true. Attempting to load latest session..."
            )
            if app_state.db_manager:
                historical_events = app_state.db_manager.get_latest_run_events()
                if historical_events:
                    logger.info(
                        f"Loaded {len(historical_events)} events from the latest run in DB."
                    )

                    # Store for broadcasting to new clients
                    app_state.latest_events_for_broadcast = historical_events

                    # --- Replay Events into State Managers ---
                    logger.info("Replaying historical events into state managers...")
                    # Clear existing state first (important!)
                    await event_manager.clear_events()
                    # Assuming graph_manager is implicitly cleared or managed per-run
                    # If not, uncomment: await graph_manager.clear_state()

                    processed_count = 0
                    for event in historical_events:
                        try:
                            event_type = event.get("event_type", "UNKNOWN")
                            # Add to event manager
                            await event_manager.add_event(event)
                            # Process for graph manager
                            await graph_manager.process_event(event)
                            processed_count += 1
                        except Exception as e:
                            logger.error(
                                f"Error replaying event {event.get('event_id')}: {e}",
                                exc_info=True,
                            )

                    logger.info(
                        f"Finished replaying {processed_count}/{len(historical_events)} events."
                    )
                    # -------------------------------------------
                else:
                    logger.info(
                        "No historical events found for the latest run in the database."
                    )
                    app_state.latest_events_for_broadcast = []
            else:
                logger.error("Database manager not initialized, cannot reload session.")
        else:
            logger.info("RELOAD_LATEST_SESSION is false. Starting with empty state.")
            app_state.latest_events_for_broadcast = []
        # ---------------------------------------

        # --- Connect to Redis and Start Listener ---
        logger.info(
            f"Attempting to connect to Redis at {app_state.config.redis_url}..."
        )
        redis_client = aredis.from_url(
            app_state.config.redis_url, decode_responses=True
        )
        logger.info("Pinging Redis...")
        await redis_client.ping()  # Verify connection
        logger.info(
            f"Async Redis connected successfully to {app_state.config.redis_url}"
        )

        # Start the Redis listener task in the background
        logger.info("Creating Redis listener task...")
        app_state.redis_listener_task = asyncio.create_task(
            redis_listener(redis_client), name="RedisListenerTask"
        )
        logger.info("Redis listener task created.")
        # -----------------------------------------

    except aredis.exceptions.ConnectionError as e:
        logger.critical(
            f"FATAL: Could not connect to Redis at {app_state.config.redis_url} on startup: {e}",
            exc_info=True,
        )
        # Optionally, exit or handle this critical failure
    except Exception as e:
        logger.critical(
            f"FATAL: Unexpected error during startup: {e}",
            exc_info=True,
        )
        # Ensure DB connection is closed if startup fails partially
        if app_state.db_manager:
            app_state.db_manager.close()
        raise  # Re-raise exception to prevent server starting in bad state


# Define a shutdown event handler (optional but good practice)
async def shutdown_event():
    logger.info("WebSocket server shutting down...")
    # --- Cancel Redis Listener Task ---
    if app_state.redis_listener_task and not app_state.redis_listener_task.done():
        logger.info("Attempting to cancel Redis listener task...")
        app_state.redis_listener_task.cancel()
        try:
            # Give the task a moment to finish after cancellation
            await asyncio.wait_for(app_state.redis_listener_task, timeout=5.0)
        except asyncio.CancelledError:
            logger.info("Redis listener task successfully cancelled.")
        except asyncio.TimeoutError:
            logger.warning("Redis listener task did not cancel within timeout.")
        except Exception as e:
            logger.error(
                f"Error during Redis listener task shutdown: {e}", exc_info=True
            )
    elif app_state.redis_listener_task:
        logger.info("Redis listener task was already done.")
    # ---------------------------------

    # --- Close Database Connection ---
    if app_state.db_manager:
        logger.info("Closing database connection...")
        app_state.db_manager.close()
    # -------------------------------

    # Add any other cleanup here
    logger.info("WebSocket server shutdown complete.")


# Configure Uvicorn logging to match our setup
# Based on: https://github.com/encode/uvicorn/issues/403#issuecomment-544960673
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,  # Keep existing loggers like ours
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": LOG_FORMAT,  # Use our format
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            # Include relevant access log info, but use our base format style
            "fmt": f'{LOG_FORMAT} - %(client_addr)s - "%(request_line)s" %(status_code)s',
            "use_colors": None,
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # Uvicorn's default is stdout for access
        },
    },
    "loggers": {
        # Configure the root logger (used by our app logger if not specified)
        "": {"handlers": ["default"], "level": "DEBUG"},
        # Configure Uvicorn's loggers
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },  # Uvicorn errors go to default handler
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False,
        },  # Uvicorn access logs go to access handler
    },
}


app = FastAPI(on_startup=[startup_event], on_shutdown=[shutdown_event])

# --- Serve React App Static Files ---
# Mount the 'assets' directory first if it exists (Vite specific)
assets_dir = REACT_BUILD_DIR / "assets"
if assets_dir.exists() and assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    print(f"Serving static assets from: {assets_dir}")


# --- End Graph API Endpoints ---


# --- End Serve React App ---

# --- New Graph API Endpoints ---


@app.get("/api/events")
async def get_events(limit: Optional[int] = None):
    """Return historical events managed by EventStateManager."""
    # TODO: Add limit support to EventStateManager?
    logger.info(f"GET /api/events requested (limit: {limit})")
    return event_manager.get_state()  # Returns all currently managed events


@app.get("/api/graph")
async def get_graph():
    """Return complete graph state from GraphStateManager."""
    logger.info("GET /api/graph requested")
    return graph_manager.get_graph_state()


@app.get("/api/graph/nodes")
async def get_nodes():
    """Return all nodes from GraphStateManager."""
    logger.info("GET /api/graph/nodes requested")
    return {"nodes": graph_manager.get_nodes()}


@app.get("/api/graph/nodes/{node_id}")
async def get_node(node_id: str):
    """Return specific node details from GraphStateManager."""
    logger.info(f"GET /api/graph/nodes/{node_id} requested")
    node = graph_manager.get_node(node_id)
    if node:
        return node
    raise HTTPException(status_code=404, detail="Node not found")


@app.get("/api/graph/edges")
async def get_edges():
    """Return all edges from GraphStateManager."""
    logger.info("GET /api/graph/edges requested")
    return {"edges": graph_manager.get_edges()}


@app.get("/api/graph/edges/{edge_id}")
async def get_edge(edge_id: str):
    """Return specific edge details from GraphStateManager."""
    # Note: GraphStateManager might not store edges by a separate edge_id,
    # but rather implicitly by parent/child node IDs.
    # This endpoint might need adjustment based on GraphStateManager capabilities.
    logger.info(f"GET /api/graph/edges/{edge_id} requested")
    # Assuming get_edge exists, otherwise adapt
    edge = graph_manager.get_edge(edge_id)
    if edge:
        return edge
    # If edges are identified differently, adjust the logic or endpoint.
    # Example: maybe search by parent/child ID pair?
    logger.warning(
        f"Edge lookup by single ID '{edge_id}' might not be supported by GraphStateManager."
    )
    raise HTTPException(
        status_code=404, detail="Edge not found or lookup method not supported"
    )


@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections, sends history if available."""
    await websocket.accept()
    logger.info(f"Client connected: {websocket.client}")
    active_connections.add(websocket)

    try:
        # --- Send Historical Events if Loaded ---
        if app_state.config.reload_session and app_state.latest_events_for_broadcast:
            logger.info(
                f"Sending {len(app_state.latest_events_for_broadcast)} historical events to new client {websocket.client}"
            )
            for event in app_state.latest_events_for_broadcast:
                try:
                    # Send the event data (already a dict from DB) as JSON string
                    await websocket.send_text(json.dumps(event))
                except WebSocketDisconnect:
                    raise  # Re-raise to be caught by outer handler
                except Exception as e:
                    logger.error(
                        f"Error sending historical event to {websocket.client}: {e}",
                        exc_info=True,
                    )
                    # Decide whether to continue or disconnect the client
            logger.info(f"Finished sending historical events to {websocket.client}")
        # ---------------------------------------

        # --- Keep Connection Alive --- (Listen for disconnect)
        while True:
            # We don't expect messages from client in this simple broadcast setup
            # But keep receiving to detect disconnects
            # Set a timeout or handle potential indefinite blocking if needed
            data = await websocket.receive_text()
            logger.info(
                f"Received unexpected text from client {websocket.client}: {data}"
            )  # Log unexpected messages
        # ---------------------------

    except WebSocketDisconnect:
        logger.warning(f"Client disconnected gracefully: {websocket.client}")
    except Exception as e:
        # Log the full traceback for WebSocket errors
        logger.error(
            f"Error in WebSocket connection for {websocket.client}: {e}", exc_info=True
        )
        # traceback.print_exc() # Use logger's exc_info instead
    finally:
        logger.info(f"Removing connection for client: {websocket.client}")
        active_connections.discard(websocket)


# Serve the main index.html for the root path and any other unhandled paths
# This allows React Router (if used) to handle client-side routing.
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    logger.info(f"Request for path: {full_path}")
    # Check if the requested path corresponds to a file in the build directory
    potential_file = REACT_BUILD_DIR / full_path
    if potential_file.exists() and potential_file.is_file():
        logger.info(f"Serving specific file: {potential_file}")
        return FileResponse(potential_file)

    # If it's not a specific file or doesn't exist, serve index.html
    if REACT_INDEX_FILE.exists():
        logger.info(f"Serving index.html: {REACT_INDEX_FILE}")
        return FileResponse(REACT_INDEX_FILE)
    else:
        logger.error(f"Error: React index.html not found at {REACT_INDEX_FILE}")
        return HTMLResponse(
            content=f"<html><body><h1>React App Not Found</h1><p>Build directory not found or index.html missing at {REACT_INDEX_FILE}. Run 'npm run build' in ui-react.</p></body></html>",
            status_code=404,
        )


def run_server(config: ServerConfig):
    """Runs the Uvicorn server.

    Args:
        config: ServerConfig instance containing all server configuration
    """
    # Configure logging based on config
    logging.basicConfig(
        level=config.log_level if not config.debug else "DEBUG", format=LOG_FORMAT
    )
    # Get the root logger and ensure handlers use the format
    logging.getLogger().handlers[0].setFormatter(logging.Formatter(LOG_FORMAT))

    # Store config in app state for use by FastAPI
    app_state.config = config

    logger.info(f"Starting Uvicorn server on {config.host}:{config.port}")
    logger.info(f"React UI build directory expected at: {REACT_BUILD_DIR}")
    logger.info(f"SQLite database path: {config.db_path}")
    logger.info(f"Reload latest session: {config.reload_session}")
    if not REACT_INDEX_FILE.exists():
        logger.warning("WARNING: React index.html not found!")
        logger.warning(f"Expected path: {REACT_INDEX_FILE}")
        logger.warning("Please build the React app first by running:")
        logger.warning("  cd ui-react && npm install && npm run build")
        logger.warning("Server will start, but UI will show an error.\n")
    # Pass the logging configuration dictionary to uvicorn.run
    logger.info(f"Uvicorn starting with log_config...")  # Log the config being used
    uvicorn.run(
        "recursive.utils.ws_server:app",  # Use "module:app" string for reload
        host=config.host,
        port=config.port,
        log_config=LOGGING_CONFIG,  # Use our custom logging config
        reload=False,  # Set reload=False when running programmatically
    )


def start_ws_thread(config: ServerConfig):
    """Starts the FastAPI server in a separate daemon thread.

    Args:
        config: ServerConfig instance containing all server configuration
    """
    logger.info("Attempting to start WebSocket server thread...")
    server_thread = threading.Thread(
        target=lambda: run_server(config), daemon=True, name="WebSocketServerThread"
    )
    server_thread.start()
    logger.info(f"WebSocket server thread started (Thread ID: {server_thread.ident})")
    return server_thread
