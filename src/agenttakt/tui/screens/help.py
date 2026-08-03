from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown

HELP_TEXT = """\
# AgentTakt ヘルプ

AI エージェント（Claude Code など）が作った実行プランを、人間が確認・編集して
承認するためのツールです。承認すると、編集後のプランがそのまま AI エージェントに
返り、その内容どおりに作業が始まります。

## ノードの各項目

- **id** — ノードを区別するための識別子（変更不可）
- **type** — 作業の種類。ノードの色分けに使われます。例: `grep`（検索）、`read`（読解）、`edit`（編集）、`test`（テスト）
- **title** — ノードの見出し（短い説明）
- **data** — 作業の具体的な指示（キーと値の組）

## type / data には何を書けばよいか

書いた内容は、そのまま AI エージェントへの指示になります。AgentTakt が中身を
検査することはないため、**AI に伝わる言葉なら何でも構いません**（日本語の文章でも
大丈夫です）。

例:

- `grep` なら `pattern`（検索する語）と `files`（対象ファイル）
- `edit` なら `file`（編集するファイル）と `strategy`（編集方針）
- `test` なら `command`（実行するコマンド）

## マウス操作

- ノードをドラッグ — 移動
- ノード右端の ● から相手ノードへドラッグ — 依存関係の線を引く
- クリック — ノード / 線を選択

## キー操作

| キー | 動作 |
|---|---|
| `a` | プラン承認 |
| `r` | プラン却下 |
| `n` | ノード追加 |
| `d` / `Delete` | 選択中を削除 |
| `u` / `U` | 元に戻す / やり直す |
| 矢印 | 選択ノードを 1 マス移動 |
| `Escape` | 選択解除 |
| `p` | 右パネルの表示切替 |
| `?` | このヘルプ |
| `q` | 終了 |
"""


class HelpScreen(ModalScreen[None]):
    """`?` で開く操作・スキーマ説明のモーダル。"""

    BINDINGS = [("escape,q,question_mark", "dismiss", "閉じる")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="help-dialog"):
            yield Markdown(HELP_TEXT)
