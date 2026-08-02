from __future__ import annotations

import json
from pathlib import Path

from textual.app import App

from agenttakt.models import Plan, apply_auto_layout
from agenttakt.tui.screens.editor import EditorScreen, ReviewResult


class AgentTaktApp(App):
    """AgentTakt の TUI アプリ。

    plan を渡すと直接エディタを開く（open デバッグモード）。
    渡さない場合の常駐モード（IdleScreen + BridgeServer）は M3 で実装する。
    """

    TITLE = "AgentTakt"
    CSS_PATH = "styles.tcss"

    def __init__(self, plan: Plan | None = None, out_path: str | None = None) -> None:
        super().__init__()
        self._initial_plan = plan
        self._out_path = out_path

    def on_mount(self) -> None:
        if self._initial_plan is not None:
            self.push_screen(EditorScreen(self._initial_plan), self._finish_open)

    def _finish_open(self, result: ReviewResult | None) -> None:
        if result is not None and self._out_path:
            Path(self._out_path).write_text(
                result.plan.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        self.exit(result)


def load_plan(path: str | Path) -> Plan:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return apply_auto_layout(Plan.model_validate(raw))


def run_open(plan_path: str, out_path: str | None = None) -> int:
    app = AgentTaktApp(plan=load_plan(plan_path), out_path=out_path)
    result = app.run()
    if isinstance(result, ReviewResult):
        detail = f"（{result.reason}）" if result.reason else ""
        print(f"{result.decision}: {result.plan.graph_id} {detail}".rstrip())
        if out_path:
            print(f"編集後の計画を {out_path} に書き出しました")
    return 0
