from __future__ import annotations

import argparse

from agenttakt import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agenttakt",
        description="AI エージェントの実行計画をターミナルでレビュー・編集・承認する MCP-TUI ツール",
    )
    parser.add_argument(
        "--version", action="version", version=f"agenttakt {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command")
    open_parser = subparsers.add_parser(
        "open", help="計画 JSON をエディタで開く（MCP なしのデバッグモード）"
    )
    open_parser.add_argument("plan_file", help="計画 JSON ファイルのパス")
    open_parser.add_argument("--out", help="承認/却下後の計画 JSON の出力先")
    subparsers.add_parser(
        "serve", help="MCP stdio サーバーを起動する（Executor が spawn する用）"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "open":
        from agenttakt.tui.app import run_open

        return run_open(args.plan_file, args.out)
    if args.command == "serve":
        from agenttakt.server.mcp_server import run

        return run()
    # サブコマンド未指定時は TUI 常駐モード
    from agenttakt.tui.app import run_standalone

    return run_standalone()
