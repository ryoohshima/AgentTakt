from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown

HELP_TEXT = """\
# AgentTakt Help

## Mouse

- Drag a node — move it
- Drag from a node's output port (●, right edge) onto another node — draw a dependency edge
- Click — select a node or edge

## Keys

| Key | Action |
|---|---|
| `a` | Approve the plan |
| `r` | Reject the plan |
| `n` | Add a node |
| `d` / `Delete` | Delete the selection |
| `u` / `U` | Undo / Redo |
| Arrow keys | Move the selected node by one cell |
| `Escape` | Clear selection |
| `p` | Toggle the parameter panel |
| `?` | This help |
| `q` | Quit |
"""


class HelpScreen(ModalScreen[None]):
    """`?` で開く操作説明のモーダル。"""

    BINDINGS = [("escape,q,question_mark", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="help-dialog"):
            yield Markdown(HELP_TEXT)
