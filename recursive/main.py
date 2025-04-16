import argparse
from datetime import datetime

from recursive.report_writing import report_writing
from recursive.story_writing import story_writing


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
    return parser


if __name__ == "__main__":
    parser = define_args()
    args = parser.parse_args()
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
