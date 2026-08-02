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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "open":
        from agenttakt.tui.app import run_open

        return run_open(args.plan_file, args.out)
    # サブコマンド未指定時の TUI 常駐起動（IdleScreen）は M3 で実装する
    parser.print_help()
    return 0
