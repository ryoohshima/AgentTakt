from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown

HELP_TEXT = """\
# AgentTakt ヘルプ

## ノードのフィールドに何を入れるか

| フィールド | 意味 |
|---|---|
| `id` | ノードの一意な識別子（読取専用） |
| `type` | ステップの種別。**Executor（AI エージェント）が解釈する自由な語彙**。TUI は色分けに使うだけ。例: `grep` `read` `edit` `test` `command` `docs` |
| `title` | 人間向けの短い表題 |
| `data` | そのステップのパラメータ（キーと値の組）。**何を入れるかは type ごとに Executor が決める** |

### data の例

- `grep` → `pattern`（検索パターン）、`files`（対象グロブのリスト）
- `edit` → `file`（対象ファイル）、`strategy`（編集方針）
- `test` → `command`（実行コマンド）

AgentTakt は type や data の中身を検証しない。プランを承認すると編集後の JSON が
そのまま Executor に返り、Executor がそれを解釈して実行する。つまり
**「Executor に伝わる言葉」で書けばよい**（自然言語の指示でも構わない）。

## マウス操作

- ノードをドラッグ — 移動
- ノード右辺の ● からドラッグして相手ノードで離す — 依存エッジを作成（循環は拒否される）
- クリック — ノード / エッジを選択

## キー操作

| キー | 動作 |
|---|---|
| `a` | プラン承認（確認ダイアログ） |
| `r` | プラン却下（理由入力） |
| `n` | ノード追加 |
| `d` / `Delete` | 選択中のノード / エッジを削除 |
| `u` / `U` | Undo / Redo |
| 矢印 | 選択ノードを 1 セル移動 |
| `Escape` | 選択解除 |
| `p` | パラメータパネルの表示切替 |
| `?` | このヘルプ |
| `q` | 終了 |
"""


class HelpScreen(ModalScreen[None]):
    """`?` で開く操作・スキーマ説明のモーダル。"""

    BINDINGS = [("escape,q,question_mark", "dismiss", "閉じる")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="help-dialog"):
            yield Markdown(HELP_TEXT)
