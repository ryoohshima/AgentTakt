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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    # サブコマンド（open / serve）と TUI 常駐起動は後続マイルストーンで追加する
    parser.print_help()
    return 0
