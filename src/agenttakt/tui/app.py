from __future__ import annotations

import json
from pathlib import Path

from textual.app import App

from agenttakt.models import Plan, apply_auto_layout
from agenttakt.tui.screens.editor import EditorScreen


class AgentTaktApp(App):
    """AgentTakt の TUI アプリ。

    plan を渡すと直接エディタを開く（open デバッグモード）。
    渡さない場合の常駐モード（IdleScreen + BridgeServer）は M3 で実装する。
    """

    TITLE = "AgentTakt"
    CSS_PATH = "styles.tcss"

    def __init__(self, plan: Plan | None = None) -> None:
        super().__init__()
        self._initial_plan = plan

    def on_mount(self) -> None:
        if self._initial_plan is not None:
            self.push_screen(EditorScreen(self._initial_plan))


def load_plan(path: str | Path) -> Plan:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return apply_auto_layout(Plan.model_validate(raw))


def run_open(plan_path: str) -> int:
    app = AgentTaktApp(plan=load_plan(plan_path))
    app.run()
    return 0
