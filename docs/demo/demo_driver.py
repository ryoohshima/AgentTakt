"""Scripted demo of the AgentTakt editor, recorded by VHS (see demo.tape).

VHS cannot synthesize mouse events, so the app drives itself: Textual's
``auto_pilot`` replays Pilot interactions (click, drag, rubber-band edge,
approve) in a real terminal while VHS records the screen.

Usage:
    uv run python docs/demo/demo_driver.py             # visible run (recorded by VHS)
    uv run python docs/demo/demo_driver.py --headless  # self-check without rendering
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from textual.pilot import Pilot

from agenttakt.tui.app import AgentTaktApp, load_plan

PLAN_PATH = Path(__file__).with_name("demo_plan.json")
STEP_SECONDS = 0.06  # delay between interpolated mouse moves (drag smoothness)


async def _glide(
    pilot: Pilot, start: tuple[int, int], end: tuple[int, int], steps: int = 18
) -> None:
    """Move the mouse from start to end in small steps (screen coordinates)."""
    for i in range(1, steps + 1):
        x = round(start[0] + (end[0] - start[0]) * i / steps)
        y = round(start[1] + (end[1] - start[1]) * i / steps)
        await pilot.hover(None, offset=(x, y))
        await asyncio.sleep(STEP_SECONDS)


async def demo(pilot: Pilot) -> None:
    await pilot.pause()
    await asyncio.sleep(2.5)  # show the incoming plan first
    editor = pilot.app.screen

    # 1. Click a node: it gets selected and the parameter panel fills in.
    refactor = editor._node_widget("refactor")
    await pilot.click(refactor, offset=(4, 1))
    await asyncio.sleep(1.8)

    # 2. Drag the misplaced node into line with the rest of the graph.
    offset = refactor.region.offset
    grab = (offset.x + 4, offset.y + 1)
    target = (grab[0] - 16, grab[1] - 7)
    await pilot.mouse_down(refactor, offset=(4, 1))
    await _glide(pilot, grab, target)
    await pilot.mouse_up(None, offset=target)
    await pilot.pause()
    await asyncio.sleep(1.5)

    # 3. Rubber-band the missing dependency edge: refactor -> test.
    test_node = editor._node_widget("test")
    right_column = refactor.rect.width - 1
    offset = refactor.region.offset
    port = (offset.x + right_column, offset.y + 1)
    drop_offset = test_node.region.offset
    drop = (drop_offset.x + 2, drop_offset.y + 1)
    await pilot.mouse_down(refactor, offset=(right_column, 1))
    await _glide(pilot, port, drop)
    await pilot.mouse_up(test_node, offset=(2, 1))
    await asyncio.sleep(2.0)

    # 4. Approve: confirmation dialog, then the app exits with the result.
    await pilot.press("escape")
    await asyncio.sleep(0.8)
    await pilot.press("a")
    await pilot.pause()
    await asyncio.sleep(1.8)
    await pilot.click("#ok")


def main() -> int:
    headless = "--headless" in sys.argv
    app = AgentTaktApp(plan=load_plan(PLAN_PATH))
    # Headless has no real terminal: give it the size the VHS window provides.
    result = app.run(auto_pilot=demo, headless=headless, size=(125, 35) if headless else None)
    if result is None:
        print("demo aborted: no review result", file=sys.stderr)
        return 1
    # Self-check: the scripted interactions must actually have happened.
    assert result.decision == "approved", result.decision
    assert any(e.source == "refactor" and e.target == "test" for e in result.plan.edges)
    print(f"{result.decision}: {result.plan.graph_id}")
    print("The edited plan JSON was returned to the Executor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
