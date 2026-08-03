from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown

HELP_TEXT = """\
# AgentTakt ヘルプ

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
    """`?` で開く操作説明のモーダル。"""

    BINDINGS = [("escape,q,question_mark", "dismiss", "閉じる")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="help-dialog"):
            yield Markdown(HELP_TEXT)
