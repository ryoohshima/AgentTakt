"""MCP stdio サーバー（Claude Code 等の Executor が spawn する）。

MCP SDK の import はこのファイルに閉じ込める（v1 FastMCP → v2 MCPServer の
移行を 1 ファイル差分で済ませるため）。TUI をこのプロセスで起動してはならない
（stdio は MCP プロトコル通信に専有されている）。
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from agenttakt.bridge.client import TuiNotRunningError, request_review, send_show_plan
from agenttakt.bridge.protocol import ReviewMeta, ReviewRequest, ShowPlanRequest
from agenttakt.models.plan import Plan

TUI_NOT_RUNNING_MESSAGE = (
    'AgentTakt editor is not running. Ask the user to run "agenttakt" in a '
    "separate terminal, then call {tool} again."
)

mcp = FastMCP("AgentTakt")


def _validate_plan(plan: dict[str, Any]) -> Plan:
    try:
        return Plan.model_validate(plan)
    except ValidationError as error:
        # Executor が自己修正できるよう検証内容をそのまま返す
        raise ValueError(f"invalid plan: {error}") from error


def _make_meta(summary: str | None) -> ReviewMeta:
    return ReviewMeta(
        summary=summary,
        cwd=os.getcwd(),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@mcp.tool()
async def request_approval(plan: dict[str, Any], summary: str | None = None) -> dict[str, Any]:
    """Submit a task execution plan for human review in the AgentTakt editor.

    Blocks until the human approves or rejects the plan in the TUI. Returns
    {"status": "approved" | "rejected", "plan": <edited plan>, "reason": <str | null>}.
    The returned plan may differ from the submitted one (the human can edit
    nodes, edges and parameters) — always execute the returned plan.

    Args:
        plan: Plan JSON with graph_id, nodes[] and edges[] (must be a DAG).
        summary: One-line description shown in the editor header.
    """
    request = ReviewRequest(
        request_id=str(uuid.uuid4()),
        plan=_validate_plan(plan),
        meta=_make_meta(summary),
    )
    try:
        response = await request_review(request)
    except TuiNotRunningError as error:
        raise RuntimeError(
            TUI_NOT_RUNNING_MESSAGE.format(tool="request_approval")
        ) from error
    return {
        "status": response.decision,
        "plan": response.plan.model_dump(),
        "reason": response.reason,
    }


@mcp.tool()
async def show_plan(plan: dict[str, Any], summary: str | None = None) -> dict[str, Any]:
    """Display a task execution plan in the AgentTakt editor, without blocking.

    Call this whenever you have formulated a multi-step plan — in any mode,
    not just plan mode — so the human can see it as a node graph. Returns
    {"status": "displayed"} as soon as the editor receives the plan; it does
    NOT wait for (or report) any human decision. Use request_approval instead
    when you need the human's approval before executing.

    Args:
        plan: Plan JSON with graph_id, nodes[] and edges[] (must be a DAG).
        summary: One-line description shown in the editor header.
    """
    request = ShowPlanRequest(
        request_id=str(uuid.uuid4()),
        plan=_validate_plan(plan),
        meta=_make_meta(summary),
    )
    try:
        await send_show_plan(request)
    except TuiNotRunningError as error:
        raise RuntimeError(TUI_NOT_RUNNING_MESSAGE.format(tool="show_plan")) from error
    return {"status": "displayed"}


def run() -> int:
    mcp.run()  # stdio transport
    return 0
