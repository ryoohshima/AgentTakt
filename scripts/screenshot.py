"""README 用のエディタ画面スクリーンショット（SVG）を生成する。

    uv run python scripts/screenshot.py

見た目を変えたらこれを再実行して docs/images/editor.svg を更新すること。
UI に全角文字を足す場合は注意（tasks/lessons.md の SVG エクスポートの項を参照）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from agenttakt.tui.app import AgentTaktApp, load_plan
from agenttakt.tui.screens.editor import EditorScreen

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "examples" / "sample_plan.json"
OUT = ROOT / "docs" / "images" / "editor.svg"


async def main() -> None:
    app = AgentTaktApp(plan=load_plan(PLAN))
    async with app.run_test(size=(160, 29)) as pilot:
        await pilot.pause()
        # パラメータパネルに中身を出すため、代表的なノードを選択した状態で撮る
        screen = app.screen
        assert isinstance(screen, EditorScreen)
        screen.select_node("node_3")
        await pilot.pause()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(app.export_screenshot(title="AgentTakt"), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


asyncio.run(main())
