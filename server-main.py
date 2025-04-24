#!/usr/bin/env python3
import argparse
from recursive.utils.ws_server import run_server
from recursive.utils.config import ServerConfig


def parse_args() -> ServerConfig:
    """Parse command line arguments and return a ServerConfig instance."""
    parser = argparse.ArgumentParser(
        description="Run WebSocket server for recursive agent events"
    )
    parser.add_argument(
        "--redis-url",
        type=str,
        help="Redis URL to connect to",
    )
    parser.add_argument(
        "--stream-name",
        type=str,
        help="Redis stream name to read from",
    )
    parser.add_argument(
        "--host",
        type=str,
        help="Host to bind the WebSocket server to",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port to bind the WebSocket server to",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--reload-session",
        action="store_true",
        help="Reload the latest session on startup",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (sets log level to DEBUG)",
    )

    # First get config from environment
    config = ServerConfig.from_env()

    # Then override with command line arguments
    args = parser.parse_args()
    if args.redis_url:
        config.redis_url = args.redis_url
    if args.stream_name:
        config.event_stream = args.stream_name
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.db_path:
        config.db_path = args.db_path
    if args.reload_session:
        config.reload_session = True
    if args.log_level:
        config.log_level = args.log_level
    if args.debug:
        config.debug = True
        config.log_level = "DEBUG"

    return config


def main():
    """Main entry point for the WebSocket server."""
    # Get configuration from environment and command line
    config = parse_args()

    # Print startup information
    print(f"Starting WebSocket server for recursive agent events")
    print(f"Redis URL: {config.redis_url}")
    print(f"Redis Stream: {config.event_stream}")
    print(f"WebSocket Server: {config.host}:{config.port}")
    print(f"Database Path: {config.db_path}")
    print(f"Reload Latest Session: {config.reload_session}")
    print(f"Log Level: {'DEBUG' if config.debug else config.log_level}")
    print(f"UI will be available at: {config.get_ui_url()}")

    # Run the server directly (not in a thread)
    run_server(config)


if __name__ == "__main__":
    main()
