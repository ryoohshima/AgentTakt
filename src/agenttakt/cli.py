from __future__ import annotations

import argparse

from agenttakt import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agenttakt",
        description="Review, edit, and approve AI agent task plans in your terminal (MCP + TUI)",
    )
    parser.add_argument(
        "--version", action="version", version=f"agenttakt {__version__}"
    )
    parser.add_argument(
        "--edges",
        choices=["braille", "orthogonal"],
        default="braille",
        help="edge rendering style (default: braille curves)",
    )
    subparsers = parser.add_subparsers(dest="command")
    open_parser = subparsers.add_parser(
        "open", help="open a plan JSON in the editor (debug mode, no MCP)"
    )
    open_parser.add_argument("plan_file", help="path to the plan JSON file")
    open_parser.add_argument("--out", help="where to write the plan JSON after approval/rejection")
    open_parser.add_argument(
        "--edges",
        choices=["braille", "orthogonal"],
        default="braille",
        help="edge rendering style (default: braille curves)",
    )
    subparsers.add_parser(
        "serve", help="run the MCP stdio server (spawned by the Executor)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "open":
        from agenttakt.tui.app import run_open

        return run_open(args.plan_file, args.out, args.edges)
    if args.command == "serve":
        from agenttakt.server.mcp_server import run

        return run()
    # サブコマンド未指定時は TUI 常駐モード
    from agenttakt.tui.app import run_standalone

    return run_standalone(args.edges)
