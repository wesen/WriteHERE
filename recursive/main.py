import argparse
from datetime import datetime, timezone
import uuid  # For run ID

from recursive.report_writing import report_writing
from recursive.story_writing import story_writing
from recursive.utils.event_bus import set_run_id

# import agents to register them
import recursive.agent.dummies
import recursive.agent.update_atom_planning
import recursive.agent.simple_executor
import recursive.agent.final_aggregate


def define_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename", type=str, required=True)
    parser.add_argument("--mode", type=str, choices=["story", "report"], required=True)
    parser.add_argument("--output-filename", type=str, required=True)
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--length", type=int)
    parser.add_argument("--engine-backend", type=str)
    parser.add_argument(
        "--nodes-json-file",
        type=str,
        help="Path to save nodes.json for real-time visualization",
    )
    current_date = datetime.now().strftime("%b %d, %Y")  # Format: "Apr 1, 2025"
    parser.add_argument(
        "--today-date",
        type=str,
        default=current_date,
        help="Today's date to use in prompts (default: current date)",
    )

    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--done-flag-file", type=str, default=None)
    parser.add_argument("--need-continue", action="store_true")
    parser.add_argument(
        "--no-ws-server",
        action="store_true",
        help="Don't start the WebSocket server thread (use when running server separately)",
    )
    return parser


if __name__ == "__main__":
    parser = define_args()
    args = parser.parse_args()

    # Start the WebSocket server in a background thread (unless disabled)
    ws_thread = None
    if not args.no_ws_server:
        from recursive.utils.ws_server import start_ws_thread

        ws_thread = start_ws_thread()
        print("WebSocket server thread started, UI available at http://localhost:9999")
    else:
        print(
            "WebSocket server thread disabled, make sure to run server-main.py separately"
        )

    # Generate a unique ID for this agent run
    current_run_id = str(uuid.uuid4())
    set_run_id(current_run_id)
    print(f"Agent Run ID: {current_run_id}")

    if args.mode == "story":
        story_writing(
            args.filename,
            args.output_filename,
            args.start,
            args.end,
            args.done_flag_file,
            args.model,
            nodes_json_file=args.nodes_json_file,
        )
    else:
        report_writing(
            args.filename,
            args.output_filename,
            args.start,
            args.end,
            args.done_flag_file,
            args.model,
            args.engine_backend,
            nodes_json_file=args.nodes_json_file,
            today_date=args.today_date,
        )
