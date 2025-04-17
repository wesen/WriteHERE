#!/usr/bin/env python3
import os
import sys
import argparse
from recursive.utils.ws_server import (
    run_server,
    EVENT_STREAM_NAME,
    REDIS_URL,
    WS_HOST,
    WS_PORT,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run WebSocket server for recursive agent events"
    )
    parser.add_argument(
        "--redis-url",
        type=str,
        default=REDIS_URL,
        help=f"Redis URL to connect to (default: {REDIS_URL})",
    )
    parser.add_argument(
        "--stream-name",
        type=str,
        default=EVENT_STREAM_NAME,
        help=f"Redis stream name to read from (default: {EVENT_STREAM_NAME})",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=WS_HOST,
        help=f"Host to bind the WebSocket server to (default: {WS_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=WS_PORT,
        help=f"Port to bind the WebSocket server to (default: {WS_PORT})",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Set environment variables for ws_server to pick up
    os.environ["REDIS_URL"] = args.redis_url
    os.environ["EVENT_STREAM"] = args.stream_name
    os.environ["WS_HOST"] = args.host
    os.environ["WS_PORT"] = str(args.port)

    print(f"Starting WebSocket server for recursive agent events")
    print(f"Redis URL: {args.redis_url}")
    print(f"Redis Stream: {args.stream_name}")
    print(f"WebSocket Server: {args.host}:{args.port}")
    print(
        f"UI will be available at: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}"
    )

    # Run the server directly (not in a thread)
    run_server()


if __name__ == "__main__":
    main()
